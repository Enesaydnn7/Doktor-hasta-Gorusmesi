import 'dart:async';

import 'package:flutter/material.dart';

import 'api_client.dart';
import 'audio_recorder_service.dart';
import 'models.dart';
import 'theme.dart';
import 'transcript_screen.dart';

enum RecordingState { idle, recording, paused, uploading }

class RecorderScreen extends StatefulWidget {
  const RecorderScreen({
    super.key,
    required this.api,
    required this.session,
    this.recorder,
  });

  final KlinotApi api;
  final UserSession session;
  final AudioRecorderService? recorder;

  @override
  State<RecorderScreen> createState() => _RecorderScreenState();
}

class _RecorderScreenState extends State<RecorderScreen> {
  late final AudioRecorderService _recorder;
  RecordingState _state = RecordingState.idle;
  StreamSubscription<double>? _levelSubscription;
  Timer? _timer;
  Duration _elapsed = Duration.zero;
  var _level = 0.0;
  var _consent = false;
  String? _error;

  bool get _isRecording =>
      _state == RecordingState.recording || _state == RecordingState.paused;

  @override
  void initState() {
    super.initState();
    _recorder = widget.recorder ?? AudioRecorderService();
    _levelSubscription = _recorder.levels.listen((level) {
      if (mounted) setState(() => _level = level);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    unawaited(_levelSubscription?.cancel());
    unawaited(_recorder.dispose());
    super.dispose();
  }

  Future<void> _start() async {
    if (!_consent) {
      setState(() => _error = 'Kayıttan önce bilgilendirme onayını alın.');
      return;
    }
    setState(() => _error = null);
    try {
      await _recorder.start();
      _timer?.cancel();
      _elapsed = Duration.zero;
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

  Future<void> _stopAndTranscribe() async {
    _timer?.cancel();
    setState(() {
      _state = RecordingState.uploading;
      _error = null;
    });
    try {
      final file = await _recorder.stop();
      if (file == null || !await file.exists() || await file.length() == 0) {
        throw StateError(
          'Kayıt dosyası boş. Mikrofonu kontrol edip tekrar deneyin.',
        );
      }
      final result = await widget.api.transcribe(widget.session.token, file);
      if (result.transcript.trim().isEmpty) {
        throw const ApiException('Ses metne dönüştürülemedi.');
      }
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => TranscriptScreen(
            api: widget.api,
            session: widget.session,
            transcription: result,
          ),
        ),
      );
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) {
        setState(() {
          _state = RecordingState.idle;
          _elapsed = Duration.zero;
          _level = 0;
        });
      }
    }
  }

  String get _time {
    final minutes = _elapsed.inMinutes.toString().padLeft(2, '0');
    final seconds = (_elapsed.inSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    final busy = _state == RecordingState.uploading;
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
                _isRecording ? 'Görüşme kaydediliyor' : 'Yeni görüşme',
                style: Theme.of(context).textTheme.headlineMedium
                    ?.copyWith(fontWeight: FontWeight.w800, color: klinotNavy),
              ),
              const SizedBox(height: 6),
              Text(
                _isRecording
                    ? 'Telefonu masanın ortasında bırakın ve doğal biçimde konuşun.'
                    : 'Telefonu doktor ile hastanın arasına, mikrofonu açık kalacak şekilde yerleştirin.',
                style: const TextStyle(color: Color(0xFF60777D), height: 1.45),
              ),
              const SizedBox(height: 22),
              Card(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(22, 28, 22, 24),
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 250),
                    child: busy
                        ? const _UploadState()
                        : _isRecording
                        ? _ActiveRecording(
                            key: const ValueKey('active'),
                            elapsed: _time,
                            level: _level,
                            paused: _state == RecordingState.paused,
                            onPause: _togglePause,
                            onStop: _stopAndTranscribe,
                            onCancel: _cancel,
                          )
                        : _IdleRecording(
                            key: const ValueKey('idle'),
                            consent: _consent,
                            onConsentChanged: (value) =>
                                setState(() => _consent = value),
                            onStart: _start,
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
              const SizedBox(height: 18),
              const _PrivacyNote(),
            ],
          ),
        ),
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
  });

  final bool consent;
  final ValueChanged<bool> onConsentChanged;
  final VoidCallback onStart;

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
              Checkbox(
                value: consent,
                onChanged: (value) => onConsentChanged(value ?? false),
              ),
              const Expanded(
                child: Padding(
                  padding: EdgeInsets.only(top: 7),
                  child: Text(
                    'Hasta, görüşmenin kaydedileceği ve rapor üretiminde kullanılacağı konusunda bilgilendirildi.',
                    style: TextStyle(height: 1.4),
                  ),
                ),
              ),
            ],
          ),
        ),
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
        'Bitir ve metne dönüştür',
        style: TextStyle(fontWeight: FontWeight.w600),
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

class _UploadState extends StatelessWidget {
  const _UploadState();

  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.symmetric(vertical: 52),
    child: Column(
      key: ValueKey('uploading'),
      children: [
        SizedBox.square(dimension: 46, child: CircularProgressIndicator()),
        SizedBox(height: 22),
        Text(
          'Ses güvenli biçimde işleniyor…',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
        ),
        SizedBox(height: 8),
        Text('Render uyanıyorsa ilk işlem biraz uzun sürebilir.'),
      ],
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
