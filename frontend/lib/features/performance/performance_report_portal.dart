// This trainer application is deployed as Flutter Web; CSV downloads use the browser.
// ignore_for_file: avoid_web_libraries_in_flutter
import 'dart:html' as html;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:frontend/core/theme/app_theme.dart';
import 'package:frontend/features/performance/assignment_detail_dialog.dart';
import 'package:frontend/state/trainer_providers.dart';

class PerformanceReportPortal extends ConsumerStatefulWidget {
  const PerformanceReportPortal({super.key});

  @override
  ConsumerState<PerformanceReportPortal> createState() =>
      _PerformanceReportPortalState();
}

class _PerformanceReportPortalState
    extends ConsumerState<PerformanceReportPortal> {
  final search = TextEditingController();
  final joined = TextEditingController();

  @override
  void dispose() {
    search.dispose();
    joined.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(performanceReportProvider);
    final report = ref.read(performanceReportProvider.notifier);
    return Container(
      color: const Color(0xFFF5F8FC),
      child: RefreshIndicator(
        onRefresh: report.refresh,
        child: ListView(padding: const EdgeInsets.all(24), children: [
          Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 12,
              runSpacing: 10,
              children: [
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Performance',
                      style:
                          TextStyle(fontSize: 27, fontWeight: FontWeight.w800)),
                  const Text(
                      'Learning outcomes and assignments that need attention.',
                      style: TextStyle(color: AppTheme.textSecondary)),
                  if (state.overview['generated_at'] != null)
                    Text('Updated ${_dateTime(state.overview['generated_at'])}',
                        style: const TextStyle(
                            fontSize: 12, color: AppTheme.textSecondary)),
                ]),
                Wrap(spacing: 8, children: [
                  OutlinedButton.icon(
                      onPressed: state.isLoading ? null : report.refresh,
                      icon: const Icon(Icons.refresh, size: 18),
                      label: const Text('Refresh')),
                  OutlinedButton.icon(
                      onPressed: _export,
                      icon: const Icon(Icons.download_outlined, size: 18),
                      label: const Text('Export CSV')),
                ]),
              ]),
          const SizedBox(height: 16),
          _ViewTabs(selected: state.view, onSelected: report.setView),
          const SizedBox(height: 16),
          _filters(state),
          if (state.isLoading)
            const Padding(
                padding: EdgeInsets.only(top: 12),
                child: LinearProgressIndicator()),
          if (state.error != null)
            Padding(
                padding: const EdgeInsets.only(top: 12),
                child: _Box(
                    child: Text(state.error!,
                        style: const TextStyle(color: AppTheme.accentRed)))),
          const SizedBox(height: 16),
          if (state.view == 0) _overview(state),
          if (state.view == 1) _courses(state),
          if (state.view == 2) _learners(state),
        ]),
      ),
    );
  }

  Widget _filters(PerformanceReportState state) {
    final options = state.options;
    final filter = state.filter;
    final report = ref.read(performanceReportProvider.notifier);
    return _Box(
        child: Wrap(
            spacing: 10,
            runSpacing: 10,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
          _Drop(
              label: 'Course',
              value: filter.courseId,
              width: 210,
              items: {
                for (final value in _list(options['courses']))
                  _map(value)['course_id'].toString():
                      _map(value)['course_name'].toString()
              },
              onChanged: (value) => report.setFilter(filter.copyWith(
                  courseId: value, clearCourse: value == null))),
          _Drop(
              label: 'Employee',
              value: filter.employeeId,
              width: 190,
              items: {
                for (final value in _list(options['employees']))
                  _map(value)['employee_id'].toString():
                      _map(value)['name'].toString()
              },
              onChanged: (value) => report.setFilter(filter.copyWith(
                  employeeId: value, clearEmployee: value == null))),
          _Drop(
              label: 'Department',
              value: filter.department,
              width: 180,
              items: {
                for (final value in _list(options['departments']))
                  value.toString(): value.toString()
              },
              onChanged: (value) => report.setFilter(filter.copyWith(
                  department: value, clearDepartment: value == null))),
          _Drop(
              label: 'Mailing list',
              value: filter.mailingList,
              width: 180,
              items: {
                for (final value in _list(options['mailing_lists']))
                  value.toString(): value.toString()
              },
              onChanged: (value) => report.setFilter(filter.copyWith(
                  mailingList: value, clearMailingList: value == null))),
          SizedBox(
              width: 175,
              child: TextField(
                  controller: joined,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                      labelText: 'Joined within days',
                      isDense: true,
                      border: OutlineInputBorder()),
                  onSubmitted: (text) {
                    final days = int.tryParse(text);
                    report.setFilter(filter.copyWith(
                        joinedLessThanDaysAgo: days,
                        clearJoined: days == null));
                  })),
          TextButton.icon(
              onPressed: () {
                joined.clear();
                search.clear();
                report.clearFilters();
              },
              icon: const Icon(Icons.filter_alt_off_outlined),
              label: const Text('Clear')),
        ]));
  }

  Widget _overview(PerformanceReportState state) {
    final data = state.overview;
    final summary = _map(data['summary']);
    final breakdowns = _map(data['breakdowns']);
    final report = ref.read(performanceReportProvider.notifier);
    if (data.isEmpty && !state.isLoading) {
      return const _Box(child: Text('No performance data available.'));
    }
    final metrics = [
      (
        'Assigned',
        '${summary['assigned'] ?? 0}',
        '${summary['unique_learners'] ?? 0} unique learners',
        null,
        AppTheme.primaryBlue,
        Icons.assignment_outlined
      ),
      (
        'Completed',
        '${summary['completion_rate'] ?? 0}%',
        '${summary['completed'] ?? 0} assignments',
        'completed',
        AppTheme.accentGreen,
        Icons.task_alt_rounded
      ),
      (
        'Due soon',
        '${summary['due_soon'] ?? 0}',
        'Within ${data['due_soon_days'] ?? 2} days',
        'due_soon',
        AppTheme.accentOrange,
        Icons.schedule_rounded
      ),
      (
        'Overdue',
        '${summary['overdue'] ?? 0}',
        'Incomplete assignments',
        'overdue',
        AppTheme.accentRed,
        Icons.error_outline_rounded
      ),
      (
        'On-time compliance',
        summary['on_time_compliance'] == null
            ? '—'
            : '${summary['on_time_compliance']}%',
        '${summary['on_time_denominator'] ?? 0} deadlines passed',
        null,
        AppTheme.accentBlue,
        Icons.verified_outlined
      ),
      (
        'Average quiz score',
        summary['average_score'] == null ? '—' : '${summary['average_score']}%',
        '${summary['scored_modules'] ?? 0} scored modules',
        null,
        const Color(0xFF7047EB),
        Icons.bar_chart_rounded
      ),
    ];
    final watchlist = _list(data['watchlist']);
    final courses = _list(breakdowns['courses']);
    final departments = _list(breakdowns['departments']);
    final mailingLists = _list(breakdowns['mailing_lists']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      LayoutBuilder(builder: (context, constraints) {
        final columns = constraints.maxWidth >= 1260
            ? 6
            : constraints.maxWidth >= 850
                ? 3
                : constraints.maxWidth >= 350
                    ? 2
                    : 1;
        final cardWidth = columns == 1
            ? constraints.maxWidth
            : (constraints.maxWidth - 12 * (columns - 1)) / columns;
        return Wrap(spacing: 12, runSpacing: 12, children: [
          for (final item in metrics)
            SizedBox(
                width: cardWidth,
                child: _KpiCard(
                  label: item.$1,
                  value: item.$2,
                  caption: item.$3,
                  color: item.$5,
                  icon: item.$6,
                  compact: cardWidth < 220,
                  onTap:
                      item.$4 == null ? null : () => report.setStatus(item.$4),
                )),
        ]);
      }),
      const SizedBox(height: 16),
      LayoutBuilder(builder: (context, constraints) {
        final attention = _Box(
            child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SectionHeader(
              title: 'Needs attention',
              subtitle: 'Start with the learners who need a follow-up.',
                  onViewAll: () => report.setStatus(null),
            ),
            LayoutBuilder(builder: (context, inner) {
              final cardWidth = inner.maxWidth >= 600
                  ? (inner.maxWidth - 16) / 3
                  : inner.maxWidth;
              return Wrap(spacing: 8, runSpacing: 8, children: [
                _AttentionCard(
                  width: cardWidth,
                  label: 'Overdue',
                  count: summary['overdue'],
                  detail: 'Incomplete past due date',
                  icon: Icons.error_outline_rounded,
                  color: AppTheme.accentRed,
                  onTap: () => report.setStatus('overdue'),
                ),
                _AttentionCard(
                  width: cardWidth,
                  label: 'Due soon',
                  count: summary['due_soon'],
                  detail: 'Within ${data['due_soon_days'] ?? 2} days',
                  icon: Icons.schedule_rounded,
                  color: AppTheme.accentOrange,
                  onTap: () => report.setStatus('due_soon'),
                ),
                _AttentionCard(
                  width: cardWidth,
                  label: 'No learner activity',
                  count: summary['inactive'],
                  detail: 'For ${data['inactive_days'] ?? 14} days',
                  icon: Icons.person_off_outlined,
                  color: AppTheme.accentBlue,
                  onTap: () => report.setStatus('inactive'),
                ),
              ]);
            }),
            const SizedBox(height: 8),
            _AttentionLink(
              label: 'Repeated quiz failures',
              count: summary['repeated_failures'],
              onTap: () => report.setStatus('repeated_failures'),
            ),
          ],
        ));
        final watchlistPanel = _Box(
            child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SectionHeader(
              title: 'Assignment watchlist',
              subtitle: 'The most urgent assignments in this scope.',
                  onViewAll: () => report.setStatus(null),
            ),
            if (watchlist.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 32),
                child: Center(
                    child: Text('No assignments currently need attention.')),
              ),
            if (watchlist.isNotEmpty) const _WatchlistHeader(),
            for (final value in watchlist.take(5))
              _WatchlistRow(
                row: _map(value),
                onTap: () =>
                    _showAssignment(_map(value)['assignment_id'].toString()),
              ),
            if (watchlist.length > 5)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('${watchlist.length - 5} more in this watchlist',
                    style: const TextStyle(
                        fontSize: 12, color: AppTheme.textSecondary)),
              ),
          ],
        ));
        return constraints.maxWidth < 1080
            ? Column(children: [
                attention,
                const SizedBox(height: 12),
                watchlistPanel
              ])
            : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(flex: 5, child: attention),
                const SizedBox(width: 12),
                Expanded(flex: 6, child: watchlistPanel),
              ]);
      }),
      const SizedBox(height: 16),
      LayoutBuilder(builder: (context, constraints) {
        final trend = _Box(
            child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const Expanded(
                  child: _Heading('Completions over time',
                      'Completed assignments per day.')),
              DropdownButton<int>(
                value: state.trendDays,
                items: const [
                  DropdownMenuItem(value: 30, child: Text('30 days')),
                  DropdownMenuItem(value: 90, child: Text('90 days')),
                ],
                onChanged: (days) {
                  if (days != null) report.setTrendDays(days);
                },
              ),
            ]),
            _Trend(points: _list(data['completion_trend'])),
          ],
        ));
        final coursePanel = _Box(
            child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SectionHeader(
              title: 'Completion by course',
              subtitle: 'Compare completion across courses.',
              onViewAll: () => report.setView(1),
            ),
            for (final value in courses.take(5)) _Bar(item: _map(value)),
            if (courses.isEmpty) const Text('No assigned courses yet.'),
          ],
        ));
        return constraints.maxWidth < 900
            ? Column(children: [trend, const SizedBox(height: 12), coursePanel])
            : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(flex: 3, child: trend),
                const SizedBox(width: 12),
                Expanded(flex: 2, child: coursePanel),
              ]);
      }),
      const SizedBox(height: 16),
      LayoutBuilder(builder: (context, constraints) {
        final departmentPanel = _Box(
            child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _Heading(
                'Department comparison', 'Completion by department.'),
            for (final value in departments) _Bar(item: _map(value)),
            if (departments.isEmpty) const Text('No department data yet.'),
          ],
        ));
        final mailingPanel = _Box(
            child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _Heading('Mailing list comparison',
                'Employees may belong to multiple lists.'),
            for (final value in mailingLists) _Bar(item: _map(value)),
            if (mailingLists.isEmpty) const Text('No mailing list data yet.'),
          ],
        ));
        return constraints.maxWidth < 760
            ? Column(children: [
                departmentPanel,
                const SizedBox(height: 12),
                mailingPanel
              ])
            : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(child: departmentPanel),
                const SizedBox(width: 12),
                Expanded(child: mailingPanel),
              ]);
      }),
    ]);
  }

  Widget _courses(PerformanceReportState state) {
    final courses = _list(state.courses['courses']);
    return _Box(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const _Heading(
          'Course performance', 'Open a course to inspect module results.'),
      if (courses.isEmpty)
        const Padding(
            padding: EdgeInsets.all(30),
            child:
                Center(child: Text('No courses match the selected filters.'))),
      for (final value in courses)
        ListTile(
            contentPadding: EdgeInsets.zero,
            onTap: () => _showCourse(_map(value)['course_id'].toString()),
            title: Text(_map(value)['course_name']?.toString() ?? '',
                style: const TextStyle(fontWeight: FontWeight.w700)),
            subtitle: Text(
                '${_map(value)['assigned']} assigned  •  ${_map(value)['completed']} completed  •  ${_map(value)['overdue']} overdue'),
            trailing: Text('${_map(value)['completion_rate']}% complete')),
    ]));
  }

  Widget _learners(PerformanceReportState state) {
    final data = state.assignments;
    final rows = _list(data['rows']);
    final total = _int(data['total']);
    final size = _int(data['page_size']) == 0 ? 25 : _int(data['page_size']);
    final report = ref.read(performanceReportProvider.notifier);
    return _Box(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const _Heading(
          'Learner assignments', 'One record per employee–course assignment.'),
      Wrap(
          spacing: 10,
          runSpacing: 10,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            SizedBox(
                width: 245,
                child: TextField(
                    controller: search,
                    decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.search),
                        hintText: 'Search learner or course',
                        isDense: true,
                        border: OutlineInputBorder()),
                    onChanged: report.setSearch)),
            _Drop(
                label: 'Status',
                value: state.status,
                width: 180,
                items: const {
                  'pending': 'Pending',
                  'started': 'Started',
                  'completed': 'Completed',
                  'overdue': 'Overdue',
                  'due_soon': 'Due soon',
                  'inactive': 'Inactive',
                  'repeated_failures': 'Repeated failures'
                },
                onChanged: report.setStatus),
            _Drop(
                label: 'Sort by',
                value: state.sort,
                width: 160,
                items: const {
                  'deadline': 'Due date',
                  'employee': 'Employee',
                  'course': 'Course',
                  'progress': 'Progress',
                  'score': 'Score',
                  'last_activity': 'Last activity',
                  'status': 'Status'
                },
                onChanged: (value) {
                  if (value != null) report.setSort(value);
                }),
            IconButton(
                tooltip:
                    state.descending ? 'Sort ascending' : 'Sort descending',
                onPressed: report.toggleSortDirection,
                icon: Icon(state.descending
                    ? Icons.arrow_downward
                    : Icons.arrow_upward)),
            Text('$total assignments',
                style: const TextStyle(color: AppTheme.textSecondary)),
          ]),
      const SizedBox(height: 14),
      if (rows.isEmpty)
        const Padding(
            padding: EdgeInsets.all(30),
            child: Center(child: Text('No matching assignments.'))),
      for (final value in rows)
        _AssignmentTile(
            row: _map(value),
            onTap: () =>
                _showAssignment(_map(value)['assignment_id'].toString())),
      if (total > size)
        Row(mainAxisAlignment: MainAxisAlignment.end, children: [
          IconButton(
              tooltip: 'Previous page',
              onPressed:
                  state.page > 1 ? () => report.setPage(state.page - 1) : null,
              icon: const Icon(Icons.chevron_left)),
          Text('Page ${state.page} of ${(total / size).ceil()}'),
          IconButton(
              tooltip: 'Next page',
              onPressed: state.page * size < total
                  ? () => report.setPage(state.page + 1)
                  : null,
              icon: const Icon(Icons.chevron_right)),
        ]),
    ]));
  }

  Future<void> _showAssignment(String id) async {
    final report = ref.read(performanceReportProvider.notifier);
    final detail = report.assignmentDetail(id);
    await showDialog<void>(
        context: context,
        builder: (context) => AssignmentDetailDialog(detail: detail));
  }

  Future<void> _showCourse(String id) async {
    final report = ref.read(performanceReportProvider.notifier);
    await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
              title: const Text('Course detail'),
              content: SizedBox(
                  width: 650,
                  child: FutureBuilder<Map<String, dynamic>>(
                      future: report.courseDetail(id),
                      builder: (context, snapshot) {
                        if (!snapshot.hasData) {
                          return Text(snapshot.hasError
                              ? snapshot.error.toString()
                              : 'Loading…');
                        }
                        final data = snapshot.data!;
                        final course = _map(data['course']);
                        return SingleChildScrollView(
                            child: Column(
                                mainAxisSize: MainAxisSize.min,
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                              Text(course['course_name']?.toString() ?? '',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w700)),
                              Text(
                                  '${course['assigned']} assigned  •  ${course['completed']} completed  •  ${course['overdue']} overdue'),
                              const SizedBox(height: 14),
                              for (final value in _list(data['modules']))
                                Padding(
                                    padding:
                                        const EdgeInsets.symmetric(vertical: 7),
                                    child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                              '${_map(value)['module_number']}. ${_map(value)['title']}',
                                              style: const TextStyle(
                                                  fontWeight: FontWeight.w700)),
                                          Text(
                                              '${_map(value)['watched']}/${_map(value)['assigned']} watched  •  ${_int(_map(value)['num_questions']) == 0 ? 'No quiz' : '${_map(value)['passed']} passed'}  •  ${_map(value)['attempts']} attempts  •  Average ${_score(_map(value)['average_score'])}'),
                                        ])),
                            ]));
                      })),
              actions: [
                TextButton(
                    onPressed: () {
                      Navigator.pop(context);
                      final current =
                          ref.read(performanceReportProvider).filter;
                      report.setFilter(current.copyWith(courseId: id));
                      report.setView(2);
                    },
                    child: const Text('View learners')),
                TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Close'))
              ],
            ));
  }

  Future<void> _export() async {
    try {
      final csv =
          await ref.read(performanceReportProvider.notifier).exportCsv();
      final blob = html.Blob([csv], 'text/csv;charset=utf-8');
      final url = html.Url.createObjectUrlFromBlob(blob);
      html.AnchorElement(href: url)
        ..download = 'performance-assignments.csv'
        ..click();
      Future.delayed(
          const Duration(seconds: 1), () => html.Url.revokeObjectUrl(url));
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.toString())));
      }
    }
  }
}

class _ViewTabs extends StatelessWidget {
  final int selected;
  final ValueChanged<int> onSelected;

  const _ViewTabs({required this.selected, required this.onSelected});

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final (index, label) in const [
            (0, 'Overview'),
            (1, 'Courses'),
            (2, 'Learners'),
          ])
            InkWell(
              onTap: () => onSelected(index),
              child: Container(
                width: 106,
                padding: const EdgeInsets.symmetric(vertical: 11),
                decoration: BoxDecoration(
                  border: Border(
                      bottom: BorderSide(
                    width: selected == index ? 3 : 1,
                    color: selected == index
                        ? AppTheme.primaryBlue
                        : AppTheme.lightGray,
                  )),
                ),
                child: Text(label,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: selected == index
                          ? AppTheme.primaryBlue
                          : AppTheme.textSecondary,
                      fontWeight:
                          selected == index ? FontWeight.w800 : FontWeight.w600,
                    )),
              ),
            ),
        ],
      );
}

class _KpiCard extends StatelessWidget {
  final String label, value, caption;
  final Color color;
  final IconData icon;
  final bool compact;
  final VoidCallback? onTap;

  const _KpiCard({
    required this.label,
    required this.value,
    required this.caption,
    required this.color,
    required this.icon,
    required this.compact,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) => Material(
        color: Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: Color(0xFFDDE6F1)),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: SizedBox(
            height: 112,
            child: Padding(
              padding: EdgeInsets.all(compact ? 10 : 13),
              child: compact
                  ? Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(children: [
                          Icon(icon, color: color, size: 19),
                          const SizedBox(width: 6),
                          Expanded(
                              child: Text(label,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                      fontSize: 11,
                                      color: AppTheme.textSecondary))),
                        ]),
                        const Spacer(),
                        Text(value,
                            style: const TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.w800,
                                color: AppTheme.textBlack)),
                        Text(caption,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                fontSize: 10, color: AppTheme.textSecondary)),
                      ],
                    )
                  : Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                          Container(
                            width: 36,
                            height: 36,
                            decoration: BoxDecoration(
                              color: Color.lerp(Colors.white, color, 0.11),
                              borderRadius: BorderRadius.circular(11),
                            ),
                            child: Icon(icon, color: color, size: 20),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                              child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(label,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                      fontSize: 12,
                                      color: AppTheme.textSecondary)),
                              const SizedBox(height: 3),
                              Text(value,
                                  style: const TextStyle(
                                      fontSize: 25,
                                      fontWeight: FontWeight.w800,
                                      color: AppTheme.textBlack)),
                              Text(caption,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                      fontSize: 11,
                                      color: AppTheme.textSecondary)),
                            ],
                          )),
                        ]),
            ),
          ),
        ),
      );
}

class _SectionHeader extends StatelessWidget {
  final String title, subtitle;
  final VoidCallback onViewAll;

  const _SectionHeader({
    required this.title,
    required this.subtitle,
    required this.onViewAll,
  });

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
              child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: const TextStyle(
                      fontSize: 17, fontWeight: FontWeight.w800)),
              Text(subtitle,
                  style: const TextStyle(
                      fontSize: 12, color: AppTheme.textSecondary)),
            ],
          )),
          TextButton(onPressed: onViewAll, child: const Text('View all')),
        ]),
      );
}

class _AttentionCard extends StatelessWidget {
  final double width;
  final String label, detail;
  final Object? count;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  const _AttentionCard({
    required this.width,
    required this.label,
    required this.count,
    required this.detail,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) => Material(
        color: Color.lerp(Colors.white, color, 0.055),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: Color.lerp(Colors.white, color, 0.2)!),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: SizedBox(
            width: width,
            height: 148,
            child: Padding(
              padding: const EdgeInsets.all(13),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Icon(icon, color: color, size: 21),
                    const SizedBox(width: 6),
                    Expanded(
                        child: Text(label,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style:
                                const TextStyle(fontWeight: FontWeight.w700))),
                  ]),
                  const SizedBox(height: 9),
                  Text('${count ?? 0}',
                      style: TextStyle(
                          fontSize: 30,
                          fontWeight: FontWeight.w800,
                          color: color)),
                  const Spacer(),
                  Row(children: [
                    Expanded(
                        child: Text(detail,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                fontSize: 11, color: AppTheme.textSecondary))),
                    Icon(Icons.arrow_forward, size: 17, color: color),
                  ]),
                ],
              ),
            ),
          ),
        ),
      );
}

class _AttentionLink extends StatelessWidget {
  final String label;
  final Object? count;
  final VoidCallback onTap;

  const _AttentionLink({
    required this.label,
    required this.count,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 9),
          child: Row(children: [
            const Icon(Icons.quiz_outlined,
                size: 18, color: AppTheme.accentBlue),
            const SizedBox(width: 9),
            Expanded(
                child: Text(label,
                    style: const TextStyle(fontWeight: FontWeight.w600))),
            Text('${count ?? 0}',
                style: const TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(width: 4),
            const Icon(Icons.chevron_right, size: 18),
          ]),
        ),
      );
}

class _WatchlistHeader extends StatelessWidget {
  const _WatchlistHeader();

  @override
  Widget build(BuildContext context) => LayoutBuilder(
        builder: (context, constraints) {
          if (constraints.maxWidth < 620) return const SizedBox.shrink();
          return const Padding(
            padding: EdgeInsets.fromLTRB(8, 4, 8, 8),
            child: Row(children: [
              Expanded(flex: 3, child: Text('LEARNER')),
              Expanded(flex: 3, child: Text('COURSE')),
              Expanded(flex: 2, child: Text('DUE')),
              Expanded(flex: 2, child: Text('PROGRESS')),
              Expanded(flex: 2, child: Text('STATUS')),
              SizedBox(width: 18),
            ]),
          );
        },
      );
}

class _WatchlistRow extends StatelessWidget {
  final Map<String, dynamic> row;
  final VoidCallback onTap;

  const _WatchlistRow({required this.row, required this.onTap});

  @override
  Widget build(BuildContext context) => LayoutBuilder(
        builder: (context, constraints) {
          final completed = _int(row['completed_modules']);
          final total = _int(row['total_modules']);
          final progress =
              total == 0 ? 0.0 : (completed / total).clamp(0.0, 1.0);
          final status = _statusLabel(row);
          if (constraints.maxWidth < 620) {
            return ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 4),
              onTap: onTap,
              title: Text(row['employee_name']?.toString() ?? 'Learner',
                  style: const TextStyle(fontWeight: FontWeight.w700)),
              subtitle: Text(
                  '${row['course_name'] ?? 'Course'} • $completed/$total modules • Due ${_date(row['deadline'])}'),
              trailing: _StatusBadge(status),
            );
          }
          return InkWell(
            onTap: onTap,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 11),
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: Color(0xFFE6EDF5))),
              ),
              child: Row(children: [
                Expanded(
                    flex: 3,
                    child: Text(row['employee_name']?.toString() ?? 'Learner',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w700))),
                Expanded(
                    flex: 3,
                    child: Text(row['course_name']?.toString() ?? 'Course',
                        maxLines: 1, overflow: TextOverflow.ellipsis)),
                Expanded(
                    flex: 2,
                    child: Text(_date(row['deadline']),
                        maxLines: 1, overflow: TextOverflow.ellipsis)),
                Expanded(
                    flex: 2,
                    child: Row(children: [
                      Expanded(
                          child: LinearProgressIndicator(
                        value: progress,
                        minHeight: 5,
                        borderRadius: BorderRadius.circular(4),
                        color: AppTheme.accentBlue,
                        backgroundColor: AppTheme.brandBlue100,
                      )),
                      const SizedBox(width: 5),
                      Text('$completed/$total',
                          style: const TextStyle(fontSize: 11)),
                      const SizedBox(width: 6),
                    ])),
                Expanded(
                    flex: 2,
                    child: Align(
                        alignment: Alignment.centerLeft,
                        child: _StatusBadge(status))),
                const Icon(Icons.chevron_right,
                    size: 18, color: AppTheme.textSecondary),
              ]),
            ),
          );
        },
      );
}

class _StatusBadge extends StatelessWidget {
  final String label;
  const _StatusBadge(this.label);

  @override
  Widget build(BuildContext context) {
    final color = label == 'Overdue'
        ? AppTheme.accentRed
        : label == 'Due soon'
            ? AppTheme.accentOrange
            : label == 'Completed'
                ? AppTheme.accentGreen
                : AppTheme.accentBlue;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
      decoration: BoxDecoration(
        color: Color.lerp(Colors.white, color, 0.11),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
              fontSize: 11, fontWeight: FontWeight.w700, color: color)),
    );
  }
}

class _Box extends StatelessWidget {
  final Widget child;
  const _Box({required this.child});
  @override
  Widget build(BuildContext context) => Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.cardDecoration(shadow: false),
      child: child);
}

class _Heading extends StatelessWidget {
  final String title, subtitle;
  const _Heading(this.title, this.subtitle);
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
        Text(subtitle,
            style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary))
      ]));
}

class _Drop extends StatelessWidget {
  final String label;
  final String? value;
  final Map<String, String> items;
  final double width;
  final ValueChanged<String?> onChanged;
  const _Drop(
      {required this.label,
      required this.value,
      required this.items,
      required this.width,
      required this.onChanged});
  @override
  Widget build(BuildContext context) => SizedBox(
      width: width,
      child: DropdownButtonFormField<String>(
          value: value != null && items.containsKey(value) ? value : '',
          isExpanded: true,
          decoration: InputDecoration(
              labelText: label,
              isDense: true,
              border: const OutlineInputBorder()),
          items: [
            const DropdownMenuItem(value: '', child: Text('All')),
            for (final item in items.entries)
              DropdownMenuItem(
                  value: item.key,
                  child: Text(item.value, overflow: TextOverflow.ellipsis))
          ],
          onChanged: (next) => onChanged(next == '' ? null : next)));
}

class _Bar extends StatelessWidget {
  final Map<String, dynamic> item;
  const _Bar({required this.item});
  @override
  Widget build(BuildContext context) {
    final rate = _int(item['completion_rate']).clamp(0, 100);
    return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(children: [
          SizedBox(
              width: 130,
              child: Text(item['label']?.toString() ?? '',
                  overflow: TextOverflow.ellipsis)),
          Expanded(
              child: LinearProgressIndicator(
                  value: rate / 100,
                  minHeight: 9,
                  backgroundColor: AppTheme.brandBlue100,
                  valueColor:
                      const AlwaysStoppedAnimation(AppTheme.primaryBlue))),
          const SizedBox(width: 10),
          Text('$rate%')
        ]));
  }
}

class _Trend extends StatelessWidget {
  final List<dynamic> points;
  const _Trend({required this.points});
  @override
  Widget build(BuildContext context) {
    if (points.isEmpty) return const Text('No trend data yet.');
    final maximum = points
        .map((value) => _int(_map(value)['completed']))
        .fold<int>(1, (a, b) => a > b ? a : b);
    return Column(children: [
      SizedBox(
          height: 100,
          child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
            for (final value in points)
              Expanded(
                  child: Tooltip(
                      message:
                          '${_map(value)['date']}: ${_map(value)['completed']} completed',
                      child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 1),
                          child: Container(
                              height: 5 +
                                  90 * _int(_map(value)['completed']) / maximum,
                              color: AppTheme.accentBlue))))
          ])),
      const SizedBox(height: 5),
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(_map(points.first)['date'].toString(),
            style: const TextStyle(fontSize: 11)),
        Text(_map(points.last)['date'].toString(),
            style: const TextStyle(fontSize: 11))
      ])
    ]);
  }
}

class _AssignmentTile extends StatelessWidget {
  final Map<String, dynamic> row;
  final VoidCallback onTap;
  const _AssignmentTile({required this.row, required this.onTap});
  @override
  Widget build(BuildContext context) => ListTile(
      contentPadding: EdgeInsets.zero,
      onTap: onTap,
      title: Text(
          '${row['employee_name']}${row['employee_status'] == 'inactive' ? ' (inactive employee)' : ''} · ${row['course_name']}',
          maxLines: 1,
          overflow: TextOverflow.ellipsis),
      subtitle: Text(
          '${row['completed_modules']}/${row['total_modules']} modules  •  Score ${_score(row['average_score'])}  •  Due ${_date(row['deadline'])}  •  Active ${_date(row['last_learner_activity_at'])}${_int(row['failed_attempts']) > 0 ? '  •  ${row['failed_attempts']} failed attempts' : ''}'),
      trailing: Text(_statusLabel(row),
          style: TextStyle(
              color: row['status'] == 'overdue'
                  ? AppTheme.accentRed
                  : AppTheme.primaryBlue,
              fontWeight: FontWeight.w700)));
}

Map<String, dynamic> _map(Object? value) =>
    value is Map<String, dynamic> ? value : <String, dynamic>{};
List<dynamic> _list(Object? value) => value is List ? value : const [];
int _int(Object? value) =>
    value is num ? value.toInt() : int.tryParse('$value') ?? 0;
String _score(Object? value) =>
    value is num ? '${value.toStringAsFixed(1)}%' : '—';
String _date(Object? value) {
  final date = DateTime.tryParse(value?.toString() ?? '');
  return date == null ? '—' : '${date.day}/${date.month}/${date.year}';
}

String _dateTime(Object? value) {
  final date = DateTime.tryParse(value?.toString() ?? '');
  return date == null
      ? '—'
      : '${date.day}/${date.month}/${date.year} ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
}

String _statusLabel(Map<String, dynamic> row) {
  if (row['status'] == 'overdue') return 'Overdue';
  if (row['due_soon'] == true) return 'Due soon';
  if (row['status'] == 'completed') return 'Completed';
  if (row['repeated_failures'] == true) return 'Quiz difficulty';
  if (row['inactive'] == true) return 'Inactive';
  return row['status'] == 'started' ? 'Started' : 'Pending';
}
