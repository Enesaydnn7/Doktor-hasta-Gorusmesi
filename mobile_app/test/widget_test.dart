import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:klinot/api_client.dart';
import 'package:klinot/app.dart';
import 'package:klinot/audio_recorder_service.dart';
import 'package:klinot/login_screen.dart';
import 'package:klinot/models.dart';
import 'package:klinot/recorder_screen.dart';
import 'package:klinot/reports_screen.dart';
import 'package:klinot/theme.dart';

class FakeApi implements KlinotApi {
  @override
  Future<PatientOtpChallenge> startPatientOtp(
    String tckn,
    String birthDate,
  ) async => const PatientOtpChallenge(
    challengeId: 'test-challenge',
    expiresIn: 300,
    phoneMasked: '*** ** 60',
    testMode: true,
  );

  @override
  Future<UserSession> verifyPatientOtp(String challengeId, String code) async =>
      const UserSession(
        token: 'patient-token',
        username: '1300013',
        role: 'patient',
        displayName: 'Test Hasta',
        patientNo: '1300013',
      );

  @override
  Future<UserSession> login(
    String username,
    String password, {
    String? requestedRole,
  }) async => UserSession(
    token: 'test-token',
    username: username,
    role: requestedRole ?? 'doctor',
    displayName: requestedRole == 'patient' ? 'Dursun Kılıçarslan' : '',
    patientNo: requestedRole == 'patient' ? username : '',
  );

  @override
  Future<void> validateSession(String token) async {}

  @override
  Stream<AnalysisEvent> analyze(
    String token,
    TranscriptionResult transcription, {
    ComedPatient? comedPatient,
  }) async* {
    yield const AnalysisProgress(percent: 33, step: 'hasta', status: 'done');
  }

  @override
  Future<List<ComedPatient>> getComedWorklist(String token) async => const [
    ComedPatient(
      visitId: '22207357',
      clinicalCardId: '30416836',
      patientName: 'Test Hasta',
      clinicalCardUrl: 'https://goztepetest.comed.mlpcare.com/test',
      patientNo: '476644',
      protocolNo: 'V-22207357',
      department: 'Kardiyoloji',
    ),
  ];

  @override
  Future<ComedTransfer> createComedTransfer(
    String token,
    int recordId,
    ComedPatient patient,
  ) async => const ComedTransfer(
    id: 7,
    status: 'ready_for_review',
    clinicalCardUrl: 'https://goztepetest.comed.mlpcare.com/test',
  );

  @override
  Future<ComedTransfer> getComedTransfer(String token, int transferId) async =>
      const ComedTransfer(
        id: 7,
        status: 'ready_for_review',
        clinicalCardUrl: 'https://goztepetest.comed.mlpcare.com/test',
      );

  @override
  Future<DownloadedPdf> downloadEpikriz(
    String token,
    Map<String, dynamic> epikriz,
  ) async => DownloadedPdf(
    bytes: Uint8List.fromList(const [37, 80, 68, 70]),
    fileName: 'epikriz_test.pdf',
  );

  @override
  Future<DownloadedPdf> downloadPatientReport(
    String token,
    Map<String, dynamic> report,
  ) async => DownloadedPdf(
    bytes: Uint8List.fromList(const [37, 80, 68, 70]),
    fileName: 'saglik_raporu_test.pdf',
  );

  @override
  Future<TranscriptionResult> transcribe(String token, File file) async =>
      const TranscriptionResult(
        transcript: 'Doktor: Merhaba\nHasta: Başım ağrıyor',
        audioId: 'audio-test',
        usage: {},
      );
}

class FlowFakeApi extends FakeApi {
  final analysisGate = Completer<void>();

  @override
  Stream<AnalysisEvent> analyze(
    String token,
    TranscriptionResult transcription, {
    ComedPatient? comedPatient,
  }) async* {
    yield const AnalysisProgress(percent: 33, step: 'hasta', status: 'done');
    await analysisGate.future;
    yield const AnalysisCompleted(
      AnalysisResult(
        doctor: {
          'epikriz': 'Doktora özel epikriz',
          'oneriler': ['Kırmızı bayrakları sorgulayın'],
        },
        recordId: 43,
      ),
    );
  }
}

class EmptyWorklistApi extends FakeApi {
  @override
  Future<List<ComedPatient>> getComedWorklist(String token) async => const [];
}

class QueuedTransferApi extends FakeApi {
  var createCalls = 0;

  @override
  Future<ComedTransfer> createComedTransfer(
    String token,
    int recordId,
    ComedPatient patient,
  ) async {
    createCalls++;
    return const ComedTransfer(id: 17, status: 'queued', clinicalCardUrl: '');
  }

  @override
  Future<ComedTransfer> getComedTransfer(String token, int transferId) async =>
      const ComedTransfer(id: 17, status: 'queued', clinicalCardUrl: '');
}

class SlowReadyTransferApi extends FakeApi {
  var statusCalls = 0;

  @override
  Future<ComedTransfer> createComedTransfer(
    String token,
    int recordId,
    ComedPatient patient,
  ) async => const ComedTransfer(
    id: 23,
    status: 'queued',
    clinicalCardUrl: 'https://goztepetest.comed.mlpcare.com/test',
  );

  @override
  Future<ComedTransfer> getComedTransfer(String token, int transferId) async {
    statusCalls++;
    return ComedTransfer(
      id: transferId,
      status: statusCalls >= 12 ? 'ready_for_review' : 'filling',
      clinicalCardUrl: 'https://goztepetest.comed.mlpcare.com/test',
    );
  }
}

class FakeRecorder extends AudioRecorderService {
  FakeRecorder(this.file);

  final File file;

  @override
  Future<void> start() async {}

  @override
  Future<File?> stop() async => file;

  @override
  Future<void> cancel() async {}

  @override
  Future<void> keepAwake() async {}

  @override
  Future<void> allowSleep() async {}

  @override
  Future<RecoveredRecording?> recoverLatest() async => null;

  @override
  Future<void> saveRecoveryMetadata(File file, Duration elapsed) async {}

  @override
  Future<void> deleteRecording(File file) async {
    if (file.existsSync()) file.deleteSync();
  }
}

void main() {
  test(
    'long recordings use upload and processing windows above 30 minutes',
    () {
      expect(ApiClient.transcriptionUploadTimeout, const Duration(minutes: 15));
      expect(
        ApiClient.transcriptionProcessingTimeout,
        const Duration(minutes: 45),
      );
    },
  );

  testWidgets('login submits credentials and returns session', (tester) async {
    UserSession? loggedIn;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildKlinotTheme(),
        home: LoginScreen(
          api: FakeApi(),
          onLoggedIn: (session) => loggedIn = session,
        ),
      ),
    );

    expect(find.text('Klinot'), findsOneWidget);
    expect(find.textContaining('v2.18.0'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('usernameField')), 'admin');
    await tester.enterText(find.byKey(const Key('passwordField')), 'secret');
    await tester.tap(find.byKey(const Key('loginButton')));
    await tester.pumpAndSettle();

    expect(loggedIn?.username, 'admin');
    expect(loggedIn?.role, 'doctor');
  });

  testWidgets('patient role login returns patient session', (tester) async {
    UserSession? loggedIn;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildKlinotTheme(),
        home: LoginScreen(
          api: FakeApi(),
          onLoggedIn: (session) => loggedIn = session,
        ),
      ),
    );

    await tester.tap(find.text('Hasta'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('patientTcknField')),
      '28411425816',
    );
    await tester.enterText(
      find.byKey(const Key('patientBirthDateField')),
      '22.10.1997',
    );
    await tester.ensureVisible(find.byKey(const Key('loginButton')));
    await tester.tap(find.byKey(const Key('loginButton')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('patientOtpField')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('patientOtpField')));
    await tester.enterText(find.byKey(const Key('patientOtpField')), '000000');
    await tester.ensureVisible(find.byKey(const Key('loginButton')));
    await tester.tap(find.byKey(const Key('loginButton')));
    await tester.pumpAndSettle();

    expect(loggedIn?.role, 'patient');
    expect(loggedIn?.patientNo, '1300013');
    expect(loggedIn?.displayName, 'Test Hasta');
  });

  testWidgets('mobile shell never exposes a management panel', (tester) async {
    await tester.pumpWidget(
      KlinotApp(
        api: FakeApi(),
        initialSession: UserSession(
          token: 'admin-token',
          username: 'admin',
          role: 'admin',
        ),
      ),
    );

    expect(find.text('Yeni görüşme'), findsOneWidget);
    expect(find.text('Yönetim'), findsNothing);
    expect(find.byIcon(Icons.dashboard_rounded), findsNothing);
  });

  testWidgets('empty COMED worklist explains bridge installation', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildKlinotTheme(),
        home: RecorderScreen(
          api: EmptyWorklistApi(),
          session: UserSession(
            token: 'doctor-token',
            username: 'doctor',
            role: 'doctor',
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('comedSetupInstructions')), findsOneWidget);
    expect(find.text('COMED bağlantısı nasıl kurulur?'), findsOneWidget);
  });

  testWidgets('result screen exposes structured epikriz and COMED actions', (
    tester,
  ) async {
    const result = AnalysisResult(
      doctor: {
        'epikriz': {
          'sikayet': 'Bacak ağrısı',
          'oyku': 'Bir haftadır devam ediyor.',
        },
        'koclugu': {
          'guclu': ['Açık ve sakin iletişim'],
          'oneriler': [
            {
              'alinti': 'Hasta: Bacağım ağrıyor.',
              'oneri': 'Ağrının niteliğini ve şiddetini ayrıntılandırın.',
            },
          ],
        },
      },
      comedPatient: ComedPatient(
        visitId: '22207357',
        clinicalCardId: '30416836',
        patientName: 'Test Hasta',
        protocolNo: 'V-22207357',
        clinicalCardUrl: 'https://goztepetest.comed.mlpcare.com/test',
      ),
      recordId: 42,
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: buildKlinotTheme(),
        home: ReportsScreen(
          api: FakeApi(),
          session: UserSession(
            token: 'doctor-token',
            username: 'doctor',
            role: 'doctor',
          ),
          result: result,
        ),
      ),
    );

    expect(find.text('Doktor epikrizi'), findsOneWidget);
    expect(find.textContaining('Test Hasta · V-22207357'), findsOneWidget);
    expect(find.text('Bacak ağrısı'), findsOneWidget);
    expect(find.text('İletişim önerileri'), findsOneWidget);
    expect(find.byKey(const Key('downloadEpikrizButton')), findsOneWidget);
    expect(find.byKey(const Key('transferToComedButton')), findsOneWidget);
    final transfer = tester.widget<FilledButton>(
      find.byKey(const Key('transferToComedButton')),
    );
    expect(transfer.onPressed, isNotNull);
    expect(find.text('Yönetim'), findsNothing);
    expect(find.text('Hasta özeti'), findsNothing);
  });

  testWidgets('patient result shows health report without COMED actions', (
    tester,
  ) async {
    const result = AnalysisResult(
      doctor: {},
      patient: {
        'ozet': 'Göğüs ağrısı görüşmesi tamamlandı.',
        'tani': 'Doktor değerlendirmesi bekleniyor.',
        'yapilacaklar': ['Kontrol randevusuna gidin'],
        'ilaclar': ['İlaçlarınızı önerildiği şekilde kullanın'],
        'kontrol': 'Bir hafta sonra kontrol.',
        'kapanis': 'Acil belirti olursa sağlık kuruluşuna başvurun.',
      },
      recordId: 44,
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: buildKlinotTheme(),
        home: ReportsScreen(
          api: FakeApi(),
          session: UserSession(
            token: 'patient-token',
            username: '476644',
            role: 'patient',
            displayName: 'Dursun Kılıçarslan',
            patientNo: '476644',
          ),
          result: result,
        ),
      ),
    );

    expect(find.text('Sağlık raporum'), findsOneWidget);
    expect(find.text('Sağlık raporu hazır'), findsOneWidget);
    expect(find.text('Göğüs ağrısı görüşmesi tamamlandı.'), findsOneWidget);
    expect(
      find.byKey(const Key('downloadPatientReportButton')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('transferToComedButton')), findsNothing);
    expect(find.textContaining('COMED'), findsNothing);
  });

  testWidgets(
    'queued COMED transfer stops spinning and retries without duplicate',
    (tester) async {
      final api = QueuedTransferApi();
      const result = AnalysisResult(
        doctor: {'epikriz': 'Kontrol notu'},
        comedPatient: ComedPatient(
          visitId: '22207357',
          clinicalCardId: '',
          patientName: 'Test Hasta',
          protocolNo: 'V-22207357',
          clinicalCardUrl: '',
        ),
        recordId: 42,
      );
      await tester.pumpWidget(
        MaterialApp(
          theme: buildKlinotTheme(),
          home: ReportsScreen(
            api: api,
            session: UserSession(
              token: 'doctor-token',
              username: 'doctor',
              role: 'doctor',
            ),
            result: result,
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('transferToComedButton')));
      await tester.pump();
      for (var i = 0; i < 16; i++) {
        await tester.pump(const Duration(seconds: 2));
      }
      expect(find.text('COMED bekliyor · Tekrar kontrol et'), findsOneWidget);
      expect(api.createCalls, 1);

      await tester.tap(find.byKey(const Key('transferToComedButton')));
      await tester.pump();
      expect(api.createCalls, 1);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(seconds: 3));
    },
  );

  testWidgets(
    'COMED status keeps polling beyond the old thirty second window',
    (tester) async {
      final api = SlowReadyTransferApi();
      const result = AnalysisResult(
        doctor: {'epikriz': 'Kontrol notu'},
        comedPatient: ComedPatient(
          visitId: '22207357',
          clinicalCardId: '30416836',
          patientName: 'Test Hasta',
          protocolNo: 'V-22207357',
          clinicalCardUrl: 'https://goztepetest.comed.mlpcare.com/test',
        ),
        recordId: 42,
      );
      await tester.pumpWidget(
        MaterialApp(
          theme: buildKlinotTheme(),
          home: ReportsScreen(
            api: api,
            session: UserSession(
              token: 'doctor-token',
              username: 'doctor',
              role: 'doctor',
            ),
            result: result,
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('transferToComedButton')));
      await tester.pump();
      for (var i = 0; i < 13; i++) {
        await tester.pump(const Duration(seconds: 3));
      }
      expect(api.statusCalls, greaterThanOrEqualTo(12));
      expect(
        find.text('Aktarım bitti · Genel doktor kontrolü gerekli'),
        findsOneWidget,
      );
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets(
    'recording shows real server progress without exposing transcript',
    (tester) async {
      final directory = Directory.systemTemp.createTempSync('klinot_test_');
      final audio = File('${directory.path}${Platform.pathSeparator}test.m4a');
      audio.writeAsBytesSync(const [1, 2, 3, 4]);
      final api = FlowFakeApi();

      await tester.pumpWidget(
        MaterialApp(
          theme: buildKlinotTheme(),
          home: Scaffold(
            body: RecorderScreen(
              api: api,
              session: UserSession(
                token: 'doctor-token',
                username: 'doctor',
                role: 'doctor',
              ),
              recorder: FakeRecorder(audio),
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byKey(const Key('startRecordingButton')));
      await tester.tap(find.byKey(const Key('recordingConsentSwitch')));
      await tester.tap(find.byKey(const Key('startRecordingButton')));
      await tester.pump();
      await tester.ensureVisible(find.byKey(const Key('stopRecordingButton')));
      await tester.tap(find.byKey(const Key('stopRecordingButton')));
      await tester.pumpAndSettle();

      expect(find.text('Görüşme tamamlandı'), findsOneWidget);
      expect(find.text('Analiz et'), findsOneWidget);
      expect(find.byKey(const Key('transcriptField')), findsNothing);
      expect(find.textContaining('Başım ağrıyor'), findsNothing);

      await tester.ensureVisible(find.byKey(const Key('analyzeButton')));
      await tester.tap(find.byKey(const Key('analyzeButton')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Görüşme tamamlandı'), findsNothing);
      expect(find.text('Epikriz hazırlanıyor'), findsWidgets);
      expect(find.byKey(const Key('epikrizLoadingIndicator')), findsOneWidget);
      expect(find.byKey(const Key('privateAnalysisNotice')), findsOneWidget);
      expect(find.byKey(const Key('analysisProgress')), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Gerçek ilerleme · %33'), findsOneWidget);
      expect(find.textContaining('Geçen süre 00:'), findsOneWidget);
      expect(find.textContaining('Başım ağrıyor'), findsNothing);
      expect(find.text('Klinik bulgular düzenleniyor'), findsOneWidget);

      api.analysisGate.complete();
      await tester.pumpAndSettle();

      expect(find.text('Doktor epikrizi'), findsOneWidget);
      expect(find.text('Doktora özel epikriz'), findsOneWidget);
      expect(find.text('Kırmızı bayrakları sorgulayın'), findsOneWidget);

      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(audio.existsSync(), isTrue);
      expect(find.text('Tekrar analiz et'), findsOneWidget);
      expect(
        find.textContaining('Ses kaydı cihazda korunuyor'),
        findsOneWidget,
      );
      directory.deleteSync(recursive: true);
    },
  );
}
