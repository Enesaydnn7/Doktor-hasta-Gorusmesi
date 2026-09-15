import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api_client.dart';
import 'login_screen.dart';
import 'models.dart';
import 'recorder_screen.dart';
import 'theme.dart';

class KlinotApp extends StatefulWidget {
  const KlinotApp({super.key, this.api, this.initialSession});

  final KlinotApi? api;
  final UserSession? initialSession;

  @override
  State<KlinotApp> createState() => _KlinotAppState();
}

class _KlinotAppState extends State<KlinotApp> {
  static const _storage = FlutterSecureStorage();
  late final KlinotApi _api;
  UserSession? _session;
  var _ready = false;

  @override
  void initState() {
    super.initState();
    _api = widget.api ?? ApiClient();
    _session = widget.initialSession;
    if (_session != null) {
      _ready = true;
    } else {
      _restoreSession();
    }
  }

  Future<void> _restoreSession() async {
    try {
      final token = await _storage.read(key: 'token');
      final username = await _storage.read(key: 'username');
      final role = await _storage.read(key: 'role');
      if (token != null && username != null && role != null) {
        final stored = UserSession(
          token: token,
          username: username,
          role: role,
        );
        try {
          await _api.validateSession(token);
          _session = stored;
        } on ApiException catch (error) {
          if (error.statusCode == 401) {
            await _storage.deleteAll();
          } else {
            // Geçici ağ/Render uyanma hatasında oturumu silme; işlem sırasında
            // sunucu yeniden kontrol edecektir.
            _session = stored;
          }
        } catch (_) {
          // Telefon çevrimdışıysa veya Render henüz uyanmadıysa geçerli olabilecek
          // oturumu gereksiz yere silme.
          _session = stored;
        }
      }
    } catch (_) {
      // Secure storage may be unavailable in tests or unsupported environments.
    }
    if (mounted) setState(() => _ready = true);
  }

  Future<void> _loggedIn(UserSession session) async {
    setState(() => _session = session);
    try {
      await _storage.write(key: 'token', value: session.token);
      await _storage.write(key: 'username', value: session.username);
      await _storage.write(key: 'role', value: session.role);
    } catch (_) {}
  }

  Future<void> _logout() async {
    setState(() => _session = null);
    try {
      await _storage.deleteAll();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Klinot',
      debugShowCheckedModeBanner: false,
      theme: buildKlinotTheme(),
      home: !_ready
          ? const _SplashScreen()
          : _session == null
          ? LoginScreen(api: _api, onLoggedIn: _loggedIn)
          : HomeShell(api: _api, session: _session!, onLogout: _logout),
    );
  }
}

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) =>
      const Scaffold(body: Center(child: CircularProgressIndicator()));
}

class HomeShell extends StatelessWidget {
  const HomeShell({
    super.key,
    required this.api,
    required this.session,
    required this.onLogout,
  });

  final KlinotApi api;
  final UserSession session;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const _Brand(),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 4),
            child: Center(
              child: Text(
                session.username,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
          ),
          IconButton(
            onPressed: onLogout,
            tooltip: 'Çıkış yap',
            icon: const Icon(Icons.logout_rounded),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: RecorderScreen(
          api: api,
          session: session,
          onSessionExpired: onLogout,
        ),
      ),
    );
  }
}

class _Brand extends StatelessWidget {
  const _Brand();

  @override
  Widget build(BuildContext context) => const Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      CircleAvatar(
        radius: 19,
        backgroundColor: klinotTeal,
        child: Icon(Icons.graphic_eq_rounded, color: Colors.white),
      ),
      SizedBox(width: 10),
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Klinot',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
          ),
          Text(
            'Klinik görüşme asistanı',
            style: TextStyle(fontSize: 10, color: Color(0xFF60777D)),
          ),
        ],
      ),
    ],
  );
}
