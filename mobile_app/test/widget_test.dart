import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:klinot/api_client.dart';
import 'package:klinot/app.dart';
import 'package:klinot/login_screen.dart';
import 'package:klinot/models.dart';
import 'package:klinot/reports_screen.dart';
import 'package:klinot/theme.dart';

class FakeApi implements KlinotApi {
  @override
  Future<UserSession> login(String username, String password) async =>
      UserSession(token: 'test-token', username: username, role: 'doctor');

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
  Future<TranscriptionResult> transcribe(String token, File file) {
    throw UnimplementedError();
  }
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
    expect(find.textContaining('v2.1.0'), findsOneWidget);
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
}
