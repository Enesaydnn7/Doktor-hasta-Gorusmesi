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
  Future<UserSession> login(String username, String password) async =>
      UserSession(token: 'test-token', username: username, role: 'doctor');

  @override
  Future<void> validateSession(String token) async {}

  @override
  Stream<AnalysisEvent> analyze(
    String token,
    TranscriptionResult transcription,
  ) async* {
    yield const AnalysisProgress(percent: 33, step: 'hasta', status: 'done');
  }

  @override
  Future<DownloadedPdf> downloadEpikriz(
    String token,
    Map<String, dynamic> epikriz,
  ) async => DownloadedPdf(
    bytes: Uint8List.fromList(const [37, 80, 68, 70]),
    fileName: 'epikriz_test.pdf',
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
    TranscriptionResult transcription,
  ) async* {
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

class FakeRecorder extends AudioRecorderService {
  FakeRecorder(this.file);

  final File file;

  @override
  Future<void> start() async {}

  @override
  Future<File?> stop() async => file;

  @override
  Future<void> cancel() async {}
}

void main() {
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
    expect(find.textContaining('v2.3.0'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('usernameField')), 'admin');
    await tester.enterText(find.byKey(const Key('passwordField')), 'secret');
    await tester.tap(find.byKey(const Key('loginButton')));
    await tester.pumpAndSettle();

    expect(loggedIn?.username, 'admin');
    expect(loggedIn?.role, 'doctor');
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

  testWidgets('result screen exposes only doctor epikriz and PDF download', (
    tester,
  ) async {
    const result = AnalysisResult(
      doctor: {'epikriz': 'Doktor raporu'},
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
    expect(find.textContaining('Kayıt #42'), findsOneWidget);
    expect(find.text('Doktor raporu'), findsOneWidget);
    expect(find.byKey(const Key('downloadEpikrizButton')), findsOneWidget);
    expect(find.text('Yönetim'), findsNothing);
    expect(find.text('Hasta özeti'), findsNothing);
  });

  testWidgets(
    'recording is analyzed without exposing transcript or progress UI',
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

      await tester.tap(find.byType(Checkbox));
      await tester.tap(find.byKey(const Key('startRecordingButton')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('stopRecordingButton')));
      await tester.pumpAndSettle();

      expect(find.text('Görüşme tamamlandı'), findsOneWidget);
      expect(find.text('Analiz et'), findsOneWidget);
      expect(find.byKey(const Key('transcriptField')), findsNothing);
      expect(find.textContaining('Başım ağrıyor'), findsNothing);

      await tester.tap(find.byKey(const Key('analyzeButton')));
      await tester.pump();

      expect(find.text('Görüşme tamamlandı'), findsNothing);
      expect(find.text('Epikriz hazırlanıyor'), findsWidgets);
      expect(find.byKey(const Key('epikrizLoadingIndicator')), findsOneWidget);
      expect(find.byKey(const Key('privateAnalysisNotice')), findsOneWidget);
      expect(find.byKey(const Key('analysisProgress')), findsNothing);
      expect(find.byType(LinearProgressIndicator), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.textContaining('%33'), findsNothing);
      expect(find.textContaining('Başım ağrıyor'), findsNothing);
      expect(
        find.textContaining('epikriz raporunu görebileceksiniz'),
        findsOneWidget,
      );

      api.analysisGate.complete();
      await tester.pumpAndSettle();

      expect(find.text('Doktor epikrizi'), findsOneWidget);
      expect(find.text('Doktora özel epikriz'), findsOneWidget);
      expect(find.text('Kırmızı bayrakları sorgulayın'), findsOneWidget);

      await tester.pageBack();
      await tester.pumpAndSettle();
      directory.deleteSync(recursive: true);
    },
  );
}
