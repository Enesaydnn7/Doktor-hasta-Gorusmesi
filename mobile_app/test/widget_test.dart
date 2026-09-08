import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:klinot/api_client.dart';
import 'package:klinot/login_screen.dart';
import 'package:klinot/models.dart';
import 'package:klinot/reports_screen.dart';
import 'package:klinot/theme.dart';

class FakeApi implements KlinotApi {
  @override
  Future<UserSession> login(String username, String password) async =>
      UserSession(token: 'test-token', username: username, role: 'admin');

  @override
  Stream<AnalysisEvent> analyze(
    String token,
    TranscriptionResult transcription,
  ) async* {
    yield const AnalysisProgress(percent: 33, step: 'hasta', status: 'done');
  }

  @override
  Future<Map<String, dynamic>> record(String token, int id) async => {};

  @override
  Future<AdminRecords> records(String token) async =>
      const AdminRecords(records: [], stats: {});

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
    expect(find.textContaining('v1.0.0'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('usernameField')), 'admin');
    await tester.enterText(find.byKey(const Key('passwordField')), 'secret');
    await tester.tap(find.byKey(const Key('loginButton')));
    await tester.pumpAndSettle();

    expect(loggedIn?.username, 'admin');
    expect(loggedIn?.isAdmin, isTrue);
  });

  testWidgets('reports render all three clinical report tabs', (tester) async {
    const result = AnalysisResult(
      patient: {'ozet': 'Hasta özeti'},
      doctor: {'epikriz': 'Doktor raporu'},
      management: {'kalite': 'Yönetim raporu'},
      recordId: 42,
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: buildKlinotTheme(),
        home: const ReportsScreen(result: result),
      ),
    );

    expect(find.text('Kayıt #42'), findsOneWidget);
    expect(find.text('Hasta özeti'), findsWidgets);
    expect(find.text('Doktor epikrizi'), findsOneWidget);
    expect(find.text('Yönetim'), findsOneWidget);
  });
}
