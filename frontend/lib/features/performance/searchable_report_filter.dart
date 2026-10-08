import 'package:flutter/material.dart';
import 'package:frontend/core/theme/app_theme.dart';

/// Searches the complete, permission-scoped option list without changing reports
/// until the trainer selects a result. Results are built lazily.
class SearchableReportFilter extends StatelessWidget {
  final String label;
  final String? value;
  final Map<String, String> items;
  final IconData icon;
  final double width;
  final ValueChanged<String?> onChanged;
  final Widget Function(Widget)? guard;
  final bool allowAll;
  final bool enabled;
  const SearchableReportFilter(
      {super.key,
      required this.label,
      required this.value,
      required this.items,
      required this.icon,
      required this.width,
      required this.onChanged,
      this.guard,
      this.allowAll = true,
      this.enabled = true});

  @override
  Widget build(BuildContext context) {
    final selected = value == null
        ? (allowAll ? 'All' : 'Choose ${label.toLowerCase()}')
        : items[value] ?? 'Selected $label';
    return SizedBox(
        width: width,
        child: Tooltip(
            message: selected,
            child: OutlinedButton(
                style: OutlinedButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: AppTheme.primaryBlue,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 14, vertical: 13),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                    side: const BorderSide(color: Color(0xFFD2E0F0))),
                onPressed: !enabled
                    ? null
                    : () async {
                        final picked = await showDialog<_Selection>(
                            context: context,
                            builder: (_) {
                              final dialog = _FilterDialog(
                                  label: label,
                                  value: value,
                                  items: items,
                                  allowAll: allowAll);
                              return guard?.call(dialog) ?? dialog;
                            });
                        if (context.mounted && picked != null) {
                          onChanged(picked.value);
                        }
                      },
                child: Row(children: [
                  Icon(icon, size: 19),
                  const SizedBox(width: 10),
                  Expanded(
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                        Text(label,
                            style: const TextStyle(
                                fontSize: 11, color: AppTheme.textSecondary)),
                        Text(selected,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w700))
                      ])),
                  const Icon(Icons.expand_more, size: 20)
                ]))));
  }
}

class _Selection {
  final String? value;
  const _Selection(this.value);
}

class _FilterDialog extends StatefulWidget {
  final String label;
  final String? value;
  final Map<String, String> items;
  final bool allowAll;
  const _FilterDialog(
      {required this.label,
      required this.value,
      required this.items,
      required this.allowAll});
  @override
  State<_FilterDialog> createState() => _FilterDialogState();
}

class _FilterDialogState extends State<_FilterDialog> {
  final search = TextEditingController();
  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final words = search.text.trim().toLowerCase().split(RegExp(r'\s+'));
    final results = widget.items.entries
        .where((item) => words.every(
            (word) => '${item.value} ${item.key}'.toLowerCase().contains(word)))
        .toList();
    return AlertDialog(
        title: Text('Select ${widget.label.toLowerCase()}'),
        content: SizedBox(
            width: 480,
            height: 420,
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              TextField(
                  controller: search,
                  autofocus: true,
                  onChanged: (_) => setState(() {}),
                  decoration: InputDecoration(
                      hintText: 'Search ${widget.label.toLowerCase()}',
                      prefixIcon: const Icon(Icons.search),
                      suffixIcon: search.text.isEmpty
                          ? null
                          : IconButton(
                              tooltip: 'Clear search',
                              icon: const Icon(Icons.close),
                              onPressed: () => setState(search.clear)),
                      border: const OutlineInputBorder())),
              const SizedBox(height: 10),
              Text('${results.length} matching options',
                  style: const TextStyle(
                      fontSize: 12, color: AppTheme.textSecondary)),
              if (widget.allowAll)
                ListTile(
                    title: Text('All ${widget.label.toLowerCase()} options'),
                    trailing: widget.value == null
                        ? const Icon(Icons.check, color: AppTheme.primaryBlue)
                        : null,
                    onTap: () =>
                        Navigator.pop(context, const _Selection(null))),
              const Divider(height: 1),
              Expanded(
                  child: results.isEmpty
                      ? const Center(child: Text('No matching options.'))
                      : ListView.builder(
                          itemCount: results.length,
                          itemBuilder: (_, index) {
                            final item = results[index];
                            return ListTile(
                                title: Text(item.value),
                                subtitle: widget.label == 'Course'
                                    ? Text(item.key,
                                        style: const TextStyle(
                                            fontSize: 11,
                                            color: AppTheme.textSecondary))
                                    : null,
                                trailing: widget.value == item.key
                                    ? const Icon(Icons.check,
                                        color: AppTheme.primaryBlue)
                                    : null,
                                onTap: () => Navigator.pop(
                                    context, _Selection(item.key)));
                          })),
            ])),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'))
        ]);
  }
}
