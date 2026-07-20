import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../models/models.dart';
import '../providers/providers.dart';
import '../theme.dart';

class PerformancePortal extends ConsumerWidget {
  const PerformancePortal({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(performanceProvider);
    final dashboard = state.dashboard;

    return Container(
      color: const Color(0xFFF7F8FA),
      child: RefreshIndicator(
        onRefresh: () => ref.read(performanceProvider.notifier).fetch(),
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            _Header(isLoading: state.isLoading),
            const SizedBox(height: 16),
            _Filters(state: state),
            if (state.error != null) ...[
              const SizedBox(height: 16),
              _Notice(text: state.error!, isError: true),
            ],
            const SizedBox(height: 16),
            if (state.isLoading && dashboard.rows.isEmpty)
              const LinearProgressIndicator()
            else ...[
              _SummaryGrid(summary: dashboard.summary),
              const SizedBox(height: 16),
              _PerformanceTable(rows: dashboard.rows),
            ],
          ],
        ),
      ),
    );
  }
}

class _Header extends ConsumerWidget {
  final bool isLoading;

  const _Header({required this.isLoading});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Course Performance',
                style: GoogleFonts.inter(
                  fontSize: 26,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textBlack,
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                'Track employee progress, completion, overdue courses, and quiz attempts.',
                style: TextStyle(color: Color(0xFF667085)),
              ),
            ],
          ),
        ),
        FilledButton.icon(
          onPressed:
              isLoading ? null : () => ref.read(performanceProvider.notifier).fetch(),
          icon: const Icon(Icons.refresh, size: 18),
          label: const Text('Refresh'),
          style: FilledButton.styleFrom(
            backgroundColor: AppTheme.primaryBlue,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          ),
        ),
      ],
    );
  }
}

class _Filters extends ConsumerWidget {
  final PerformanceState state;

  const _Filters({required this.state});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dashboard = state.dashboard;
    final filter = state.filter;
    return _Panel(
      child: Wrap(
        spacing: 12,
        runSpacing: 12,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          _FilterDropdown(
            width: 230,
            label: 'Course',
            value: filter.courseId,
            items: {
              for (final course in dashboard.options.courses) course.id: course.title,
            },
            onChanged: (value) => ref.read(performanceProvider.notifier).updateFilter(
                  filter.copyWith(courseId: value, clearCourse: value == null),
                ),
          ),
          _FilterDropdown(
            width: 230,
            label: 'Employee',
            value: filter.employeeId,
            items: {
              for (final employee in dashboard.options.employees)
                employee.id: '${employee.name} (${employee.employeeCode})',
            },
            onChanged: (value) => ref.read(performanceProvider.notifier).updateFilter(
                  filter.copyWith(employeeId: value, clearEmployee: value == null),
                ),
          ),
          _FilterDropdown(
            width: 190,
            label: 'Department',
            value: filter.department,
            items: {for (final department in dashboard.options.departments) department: department},
            onChanged: (value) => ref.read(performanceProvider.notifier).updateFilter(
                  filter.copyWith(department: value, clearDepartment: value == null),
                ),
          ),
          _FilterDropdown(
            width: 180,
            label: 'Role',
            value: filter.role,
            items: {for (final role in dashboard.options.roles) role: role},
            onChanged: (value) => ref.read(performanceProvider.notifier).updateFilter(
                  filter.copyWith(role: value, clearRole: value == null),
                ),
          ),
          _FilterDropdown(
            width: 170,
            label: 'Status',
            value: filter.status,
            items: {
              for (final status in dashboard.options.statuses) status.key: status.label,
            },
            onChanged: (value) => ref.read(performanceProvider.notifier).updateFilter(
                  filter.copyWith(status: value, clearStatus: value == null),
                ),
          ),
          _JoinedDaysFilter(filter: filter),
          OutlinedButton.icon(
            onPressed: () => ref.read(performanceProvider.notifier).clearFilters(),
            icon: const Icon(Icons.filter_alt_off_outlined, size: 18),
            label: const Text('Clear'),
          ),
        ],
      ),
    );
  }
}

class _JoinedDaysFilter extends ConsumerStatefulWidget {
  final PerformanceFilter filter;

  const _JoinedDaysFilter({required this.filter});

  @override
  ConsumerState<_JoinedDaysFilter> createState() => _JoinedDaysFilterState();
}

class _JoinedDaysFilterState extends ConsumerState<_JoinedDaysFilter> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(
      text: widget.filter.joinedLessThanDaysAgo?.toString() ?? '',
    );
  }

  @override
  void didUpdateWidget(covariant _JoinedDaysFilter oldWidget) {
    super.didUpdateWidget(oldWidget);
    final next = widget.filter.joinedLessThanDaysAgo?.toString() ?? '';
    if (_controller.text != next) {
      _controller.text = next;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 210,
      child: TextField(
        controller: _controller,
        keyboardType: TextInputType.number,
        inputFormatters: [FilteringTextInputFormatter.digitsOnly],
        decoration: const InputDecoration(
          labelText: 'Joined less than days',
          isDense: true,
          border: OutlineInputBorder(),
        ),
        onChanged: _apply,
      ),
    );
  }

  void _apply(String value) {
    final parsed = int.tryParse(value);
    ref.read(performanceProvider.notifier).updateFilter(
          widget.filter.copyWith(
            joinedLessThanDaysAgo: parsed,
            clearJoined: parsed == null,
          ),
        );
  }
}

class _FilterDropdown extends StatelessWidget {
  final double width;
  final String label;
  final String? value;
  final Map<String, String> items;
  final ValueChanged<String?> onChanged;

  const _FilterDropdown({
    required this.width,
    required this.label,
    required this.value,
    required this.items,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: DropdownButtonFormField<String>(
        value: value ?? '',
        isExpanded: true,
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          border: const OutlineInputBorder(),
        ),
        items: [
          const DropdownMenuItem(value: '', child: Text('All')),
          for (final entry in items.entries)
            DropdownMenuItem(
              value: entry.key,
              child: Text(entry.value, overflow: TextOverflow.ellipsis),
            ),
        ],
        onChanged: (next) => onChanged(next == '' ? null : next),
      ),
    );
  }
}

class _SummaryGrid extends StatelessWidget {
  final PerformanceSummary summary;

  const _SummaryGrid({required this.summary});

  @override
  Widget build(BuildContext context) {
    final cards = [
      _Metric('Assigned', summary.assigned.toString(), AppTheme.primaryBlue),
      _Metric('Pending', summary.pending.toString(), AppTheme.gray),
      _Metric('Started', summary.started.toString(), AppTheme.accentBlue),
      _Metric('Completed', summary.completed.toString(), AppTheme.accentGreen),
      _Metric('Overdue', summary.overdue.toString(), AppTheme.accentRed),
      _Metric('Completion', '${summary.completionRate}%', AppTheme.accentCyan),
      _Metric('Avg attempts', summary.averageAttempts.toStringAsFixed(1), const Color(0xFF7047EB)),
    ];
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth >= 1200
            ? 4
            : constraints.maxWidth >= 760
                ? 2
                : 1;
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: cards.length,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            mainAxisExtent: 96,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
          ),
          itemBuilder: (context, index) => _MetricCard(metric: cards[index]),
        );
      },
    );
  }
}

class _Metric {
  final String label;
  final String value;
  final Color color;

  const _Metric(this.label, this.value, this.color);
}

class _MetricCard extends StatelessWidget {
  final _Metric metric;

  const _MetricCard({required this.metric});

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Row(
        children: [
          Container(width: 5, height: 48, color: metric.color),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(metric.label, style: const TextStyle(color: Color(0xFF667085))),
                const SizedBox(height: 4),
                Text(
                  metric.value,
                  style: GoogleFonts.inter(
                    fontSize: 26,
                    fontWeight: FontWeight.w800,
                    color: AppTheme.textBlack,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PerformanceTable extends StatelessWidget {
  final List<PerformanceRow> rows;

  const _PerformanceTable({required this.rows});

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Employee detail',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                ),
              ),
              Text('${rows.length} rows', style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
          const SizedBox(height: 12),
          if (rows.isEmpty)
            const SizedBox(height: 180, child: Center(child: Text('No matching records')))
          else
            for (final row in rows) _PerformanceRowTile(row: row),
        ],
      ),
    );
  }
}

class _PerformanceRowTile extends StatelessWidget {
  final PerformanceRow row;

  const _PerformanceRowTile({required this.row});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFFE6E9EF)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
        title: Wrap(
          spacing: 16,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            _Cell(width: 220, top: row.employee.name, bottom: row.employee.department),
            _Cell(width: 260, top: row.courseTitle, bottom: row.employee.role),
            _StatusChip(label: row.statusLabel, statusKey: row.statusKey),
            _Cell(
              width: 130,
              top: '${row.completedModules}/${row.totalModules} modules',
              bottom: '${row.completionPercent}% complete',
            ),
            _Cell(
              width: 110,
              top: '${row.totalAttempts} attempts',
              bottom: _scoreText(row.bestScore),
            ),
            _Cell(width: 130, top: _shortDate(row.deadline), bottom: 'Due date'),
          ],
        ),
        children: [
          const Divider(height: 1),
          const SizedBox(height: 12),
          for (final module in row.modules)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Module ${module.moduleNumber}: ${module.title}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  _MiniState(label: 'Video', active: module.videoWatched),
                  const SizedBox(width: 8),
                  _MiniState(label: 'Quiz', active: module.quizPassed),
                  const SizedBox(width: 12),
                  SizedBox(
                    width: 92,
                    child: Text(
                      '${module.attemptCount} attempts',
                      textAlign: TextAlign.right,
                      style: const TextStyle(color: Color(0xFF667085)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  SizedBox(
                    width: 72,
                    child: Text(
                      _scoreText(module.quizScore ?? module.lastScore),
                      textAlign: TextAlign.right,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _Cell extends StatelessWidget {
  final double width;
  final String top;
  final String bottom;

  const _Cell({required this.width, required this.top, required this.bottom});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            top,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 2),
          Text(
            bottom,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  final String label;
  final String statusKey;

  const _StatusChip({required this.label, required this.statusKey});

  @override
  Widget build(BuildContext context) {
    final color = switch (statusKey) {
      'completed' => AppTheme.accentGreen,
      'overdue' => AppTheme.accentRed,
      'started' => AppTheme.accentBlue,
      _ => AppTheme.gray,
    };
    return Container(
      width: 96,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        textAlign: TextAlign.center,
        style: TextStyle(color: color, fontWeight: FontWeight.w800),
      ),
    );
  }
}

class _MiniState extends StatelessWidget {
  final String label;
  final bool active;

  const _MiniState({required this.label, required this.active});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          active ? Icons.check_circle : Icons.radio_button_unchecked,
          size: 16,
          color: active ? AppTheme.accentGreen : AppTheme.gray,
        ),
        const SizedBox(width: 4),
        Text(label),
      ],
    );
  }
}

class _Panel extends StatelessWidget {
  final Widget child;

  const _Panel({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: const Color(0xFFE6E9EF)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: child,
    );
  }
}

class _Notice extends StatelessWidget {
  final String text;
  final bool isError;

  const _Notice({required this.text, required this.isError});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isError ? const Color(0xFFFFF1F3) : const Color(0xFFEFFAF3),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isError ? const Color(0xFFFFCCD5) : const Color(0xFFB7E4C7),
        ),
      ),
      child: Text(
        text,
        style: TextStyle(color: isError ? const Color(0xFFA11D33) : const Color(0xFF087443)),
      ),
    );
  }
}

String _shortDate(String? value) {
  if (value == null || value.isEmpty) return '-';
  final date = DateTime.tryParse(value);
  if (date == null) return '-';
  return '${date.day}/${date.month}/${date.year}';
}

String _scoreText(double? score) {
  if (score == null) return 'No score';
  if (score <= 1) return '${(score * 100).round()}%';
  return '${score.round()}%';
}
