import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api_client.dart';
import 'models.dart';
import 'theme.dart';

/// Hasta doğum tarihini elle yazarken noktaları otomatik ekler:
/// `25082002` → `25.08.2002`. Takvimden seçmek hâlâ mümkün, zorunlu değil.
class _BirthDateInputFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digits = newValue.text.replaceAll(RegExp(r'\D'), '');
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length && i < 8; i++) {
      if (i == 2 || i == 4) buffer.write('.');
      buffer.write(digits[i]);
    }
    final text = buffer.toString();
    return TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: text.length),
    );
  }
}

/// Hem elle yazılan hem takvimden seçilen değeri doğrular.
String? _validateBirthDate(String? value) {
  final digits = (value ?? '').replaceAll(RegExp(r'\D'), '');
  if (digits.isEmpty) return 'Doğum tarihinizi girin.';
  if (digits.length != 8) return 'Tarihi GG.AA.YYYY olarak girin.';
  final day = int.parse(digits.substring(0, 2));
  final month = int.parse(digits.substring(2, 4));
  final year = int.parse(digits.substring(4));
  if (month < 1 || month > 12) return 'Ay 01-12 arasında olmalı.';
  final now = DateTime.now();
  if (year < 1900 || year > now.year) return 'Yıl geçerli değil.';
  final parsed = DateTime(year, month, day);
  // Taşan günleri yakala: 31.02.2002 → DateTime 03.03'e kayar.
  if (parsed.day != day || parsed.month != month || parsed.year != year) {
    return 'Böyle bir tarih yok.';
  }
  if (parsed.isAfter(now)) return 'Doğum tarihi gelecekte olamaz.';
  return null;
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.api, required this.onLoggedIn});

  final KlinotApi api;
  final ValueChanged<UserSession> onLoggedIn;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _username = TextEditingController();
  final _password = TextEditingController();
  final _tckn = TextEditingController();
  final _birthDate = TextEditingController();
  final _otp = TextEditingController();
  var _busy = false;
  var _obscure = true;
  var _selectedRole = 'doctor';
  PatientOtpChallenge? _challenge;
  String? _error;

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    _tckn.dispose();
    _birthDate.dispose();
    _otp.dispose();
    super.dispose();
  }

  Future<void> _pickBirthDate() async {
    final value = await showDatePicker(
      context: context,
      firstDate: DateTime(1900),
      lastDate: DateTime.now(),
      initialDate: DateTime(1990),
      helpText: 'Doğum tarihini seçin',
    );
    if (value != null) {
      _birthDate.text =
          '${value.day.toString().padLeft(2, '0')}.${value.month.toString().padLeft(2, '0')}.${value.year}';
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (_selectedRole == 'patient') {
        if (_challenge == null) {
          final challenge = await widget.api.startPatientOtp(
            _tckn.text.trim(),
            _birthDate.text.trim(),
          );
          if (mounted) setState(() => _challenge = challenge);
        } else {
          final session = await widget.api.verifyPatientOtp(
            _challenge!.challengeId,
            _otp.text.trim(),
          );
          widget.onLoggedIn(session);
        }
      } else {
        final session = await widget.api.login(
          _username.text.trim(),
          _password.text,
          requestedRole: 'doctor',
        );
        if (session.role != 'doctor') {
          throw const ApiException('Seçilen giriş türü bu hesapla eşleşmiyor.');
        }
        widget.onLoggedIn(session);
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _selectRole(String role) {
    setState(() {
      _selectedRole = role;
      _challenge = null;
      _error = null;
      _otp.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    final patient = _selectedRole == 'patient';
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Align(
                          child: CircleAvatar(
                            radius: 34,
                            backgroundColor: klinotTeal,
                            child: Icon(Icons.graphic_eq_rounded, size: 36, color: Colors.white),
                          ),
                        ),
                        const SizedBox(height: 18),
                        Text(
                          'Klinot',
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          patient
                              ? 'T.C. kimlik numaranız ve doğum tarihinizle\nrandevularınıza güvenle ulaşın.'
                              : 'Yüz yüze görüşmeyi kaydedin,\nAI epikrizi güvenle hazırlayın.',
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: Color(0xFF60777D), height: 1.45),
                        ),
                        const SizedBox(height: 24),
                        SegmentedButton<String>(
                          key: const Key('loginRoleSelector'),
                          segments: const [
                            ButtonSegment(value: 'doctor', icon: Icon(Icons.medical_services_outlined), label: Text('Doktor')),
                            ButtonSegment(value: 'patient', icon: Icon(Icons.person_outline_rounded), label: Text('Hasta')),
                          ],
                          selected: {_selectedRole},
                          onSelectionChanged: _busy ? null : (selection) => _selectRole(selection.first),
                          showSelectedIcon: false,
                        ),
                        const SizedBox(height: 22),
                        if (!patient) ...[
                          TextFormField(
                            key: const Key('usernameField'),
                            controller: _username,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: 'Doktor kullanıcı adı',
                              prefixIcon: Icon(Icons.person_outline_rounded),
                            ),
                            validator: (value) => (value ?? '').trim().isEmpty ? 'Kullanıcı adını girin.' : null,
                          ),
                          const SizedBox(height: 14),
                          TextFormField(
                            key: const Key('passwordField'),
                            controller: _password,
                            obscureText: _obscure,
                            onFieldSubmitted: (_) => _busy ? null : _submit(),
                            decoration: InputDecoration(
                              labelText: 'Şifre',
                              prefixIcon: const Icon(Icons.lock_outline_rounded),
                              suffixIcon: IconButton(
                                onPressed: () => setState(() => _obscure = !_obscure),
                                icon: Icon(_obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                              ),
                            ),
                            validator: (value) => (value ?? '').isEmpty ? 'Şifrenizi girin.' : null,
                          ),
                        ] else if (_challenge == null) ...[
                          TextFormField(
                            key: const Key('patientTcknField'),
                            controller: _tckn,
                            keyboardType: TextInputType.number,
                            inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(11)],
                            decoration: const InputDecoration(
                              labelText: 'T.C. kimlik numarası',
                              prefixIcon: Icon(Icons.badge_outlined),
                            ),
                            validator: (value) => (value ?? '').length == 11 ? null : '11 haneli T.C. kimlik numaranızı girin.',
                          ),
                          const SizedBox(height: 14),
                          TextFormField(
                            key: const Key('patientBirthDateField'),
                            controller: _birthDate,
                            keyboardType: TextInputType.number,
                            // Takvim zorunlu degil: 25082002 yazmak yeterli,
                            // noktalar otomatik eklenir.
                            inputFormatters: [
                              FilteringTextInputFormatter.digitsOnly,
                              LengthLimitingTextInputFormatter(8),
                              _BirthDateInputFormatter(),
                            ],
                            decoration: InputDecoration(
                              labelText: 'Doğum tarihi',
                              hintText: 'GG.AA.YYYY',
                              helperText: 'Elle yazabilir ya da takvimden seçebilirsiniz.',
                              prefixIcon: const Icon(Icons.calendar_month_outlined),
                              suffixIcon: IconButton(
                                onPressed: _pickBirthDate,
                                tooltip: 'Takvimden seç',
                                icon: const Icon(Icons.edit_calendar_outlined),
                              ),
                            ),
                            validator: _validateBirthDate,
                          ),
                        ] else ...[
                          Text(
                            '6 haneli doğrulama kodu ${_challenge!.phoneMasked} numaralı telefona gönderildi.',
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: Color(0xFF60777D), height: 1.45),
                          ),
                          if (_challenge!.testMode)
                            const Padding(
                              padding: EdgeInsets.only(top: 8),
                              child: Text('Test ortamı kodu: 000000', textAlign: TextAlign.center, style: TextStyle(color: klinotTeal, fontWeight: FontWeight.w700)),
                            ),
                          const SizedBox(height: 14),
                          TextFormField(
                            key: const Key('patientOtpField'),
                            controller: _otp,
                            autofocus: true,
                            keyboardType: TextInputType.number,
                            textAlign: TextAlign.center,
                            inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(6)],
                            decoration: const InputDecoration(labelText: 'SMS doğrulama kodu', prefixIcon: Icon(Icons.sms_outlined)),
                            validator: (value) => (value ?? '').length == 6 ? null : '6 haneli kodu girin.',
                            onFieldSubmitted: (_) => _busy ? null : _submit(),
                          ),
                          TextButton(
                            onPressed: _busy ? null : () => setState(() { _challenge = null; _otp.clear(); }),
                            child: const Text('Kimlik bilgilerine dön'),
                          ),
                        ],
                        if (_error != null) ...[
                          const SizedBox(height: 14),
                          Text(_error!, textAlign: TextAlign.center, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                        ],
                        const SizedBox(height: 20),
                        FilledButton.icon(
                          key: const Key('loginButton'),
                          onPressed: _busy ? null : _submit,
                          icon: _busy
                              ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : Icon(patient && _challenge == null ? Icons.sms_outlined : Icons.login_rounded),
                          label: Text(_busy ? 'Bağlanıyor…' : patient && _challenge == null ? 'SMS kodu gönder' : 'Giriş yap'),
                        ),
                        const SizedBox(height: 18),
                        const Text('Klinot · v2.32.1', textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: Color(0xFF84969A))),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
