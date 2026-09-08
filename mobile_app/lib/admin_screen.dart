import 'package:flutter/material.dart';

import 'api_client.dart';
import 'models.dart';
import 'reports_screen.dart';
import 'theme.dart';

class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key, required this.api, required this.session});
  final KlinotApi api;
  final UserSession session;

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  late Future<AdminRecords> _future;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  void _refresh() {
    _future = widget.api.records(widget.session.token);
  }

  Future<void> _open(RecordSummary summary) async {
    try {
      final data = await widget.api.record(widget.session.token, summary.id);
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => DefaultTabController(
            length: 4,
            child: Scaffold(
              appBar: AppBar(
                title: Text('Kayıt #${summary.id}'),
                bottom: const TabBar(
                  isScrollable: true,
                  tabAlignment: TabAlignment.start,
                  tabs: [
                    Tab(text: 'Hasta'),
                    Tab(text: 'Epikriz'),
                    Tab(text: 'Yönetim'),
                    Tab(text: 'Metin'),
                  ],
                ),
              ),
              body: TabBarView(
                children: [
                  JsonReportView(
                    data: Map<String, dynamic>.from(
                      data['hasta'] as Map? ?? const {},
                    ),
                  ),
                  JsonReportView(
                    data: Map<String, dynamic>.from(
                      data['doktor'] as Map? ?? const {},
                    ),
                  ),
                  JsonReportView(
                    data: Map<String, dynamic>.from(
                      data['yonetim'] as Map? ?? const {},
                    ),
                  ),
                  SingleChildScrollView(
                    padding: const EdgeInsets.all(20),
                    child: SelectableText(
                      data['transkript']?.toString() ?? '',
                      style: const TextStyle(fontSize: 16, height: 1.55),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.toString())));
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async {
        setState(_refresh);
        await _future;
      },
      child: FutureBuilder<AdminRecords>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return ListView(
              padding: const EdgeInsets.all(28),
              children: [
                const Icon(
                  Icons.cloud_off_rounded,
                  size: 50,
                  color: Color(0xFF71868B),
                ),
                const SizedBox(height: 14),
                Text(snapshot.error.toString(), textAlign: TextAlign.center),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () => setState(_refresh),
                  child: const Text('Tekrar dene'),
                ),
              ],
            );
          }
          final data = snapshot.data!;
          return ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(18, 12, 18, 32),
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Yönetim paneli',
                      style: Theme.of(context).textTheme.headlineSmall
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                  ),
                  IconButton.filledTonal(
                    onPressed: () => setState(_refresh),
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: _StatCard(
                      label: 'Kayıt',
                      value: '${data.stats['kayit'] ?? 0}',
                      icon: Icons.folder_copy_outlined,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _StatCard(
                      label: 'Token',
                      value: '${data.stats['token'] ?? 0}',
                      icon: Icons.data_usage_rounded,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _StatCard(
                      label: 'Maliyet',
                      value: '\$${data.stats['cost_usd'] ?? 0}',
                      icon: Icons.payments_outlined,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              const Text(
                'Son görüşmeler',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 10),
              for (final record in data.records)
                Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 8,
                    ),
                    leading: CircleAvatar(
                      backgroundColor: record.source == 'mobile'
                          ? const Color(0xFFE5F5F3)
                          : const Color(0xFFEDF1F4),
                      child: Icon(
                        record.source == 'mobile'
                            ? Icons.phone_iphone_rounded
                            : Icons.computer_rounded,
                        color: klinotTeal,
                      ),
                    ),
                    title: Text(
                      record.summary,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    subtitle: Text(
                      '#${record.id} · ${record.createdAt.replaceFirst('T', ' ')}${record.hasAudio ? ' · Ses var' : ''}',
                    ),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () => _open(record),
                  ),
                ),
              if (data.records.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(30),
                  child: Center(child: Text('Henüz kayıt yok.')),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.label,
    required this.value,
    required this.icon,
  });
  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 20, color: klinotTeal),
        const SizedBox(height: 8),
        FittedBox(
          child: Text(
            value,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
          ),
        ),
        Text(
          label,
          style: const TextStyle(fontSize: 11, color: Color(0xFF60777D)),
        ),
      ],
    ),
  );
}
