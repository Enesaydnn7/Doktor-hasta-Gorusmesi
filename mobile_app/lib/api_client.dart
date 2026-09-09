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
  Future<UserSession> login(String username, String password);
  Future<TranscriptionResult> transcribe(String token, File file);
  Stream<AnalysisEvent> analyze(
    String token,
    TranscriptionResult transcription,
  );
  Future<DownloadedPdf> downloadEpikriz(
    String token,
    Map<String, dynamic> epikriz,
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
  Future<UserSession> login(String username, String password) async {
    final response = await _client
        .post(
          _uri('/api/v1/mobile/auth/login'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'username': username, 'password': password}),
        )
        .timeout(const Duration(seconds: 70));
    return UserSession.fromJson(_decodeResponse(response));
  }

  @override
  Future<TranscriptionResult> transcribe(String token, File file) async {
    final request = http.MultipartRequest(
      'POST',
      _uri('/api/v1/mobile/transcribe'),
    )..headers.addAll(_headers(token));
    request.files.add(
      await http.MultipartFile.fromPath(
        'file',
        file.path,
        filename: 'klinot_${DateTime.now().millisecondsSinceEpoch}.m4a',
      ),
    );
    final streamed = await _client
        .send(request)
        .timeout(const Duration(seconds: 120));
    final response = await http.Response.fromStream(streamed);
    return TranscriptionResult.fromJson(_decodeResponse(response));
  }

  @override
  Stream<AnalysisEvent> analyze(
    String token,
    TranscriptionResult transcription,
  ) async* {
    final request = http.Request('POST', _uri('/api/v1/mobile/analyze/stream'))
      ..headers.addAll({..._headers(token), 'Content-Type': 'application/json'})
      ..body = jsonEncode({
        'transcript': transcription.transcript,
        'audio_id': transcription.audioId,
        'stt_usage': transcription.usage,
        'source': 'mobile',
        'client_version': '2.1.0',
        'metadata': {'platform': Platform.operatingSystem},
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
}
