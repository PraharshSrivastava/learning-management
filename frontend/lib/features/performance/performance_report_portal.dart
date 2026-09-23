// This trainer application is deployed as Flutter Web; CSV downloads use the browser.
// ignore_for_file: avoid_web_libraries_in_flutter
import 'dart:html' as html;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:frontend/core/theme/app_theme.dart';
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
      decoration: AppTheme.pageBackground(),
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
          SegmentedButton<int>(segments: const [
            ButtonSegment(value: 0, label: Text('Overview')),
            ButtonSegment(value: 1, label: Text('Courses')),
            ButtonSegment(value: 2, label: Text('Learners')),
          ], selected: {
            state.view
          }, onSelectionChanged: (values) => report.setView(values.first)),
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
        AppTheme.primaryBlue
      ),
      (
        'Completed',
        '${summary['completion_rate'] ?? 0}%',
        '${summary['completed'] ?? 0} assignments',
        'completed',
        AppTheme.accentGreen
      ),
      (
        'Due soon',
        '${summary['due_soon'] ?? 0}',
        'Within ${data['due_soon_days'] ?? 2} days',
        'due_soon',
        AppTheme.accentOrange
      ),
      (
        'Overdue',
        '${summary['overdue'] ?? 0}',
        'Incomplete assignments',
        'overdue',
        AppTheme.accentRed
      ),
      (
        'On-time compliance',
        summary['on_time_compliance'] == null
            ? '—'
            : '${summary['on_time_compliance']}%',
        '${summary['on_time_denominator'] ?? 0} deadlines passed',
        null,
        AppTheme.accentBlue
      ),
      (
        'Average quiz score',
        summary['average_score'] == null ? '—' : '${summary['average_score']}%',
        '${summary['scored_modules'] ?? 0} scored modules',
        null,
        const Color(0xFF7047EB)
      ),
    ];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      LayoutBuilder(builder: (context, constraints) {
        final width = constraints.maxWidth >= 1000
            ? (constraints.maxWidth - 24) / 3
            : constraints.maxWidth >= 650
                ? (constraints.maxWidth - 12) / 2
                : constraints.maxWidth;
        return Wrap(spacing: 12, runSpacing: 12, children: [
          for (final item in metrics)
            SizedBox(
                width: width,
                child: InkWell(
                    onTap: item.$4 == null
                        ? null
                        : () => report.setStatus(item.$4),
                    child: _Box(
                        child: Row(children: [
                      Container(width: 5, height: 54, color: item.$5),
                      const SizedBox(width: 12),
                      Expanded(
                          child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                            Text(item.$1,
                                style: const TextStyle(
                                    color: AppTheme.textSecondary)),
                            Text(item.$2,
                                style: const TextStyle(
                                    fontSize: 26, fontWeight: FontWeight.w800)),
                            Text(item.$3,
                                style: const TextStyle(
                                    fontSize: 12,
                                    color: AppTheme.textSecondary))
                          ])),
                      if (item.$4 != null)
                        const Icon(Icons.chevron_right, size: 18)
                    ]))))
        ]);
      }),
      const SizedBox(height: 16),
      LayoutBuilder(builder: (context, constraints) {
        final attention = _Box(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const _Heading('Needs attention',
              'Select a count to see the affected learners.'),
          _Attention('Overdue', summary['overdue'], 'overdue'),
          _Attention('Due soon', summary['due_soon'], 'due_soon'),
          _Attention(
              'No learner activity for ${data['inactive_days'] ?? 14} days',
              summary['inactive'],
              'inactive'),
          _Attention('Repeated quiz failures', summary['repeated_failures'],
              'repeated_failures'),
        ]));
        final comparison = _Box(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const _Heading(
              'Completion by course', 'Open Courses for module results.'),
          for (final value in _list(breakdowns['courses']).take(6))
            _Bar(item: _map(value)),
          if (_list(breakdowns['courses']).isEmpty)
            const Text('No assigned courses yet.'),
        ]));
        return constraints.maxWidth < 800
            ? Column(
                children: [attention, const SizedBox(height: 12), comparison])
            : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(child: attention),
                const SizedBox(width: 12),
                Expanded(child: comparison)
              ]);
      }),
      const SizedBox(height: 16),
      _Box(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Expanded(
              child: _Heading(
                  'Completions over time', 'Completed assignments per day.')),
          DropdownButton<int>(
              value: state.trendDays,
              items: const [
                DropdownMenuItem(value: 30, child: Text('30 days')),
                DropdownMenuItem(value: 90, child: Text('90 days'))
              ],
              onChanged: (days) {
                if (days != null) report.setTrendDays(days);
              })
        ]),
        _Trend(points: _list(data['completion_trend'])),
      ])),
      const SizedBox(height: 16),
      _Box(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const _Heading('Assignment watchlist',
            'The most urgent assignments in this scope.'),
        if (_list(data['watchlist']).isEmpty)
          const Text('No assignments currently need attention.'),
        for (final value in _list(data['watchlist']))
          _AssignmentTile(
              row: _map(value),
              onTap: () =>
                  _showAssignment(_map(value)['assignment_id'].toString())),
      ])),
      const SizedBox(height: 16),
      _Box(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const _Heading('Department comparison', 'Completion by department.'),
        for (final value in _list(breakdowns['departments']))
          _Bar(item: _map(value)),
      ])),
      const SizedBox(height: 16),
      _Box(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const _Heading('Mailing list comparison',
            'Employees may belong to multiple lists.'),
        for (final value in _list(breakdowns['mailing_lists']))
          _Bar(item: _map(value)),
      ])),
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
    await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
              title: const Text('Assignment detail'),
              content: SizedBox(
                  width: 650,
                  child: FutureBuilder<Map<String, dynamic>>(
                      future: report.assignmentDetail(id),
                      builder: (context, snapshot) {
                        if (!snapshot.hasData) {
                          return Text(snapshot.hasError
                              ? snapshot.error.toString()
                              : 'Loading…');
                        }
                        final data = snapshot.data!;
                        final row = _map(data['assignment']);
                        final modules = _list(data['modules']);
                        final moduleTitles = {
                          for (final value in modules)
                            _map(value)['module_id']?.toString():
                                _map(value)['title']?.toString() ?? 'Module'
                        };
                        return SingleChildScrollView(
                            child: Column(
                                mainAxisSize: MainAxisSize.min,
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                              Text(
                                  '${row['employee_name']} · ${row['course_name']}',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w700)),
                              Text(
                                  'Due ${_date(row['deadline'])}  •  ${row['completed_modules']}/${row['total_modules']} modules'),
                              Text(
                                  'Assigned ${_date(row['assigned_at'])}  •  Last learner activity ${_date(row['last_learner_activity_at'])}'),
                              Text(
                                  'Started ${_date(row['started_at'])}  •  Completed ${_date(row['completed_at'])}'),
                              const SizedBox(height: 14),
                              const Text('Modules',
                                  style:
                                      TextStyle(fontWeight: FontWeight.w700)),
                              for (final value in modules)
                                Padding(
                                    padding:
                                        const EdgeInsets.symmetric(vertical: 6),
                                    child: Text(
                                        '${_map(value)['module_number']}. ${_map(value)['title']}  •  ${_map(value)['video_watched'] == true ? 'Video watched' : 'Video pending'}  •  ${_int(_map(value)['num_questions']) == 0 ? 'No quiz' : _map(value)['quiz_passed'] == true ? 'Quiz passed' : 'Quiz pending'}  •  ${_map(value)['attempt_count']} attempts  •  ${_score(_map(value)['latest_score'])}')),
                              const SizedBox(height: 14),
                              Text(
                                  'Recorded quiz attempts (${_list(data['attempts']).length})',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w700)),
                              const Text(
                                  'History is available from the reporting upgrade onward.',
                                  style: TextStyle(
                                      fontSize: 12,
                                      color: AppTheme.textSecondary)),
                              for (final value
                                  in _list(data['attempts']).take(20))
                                Text(
                                    '${moduleTitles[_map(value)['module_id']?.toString()] ?? 'Module'}  •  ${_dateTime(_map(value)['occurred_at'])}  •  ${_score(_map(value)['score'])}  •  ${_map(value)['passed'] == true ? 'Passed' : 'Failed'}'),
                            ]));
                      })),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Close'))
              ],
            ));
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

class _Attention extends ConsumerWidget {
  final String label, status;
  final Object? count;
  const _Attention(this.label, this.count, this.status);
  @override
  Widget build(BuildContext context, WidgetRef ref) => ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(label),
      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
        Text('${count ?? 0}',
            style: const TextStyle(fontWeight: FontWeight.w800)),
        const Icon(Icons.chevron_right)
      ]),
      onTap: () =>
          ref.read(performanceReportProvider.notifier).setStatus(status));
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
