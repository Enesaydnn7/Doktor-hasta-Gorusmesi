import 'package:flutter/material.dart';

import 'api_client.dart';
import 'models.dart';
import 'reports_screen.dart';
import 'theme.dart';

class TranscriptScreen extends StatefulWidget {
  const TranscriptScreen({
    super.key,
    required this.api,
    required this.session,
    required this.transcription,
  });

  final KlinotApi api;
  final UserSession session;
  final TranscriptionResult transcription;

  @override
  State<TranscriptScreen> createState() => _TranscriptScreenState();
}

class _TranscriptScreenState extends State<TranscriptScreen> {
  late final TextEditingController _controller;
  var _analyzing = false;
  var _percent = 0;
  var _step = '';
  String? _error;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.transcription.transcript);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  String _stepLabel(String step) => switch (step) {
    'hasta' => 'Hasta özeti hazırlanıyor',
    'doktor' => 'Detaylı epikriz hazırlanıyor',
    'yonetim' => 'Yönetim raporu hazırlanıyor',
    _ => 'Analiz hazırlanıyor',
  };

  Future<void> _analyze() async {
    final text = _controller.text.trim();
    if (text.isEmpty) {
      setState(() => _error = 'Görüşme metni boş olamaz.');
      return;
    }
    setState(() {
      _analyzing = true;
      _percent = 0;
      _step = 'hasta';
      _error = null;
    });
    final updated = TranscriptionResult(
      transcript: text,
      audioId: widget.transcription.audioId,
      usage: widget.transcription.usage,
    );
    try {
      await for (final event in widget.api.analyze(
        widget.session.token,
        updated,
      )) {
        if (!mounted) return;
        if (event is AnalysisProgress) {
          setState(() {
            _percent = event.percent;
            _step = event.step;
          });
        } else if (event is AnalysisCompleted) {
          setState(() => _percent = 100);
          await Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (_) => ReportsScreen(result: event.result),
            ),
          );
          return;
        }
      }
      throw const ApiException('Sunucu analiz sonucunu göndermedi.');
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _analyzing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_analyzing,
      child: Scaffold(
        appBar: AppBar(title: const Text('Görüşme metni')),
        body: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 760),
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
                children: [
                  Text(
                    'Metni kontrol edin',
                    style: Theme.of(context).textTheme.headlineSmall
                        ?.copyWith(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 7),
                  const Text(
                    'Doktor ve hasta etiketlerini, ilaç adlarını ve önemli sayıları gerekirse düzeltin.',
                    style: TextStyle(color: Color(0xFF60777D), height: 1.45),
                  ),
                  const SizedBox(height: 18),
                  TextField(
                    key: const Key('transcriptField'),
                    controller: _controller,
                    enabled: !_analyzing,
                    minLines: 14,
                    maxLines: 24,
                    decoration: const InputDecoration(
                      alignLabelWithHint: true,
                      labelText: 'Doktor–hasta görüşmesi',
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (_analyzing)
                    _AnalysisProgressCard(
                      percent: _percent,
                      step: _stepLabel(_step),
                    ),
                  if (_error != null) ...[
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFFECEC),
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Text(
                        _error!,
                        style: const TextStyle(color: Color(0xFFA62828)),
                      ),
                    ),
                    const SizedBox(height: 14),
                  ],
                  FilledButton.icon(
                    key: const Key('analyzeButton'),
                    onPressed: _analyzing ? null : _analyze,
                    icon: const Icon(Icons.auto_awesome_rounded),
                    label: Text(
                      _analyzing
                          ? 'Analiz sürüyor · %$_percent'
                          : 'Üç raporu hazırla',
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Raporlar sırayla üretilir. Gösterilen yüzde sunucudan gelen gerçek tamamlanma bilgisidir.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12, color: Color(0xFF71868B)),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _AnalysisProgressCard extends StatelessWidget {
  const _AnalysisProgressCard({required this.percent, required this.step});
  final int percent;
  final String step;

  @override
  Widget build(BuildContext context) => Container(
    key: const Key('analysisProgress'),
    margin: const EdgeInsets.only(bottom: 16),
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: const Color(0xFFE7F5F3),
      borderRadius: BorderRadius.circular(16),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.auto_awesome_rounded, color: klinotTeal),
            const SizedBox(width: 9),
            Expanded(
              child: Text(
                step,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ),
            Text(
              '%$percent',
              style: const TextStyle(
                fontWeight: FontWeight.w800,
                color: klinotTeal,
              ),
            ),
          ],
        ),
        const SizedBox(height: 13),
        LinearProgressIndicator(
          value: percent / 100,
          minHeight: 9,
          borderRadius: BorderRadius.circular(99),
        ),
      ],
    ),
  );
}
