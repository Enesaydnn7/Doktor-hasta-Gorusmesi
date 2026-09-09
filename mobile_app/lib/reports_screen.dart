import 'package:flutter/material.dart';
import 'package:file_saver/file_saver.dart';

import 'api_client.dart';
import 'models.dart';
import 'theme.dart';

class ReportsScreen extends StatefulWidget {
  const ReportsScreen({
    super.key,
    required this.api,
    required this.session,
    required this.result,
  });

  final KlinotApi api;
  final UserSession session;
  final AnalysisResult result;

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> {
  var _downloading = false;

  Future<void> _downloadPdf() async {
    if (_downloading) return;
    setState(() => _downloading = true);
    try {
      final pdf = await widget.api.downloadEpikriz(
        widget.session.token,
        widget.result.doctor,
      );
      final baseName = pdf.fileName.replaceFirst(
        RegExp(r'\.pdf$', caseSensitive: false),
        '',
      );
      final savedPath = await FileSaver.instance.saveAs(
        name: baseName,
        bytes: pdf.bytes,
        fileExtension: 'pdf',
        mimeType: MimeType.pdf,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            savedPath == null
                ? 'PDF kaydetme işlemi iptal edildi.'
                : 'Epikriz PDF olarak kaydedildi.',
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('PDF indirilemedi: $error')));
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final recordLabel = widget.result.recordId == null
        ? 'Yeni görüşme'
        : 'Kayıt #${widget.result.recordId}';
    return Scaffold(
      appBar: AppBar(title: const Text('Doktor epikrizi')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(18, 8, 18, 0),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(18),
                    decoration: BoxDecoration(
                      color: const Color(0xFFE7F5F3),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: const Color(0xFFB4DFDB)),
                    ),
                    child: Row(
                      children: [
                        const CircleAvatar(
                          radius: 24,
                          backgroundColor: klinotTeal,
                          child: Icon(
                            Icons.description_rounded,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Epikriz hazır',
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w800,
                                  color: klinotNavy,
                                ),
                              ),
                              const SizedBox(height: 3),
                              Text(
                                '$recordLabel · Doktor kontrolüne hazır',
                                style: const TextStyle(
                                  color: Color(0xFF4F696F),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const Icon(
                          Icons.check_circle_rounded,
                          color: klinotTeal,
                        ),
                      ],
                    ),
                  ),
                ),
                Expanded(child: JsonReportView(data: widget.result.doctor)),
              ],
            ),
          ),
        ),
      ),
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.fromLTRB(16, 10, 16, 16),
        child: Center(
          heightFactor: 1,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                FilledButton.icon(
                  key: const Key('downloadEpikrizButton'),
                  onPressed: _downloading ? null : _downloadPdf,
                  icon: _downloading
                      ? const SizedBox.square(
                          dimension: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.picture_as_pdf_rounded),
                  label: Text(
                    _downloading
                        ? 'PDF hazırlanıyor…'
                        : 'Epikrizi PDF olarak indir',
                  ),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _downloading
                      ? null
                      : () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.add_rounded),
                  label: const Text('Yeni görüşme'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class JsonReportView extends StatelessWidget {
  const JsonReportView({super.key, required this.data});
  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.fromLTRB(18, 18, 18, 32),
    children: [
      for (final entry in data.entries)
        _ReportValue(label: _humanize(entry.key), value: entry.value),
      if (data.isEmpty)
        const Padding(
          padding: EdgeInsets.all(28),
          child: Center(child: Text('Epikrizde gösterilecek veri yok.')),
        ),
    ],
  );
}

String _humanize(String value) {
  final spaced = value
      .replaceAllMapped(
        RegExp(r'([a-zçğıöşü])([A-ZÇĞİÖŞÜ])'),
        (m) => '${m[1]} ${m[2]}',
      )
      .replaceAll('_', ' ')
      .trim();
  if (spaced.isEmpty) return value;
  return '${spaced[0].toUpperCase()}${spaced.substring(1)}';
}

class _ReportValue extends StatelessWidget {
  const _ReportValue({required this.label, required this.value});
  final String label;
  final dynamic value;

  @override
  Widget build(BuildContext context) {
    if (value is Map) {
      final map = Map<String, dynamic>.from(value as Map);
      return Card(
        margin: const EdgeInsets.only(bottom: 14),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                label.toUpperCase(),
                style: const TextStyle(
                  fontSize: 12,
                  letterSpacing: .6,
                  color: klinotTeal,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 10),
              for (final item in map.entries)
                _NestedRow(label: _humanize(item.key), value: item.value),
            ],
          ),
        ),
      );
    }
    if (value is List) {
      return Card(
        margin: const EdgeInsets.only(bottom: 14),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  color: klinotNavy,
                ),
              ),
              const SizedBox(height: 10),
              for (final item in value as List)
                Padding(
                  padding: const EdgeInsets.only(bottom: 7),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Padding(
                        padding: EdgeInsets.only(top: 7),
                        child: CircleAvatar(
                          radius: 3,
                          backgroundColor: klinotTeal,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          _display(item),
                          style: const TextStyle(height: 1.45),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      );
    }
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(17),
        child: _NestedRow(label: label, value: value),
      ),
    );
  }
}

class _NestedRow extends StatelessWidget {
  const _NestedRow({required this.label, required this.value});
  final String label;
  final dynamic value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            color: Color(0xFF60777D),
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          _display(value),
          style: const TextStyle(height: 1.45, fontSize: 15),
        ),
      ],
    ),
  );
}

String _display(dynamic value) {
  if (value == null || value.toString().trim().isEmpty) return 'Belirtilmedi';
  if (value is List) return value.map(_display).join(' · ');
  if (value is Map) {
    return value.entries
        .map(
          (entry) =>
              '${_humanize(entry.key.toString())}: ${_display(entry.value)}',
        )
        .join('\n');
  }
  return value.toString();
}
