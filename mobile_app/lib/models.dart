import 'dart:typed_data';

class UserSession {
  const UserSession({
    required this.token,
    required this.username,
    required this.role,
  });

  final String token;
  final String username;
  final String role;

  factory UserSession.fromJson(Map<String, dynamic> json) {
    final user = Map<String, dynamic>.from(json['user'] as Map? ?? const {});
    return UserSession(
      token: json['access_token']?.toString() ?? '',
      username: user['username']?.toString() ?? '',
      role: user['role']?.toString() ?? 'doctor',
    );
  }
}

class TranscriptionResult {
  const TranscriptionResult({
    required this.transcript,
    required this.audioId,
    required this.usage,
  });

  final String transcript;
  final String? audioId;
  final Map<String, dynamic> usage;

  factory TranscriptionResult.fromJson(Map<String, dynamic> json) =>
      TranscriptionResult(
        transcript: json['transcript']?.toString() ?? '',
        audioId: json['audio_id']?.toString(),
        usage: Map<String, dynamic>.from(json['usage'] as Map? ?? const {}),
      );
}

sealed class AnalysisEvent {
  const AnalysisEvent();
}

class AnalysisProgress extends AnalysisEvent {
  const AnalysisProgress({
    required this.percent,
    required this.step,
    required this.status,
  });

  final int percent;
  final String step;
  final String status;
}

class AnalysisCompleted extends AnalysisEvent {
  const AnalysisCompleted(this.result);
  final AnalysisResult result;
}

class AnalysisResult {
  const AnalysisResult({required this.doctor, this.recordId});

  final Map<String, dynamic> doctor;
  final int? recordId;

  factory AnalysisResult.fromJson(Map<String, dynamic> json) => AnalysisResult(
    doctor: Map<String, dynamic>.from(json['doktor'] as Map? ?? const {}),
    recordId: (json['kayit_id'] as num?)?.toInt(),
  );
}

class DownloadedPdf {
  const DownloadedPdf({required this.bytes, required this.fileName});

  final Uint8List bytes;
  final String fileName;
}
