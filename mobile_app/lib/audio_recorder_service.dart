import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

class RecoveredRecording {
  const RecoveredRecording({required this.file, this.elapsed});

  final File file;
  final Duration? elapsed;
}

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
    final documents = await getApplicationDocumentsDirectory();
    final directory = Directory(
      '${documents.path}${Platform.pathSeparator}klinot_recordings',
    );
    await directory.create(recursive: true);
    final path =
        '${directory.path}${Platform.pathSeparator}'
        'klinot_${DateTime.now().millisecondsSinceEpoch}.m4a';
    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.aacLc,
        // Konuşma için 64 kbps yeterlidir; 30 dakikalık kayıt yaklaşık 14 MB
        // kalır ve hem mobil yükleme hem STT yedek sağlayıcısı sınırına sığar.
        bitRate: 64000,
        sampleRate: 32000,
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

  Future<void> keepAwake() => WakelockPlus.enable();
  Future<void> allowSleep() => WakelockPlus.disable();

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

  Future<void> saveRecoveryMetadata(File file, Duration elapsed) async {
    try {
      await File('${file.path}.meta.json').writeAsString(
        jsonEncode({'elapsed_seconds': elapsed.inSeconds}),
        flush: true,
      );
    } catch (_) {
      // Ses dosyası tek başına da kurtarılabilir; metadata yardımcı bilgidir.
    }
  }

  Future<RecoveredRecording?> recoverLatest() async {
    try {
      final directories = <Directory>[];
      final documents = await getApplicationDocumentsDirectory();
      directories.add(
        Directory(
          '${documents.path}${Platform.pathSeparator}klinot_recordings',
        ),
      );
      // v2.8.1 ve önceki sürümler kayıtları geçici klasöre yazıyordu.
      directories.add(await getTemporaryDirectory());

      final candidates = <File>[];
      for (final directory in directories) {
        if (!directory.existsSync()) continue;
        for (final entity in directory.listSync()) {
          if (entity is File &&
              RegExp(r'klinot_.*\.m4a$').hasMatch(entity.path) &&
              entity.lengthSync() > 0) {
            candidates.add(entity);
          }
        }
      }
      if (candidates.isEmpty) return null;
      candidates.sort(
        (a, b) => b.lastModifiedSync().compareTo(a.lastModifiedSync()),
      );
      final file = candidates.first;
      Duration? elapsed;
      final metadata = File('${file.path}.meta.json');
      if (metadata.existsSync()) {
        final decoded = jsonDecode(await metadata.readAsString());
        final seconds = (decoded as Map<String, dynamic>)['elapsed_seconds'];
        if (seconds is num && seconds >= 0) {
          elapsed = Duration(seconds: seconds.toInt());
        }
      }
      return RecoveredRecording(file: file, elapsed: elapsed);
    } catch (_) {
      return null;
    }
  }

  Future<void> deleteRecording(File file) async {
    final metadata = File('${file.path}.meta.json');
    if (file.existsSync()) await file.delete();
    if (metadata.existsSync()) await metadata.delete();
  }

  Future<void> dispose() async {
    await _amplitudeSub?.cancel();
    await _recorder.dispose();
    await _levels.close();
    await WakelockPlus.disable();
  }
}
