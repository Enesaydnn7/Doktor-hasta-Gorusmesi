import 'dart:async';
import 'dart:io';

import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api_client.dart';
import 'audio_recorder_service.dart';
import 'models.dart';
import 'reports_screen.dart';
import 'theme.dart';

enum RecordingState { idle, recording, paused, ready, processing }

class RecorderScreen extends StatefulWidget {
  const RecorderScreen({
    super.key,
    required this.api,
    required this.session,
    this.recorder,
    this.onSessionExpired,
  });

  final KlinotApi api;
  final UserSession session;
  final AudioRecorderService? recorder;
  final VoidCallback? onSessionExpired;

  @override
  State<RecorderScreen> createState() => _RecorderScreenState();
}

class _RecorderScreenState extends State<RecorderScreen> {
  late final AudioRecorderService _recorder;
  RecordingState _state = RecordingState.idle;
  StreamSubscription<double>? _levelSubscription;
  Timer? _timer;
  Timer? _processingTimer;
  final Stopwatch _processingStopwatch = Stopwatch();
  Duration _elapsed = Duration.zero;
  Duration _processingElapsed = Duration.zero;
  int? _processingPercent;
  String _processingPhase = 'Ses kaydı metne dönüştürülüyor';
  var _level = 0.0;
  var _consent = false;
  File? _recordedFile;
  var _recoveredRecording = false;
  var _analysisCompleted = false;
  String? _error;
  List<ComedPatient> _worklist = const [];
  ComedPatient? _selectedPatient;
  var _loadingWorklist = true;
  String? _worklistError;

  bool get _isRecording =>
      _state == RecordingState.recording || _state == RecordingState.paused;
  bool get _patientMode => widget.session.role == 'patient';

  @override
  void initState() {
    super.initState();
    _recorder = widget.recorder ?? AudioRecorderService();
    _levelSubscription = _recorder.levels.listen((level) {
      if (mounted) setState(() => _level = level);
    });
    unawaited(_loadWorklist());
    unawaited(_recoverRecording());
  }

  Future<void> _recoverRecording() async {
    final recovered = await _recorder.recoverLatest();
    if (!mounted || recovered == null || _state != RecordingState.idle) return;
    setState(() {
      _recordedFile = recovered.file;
      _elapsed = recovered.elapsed ?? Duration.zero;
      _recoveredRecording = true;
      _analysisCompleted = false;
      _state = RecordingState.ready;
      _error = null;
    });
  }

  Future<void> _loadWorklist() async {
    if (mounted) {
      setState(() {
        _loadingWorklist = true;
        _worklistError = null;
      });
    }
    try {
      final patients = await widget.api.getComedWorklist(widget.session.token);
      if (!mounted) return;
      setState(() {
        _worklist = patients;
        _selectedPatient = patients.length == 1 ? patients.first : null;
        _loadingWorklist = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loadingWorklist = false;
        _worklistError = error.toString();
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _processingTimer?.cancel();
    _processingStopwatch.stop();
    unawaited(_levelSubscription?.cancel());
    unawaited(_recorder.dispose());
    super.dispose();
  }

  Future<void> _start() async {
    if (_selectedPatient == null) {
      setState(
        () => _error = _patientMode
            ? 'Kayda başlamadan önce randevunuzu seçin.'
            : 'Kayda başlamadan önce COMED iş listesinden hastayı seçin.',
      );
      return;
    }
    if (!_consent) {
      setState(() => _error = 'Kayıttan önce bilgilendirme onayını alın.');
      return;
    }
    setState(() => _error = null);
    try {
      await _recorder.start();
      _timer?.cancel();
      _elapsed = Duration.zero;
      _recoveredRecording = false;
      _analysisCompleted = false;
      _timer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted && _state == RecordingState.recording) {
          setState(() => _elapsed += const Duration(seconds: 1));
        }
      });
      if (mounted) setState(() => _state = RecordingState.recording);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _togglePause() async {
    if (_state == RecordingState.recording) {
      await _recorder.pause();
      if (mounted) setState(() => _state = RecordingState.paused);
    } else if (_state == RecordingState.paused) {
      await _recorder.resume();
      if (mounted) setState(() => _state = RecordingState.recording);
    }
  }

  Future<void> _cancel() async {
    await _recorder.cancel();
    _timer?.cancel();
    if (mounted) {
      setState(() {
        _state = RecordingState.idle;
        _elapsed = Duration.zero;
        _level = 0;
      });
    }
  }

  Future<void> _stop() async {
    _timer?.cancel();
    try {
      final file = await _recorder.stop();
      if (file == null || !file.existsSync() || file.lengthSync() == 0) {
        throw StateError(
          'Kayıt dosyası boş. Mikrofonu kontrol edip tekrar deneyin.',
        );
      }
      if (!mounted) return;
      unawaited(_recorder.saveRecoveryMetadata(file, _elapsed));
      setState(() {
        _recordedFile = file;
        _recoveredRecording = false;
        _analysisCompleted = false;
        _state = RecordingState.ready;
        _level = 0;
        _error = null;
      });
    } catch (error) {
      if (mounted) {
        setState(() {
          _state = RecordingState.idle;
          _level = 0;
          _error = error.toString();
        });
      }
    }
  }

  Future<void> _discardRecordedFile() async {
    final file = _recordedFile;
    if (file != null) unawaited(_recorder.deleteRecording(file));
    if (!mounted) return;
    setState(() {
      _recordedFile = null;
      _recoveredRecording = false;
      _analysisCompleted = false;
      _state = RecordingState.idle;
      _elapsed = Duration.zero;
      _level = 0;
      _error = null;
    });
  }

  Future<void> _analyze() async {
    final file = _recordedFile;
    if (file == null) return;
    if (_selectedPatient == null) {
      setState(
        () => _error = _patientMode
            ? 'Analizden önce randevunuzu seçin.'
            : 'Analizden önce COMED iş listesinden hastayı seçin.',
      );
      return;
    }
    _processingTimer?.cancel();
    _processingStopwatch
      ..reset()
      ..start();
    _processingElapsed = Duration.zero;
    _processingPercent = null;
    _processingPhase = 'Ses kaydı metne dönüştürülüyor';
    _processingTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted && _state == RecordingState.processing) {
        setState(() => _processingElapsed = _processingStopwatch.elapsed);
      }
    });
    setState(() {
      _state = RecordingState.processing;
      _error = null;
    });

    var keepAwake = false;
    try {
      await _recorder.keepAwake();
      keepAwake = true;
      final transcription = await widget.api.transcribe(
        widget.session.token,
        file,
      );
      if (transcription.transcript.trim().isEmpty) {
        throw const ApiException('Ses metne dönüştürülemedi.');
      }
      if (mounted) {
        setState(() {
          _processingPercent = 0;
          _processingPhase = 'Klinik raporlar hazırlanıyor';
        });
      }

      AnalysisResult? completed;
      await for (final event in widget.api.analyze(
        widget.session.token,
        transcription,
        comedPatient: _selectedPatient,
      )) {
        if (event is AnalysisProgress && mounted) {
          setState(() {
            _processingPercent = event.percent.clamp(0, 100).toInt();
            _processingPhase = _analysisPhaseLabel(event.step);
          });
        }
        if (event is AnalysisCompleted) completed = event.result;
      }
      if (completed == null) {
        throw const ApiException('Sunucu analiz sonucunu göndermedi.');
      }
      if (!mounted) return;

      setState(() {
        _processingPercent = 100;
        _processingPhase = _patientMode
            ? 'Sağlık raporu hazır'
            : 'Epikriz hazır';
      });

      await _recorder.allowSleep();
      keepAwake = false;
      if (!mounted) return;

      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ReportsScreen(
            api: widget.api,
            session: widget.session,
            result: completed!,
          ),
        ),
      );
      if (!mounted) return;
      setState(() {
        // Doktor aynı sesi yeniden analiz edebilsin. Dosya yalnız açıkça
        // "Kaydı sil" seçildiğinde veya yeni kayıt başlatıldığında kaldırılır.
        _state = RecordingState.ready;
        _analysisCompleted = true;
        _error = null;
      });
    } catch (error) {
      if (!mounted) return;
      if (error is ApiException &&
          error.statusCode == 401 &&
          widget.onSessionExpired != null) {
        widget.onSessionExpired!();
        return;
      }
      setState(() {
        _state = RecordingState.ready;
        _error = error.toString();
      });
    } finally {
      _processingTimer?.cancel();
      _processingTimer = null;
      _processingStopwatch.stop();
      if (keepAwake) await _recorder.allowSleep();
    }
  }

  String _analysisPhaseLabel(String step) => switch (step) {
    'hasta' => 'Klinik bulgular düzenleniyor',
    'doktor' =>
      _patientMode
          ? 'Sağlık raporu son kontrollerden geçiyor'
          : 'Detaylı epikriz hazırlanıyor',
    'yonetim' => 'Görüşme kaydı tamamlanıyor',
    _ => 'Klinik raporlar hazırlanıyor',
  };

  String get _time {
    final minutes = _elapsed.inMinutes.toString().padLeft(2, '0');
    final seconds = (_elapsed.inSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    final ready =
        _state == RecordingState.ready || _state == RecordingState.processing;
    final processing = _state == RecordingState.processing;
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 680),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 8),
              Text(
                _isRecording
                    ? 'Görüşme kaydediliyor'
                    : processing
                    ? (_patientMode
                          ? 'Sağlık raporu hazırlanıyor'
                          : 'Epikriz hazırlanıyor')
                    : ready
                    ? 'Görüşme tamamlandı'
                    : 'Yeni görüşme',
                style: Theme.of(context).textTheme.headlineMedium
                    ?.copyWith(fontWeight: FontWeight.w800, color: klinotNavy),
              ),
              const SizedBox(height: 6),
              Text(
                _isRecording
                    ? 'Telefonu masanın ortasında bırakın ve doğal biçimde konuşun.'
                    : processing
                    ? 'Görüşmeniz güvenli biçimde analiz ediliyor. ${_patientMode ? 'Sağlık raporu' : 'Epikriz'} hazır olduğunda otomatik açılacak.'
                    : ready
                    ? 'Görüşme metni ekranda gösterilmez; kayıt analiz için hazır.'
                    : 'Telefonu doktor ile hastanın arasına, mikrofonu açık kalacak şekilde yerleştirin.',
                style: const TextStyle(color: Color(0xFF60777D), height: 1.45),
              ),
              const SizedBox(height: 22),
              // Hastada randevu zaten belli; secim karti ekranin en degerli
              // yerini kapliyor ve kayit dugmesini asagi itiyordu. Tek randevu
              // varsa yalnizca kisa bir bilgi seridi gosterilir ve kayit karti
              // basa alinir. Birden fazla randevuda secim sart oldugu icin tam
              // secici korunur.
              if (!_patientMode || _worklist.length > 1 || _loadingWorklist
                  || _worklistError != null) ...[
                _ComedPatientSelector(
                  patientMode: _patientMode,
                  patients: _worklist,
                  selected: _selectedPatient,
                  loading: _loadingWorklist,
                  error: _worklistError,
                  locked: _isRecording || processing,
                  onChanged: (patient) => setState(() {
                    _selectedPatient = patient;
                    _error = null;
                  }),
                  onRefresh: _loadWorklist,
                ),
                const SizedBox(height: 14),
              ],
              Card(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(22, 28, 22, 24),
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 250),
                    child: _isRecording
                        ? _ActiveRecording(
                            key: const ValueKey('active'),
                            elapsed: _time,
                            level: _level,
                            paused: _state == RecordingState.paused,
                            onPause: _togglePause,
                            onStop: _stop,
                            onCancel: _cancel,
                          )
                        : processing
                        ? _ProcessingRecording(
                            key: ValueKey('processing'),
                            elapsed: _processingElapsed,
                            percent: _processingPercent,
                            phase: _processingPhase,
                            patientMode: _patientMode,
                          )
                        : ready
                        ? _ReadyRecording(
                            key: const ValueKey('ready'),
                            elapsed: _time,
                            recovered: _recoveredRecording,
                            analyzed: _analysisCompleted,
                            onAnalyze: _analyze,
                            onDiscard: _discardRecordedFile,
                            patientMode: _patientMode,
                          )
                        : _IdleRecording(
                            key: const ValueKey('idle'),
                            consent: _consent,
                            onConsentChanged: (value) =>
                                setState(() => _consent = value),
                            onStart: _start,
                            patientMode: _patientMode,
                          ),
                  ),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFECEC),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.error_outline_rounded,
                        color: Color(0xFFC43C3C),
                      ),
                      const SizedBox(width: 10),
                      Expanded(child: Text(_error!)),
                    ],
                  ),
                ),
              ],
              // Tek randevulu hastada bilgi seridi kayit kartinin ALTINDA
              // durur; boylece uygulama acildiginda ilk gorulen sey kayit olur.
              if (_patientMode && _worklist.length == 1 && !_loadingWorklist
                  && _worklistError == null && _selectedPatient != null) ...[
                const SizedBox(height: 14),
                _PatientAppointmentStrip(
                  patient: _selectedPatient!,
                  onRefresh: _loadingWorklist ? null : _loadWorklist,
                ),
              ],
              const SizedBox(height: 18),
              const _PrivacyNote(),
            ],
          ),
        ),
      ),
    );
  }
}

class _ComedPatientSelector extends StatelessWidget {
  const _ComedPatientSelector({
    required this.patients,
    required this.selected,
    required this.loading,
    required this.error,
    required this.locked,
    required this.onChanged,
    required this.onRefresh,
    required this.patientMode,
  });

  final List<ComedPatient> patients;
  final ComedPatient? selected;
  final bool loading;
  final String? error;
  final bool locked;
  final ValueChanged<ComedPatient?> onChanged;
  final VoidCallback onRefresh;
  final bool patientMode;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('comedPatientSelector'),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: const Color(0xFFE8EEFF),
                    borderRadius: BorderRadius.circular(13),
                  ),
                  child: const Icon(
                    Icons.badge_outlined,
                    color: Color(0xFF4A64C8),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        patientMode ? 'Randevularım' : 'COMED iş listesi',
                        style: TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: 16,
                        ),
                      ),
                      SizedBox(height: 2),
                      Text(
                        patientMode
                            ? 'Görüşmenin yapılacağı randevuyu seçin'
                            : 'Görüşme yapılacak hastayı seçin',
                        style: TextStyle(
                          color: Color(0xFF60777D),
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  key: const Key('refreshComedWorklist'),
                  onPressed: loading || locked ? null : onRefresh,
                  tooltip: 'İş listesini yenile',
                  icon: const Icon(Icons.refresh_rounded),
                ),
              ],
            ),
            const SizedBox(height: 14),
            if (loading)
              const LinearProgressIndicator(minHeight: 3)
            else if (patients.isEmpty)
              Column(
                children: [
                  Container(
                    padding: const EdgeInsets.all(13),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFF7E8),
                      borderRadius: BorderRadius.circular(13),
                    ),
                    child: Text(
                      error == null
                          ? (patientMode
                                ? 'Henüz eşitlenmiş bir randevu bulunamadı.'
                                : 'İş listesi henüz eşitlenmedi. Köprü kurulumunu tamamlayıp COMED iş listesini yenileyin.')
                          : '${patientMode ? 'Randevular' : 'İş listesi'} alınamadı: $error',
                      style: const TextStyle(
                        color: Color(0xFF795A18),
                        height: 1.4,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  if (!patientMode)
                    const ExpansionTile(
                      key: Key('comedSetupInstructions'),
                      tilePadding: EdgeInsets.symmetric(horizontal: 4),
                      childrenPadding: EdgeInsets.fromLTRB(8, 0, 8, 10),
                      leading: Icon(Icons.extension_outlined),
                      title: Text(
                        'COMED bağlantısı nasıl kurulur?',
                        style: TextStyle(fontWeight: FontWeight.w700),
                      ),
                      children: [
                        Text(
                          '1. Bilgisayardaki Chrome’a Klinot COMED Köprüsü eklentisini kurun.\n'
                          '2. COMED’e kendi hesabınızla normal şekilde giriş yapın.\n'
                          '3. Eklentiyi Klinot kullanıcı adınız ve şifrenizle bağlayın. COMED parolanızı eklentiye yazmayın.\n'
                          '4. COMED iş listesini yenileyin, sonra bu ekrandaki yenile simgesine basın.',
                          style: TextStyle(
                            color: Color(0xFF526B73),
                            height: 1.55,
                          ),
                        ),
                      ],
                    ),
                ],
              )
            else
              DropdownButtonFormField<ComedPatient>(
                key: const Key('comedPatientDropdown'),
                initialValue: selected,
                isExpanded: true,
                onChanged: locked ? null : onChanged,
                decoration: InputDecoration(
                  labelText: patientMode
                      ? 'Randevu / protokol'
                      : 'Hasta / protokol',
                  prefixIcon: const Icon(Icons.person_search_outlined),
                ),
                items: patients
                    .map(
                      (patient) => DropdownMenuItem(
                        value: patient,
                        child: Text(
                          '${patient.patientName} · ${patient.protocolNo.isEmpty ? patient.visitId : patient.protocolNo}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    )
                    .toList(),
              ),
            if (selected != null) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _PatientChip(
                    Icons.local_hospital_outlined,
                    selected!.department,
                  ),
                  _PatientChip(
                    Icons.medical_services_outlined,
                    selected!.doctorName,
                  ),
                  _PatientChip(
                    Icons.confirmation_number_outlined,
                    'Hasta No ${selected!.patientNo}',
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Tek randevulu hastada secim karti yerine gosterilen kompakt bilgi seridi.
/// Secim sunmaz; yalnizca gorusmenin hangi randevuya islenecegini bildirir.
class _PatientAppointmentStrip extends StatelessWidget {
  const _PatientAppointmentStrip({required this.patient, this.onRefresh});

  final ComedPatient patient;
  final VoidCallback? onRefresh;

  @override
  Widget build(BuildContext context) {
    final detay = [
      patient.department,
      patient.doctorName,
      'Hasta No ${patient.patientNo}',
    ].where((value) => value.trim().isNotEmpty).join(' · ');

    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 8, 12),
      decoration: BoxDecoration(
        color: const Color(0xFFF2F8F8),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFDCE9EB)),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.event_available_outlined,
            size: 20,
            color: klinotTeal,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Bu görüşme randevunuza işlenecek',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                    color: klinotNavy,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  detay,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Color(0xFF60777D),
                    fontSize: 12,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: onRefresh,
            tooltip: 'Randevuları yenile',
            icon: const Icon(Icons.refresh_rounded, size: 20),
            color: klinotTeal,
          ),
        ],
      ),
    );
  }
}

class _PatientChip extends StatelessWidget {
  const _PatientChip(this.icon, this.label);
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    if (label.trim().isEmpty || label.trim() == 'Hasta No') {
      return const SizedBox.shrink();
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: klinotCanvas,
        borderRadius: BorderRadius.circular(99),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 15, color: klinotTeal),
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

class _IdleRecording extends StatelessWidget {
  const _IdleRecording({
    super.key,
    required this.consent,
    required this.onConsentChanged,
    required this.onStart,
    required this.patientMode,
  });

  final bool consent;
  final ValueChanged<bool> onConsentChanged;
  final VoidCallback onStart;
  final bool patientMode;

  Future<void> _showPrivacyNotice(BuildContext context) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 4, 24, 28),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('Kişisel Verilerin Korunması', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                const SizedBox(height: 14),
                const Text(
                  'Görüşme sesi; sağlık hizmetinin yürütülmesi, görüşmenin yazıya çevrilmesi ve doktor/hasta raporlarının hazırlanması amacıyla işlenir. Kayıt yalnızca yetkili hesaplarla ilişkilendirilir. Doktor son kontrolü yapmadan COMED kaydı imzalanmaz.',
                  style: TextStyle(height: 1.55),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Veri sorumlusunun ayrıntılı aydınlatma metni, başvuru yöntemleri ve KVKK kapsamındaki haklarınız için MLP Care kişisel verilerin korunması sayfasını inceleyebilirsiniz.',
                  style: TextStyle(height: 1.55, color: Color(0xFF60777D)),
                ),
                const SizedBox(height: 18),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () => launchUrl(
                      Uri.parse('https://www.mlpcare.com/tr/protection-of-personal-data'),
                      mode: LaunchMode.externalApplication,
                    ),
                    icon: const Icon(Icons.open_in_new_rounded),
                    label: const Text('MLP Care aydınlatma metnini aç'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Container(
        width: 112,
        height: 112,
        decoration: BoxDecoration(
          color: const Color(0xFFE5F5F3),
          shape: BoxShape.circle,
          border: Border.all(color: const Color(0xFFB4DFDB), width: 8),
        ),
        child: const Icon(Icons.mic_rounded, size: 52, color: klinotTeal),
      ),
      const SizedBox(height: 22),
      Text(
        'Kayda hazır',
        style: Theme.of(context).textTheme.titleLarge
            ?.copyWith(fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 8),
      const Text(
        'Sessiz bir ortam ve masanın ortası en iyi sonucu verir.',
        textAlign: TextAlign.center,
        style: TextStyle(color: Color(0xFF60777D)),
      ),
      const SizedBox(height: 24),
      InkWell(
        onTap: () => onConsentChanged(!consent),
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.all(13),
          decoration: BoxDecoration(
            color: klinotCanvas,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CupertinoSwitch(
                key: const Key('recordingConsentSwitch'),
                value: consent,
                onChanged: onConsentChanged,
                activeTrackColor: klinotTeal,
              ),
              Expanded(
                child: Padding(
                  padding: EdgeInsets.only(top: 7),
                  child: Text(
                    patientMode
                        ? 'Görüşmenin kaydedileceği ve sağlık raporu üretiminde kullanılacağı konusunda bilgilendirildim.'
                        : 'Hasta, görüşmenin kaydedileceği ve rapor üretiminde kullanılacağı konusunda bilgilendirildi.',
                    style: const TextStyle(height: 1.4),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
      TextButton.icon(
        key: const Key('privacyNoticeButton'),
        onPressed: () => _showPrivacyNotice(context),
        icon: const Icon(Icons.shield_outlined, size: 18),
        label: const Text('Aydınlatma metnini incele'),
      ),
      const SizedBox(height: 20),
      SizedBox(
        width: double.infinity,
        child: FilledButton.icon(
          key: const Key('startRecordingButton'),
          onPressed: onStart,
          icon: const Icon(Icons.fiber_manual_record_rounded),
          label: const Text('Kaydı başlat'),
        ),
      ),
    ],
  );
}

class _ActiveRecording extends StatelessWidget {
  const _ActiveRecording({
    super.key,
    required this.elapsed,
    required this.level,
    required this.paused,
    required this.onPause,
    required this.onStop,
    required this.onCancel,
  });

  final String elapsed;
  final double level;
  final bool paused;
  final VoidCallback onPause;
  final VoidCallback onStop;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: paused ? const Color(0xFFFFF1D6) : const Color(0xFFFFE6E6),
          borderRadius: BorderRadius.circular(99),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              paused ? Icons.pause_rounded : Icons.fiber_manual_record_rounded,
              size: 17,
              color: paused ? const Color(0xFFB77900) : const Color(0xFFC43C3C),
            ),
            const SizedBox(width: 7),
            Text(
              paused ? 'KAYIT DURAKLATILDI' : 'KAYIT YAPILIYOR',
              style: TextStyle(
                fontSize: 12,
                letterSpacing: .7,
                fontWeight: FontWeight.w800,
                color: paused
                    ? const Color(0xFF8A5B00)
                    : const Color(0xFFA62828),
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: 24),
      Text(
        elapsed,
        key: const Key('recordingTimer'),
        style: Theme.of(context).textTheme.displayMedium?.copyWith(
          fontWeight: FontWeight.w700,
          fontFeatures: const [FontFeature.tabularFigures()],
        ),
      ),
      const SizedBox(height: 24),
      _LevelMeter(level: paused ? 0.05 : level),
      const SizedBox(height: 8),
      Text(
        level < .08 && !paused ? 'Ses seviyesi düşük' : 'Mikrofon aktif',
        style: const TextStyle(color: Color(0xFF60777D), fontSize: 13),
      ),
      const SizedBox(height: 26),
      Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          IconButton.filledTonal(
            onPressed: onPause,
            tooltip: paused ? 'Devam et' : 'Duraklat',
            icon: Icon(paused ? Icons.play_arrow_rounded : Icons.pause_rounded),
          ),
          const SizedBox(width: 18),
          SizedBox(
            width: 84,
            height: 84,
            child: FilledButton(
              key: const Key('stopRecordingButton'),
              onPressed: onStop,
              style: FilledButton.styleFrom(
                shape: const CircleBorder(),
                backgroundColor: const Color(0xFFC43C3C),
                padding: EdgeInsets.zero,
              ),
              child: const Icon(Icons.stop_rounded, size: 39),
            ),
          ),
          const SizedBox(width: 18),
          IconButton.filledTonal(
            onPressed: onCancel,
            tooltip: 'Kaydı iptal et',
            icon: const Icon(Icons.delete_outline_rounded),
          ),
        ],
      ),
      const SizedBox(height: 10),
      const Text(
        'Görüşmeyi bitir',
        style: TextStyle(fontWeight: FontWeight.w600),
      ),
    ],
  );
}

class _ReadyRecording extends StatelessWidget {
  const _ReadyRecording({
    super.key,
    required this.elapsed,
    required this.recovered,
    required this.analyzed,
    required this.onAnalyze,
    required this.onDiscard,
    required this.patientMode,
  });

  final String elapsed;
  final bool recovered;
  final bool analyzed;
  final VoidCallback onAnalyze;
  final VoidCallback onDiscard;
  final bool patientMode;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      const CircleAvatar(
        radius: 48,
        backgroundColor: Color(0xFFE5F5F3),
        child: Icon(Icons.check_rounded, size: 52, color: klinotTeal),
      ),
      const SizedBox(height: 20),
      Text(
        'Kayıt hazır',
        style: Theme.of(context).textTheme.titleLarge
            ?.copyWith(fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 7),
      Text(
        recovered && elapsed == '00:00'
            ? 'Önceki kayıt cihazdan kurtarıldı'
            : 'Görüşme süresi $elapsed',
        style: const TextStyle(color: Color(0xFF60777D)),
      ),
      const SizedBox(height: 8),
      Text(
        analyzed
            ? 'Ses kaydı cihazda korunuyor. Aynı görüşmeyi yeniden analiz edebilir veya kaydı silip yeni görüşmeye başlayabilirsiniz.'
            : 'Analiz başladığında görüşme metni ve işlem adımları gösterilmez. ${patientMode ? 'Sağlık raporu' : 'Epikriz'} hazır olunca ekran otomatik açılır.',
        textAlign: TextAlign.center,
        style: TextStyle(color: Color(0xFF60777D), height: 1.45),
      ),
      const SizedBox(height: 24),
      SizedBox(
        width: double.infinity,
        child: FilledButton.icon(
          key: const Key('analyzeButton'),
          onPressed: onAnalyze,
          icon: const Icon(Icons.auto_awesome_rounded),
          label: Text(analyzed ? 'Tekrar analiz et' : 'Analiz et'),
        ),
      ),
      const SizedBox(height: 8),
      TextButton.icon(
        key: const Key('discardRecordingButton'),
        onPressed: onDiscard,
        icon: const Icon(Icons.delete_outline_rounded),
        label: const Text('Kaydı sil ve yeniden başla'),
      ),
    ],
  );
}

class _ProcessingRecording extends StatelessWidget {
  const _ProcessingRecording({
    super.key,
    required this.elapsed,
    required this.percent,
    required this.phase,
    required this.patientMode,
  });

  final Duration elapsed;
  final int? percent;
  final String phase;
  final bool patientMode;

  String get elapsedLabel {
    final minutes = elapsed.inMinutes.toString().padLeft(2, '0');
    final seconds = (elapsed.inSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) => Column(
    children: [
      SizedBox.square(
        dimension: 116,
        child: Stack(
          alignment: Alignment.center,
          children: [
            SizedBox.expand(
              child: CircularProgressIndicator(
                key: const Key('epikrizLoadingIndicator'),
                value: percent == null ? null : percent! / 100,
                strokeWidth: 9,
                color: klinotTeal,
                backgroundColor: const Color(0xFFD9EFEC),
              ),
            ),
            Container(
              width: 82,
              height: 82,
              decoration: const BoxDecoration(
                color: Color(0xFFE5F5F3),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.description_rounded,
                size: 42,
                color: klinotTeal,
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: 26),
      Text(
        patientMode ? 'Sağlık raporu hazırlanıyor' : 'Epikriz hazırlanıyor',
        style: Theme.of(context).textTheme.titleLarge
            ?.copyWith(fontWeight: FontWeight.w800, color: klinotNavy),
      ),
      const SizedBox(height: 10),
      Text(
        phase,
        textAlign: TextAlign.center,
        style: const TextStyle(
          color: Color(0xFF60777D),
          height: 1.5,
          fontWeight: FontWeight.w600,
        ),
      ),
      const SizedBox(height: 16),
      LinearProgressIndicator(
        key: const Key('analysisProgress'),
        value: percent == null ? null : percent! / 100,
        minHeight: 9,
        borderRadius: BorderRadius.circular(99),
        color: klinotTeal,
        backgroundColor: const Color(0xFFD9EFEC),
      ),
      const SizedBox(height: 10),
      Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            'Geçen süre $elapsedLabel',
            key: const Key('processingElapsed'),
            style: const TextStyle(color: Color(0xFF60777D)),
          ),
          Text(
            percent == null ? 'Ses işleniyor' : 'Gerçek ilerleme · %$percent',
            key: const Key('processingPercent'),
            style: const TextStyle(
              color: klinotTeal,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
      const SizedBox(height: 18),
      Container(
        key: const Key('privateAnalysisNotice'),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        decoration: BoxDecoration(
          color: klinotCanvas,
          borderRadius: BorderRadius.circular(14),
        ),
        child: const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.visibility_off_outlined, color: klinotTeal, size: 21),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'Süre cihaz saatinden, yüzde ise sunucunun tamamladığı gerçek rapor adımlarından gelir.',
                style: TextStyle(color: Color(0xFF60777D), height: 1.4),
              ),
            ),
          ],
        ),
      ),
    ],
  );
}

class _LevelMeter extends StatelessWidget {
  const _LevelMeter({required this.level});
  final double level;

  @override
  Widget build(BuildContext context) => Semantics(
    label: 'Canlı mikrofon ses seviyesi yüzde ${(level * 100).round()}',
    child: SizedBox(
      height: 54,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: List.generate(24, (index) {
          final distance = (index - 11.5).abs() / 11.5;
          final shape = (1 - distance * .55).clamp(.35, 1.0);
          final height = 7 + 45 * level * shape;
          return AnimatedContainer(
            duration: const Duration(milliseconds: 100),
            width: 5,
            height: height,
            margin: const EdgeInsets.symmetric(horizontal: 2),
            decoration: BoxDecoration(
              color: level < .08 ? const Color(0xFFB6C7CA) : klinotTeal,
              borderRadius: BorderRadius.circular(99),
            ),
          );
        }),
      ),
    ),
  );
}

class _PrivacyNote extends StatelessWidget {
  const _PrivacyNote();

  @override
  Widget build(BuildContext context) => const Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Icon(Icons.shield_outlined, size: 21, color: klinotTeal),
      SizedBox(width: 10),
      Expanded(
        child: Text(
          'Kayıt sırasında uygulamayı kapatmayın. Analiz tamamlandığında görüşme mevcut yönetim panelindeki kayıtlarla birlikte saklanır.',
          style: TextStyle(
            fontSize: 13,
            color: Color(0xFF60777D),
            height: 1.45,
          ),
        ),
      ),
    ],
  );
}
