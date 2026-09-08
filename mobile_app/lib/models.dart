class UserSession {
  const UserSession({
    required this.token,
    required this.username,
    required this.role,
  });

  final String token;
  final String username;
  final String role;

  bool get isAdmin => role == 'admin';

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
  const AnalysisResult({
    required this.patient,
    required this.doctor,
    required this.management,
    this.recordId,
  });

  final Map<String, dynamic> patient;
  final Map<String, dynamic> doctor;
  final Map<String, dynamic> management;
  final int? recordId;

  factory AnalysisResult.fromJson(Map<String, dynamic> json) => AnalysisResult(
    patient: Map<String, dynamic>.from(json['hasta'] as Map? ?? const {}),
    doctor: Map<String, dynamic>.from(json['doktor'] as Map? ?? const {}),
    management: Map<String, dynamic>.from(json['yonetim'] as Map? ?? const {}),
    recordId: (json['kayit_id'] as num?)?.toInt(),
  );
}

class RecordSummary {
  const RecordSummary({
    required this.id,
    required this.createdAt,
    required this.summary,
    required this.hasAudio,
    required this.source,
  });

  final int id;
  final String createdAt;
  final String summary;
  final bool hasAudio;
  final String source;

  factory RecordSummary.fromJson(Map<String, dynamic> json) => RecordSummary(
    id: (json['id'] as num?)?.toInt() ?? 0,
    createdAt: json['olusturma']?.toString() ?? '',
    summary: json['ozet']?.toString() ?? 'Özet yok',
    hasAudio: json['ses_var'] == 1 || json['ses_var'] == true,
    source: json['source']?.toString() ?? 'web',
  );
}

class AdminRecords {
  const AdminRecords({required this.records, required this.stats});
  final List<RecordSummary> records;
  final Map<String, dynamic> stats;
}
