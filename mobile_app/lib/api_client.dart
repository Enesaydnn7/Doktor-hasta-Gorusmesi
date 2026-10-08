import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import 'models.dart';

const defaultApiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://doktor-hasta-gorusmesi.onrender.com',
);

abstract class KlinotApi {
  Future<UserSession> login(
    String username,
    String password, {
    String? requestedRole,
  });
  Future<PatientOtpChallenge> startPatientOtp(String tckn, String birthDate);
  Future<UserSession> verifyPatientOtp(String challengeId, String code);
  Future<void> validateSession(String token);
  Future<TranscriptionResult> transcribe(String token, File file);
  Stream<AnalysisEvent> analyze(
    String token,
    TranscriptionResult transcription, {
    ComedPatient? comedPatient,
  });
  Future<List<ComedPatient>> getComedWorklist(String token);
  Future<ComedTransfer> createComedTransfer(
    String token,
    int recordId,
    ComedPatient patient,
  );
  Future<ComedTransfer> getComedTransfer(String token, int transferId);
  Future<DownloadedPdf> downloadEpikriz(
    String token,
    Map<String, dynamic> epikriz,
  );
  Future<DownloadedPdf> downloadPatientReport(
    String token,
    Map<String, dynamic> report,
  );
}

class ApiException implements Exception {
  const ApiException(this.message, [this.statusCode]);
  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class ApiClient implements KlinotApi {
  ApiClient({String baseUrl = defaultApiBaseUrl, http.Client? client})
    : baseUrl = baseUrl.replaceFirst(RegExp(r'/$'), ''),
      _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  static const transcriptionUploadTimeout = Duration(minutes: 15);
  static const transcriptionProcessingTimeout = Duration(minutes: 45);
  static const transcriptionPollInterval = Duration(seconds: 3);

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  Map<String, String> _headers(String token) => {
    'Authorization': 'Bearer $token',
    'Accept': 'application/json',
  };

  Map<String, dynamic> _decodeResponse(http.Response response) {
    Map<String, dynamic> data = const {};
    try {
      data = Map<String, dynamic>.from(
        jsonDecode(utf8.decode(response.bodyBytes)),
      );
    } catch (_) {
      // The status code and fallback text below still produce a useful error.
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        data['detail']?.toString() ??
            data['error']?.toString() ??
            'Sunucu isteği tamamlayamadı.',
        response.statusCode,
      );
    }
    return data;
  }

  @override
  Future<UserSession> login(
    String username,
    String password, {
    String? requestedRole,
  }) async {
    final body = <String, dynamic>{
      'username': username,
      'password': password,
      'client_type': 'mobile',
    };
    if (requestedRole != null) body['requested_role'] = requestedRole;
    final response = await _client
        .post(
          _uri('/api/v1/mobile/auth/login'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(const Duration(seconds: 70));
    return UserSession.fromJson(_decodeResponse(response));
  }

  @override
  Future<PatientOtpChallenge> startPatientOtp(
    String tckn,
    String birthDate,
  ) async {
    final response = await _client
        .post(
          _uri('/api/v1/mobile/auth/patient/otp/start'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'tckn': tckn, 'birth_date': birthDate}),
        )
        .timeout(const Duration(seconds: 70));
    return PatientOtpChallenge.fromJson(_decodeResponse(response));
  }

  @override
  Future<UserSession> verifyPatientOtp(String challengeId, String code) async {
    final response = await _client
        .post(
          _uri('/api/v1/mobile/auth/patient/otp/verify'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'challenge_id': challengeId, 'code': code}),
        )
        .timeout(const Duration(seconds: 70));
    return UserSession.fromJson(_decodeResponse(response));
  }

  @override
  Future<void> validateSession(String token) async {
    final response = await _client
        .get(_uri('/api/v1/mobile/auth/session'), headers: _headers(token))
        .timeout(const Duration(seconds: 70));
    _decodeResponse(response);
  }

  @override
  Future<TranscriptionResult> transcribe(String token, File file) async {
    try {
      return await _transcribeWithJob(token, file);
    } on ApiException catch (error) {
      // Dağıtım sırasında yeni iş uç noktası henüz ayağa kalkmadıysa eski
      // sunucuyla da çalış. Yeni sunucuda bütün uzun kayıtlar iş kuyruğunu kullanır.
      if (error.statusCode == 404) {
        return _transcribeLegacy(token, file);
      }
      rethrow;
    } on TimeoutException catch (_) {
      throw const ApiException(
        'Ses kaydı sunucuya gönderilirken bağlantı zaman aşımına uğradı. '
        'Kayıt cihazda güvende; bağlantıyı kontrol edip Analiz et düğmesine yeniden basın.',
      );
    } on SocketException catch (_) {
      throw const ApiException(
        'İnternet bağlantısı kesildi. Kayıt cihazda güvende; bağlantı gelince Analiz et düğmesine yeniden basın.',
      );
    } on http.ClientException catch (_) {
      throw const ApiException(
        'Sunucu bağlantısı geçici olarak kesildi. Kayıt cihazda güvende; Analiz et düğmesine yeniden basabilirsiniz.',
      );
    }
  }

  Future<TranscriptionResult> _transcribeWithJob(
    String token,
    File file,
  ) async {
    Map<String, dynamic>? job;
    Object? lastTransientError;
    for (var attempt = 0; attempt < 3; attempt++) {
      try {
        job = await _startTranscriptionJob(token, file);
        break;
      } on ApiException catch (error) {
        if (error.statusCode == 404) rethrow;
        if (!_isTransient(error) || attempt == 2) rethrow;
        lastTransientError = error;
      } on Object catch (error) {
        if (!_isTransient(error) || attempt == 2) rethrow;
        lastTransientError = error;
      }
      await Future<void>.delayed(Duration(seconds: 2 + attempt * 3));
    }
    if (job == null) {
      throw lastTransientError ?? const ApiException('Ses yüklenemedi.');
    }

    final deadline = DateTime.now().add(transcriptionProcessingTimeout);
    var current = job;
    while (true) {
      final completed = _completedTranscription(current);
      if (completed != null) return completed;
      if (current['status'] == 'failed') {
        throw ApiException(
          current['error']?.toString() ?? 'Ses kaydı metne dönüştürülemedi. Kayıt cihazda korundu; yeniden deneyebilirsiniz.',
        );
      }
      final jobId = current['job_id']?.toString() ?? '';
      if (jobId.isEmpty) {
        throw const ApiException('Sunucu ses işleme kimliği göndermedi.');
      }
      if (DateTime.now().isAfter(deadline)) {
        throw const ApiException(
          'Ses işleme beklenenden uzun sürdü. Sunucudaki işlem korunuyor; birkaç dakika sonra Analiz et düğmesine yeniden basın.',
        );
      }

      await Future<void>.delayed(transcriptionPollInterval);
      try {
        final response = await _client
            .get(
              _uri('/api/v1/mobile/transcriptions/$jobId'),
              headers: _headers(token),
            )
            .timeout(const Duration(seconds: 70));
        current = _decodeResponse(response);
      } on Object catch (error) {
        if (!_isTransient(error)) rethrow;
        // Telefon kısa süre çevrimdışı kalsa veya ekran elle kapatılsa bile iş
        // sunucuda sürer; son tarihe kadar durum sorgulamaya devam et.
        await Future<void>.delayed(const Duration(seconds: 5));
      }
    }
  }

  Future<Map<String, dynamic>> _startTranscriptionJob(
    String token,
    File file,
  ) async {
    final request = http.MultipartRequest(
      'POST',
      _uri('/api/v1/mobile/transcriptions'),
    )..headers.addAll(_headers(token));
    request.files.add(
      await http.MultipartFile.fromPath(
        'file',
        file.path,
        filename: file.uri.pathSegments.isEmpty
            ? 'klinot-kayit.m4a'
            : file.uri.pathSegments.last,
      ),
    );
    final streamed = await _client
        .send(request)
        .timeout(transcriptionUploadTimeout);
    final response = await http.Response.fromStream(streamed)
        .timeout(const Duration(seconds: 70));
    return _decodeResponse(response);
  }

  TranscriptionResult? _completedTranscription(Map<String, dynamic> job) {
    if (job['status'] != 'completed') return null;
    return TranscriptionResult.fromJson(job);
  }

  bool _isTransient(Object error) {
    if (error is TimeoutException ||
        error is SocketException ||
        error is http.ClientException) {
      return true;
    }
    return error is ApiException &&
        error.statusCode != null &&
        error.statusCode! >= 500;
  }

  Future<TranscriptionResult> _transcribeLegacy(String token, File file) async {
    final request = http.MultipartRequest(
      'POST',
      _uri('/api/v1/mobile/transcribe'),
    )..headers.addAll(_headers(token));
    request.files.add(await http.MultipartFile.fromPath('file', file.path));
    final streamed = await _client
        .send(request)
        .timeout(transcriptionProcessingTimeout);
    final response = await http.Response.fromStream(streamed)
        .timeout(const Duration(minutes: 2));
    return TranscriptionResult.fromJson(_decodeResponse(response));
  }

  @override
  Stream<AnalysisEvent> analyze(
    String token,
    TranscriptionResult transcription, {
    ComedPatient? comedPatient,
  }) async* {
    final request = http.Request('POST', _uri('/api/v1/mobile/analyze/stream'))
      ..headers.addAll({..._headers(token), 'Content-Type': 'application/json'})
      ..body = jsonEncode({
        'transcript': transcription.transcript,
        'audio_id': transcription.audioId,
        'stt_usage': transcription.usage,
        'source': 'mobile',
        'client_version': '2.16.0',
        'metadata': {
          'platform': Platform.operatingSystem,
          if (comedPatient != null) 'comed_patient': comedPatient.toJson(),
        },
      });

    final response = await _client
        .send(request)
        .timeout(const Duration(seconds: 70));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final body = await response.stream.bytesToString();
      var message = 'Analiz başlatılamadı.';
      try {
        final data = jsonDecode(body) as Map<String, dynamic>;
        message =
            data['detail']?.toString() ?? data['error']?.toString() ?? message;
      } catch (_) {}
      throw ApiException(message, response.statusCode);
    }

    await for (final line
        in response.stream
            .transform(utf8.decoder)
            .transform(const LineSplitter())) {
      if (line.trim().isEmpty) continue;
      final event = Map<String, dynamic>.from(jsonDecode(line));
      switch (event['type']) {
        case 'progress':
          yield AnalysisProgress(
            percent: (event['percent'] as num?)?.toInt() ?? 0,
            step: event['step']?.toString() ?? '',
            status: event['status']?.toString() ?? '',
          );
          break;
        case 'result':
          yield AnalysisCompleted(
            AnalysisResult.fromJson(
              Map<String, dynamic>.from(event['data'] as Map? ?? const {}),
            ),
          );
          break;
        case 'error':
          throw ApiException(event['error']?.toString() ?? 'Analiz başarısız.');
        default:
          // Heartbeats intentionally keep the connection alive without UI noise.
          break;
      }
    }
  }

  @override
  Future<List<ComedPatient>> getComedWorklist(String token) async {
    final response = await _client
        .get(_uri('/api/v1/mobile/comed/worklist'), headers: _headers(token))
        .timeout(const Duration(seconds: 70));
    final data = _decodeResponse(response);
    return (data['items'] as List? ?? const [])
        .map(
          (item) =>
              ComedPatient.fromJson(Map<String, dynamic>.from(item as Map)),
        )
        .toList();
  }

  @override
  Future<ComedTransfer> createComedTransfer(
    String token,
    int recordId,
    ComedPatient patient,
  ) async {
    final response = await _client
        .post(
          _uri('/api/v1/mobile/comed/transfers'),
          headers: {..._headers(token), 'Content-Type': 'application/json'},
          body: jsonEncode({
            'record_id': recordId,
            'patient': patient.toJson(),
          }),
        )
        .timeout(const Duration(seconds: 70));
    return ComedTransfer.fromJson(_decodeResponse(response));
  }

  @override
  Future<ComedTransfer> getComedTransfer(String token, int transferId) async {
    final response = await _client
        .get(
          _uri('/api/v1/mobile/comed/transfers/$transferId'),
          headers: _headers(token),
        )
        .timeout(const Duration(seconds: 70));
    return ComedTransfer.fromJson(_decodeResponse(response));
  }

  @override
  Future<DownloadedPdf> downloadEpikriz(
    String token,
    Map<String, dynamic> epikriz,
  ) async {
    final response = await _client
        .post(
          _uri('/api/v1/mobile/pdf/epikriz'),
          headers: {..._headers(token), 'Content-Type': 'application/json'},
          body: jsonEncode({'data': epikriz}),
        )
        .timeout(const Duration(seconds: 70));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      _decodeResponse(response);
    }
    final disposition = response.headers['content-disposition'] ?? '';
    final match = RegExp(r'filename="?([^";]+)').firstMatch(disposition);
    final fileName =
        match?.group(1)?.trim() ??
        'epikriz_${DateTime.now().millisecondsSinceEpoch}.pdf';
    return DownloadedPdf(bytes: response.bodyBytes, fileName: fileName);
  }

  @override
  Future<DownloadedPdf> downloadPatientReport(
    String token,
    Map<String, dynamic> report,
  ) async {
    final response = await _client
        .post(
          _uri('/api/v1/mobile/pdf/saglik-raporu'),
          headers: {..._headers(token), 'Content-Type': 'application/json'},
          body: jsonEncode({'data': report}),
        )
        .timeout(const Duration(seconds: 70));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      _decodeResponse(response);
    }
    final disposition = response.headers['content-disposition'] ?? '';
    final match = RegExp(r'filename="?([^";]+)').firstMatch(disposition);
    final fileName =
        match?.group(1)?.trim() ??
        'saglik_raporu_${DateTime.now().millisecondsSinceEpoch}.pdf';
    return DownloadedPdf(bytes: response.bodyBytes, fileName: fileName);
  }
}
