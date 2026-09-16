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

class ComedPatient {
  const ComedPatient({
    required this.visitId,
    required this.clinicalCardId,
    required this.patientName,
    required this.clinicalCardUrl,
    this.patientId = '',
    this.patientNo = '',
    this.protocolNo = '',
    this.department = '',
    this.doctorName = '',
    this.task = '',
    this.status = '',
  });

  final String visitId;
  final String clinicalCardId;
  final String patientId;
  final String patientName;
  final String patientNo;
  final String protocolNo;
  final String department;
  final String doctorName;
  final String task;
  final String status;
  final String clinicalCardUrl;

  factory ComedPatient.fromJson(Map<String, dynamic> json) => ComedPatient(
    visitId: json['visit_id']?.toString() ?? '',
    clinicalCardId: json['clinical_card_id']?.toString() ?? '',
    patientId: json['patient_id']?.toString() ?? '',
    patientName: json['patient_name']?.toString() ?? '',
    patientNo: json['patient_no']?.toString() ?? '',
    protocolNo: json['protocol_no']?.toString() ?? '',
    department: json['department']?.toString() ?? '',
    doctorName: json['doctor_name']?.toString() ?? '',
    task: json['task']?.toString() ?? '',
    status: json['status']?.toString() ?? '',
    clinicalCardUrl: json['clinical_card_url']?.toString() ?? '',
  );

  Map<String, dynamic> toJson() => {
    'visit_id': visitId,
    'clinical_card_id': clinicalCardId,
    'patient_id': patientId,
    'patient_name': patientName,
    'patient_no': patientNo,
    'protocol_no': protocolNo,
    'department': department,
    'doctor_name': doctorName,
    'task': task,
    'status': status,
    'clinical_card_url': clinicalCardUrl,
  };
}

class ComedTransfer {
  const ComedTransfer({
    required this.id,
    required this.status,
    required this.clinicalCardUrl,
    this.error,
    this.missingRequired = const [],
  });

  final int id;
  final String status;
  final String clinicalCardUrl;
  final String? error;
  final List<String> missingRequired;

  factory ComedTransfer.fromJson(Map<String, dynamic> json) {
    final bundle = Map<String, dynamic>.from(
      json['bundle'] as Map? ?? const {},
    );
    return ComedTransfer(
      id: (json['id'] as num?)?.toInt() ?? 0,
      status: json['status']?.toString() ?? 'queued',
      clinicalCardUrl: json['clinical_card_url']?.toString() ?? '',
      error: json['error']?.toString(),
      missingRequired: List<String>.from(
        (bundle['missing_required'] as List? ?? const []).map(
          (e) => e.toString(),
        ),
      ),
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
    required this.doctor,
    this.comed = const {},
    this.comedPatient,
    this.recordId,
  });

  final Map<String, dynamic> doctor;
  final Map<String, dynamic> comed;
  final ComedPatient? comedPatient;
  final int? recordId;

  factory AnalysisResult.fromJson(Map<String, dynamic> json) => AnalysisResult(
    doctor: Map<String, dynamic>.from(json['doktor'] as Map? ?? const {}),
    comed: Map<String, dynamic>.from(json['comed'] as Map? ?? const {}),
    comedPatient: json['comed_patient'] is Map
        ? ComedPatient.fromJson(
            Map<String, dynamic>.from(json['comed_patient'] as Map),
          )
        : null,
    recordId: (json['kayit_id'] as num?)?.toInt(),
  );
}

class DownloadedPdf {
  const DownloadedPdf({required this.bytes, required this.fileName});

  final Uint8List bytes;
  final String fileName;
}
