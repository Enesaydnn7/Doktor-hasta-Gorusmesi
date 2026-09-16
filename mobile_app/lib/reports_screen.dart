import 'dart:async';

import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

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
  var _transferring = false;
  ComedTransfer? _transfer;

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
      _notice(
        savedPath == null
            ? 'PDF kaydetme işlemi iptal edildi.'
            : 'Epikriz PDF olarak kaydedildi.',
      );
    } catch (error) {
      if (mounted) _notice('PDF indirilemedi: $error', error: true);
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  Future<void> _transferToComed() async {
    final patient = widget.result.comedPatient;
    final recordId = widget.result.recordId;
    if (_transferring || patient == null || recordId == null) return;
    setState(() => _transferring = true);
    try {
      final transfer = await widget.api.createComedTransfer(
        widget.session.token,
        recordId,
        patient,
      );
      if (!mounted) return;
      setState(() => _transfer = transfer);
      _notice(
        'COMED aktarımı kuyruğa alındı. Açık COMED ekranına gönderiliyor.',
      );
      await _pollTransfer(transfer.id);
    } catch (error) {
      if (mounted) _notice('COMED aktarımı başlatılamadı: $error', error: true);
    } finally {
      if (mounted) setState(() => _transferring = false);
    }
  }

  Future<void> _pollTransfer(int transferId) async {
    for (var attempt = 0; attempt < 15 && mounted; attempt++) {
      await Future<void>.delayed(const Duration(seconds: 2));
      if (!mounted) return;
      try {
        final current = await widget.api.getComedTransfer(
          widget.session.token,
          transferId,
        );
        if (!mounted) return;
        setState(() => _transfer = current);
        if ({
          'ready_for_review',
          'completed',
          'failed',
        }.contains(current.status)) {
          return;
        }
      } catch (_) {
        return;
      }
    }
  }

  Future<void> _openComed() async {
    final value =
        _transfer?.clinicalCardUrl ??
        widget.result.comedPatient?.clinicalCardUrl ??
        '';
    final uri = Uri.tryParse(value);
    if (uri == null ||
        !await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (mounted) _notice('COMED bağlantısı açılamadı.', error: true);
    }
  }

  void _notice(String message, {bool error = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: error ? Theme.of(context).colorScheme.error : null,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final recordLabel = widget.result.recordId == null
        ? 'Yeni görüşme'
        : 'Kayıt #${widget.result.recordId}';
    final patient = widget.result.comedPatient;
    return Scaffold(
      appBar: AppBar(title: const Text('Doktor epikrizi')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 780),
            child: CustomScrollView(
              slivers: [
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(18, 8, 18, 0),
                  sliver: SliverToBoxAdapter(
                    child: _ReadyHeader(
                      recordLabel: recordLabel,
                      patient: patient,
                    ),
                  ),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(18, 14, 18, 30),
                  sliver: SliverToBoxAdapter(
                    child: JsonReportView(data: widget.result.doctor),
                  ),
                ),
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
            constraints: const BoxConstraints(maxWidth: 780),
            child: _ReportActions(
              downloading: _downloading,
              transferring: _transferring,
              transfer: _transfer,
              canTransfer: patient != null && widget.result.recordId != null,
              canOpenComed: patient?.clinicalCardUrl.isNotEmpty == true,
              onDownload: _downloadPdf,
              onTransfer: _transferToComed,
              onOpenComed: _openComed,
              onNew: () => Navigator.of(context).pop(),
            ),
          ),
        ),
      ),
    );
  }
}

class _ReadyHeader extends StatelessWidget {
  const _ReadyHeader({required this.recordLabel, required this.patient});
  final String recordLabel;
  final ComedPatient? patient;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(19),
    decoration: BoxDecoration(
      gradient: const LinearGradient(
        colors: [Color(0xFF087F78), Color(0xFF0A6B78)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      borderRadius: BorderRadius.circular(22),
      boxShadow: const [
        BoxShadow(
          color: Color(0x22087F78),
          blurRadius: 20,
          offset: Offset(0, 8),
        ),
      ],
    ),
    child: Row(
      children: [
        Container(
          width: 54,
          height: 54,
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: .16),
            borderRadius: BorderRadius.circular(17),
          ),
          child: const Icon(
            Icons.description_rounded,
            color: Colors.white,
            size: 29,
          ),
        ),
        const SizedBox(width: 15),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Epikriz hazır',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                patient == null
                    ? '$recordLabel · Doktor kontrolüne hazır'
                    : '${patient!.patientName} · ${patient!.protocolNo.isEmpty ? patient!.visitId : patient!.protocolNo}',
                style: const TextStyle(color: Color(0xFFD5F2EF), height: 1.35),
              ),
            ],
          ),
        ),
        const Icon(
          Icons.check_circle_rounded,
          color: Color(0xFFBDF5E7),
          size: 29,
        ),
      ],
    ),
  );
}

class _ReportActions extends StatelessWidget {
  const _ReportActions({
    required this.downloading,
    required this.transferring,
    required this.transfer,
    required this.canTransfer,
    required this.canOpenComed,
    required this.onDownload,
    required this.onTransfer,
    required this.onOpenComed,
    required this.onNew,
  });

  final bool downloading;
  final bool transferring;
  final ComedTransfer? transfer;
  final bool canTransfer;
  final bool canOpenComed;
  final VoidCallback onDownload;
  final VoidCallback onTransfer;
  final VoidCallback onOpenComed;
  final VoidCallback onNew;

  String get _transferText => switch (transfer?.status) {
    'filling' => 'COMED alanları dolduruluyor…',
    'ready_for_review' => 'COMED’e aktarıldı · Kontrol bekliyor',
    'completed' => 'COMED kaydı tamamlandı',
    'failed' => 'Aktarım başarısız · Tekrar dene',
    'queued' => 'COMED aktarımı sırada…',
    _ => 'COMED’e aktar',
  };

  @override
  Widget build(BuildContext context) => Material(
    color: Theme.of(context).scaffoldBackgroundColor,
    child: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        FilledButton.icon(
          key: const Key('transferToComedButton'),
          onPressed:
              (!canTransfer || transferring || transfer?.status == 'completed')
              ? null
              : onTransfer,
          style: FilledButton.styleFrom(
            backgroundColor: const Color(0xFF3158C8),
          ),
          icon: transferring || {'queued', 'filling'}.contains(transfer?.status)
              ? const SizedBox.square(
                  dimension: 19,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : Icon(
                  transfer?.status == 'completed'
                      ? Icons.check_circle
                      : Icons.send_rounded,
                ),
          label: Text(_transferText),
        ),
        if (transfer?.missingRequired.isNotEmpty == true) ...[
          const SizedBox(height: 7),
          Text(
            '${transfer!.missingRequired.length} zorunlu alan doktor kontrolünde tamamlanacak.',
            textAlign: TextAlign.center,
            style: const TextStyle(color: Color(0xFF8A5B00), fontSize: 12),
          ),
        ],
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                key: const Key('downloadEpikrizButton'),
                onPressed: downloading ? null : onDownload,
                icon: downloading
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.picture_as_pdf_rounded),
                label: Text(downloading ? 'Hazırlanıyor…' : 'Epikriz PDF'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton.icon(
                key: const Key('openComedButton'),
                onPressed: canOpenComed ? onOpenComed : null,
                icon: const Icon(Icons.open_in_new_rounded),
                label: const Text('COMED’de aç'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 7),
        TextButton.icon(
          onPressed: downloading || transferring ? null : onNew,
          icon: const Icon(Icons.add_rounded),
          label: const Text('Yeni görüşme'),
        ),
      ],
    ),
  );
}

class JsonReportView extends StatelessWidget {
  const JsonReportView({super.key, required this.data});
  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final epikriz = data['epikriz'] is Map
        ? Map<String, dynamic>.from(data['epikriz'] as Map)
        : <String, dynamic>{};
    final coaching = data['koclugu'] is Map
        ? Map<String, dynamic>.from(data['koclugu'] as Map)
        : <String, dynamic>{};
    if (epikriz.isEmpty && coaching.isEmpty) {
      return _FallbackReport(data: data);
    }
    final history = Map<String, dynamic>.from(
      epikriz['ozgecmis'] as Map? ?? const {},
    );
    final control = Map<String, dynamic>.from(
      epikriz['kontrol'] as Map? ?? const {},
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _SectionCard(
          icon: Icons.event_note_rounded,
          title: 'Görüşme özeti',
          tint: const Color(0xFFEAF6F4),
          children: [
            _InfoGrid(
              items: [
                ('Görüşme tarihi', epikriz['gorusmeTarihi']),
                ('Doktor', epikriz['doktor']),
                ('Başlangıç', epikriz['baslangic']),
                ('Ağrı skoru', epikriz['agriSkoru']),
              ],
            ),
            _LabeledText(label: 'Şikâyet', value: epikriz['sikayet']),
            _LabeledText(label: 'Öykü', value: epikriz['oyku']),
            _LabeledText(
              label: 'Fizik muayene',
              value: epikriz['fizikMuayene'],
            ),
          ],
        ),
        _SectionCard(
          icon: Icons.person_outline_rounded,
          title: 'Özgeçmiş ve soygeçmiş',
          tint: const Color(0xFFF3EEFF),
          children: [
            _TagGroup(label: 'Kronik hastalıklar', values: history['kronik']),
            _TagGroup(label: 'Ameliyatlar', values: history['ameliyatlar']),
            _TagGroup(label: 'İlaçlar', values: history['ilaclar']),
            _TagGroup(label: 'Alerjiler', values: history['alerji']),
            _TagGroup(label: 'Alışkanlıklar', values: history['aliskanlik']),
            _TagGroup(label: 'Soygeçmiş', values: epikriz['soygecmis']),
          ],
        ),
        _SectionCard(
          icon: Icons.monitor_heart_outlined,
          title: 'Tanı ve klinik plan',
          tint: const Color(0xFFFFF4E5),
          children: [
            _DiagnosisBlock(epikriz: epikriz),
            _TagGroup(label: 'Laboratuvar / tetkik', values: epikriz['lab']),
            _TagGroup(label: 'Tedavi', values: epikriz['tedavi']),
            _LabeledText(label: 'İzlem ve plan', value: epikriz['plan']),
            _LabeledText(
              label: 'Kontrol',
              value: control['onerildi'] == true
                  ? '${_display(control['zaman'])}\n${_display(control['not'])}'
                  : control['onerildi'] == false
                  ? 'Kontrol önerilmedi.'
                  : control['not'],
            ),
          ],
        ),
        _CommunicationSection(coaching: coaching),
      ],
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({
    required this.icon,
    required this.title,
    required this.tint,
    required this.children,
  });
  final IconData icon;
  final String title;
  final Color tint;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 14),
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: tint,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: klinotNavy, size: 21),
              ),
              const SizedBox(width: 11),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                    color: klinotNavy,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ...children,
        ],
      ),
    ),
  );
}

class _InfoGrid extends StatelessWidget {
  const _InfoGrid({required this.items});
  final List<(String, dynamic)> items;

  @override
  Widget build(BuildContext context) => Wrap(
    spacing: 9,
    runSpacing: 9,
    children: items
        .map(
          (item) => Container(
            width: 155,
            padding: const EdgeInsets.all(11),
            decoration: BoxDecoration(
              color: klinotCanvas,
              borderRadius: BorderRadius.circular(13),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.$1,
                  style: const TextStyle(
                    color: Color(0xFF60777D),
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _display(item.$2),
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
        )
        .toList(),
  );
}

class _LabeledText extends StatelessWidget {
  const _LabeledText({required this.label, required this.value});
  final String label;
  final dynamic value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: klinotTeal,
            fontSize: 12,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 5),
        Text(
          _display(value),
          style: const TextStyle(height: 1.5, fontSize: 15),
        ),
      ],
    ),
  );
}

class _TagGroup extends StatelessWidget {
  const _TagGroup({required this.label, required this.values});
  final String label;
  final dynamic values;

  @override
  Widget build(BuildContext context) {
    final items = values is List
        ? List<dynamic>.from(values as List)
        : const [];
    return Padding(
      padding: const EdgeInsets.only(bottom: 13),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              color: Color(0xFF60777D),
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 7),
          items.isEmpty
              ? const Text(
                  'Belirtilmedi',
                  style: TextStyle(
                    color: Color(0xFF91A0A4),
                    fontStyle: FontStyle.italic,
                  ),
                )
              : Wrap(
                  spacing: 7,
                  runSpacing: 7,
                  children: items
                      .map(
                        (item) => Chip(
                          label: Text(_display(item)),
                          visualDensity: VisualDensity.compact,
                        ),
                      )
                      .toList(),
                ),
        ],
      ),
    );
  }
}

class _DiagnosisBlock extends StatelessWidget {
  const _DiagnosisBlock({required this.epikriz});
  final Map<String, dynamic> epikriz;

  @override
  Widget build(BuildContext context) {
    final icd = (epikriz['icd'] as List? ?? const [])
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFAF0),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: const Color(0xFFF1DFC0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _LabeledText(label: 'Ön tanı', value: epikriz['onTani']),
          _LabeledText(label: 'Kesin tanı', value: epikriz['kesinTani']),
          if (icd.isNotEmpty) ...[
            const SizedBox(height: 11),
            Wrap(
              spacing: 7,
              runSpacing: 7,
              children: icd
                  .map(
                    (item) => Chip(
                      avatar: const Icon(Icons.label_outline_rounded, size: 17),
                      label: Text(
                        '${item['kod'] ?? ''} · ${item['aciklama'] ?? ''}',
                      ),
                    ),
                  )
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }
}

class _CommunicationSection extends StatelessWidget {
  const _CommunicationSection({required this.coaching});
  final Map<String, dynamic> coaching;

  @override
  Widget build(BuildContext context) {
    final strengths = coaching['guclu'] as List? ?? const [];
    final suggestions = coaching['oneriler'] as List? ?? const [];
    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      color: const Color(0xFFF8F9FF),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Row(
              children: [
                CircleAvatar(
                  backgroundColor: Color(0xFFE8EAFE),
                  foregroundColor: Color(0xFF4E5EC7),
                  child: Icon(Icons.forum_outlined),
                ),
                SizedBox(width: 11),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'İletişim önerileri',
                        style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w800,
                          color: klinotNavy,
                        ),
                      ),
                      Text(
                        'Görüşmeden alınan somut ve uygulanabilir notlar',
                        style: TextStyle(
                          color: Color(0xFF60777D),
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (strengths.isNotEmpty) ...[
              const SizedBox(height: 16),
              Wrap(
                spacing: 7,
                runSpacing: 7,
                children: strengths
                    .map(
                      (item) => Chip(
                        avatar: const Icon(
                          Icons.check_circle,
                          color: klinotTeal,
                          size: 18,
                        ),
                        label: Text(_display(item)),
                        backgroundColor: const Color(0xFFE8F6F3),
                      ),
                    )
                    .toList(),
              ),
            ],
            const SizedBox(height: 14),
            if (suggestions.isEmpty)
              const Text(
                'Bu görüşme için ek öneri yok.',
                style: TextStyle(color: Color(0xFF60777D)),
              )
            else
              ...suggestions.indexed.map((entry) {
                final item = Map<String, dynamic>.from(entry.$2 as Map);
                return Container(
                  margin: const EdgeInsets.only(bottom: 10),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(15),
                    border: Border.all(color: const Color(0xFFDDE1F4)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          CircleAvatar(
                            radius: 13,
                            backgroundColor: const Color(0xFFE8EAFE),
                            child: Text(
                              '${entry.$1 + 1}',
                              style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w800,
                                color: Color(0xFF4E5EC7),
                              ),
                            ),
                          ),
                          const SizedBox(width: 9),
                          Expanded(
                            child: Text(
                              _display(item['an']),
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                height: 1.4,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(11),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFFFAE8),
                          borderRadius: BorderRadius.circular(11),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Icon(
                              Icons.lightbulb_outline_rounded,
                              color: Color(0xFFB47A00),
                              size: 20,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _display(item['oneri']),
                                style: const TextStyle(height: 1.45),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              }),
          ],
        ),
      ),
    );
  }
}

class _FallbackReport extends StatelessWidget {
  const _FallbackReport({required this.data});
  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: data.entries
            .map(
              (entry) =>
                  _LabeledText(label: _humanize(entry.key), value: entry.value),
            )
            .toList(),
      ),
    ),
  );
}

String _humanize(String value) {
  const labels = {
    'epikriz': 'Epikriz',
    'oneriler': 'Öneriler',
    'koclugu': 'İletişim koçluğu',
    'gorusmeTarihi': 'Görüşme tarihi',
    'onTani': 'Ön tanı',
    'kesinTani': 'Kesin tanı',
    'fizikMuayene': 'Fizik muayene',
    'agriSkoru': 'Ağrı skoru',
  };
  if (labels[value] != null) return labels[value]!;
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

String _display(dynamic value) {
  if (value == null || value.toString().trim().isEmpty) return 'Belirtilmedi';
  if (value is List) {
    return value.isEmpty ? 'Belirtilmedi' : value.map(_display).join(' · ');
  }
  if (value is Map) {
    return value.entries
        .map(
          (entry) =>
              '${_humanize(entry.key.toString())}: ${_display(entry.value)}',
        )
        .join('\n');
  }
  final text = value.toString();
  return text.toLowerCase() == 'belirtilmedi' ? 'Belirtilmedi' : text;
}
