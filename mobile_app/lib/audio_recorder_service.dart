import 'dart:async';
import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

class AudioRecorderService {
  final AudioRecorder _recorder = AudioRecorder();
  StreamSubscription<Amplitude>? _amplitudeSub;
  final StreamController<double> _levels = StreamController.broadcast();

  Stream<double> get levels => _levels.stream;

  Future<bool> hasPermission() => _recorder.hasPermission();

  Future<void> start() async {
    if (!await hasPermission()) {
      throw StateError('Mikrofon izni verilmedi.');
    }
    final directory = await getTemporaryDirectory();
    final path =
        '${directory.path}${Platform.pathSeparator}'
        'klinot_${DateTime.now().millisecondsSinceEpoch}.m4a';
    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.aacLc,
        bitRate: 128000,
        sampleRate: 44100,
        numChannels: 1,
        autoGain: true,
        noiseSuppress: true,
        echoCancel: false,
      ),
      path: path,
    );
    _amplitudeSub = _recorder
        .onAmplitudeChanged(const Duration(milliseconds: 120))
        .listen((amplitude) {
          final normalized = ((amplitude.current + 55) / 55).clamp(0.0, 1.0);
          _levels.add(normalized);
        });
    await WakelockPlus.enable();
  }

  Future<void> pause() => _recorder.pause();
  Future<void> resume() => _recorder.resume();

  Future<File?> stop() async {
    final path = await _recorder.stop();
    await _finish();
    return path == null ? null : File(path);
  }

  Future<void> cancel() async {
    await _recorder.cancel();
    await _finish();
  }

  Future<void> _finish() async {
    await _amplitudeSub?.cancel();
    _amplitudeSub = null;
    _levels.add(0);
    await WakelockPlus.disable();
  }

  Future<void> dispose() async {
    await _amplitudeSub?.cancel();
    await _recorder.dispose();
    await _levels.close();
  }
}
