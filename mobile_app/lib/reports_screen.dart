import 'package:flutter/material.dart';

import 'models.dart';
import 'theme.dart';

class ReportsScreen extends StatelessWidget {
  const ReportsScreen({super.key, required this.result});
  final AnalysisResult result;

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: Text(
            result.recordId == null
                ? 'Hazırlanan raporlar'
                : 'Kayıt #${result.recordId}',
          ),
          bottom: const TabBar(
            isScrollable: true,
            tabAlignment: TabAlignment.start,
            tabs: [
              Tab(
                icon: Icon(Icons.person_outline_rounded),
                text: 'Hasta özeti',
              ),
              Tab(
                icon: Icon(Icons.description_outlined),
                text: 'Doktor epikrizi',
              ),
              Tab(icon: Icon(Icons.shield_outlined), text: 'Yönetim'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            JsonReportView(data: result.patient),
            JsonReportView(data: result.doctor),
            JsonReportView(data: result.management),
          ],
        ),
        bottomNavigationBar: SafeArea(
          minimum: const EdgeInsets.all(16),
          child: FilledButton.icon(
            onPressed: () => Navigator.of(context).pop(),
            icon: const Icon(Icons.add_rounded),
            label: const Text('Yeni görüşme'),
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
          child: Center(child: Text('Bu raporda gösterilecek veri yok.')),
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
