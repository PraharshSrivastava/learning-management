import 'package:flutter/material.dart';

import 'package:frontend/core/theme/app_theme.dart';

typedef EmployeeReportLoader = Future<Map<String, dynamic>> Function(
    Map<String, String> params);

class EmployeeSummaryPanel extends StatefulWidget {
  final String scopeKey;
  final String revision;
  final int resetVersion;
  final EmployeeReportLoader load;
  final ValueChanged<String> onOpenEmployee;
  final Future<void> Function(Map<String, String>)? onExport;

  const EmployeeSummaryPanel(
      {super.key,
      required this.scopeKey,
      required this.revision,
      this.resetVersion = 0,
      this.onExport,
      required this.load,
      required this.onOpenEmployee});

  @override
  State<EmployeeSummaryPanel> createState() => _EmployeeSummaryPanelState();
}

class _EmployeeSummaryPanelState extends State<EmployeeSummaryPanel> {
  final search = TextEditingController();
  String submittedSearch = '';
  String attention = 'all';
  String sort = 'employee';
  bool descending = false;
  int page = 1;
  int request = 0;
  bool loading = true;
  bool exporting = false;
  String? error;
  Map<String, dynamic> data = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant EmployeeSummaryPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.resetVersion != widget.resetVersion) {
      search.clear();
      submittedSearch = '';
      attention = 'all';
      sort = 'employee';
      descending = false;
    }
    if (oldWidget.scopeKey != widget.scopeKey ||
        oldWidget.revision != widget.revision ||
        oldWidget.resetVersion != widget.resetVersion) {
      page = 1;
      _load();
    }
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final current = ++request;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await widget.load({
        if (submittedSearch.isNotEmpty) 'search': submittedSearch,
        if (attention != 'all') 'attention': attention,
        'sort': sort,
        'descending': '$descending',
        'page': '$page',
      });
      if (!mounted || current != request) return;
      setState(() {
        data = result;
        loading = false;
      });
    } catch (failure) {
      if (!mounted || current != request) return;
      setState(() {
        error = failure.toString();
        loading = false;
      });
    }
  }

  void _search() {
    submittedSearch = search.text.trim();
    page = 1;
    _load();
  }

  Future<void> _export() async {
    setState(() => exporting = true);
    try {
      await widget.onExport!({
        if (submittedSearch.isNotEmpty) 'search': submittedSearch,
        if (attention != 'all') 'attention': attention,
        'sort': sort,
        'descending': '$descending',
      });
    } finally {
      if (mounted) setState(() => exporting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final summary = _map(data['summary']);
    final rows = _rows(data['rows']);
    final total = _number(data['total']);
    final size =
        _number(data['page_size']) == 0 ? 25 : _number(data['page_size']);
    return _Surface(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Employee performance',
          style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800)),
      const SizedBox(height: 4),
      const Text(
          'One row per employee · Your published courses and current filters.',
          style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
      const SizedBox(height: 18),
      Wrap(
          spacing: 10,
          runSpacing: 10,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            SizedBox(
                width: 270,
                child: TextField(
                  controller: search,
                  textInputAction: TextInputAction.search,
                  onSubmitted: (_) => _search(),
                  decoration: InputDecoration(
                    prefixIcon: const Icon(Icons.search),
                    hintText: 'Employee name or ID · Enter',
                    isDense: true,
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                        tooltip: 'Clear employee search',
                        icon: const Icon(Icons.close, size: 18),
                        onPressed: () {
                          search.clear();
                          _search();
                        }),
                  ),
                )),
            FilledButton(
                onPressed: loading ? null : _search,
                child: const Text('Search')),
            _Select(
                label: 'Attention',
                value: attention,
                items: const {
                  'all': 'All employees',
                  'needs_attention': 'Needs attention',
                  'overdue': 'Has overdue courses',
                  'completed': 'All courses completed',
                },
                onChanged: (value) {
                  attention = value;
                  page = 1;
                  _load();
                }),
            _Select(
                label: 'Sort by',
                value: sort,
                items: const {
                  'employee': 'Employee name',
                  'assigned': 'Assigned courses',
                  'completion': 'Completion rate',
                  'overdue': 'Overdue courses',
                  'score': 'Quiz score',
                },
                onChanged: (value) {
                  sort = value;
                  page = 1;
                  _load();
                }),
            IconButton(
                tooltip: descending ? 'Sort ascending' : 'Sort descending',
                icon: Icon(
                    descending ? Icons.arrow_downward : Icons.arrow_upward),
                onPressed: () {
                  descending = !descending;
                  page = 1;
                  _load();
                }),
            if (widget.onExport != null)
              OutlinedButton.icon(
                  onPressed:
                      loading || exporting || error != null || data.isEmpty
                          ? null
                          : _export,
                  icon: const Icon(Icons.download_outlined, size: 18),
                  label:
                      Text(exporting ? 'Exporting…' : 'Export employees CSV')),
          ]),
      if (loading)
        const Padding(
            padding: EdgeInsets.only(top: 16),
            child: LinearProgressIndicator()),
      if (error != null)
        Padding(
            padding: const EdgeInsets.symmetric(vertical: 20),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Could not load employees. $error',
                  style: const TextStyle(color: Colors.red)),
              TextButton(onPressed: _load, child: const Text('Retry')),
            ])),
      if (error == null && data.isNotEmpty) ...[
        const SizedBox(height: 18),
        LayoutBuilder(builder: (context, constraints) {
          final count = constraints.maxWidth > 750
              ? 4
              : constraints.maxWidth > 390
                  ? 2
                  : 1;
          final width = (constraints.maxWidth - (count - 1) * 10) / count;
          return Wrap(spacing: 10, runSpacing: 10, children: [
            _Metric(
                label: 'Employees',
                value: '${summary['employees'] ?? 0}',
                icon: Icons.people_outline,
                width: width),
            _Metric(
                label: 'Assigned courses',
                value: '${summary['assigned'] ?? 0}',
                icon: Icons.menu_book_outlined,
                width: width),
            _Metric(
                label: 'Completed courses',
                value: '${summary['completed'] ?? 0}',
                icon: Icons.check_circle_outline,
                color: _green,
                width: width),
            _Metric(
                label: 'Overdue assignments',
                value: '${summary['overdue'] ?? 0}',
                icon: Icons.error_outline,
                color: _red,
                width: width),
          ]);
        }),
        const SizedBox(height: 18),
        if (rows.isEmpty)
          const Padding(
              padding: EdgeInsets.all(30),
              child: Center(child: Text('No matching employees.')))
        else
          EmployeeSummaryTable(
              rows: rows,
              onOpenEmployee: loading ? (_) {} : widget.onOpenEmployee),
        const SizedBox(height: 12),
        const Text(
            'Select an employee to see their courses. Completion = completed courses ÷ assigned courses.',
            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        if (total > size)
          Row(children: [
            Expanded(
                child: Text(
                    'Showing ${(page - 1) * size + 1}–${(page * size).clamp(0, total)} of $total employees',
                    style: const TextStyle(fontSize: 12))),
            IconButton(
                tooltip: 'Previous employee page',
                onPressed: !loading && page > 1
                    ? () {
                        page--;
                        _load();
                      }
                    : null,
                icon: const Icon(Icons.chevron_left)),
            Text('$page / ${(total / size).ceil()}'),
            IconButton(
                tooltip: 'Next employee page',
                onPressed: !loading && page * size < total
                    ? () {
                        page++;
                        _load();
                      }
                    : null,
                icon: const Icon(Icons.chevron_right)),
          ]),
      ],
    ]));
  }
}

class EmployeeSummaryTable extends StatelessWidget {
  final List<Map<String, dynamic>> rows;
  final ValueChanged<String> onOpenEmployee;
  const EmployeeSummaryTable(
      {super.key, required this.rows, required this.onOpenEmployee});

  @override
  Widget build(BuildContext context) =>
      LayoutBuilder(builder: (context, constraints) {
        final wide = constraints.maxWidth >= 850;
        return Column(children: [
          if (wide)
            Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                    color: const Color(0xFFF3F7FC),
                    borderRadius: BorderRadius.circular(8)),
                child: const Row(children: [
                  Expanded(flex: 3, child: Text('EMPLOYEE', style: _header)),
                  Expanded(child: Text('ASSIGNED', style: _header)),
                  Expanded(child: Text('COMPLETED', style: _header)),
                  Expanded(flex: 2, child: Text('COMPLETION', style: _header)),
                  Expanded(child: Text('OVERDUE', style: _header)),
                  Expanded(child: Text('AVG. QUIZ', style: _header)),
                  SizedBox(width: 24),
                ])),
          for (final row in rows)
            Material(
                color: Colors.white,
                child: InkWell(
                  onTap: () => onOpenEmployee(row['employee_id'].toString()),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 14, vertical: 16),
                    decoration: const BoxDecoration(
                        border: Border(
                            bottom: BorderSide(color: Color(0xFFE6EDF5)))),
                    child: wide
                        ? Row(children: [
                            Expanded(flex: 3, child: _Identity(row: row)),
                            Expanded(
                                child: Text('${row['assigned']}',
                                    style: const TextStyle(
                                        fontWeight: FontWeight.w700))),
                            Expanded(child: Text('${row['completed']}')),
                            Expanded(
                                flex: 2,
                                child: Padding(
                                    padding: const EdgeInsets.only(right: 24),
                                    child: _Completion(row: row))),
                            Expanded(
                                child: Align(
                                    alignment: Alignment.centerLeft,
                                    child: _Badge(
                                        text: '${row['overdue'] ?? 0}',
                                        color: _number(row['overdue']) > 0
                                            ? _red
                                            : AppTheme.textSecondary))),
                            Expanded(
                                child: Text(_percent(row['average_score']))),
                            const Icon(Icons.chevron_right,
                                size: 24, color: AppTheme.textSecondary),
                          ])
                        : Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                                Row(children: [
                                  Expanded(child: _Identity(row: row)),
                                  const Icon(Icons.chevron_right)
                                ]),
                                const SizedBox(height: 12),
                                _Completion(row: row),
                                const SizedBox(height: 10),
                                Wrap(spacing: 16, runSpacing: 6, children: [
                                  Text('${row['assigned']} assigned'),
                                  Text('${row['completed']} completed'),
                                  Text('${row['overdue']} overdue',
                                      style: TextStyle(
                                          color: _number(row['overdue']) > 0
                                              ? _red
                                              : AppTheme.textSecondary)),
                                  Text(
                                      'Quiz ${_percent(row['average_score'])}'),
                                ]),
                              ]),
                  ),
                )),
        ]);
      });
}

class EmployeeDetailDrawer extends StatelessWidget {
  final Future<Map<String, dynamic>> detail;
  final ValueChanged<String> onOpenAssignment;
  const EmployeeDetailDrawer(
      {super.key, required this.detail, required this.onOpenAssignment});

  @override
  Widget build(BuildContext context) => Material(
        color: Colors.white,
        borderRadius: const BorderRadius.horizontal(left: Radius.circular(22)),
        clipBehavior: Clip.antiAlias,
        child: SizedBox(
          width: MediaQuery.sizeOf(context).width.clamp(0, 900),
          height: MediaQuery.sizeOf(context).height,
          child: Column(children: [
            Padding(
                padding: const EdgeInsets.fromLTRB(24, 16, 12, 12),
                child: Row(children: [
                  const Expanded(
                      child: Text('Employee performance',
                          style: TextStyle(
                              fontSize: 21, fontWeight: FontWeight.w800))),
                  IconButton(
                      tooltip: 'Close employee detail',
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close)),
                ])),
            Expanded(
                child: FutureBuilder<Map<String, dynamic>>(
                    future: detail,
                    builder: (context, snapshot) {
                      if (snapshot.hasError) {
                        return Center(
                            child: Padding(
                                padding: const EdgeInsets.all(24),
                                child: Text(
                                    'Could not load employee detail. ${snapshot.error}')));
                      }
                      if (!snapshot.hasData) {
                        return const Center(child: CircularProgressIndicator());
                      }
                      final employee = _map(snapshot.data!['employee']);
                      final assignments = _rows(snapshot.data!['assignments']);
                      return SingleChildScrollView(
                          child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                            Container(
                                width: double.infinity,
                                padding: const EdgeInsets.all(24),
                                color: const Color(0xFFF0F6FD),
                                child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      _Identity(row: employee, prominent: true),
                                      const SizedBox(height: 10),
                                      Text(
                                          'Employee ID: ${employee['employee_id']}',
                                          style: const TextStyle(
                                              fontSize: 12,
                                              color: AppTheme.textSecondary)),
                                    ])),
                            Padding(
                                padding: const EdgeInsets.all(24),
                                child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      LayoutBuilder(
                                          builder: (context, constraints) {
                                        final columns =
                                            constraints.maxWidth >= 650
                                                ? 4
                                                : constraints.maxWidth >= 290
                                                    ? 2
                                                    : 1;
                                        final width = (constraints.maxWidth -
                                                (columns - 1) * 10) /
                                            columns;
                                        return Wrap(
                                            spacing: 10,
                                            runSpacing: 10,
                                            children: [
                                              _Metric(
                                                  label: 'Assigned courses',
                                                  value:
                                                      '${employee['assigned'] ?? 0}',
                                                  icon:
                                                      Icons.menu_book_outlined,
                                                  width: width),
                                              _Metric(
                                                  label: 'Completed',
                                                  value:
                                                      '${employee['completed'] ?? 0}',
                                                  icon: Icons
                                                      .check_circle_outline,
                                                  color: _green,
                                                  width: width),
                                              _Metric(
                                                  label: 'In progress',
                                                  value:
                                                      '${employee['in_progress'] ?? 0}',
                                                  icon: Icons.timelapse,
                                                  width: width),
                                              _Metric(
                                                  label: 'Not started',
                                                  value:
                                                      '${employee['not_started'] ?? 0}',
                                                  icon: Icons
                                                      .pause_circle_outline,
                                                  color: AppTheme.textSecondary,
                                                  width: width),
                                            ]);
                                      }),
                                      const SizedBox(height: 18),
                                      _LearningSnapshot(employee: employee),
                                      const SizedBox(height: 24),
                                      const Text('Course breakdown',
                                          style: TextStyle(
                                              fontSize: 18,
                                              fontWeight: FontWeight.w800)),
                                      const SizedBox(height: 6),
                                      Text(
                                          '${assignments.length} courses within your current reporting scope. Select a course for module results.',
                                          style: const TextStyle(
                                              fontSize: 12,
                                              color: AppTheme.textSecondary)),
                                      const SizedBox(height: 14),
                                      _EmployeeCourseTable(
                                          assignments: assignments,
                                          onOpenAssignment: onOpenAssignment),
                                      const SizedBox(height: 16),
                                      const Text(
                                          'Completion counts completed courses. Overdue and due soon are deadline flags. Scores exclude unattempted modules.',
                                          style: TextStyle(
                                              fontSize: 11,
                                              color: AppTheme.textSecondary)),
                                    ])),
                          ]));
                    })),
          ]),
        ),
      );
}

class _LearningSnapshot extends StatelessWidget {
  final Map<String, dynamic> employee;
  const _LearningSnapshot({required this.employee});

  @override
  Widget build(BuildContext context) {
    final completion =
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Overall completion',
          style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
      const SizedBox(height: 8),
      Row(children: [
        Text(_percent(employee['completion_rate']),
            style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800)),
        const SizedBox(width: 18),
        Expanded(child: _Completion(row: employee, showLabel: false)),
      ]),
      const SizedBox(height: 8),
      Text(
          '${employee['completed'] ?? 0} of ${employee['assigned'] ?? 0} courses completed',
          style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
    ]);
    final quiz =
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Average quiz score',
          style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
      const SizedBox(height: 4),
      Text(_percent(employee['average_score']),
          style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800)),
      const SizedBox(height: 4),
      Text('Last activity: ${_date(employee['last_learner_activity_at'])}',
          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
    ]);
    final failures = _number(employee['repeated_failures']);
    return _Surface(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Learning snapshot',
          style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800)),
      const SizedBox(height: 18),
      LayoutBuilder(
          builder: (context, constraints) => constraints.maxWidth >= 560
              ? Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
                  Expanded(flex: 3, child: completion),
                  Container(
                      width: 1,
                      height: 85,
                      margin: const EdgeInsets.symmetric(horizontal: 24),
                      color: const Color(0xFFE3EBF5)),
                  Expanded(flex: 2, child: quiz),
                ])
              : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  completion,
                  const SizedBox(height: 18),
                  quiz,
                ])),
      const SizedBox(height: 20),
      Wrap(spacing: 8, runSpacing: 8, children: [
        _SignalChip(
            text: '${_number(employee['overdue'])} overdue',
            icon: Icons.event_busy_outlined,
            color: _number(employee['overdue']) > 0
                ? _red
                : AppTheme.textSecondary),
        _SignalChip(
            text: '${_number(employee['due_soon'])} due soon',
            icon: Icons.schedule_outlined,
            color: _number(employee['due_soon']) > 0
                ? _amber
                : AppTheme.textSecondary),
        _SignalChip(
            text: '${_number(employee['inactive'])} inactive courses',
            tooltip:
                'Incomplete courses with no learning activity for 14+ days.',
            icon: Icons.pause_circle_outline,
            color: _number(employee['inactive']) > 0
                ? _amber
                : AppTheme.textSecondary),
        _SignalChip(
            text:
                'Repeated quiz failures · $failures ${failures == 1 ? 'course' : 'courses'}',
            icon: failures > 0
                ? Icons.warning_amber_rounded
                : Icons.fact_check_outlined,
            color: failures > 0 ? _amber : AppTheme.textSecondary),
      ]),
    ]));
  }
}

class _SignalChip extends StatelessWidget {
  final String text;
  final String? tooltip;
  final IconData icon;
  final Color color;
  const _SignalChip(
      {required this.text,
      required this.icon,
      required this.color,
      this.tooltip});
  @override
  Widget build(BuildContext context) => Tooltip(
      message: tooltip ?? text,
      child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
          decoration: BoxDecoration(
              color: color.withOpacity(0.07),
              borderRadius: BorderRadius.circular(10)),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, color: color, size: 17),
            const SizedBox(width: 7),
            Flexible(
                child: Text(text,
                    style: TextStyle(
                        color: color,
                        fontSize: 12,
                        fontWeight: FontWeight.w600))),
          ])));
}

class _EmployeeCourseTable extends StatelessWidget {
  final List<Map<String, dynamic>> assignments;
  final ValueChanged<String> onOpenAssignment;
  const _EmployeeCourseTable(
      {required this.assignments, required this.onOpenAssignment});

  Color _statusColor(dynamic status) => status == 'completed'
      ? _green
      : status == 'overdue'
          ? _red
          : status == 'pending'
              ? AppTheme.textSecondary
              : AppTheme.primaryBlue;

  Widget _progress(Map<String, dynamic> row) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(
            '${row['completed_modules'] ?? 0}/${row['total_modules'] ?? 0} modules',
            style:
                const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
        const SizedBox(height: 6),
        _Completion(row: {'completion_rate': row['completion_percent']}),
      ]);

  @override
  Widget build(BuildContext context) =>
      LayoutBuilder(builder: (context, constraints) {
        final wide = constraints.maxWidth >= 700;
        return Container(
            clipBehavior: Clip.antiAlias,
            decoration: BoxDecoration(
                border: Border.all(color: const Color(0xFFE3EBF5)),
                borderRadius: BorderRadius.circular(12)),
            child: Column(children: [
              if (wide)
                Container(
                    color: const Color(0xFFF3F7FC),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 13),
                    child: const Row(children: [
                      Expanded(flex: 5, child: Text('COURSE', style: _header)),
                      Expanded(
                          flex: 4, child: Text('PROGRESS', style: _header)),
                      Expanded(flex: 2, child: Text('QUIZ', style: _header)),
                      Expanded(
                          flex: 3, child: Text('DUE DATE', style: _header)),
                      Expanded(flex: 3, child: Text('STATUS', style: _header)),
                      SizedBox(width: 20),
                    ])),
              if (assignments.isEmpty)
                const Padding(
                    padding: EdgeInsets.all(24),
                    child: Text('No courses in the current reporting scope.')),
              for (final row in assignments)
                Material(
                    color: Colors.white,
                    child: InkWell(
                        onTap: () =>
                            onOpenAssignment(row['assignment_id'].toString()),
                        child: Container(
                            padding: const EdgeInsets.all(16),
                            decoration: const BoxDecoration(
                                border: Border(
                                    bottom:
                                        BorderSide(color: Color(0xFFE6EDF5)))),
                            child: wide
                                ? Row(children: [
                                    Expanded(
                                        flex: 5,
                                        child: Padding(
                                            padding: const EdgeInsets.only(
                                                right: 12),
                                            child: Text('${row['course_name']}',
                                                style: const TextStyle(
                                                    fontSize: 13,
                                                    fontWeight:
                                                        FontWeight.w700)))),
                                    Expanded(
                                        flex: 4,
                                        child: Padding(
                                            padding: const EdgeInsets.only(
                                                right: 20),
                                            child: _progress(row))),
                                    Expanded(
                                        flex: 2,
                                        child: Text(
                                            _percent(row['average_score']),
                                            style:
                                                const TextStyle(fontSize: 12))),
                                    Expanded(
                                        flex: 3,
                                        child: Text(_date(row['deadline']),
                                            style:
                                                const TextStyle(fontSize: 12))),
                                    Expanded(
                                        flex: 3,
                                        child: Align(
                                            alignment: Alignment.centerLeft,
                                            child: _Badge(
                                                text:
                                                    _statusLabel(row['status']),
                                                color: _statusColor(
                                                    row['status'])))),
                                    const Icon(Icons.chevron_right,
                                        size: 20,
                                        color: AppTheme.textSecondary),
                                  ])
                                : Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                        Row(children: [
                                          Expanded(
                                              child: Text(
                                                  '${row['course_name']}',
                                                  style: const TextStyle(
                                                      fontWeight:
                                                          FontWeight.w700))),
                                          const Icon(Icons.chevron_right,
                                              size: 20,
                                              color: AppTheme.textSecondary),
                                        ]),
                                        const SizedBox(height: 12),
                                        _progress(row),
                                        const SizedBox(height: 12),
                                        Wrap(
                                            spacing: 12,
                                            runSpacing: 8,
                                            crossAxisAlignment:
                                                WrapCrossAlignment.center,
                                            children: [
                                              Text(
                                                  'Quiz ${_percent(row['average_score'])}',
                                                  style: const TextStyle(
                                                      fontSize: 12)),
                                              Text(
                                                  'Due ${_date(row['deadline'])}',
                                                  style: const TextStyle(
                                                      fontSize: 12)),
                                              _Badge(
                                                  text: _statusLabel(
                                                      row['status']),
                                                  color: _statusColor(
                                                      row['status'])),
                                            ]),
                                      ])))),
            ]));
      });
}

const _green = Color(0xFF008B73);
const _red = Color(0xFFCE3546);
const _amber = Color(0xFFAA7000);
const _header = TextStyle(
    fontSize: 10, fontWeight: FontWeight.w800, color: AppTheme.textSecondary);

class _Surface extends StatelessWidget {
  final Widget child;
  const _Surface({required this.child});
  @override
  Widget build(BuildContext context) => Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(color: const Color(0xFFE3EBF5)),
          borderRadius: BorderRadius.circular(16)),
      child: child);
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;
  final double width;
  const _Metric(
      {required this.label,
      required this.value,
      required this.icon,
      this.color = AppTheme.primaryBlue,
      this.width = 176});
  @override
  Widget build(BuildContext context) => Container(
      width: width,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
          border: Border.all(color: const Color(0xFFE2EAF4)),
          borderRadius: BorderRadius.circular(12)),
      child: Row(children: [
        Icon(icon, color: color, size: 24),
        const SizedBox(width: 12),
        Expanded(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label,
              style:
                  const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
          Text(value,
              style:
                  const TextStyle(fontSize: 23, fontWeight: FontWeight.w800)),
        ])),
      ]));
}

class _Identity extends StatelessWidget {
  final Map<String, dynamic> row;
  final bool prominent;
  const _Identity({required this.row, this.prominent = false});
  @override
  Widget build(BuildContext context) {
    final name = row['employee_name']?.toString() ?? 'Employee';
    final initials = name
        .trim()
        .split(RegExp(r'\s+'))
        .where((part) => part.isNotEmpty)
        .take(2)
        .map((part) => part[0])
        .join()
        .toUpperCase();
    return Row(children: [
      CircleAvatar(
          radius: prominent ? 28 : 21,
          backgroundColor: AppTheme.brandBlue100,
          child: Text(initials,
              style: TextStyle(
                  fontSize: prominent ? 18 : 13,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.primaryBlue))),
      const SizedBox(width: 10),
      Expanded(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(name,
            style: TextStyle(
                fontWeight: FontWeight.w800, fontSize: prominent ? 18 : null)),
        Text(row['department']?.toString() ?? 'No department',
            style:
                const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
      ])),
    ]);
  }
}

class _Completion extends StatelessWidget {
  final Map<String, dynamic> row;
  final bool showLabel;
  const _Completion({required this.row, this.showLabel = true});
  @override
  Widget build(BuildContext context) {
    final value = (row['completion_rate'] as num?)?.toDouble() ?? 0;
    return Row(children: [
      Expanded(
          child: ClipRRect(
              borderRadius: BorderRadius.circular(5),
              child: LinearProgressIndicator(
                  value: value.clamp(0, 100) / 100,
                  minHeight: 7,
                  color: value >= 100 ? _green : const Color(0xFF3076D9),
                  backgroundColor: const Color(0xFFE9EEF5)))),
      if (showLabel) const SizedBox(width: 10),
      if (showLabel)
        Text(_percent(value),
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
    ]);
  }
}

class _Badge extends StatelessWidget {
  final String text;
  final Color color;
  const _Badge({required this.text, required this.color});
  @override
  Widget build(BuildContext context) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
          color: color.withOpacity(0.09),
          borderRadius: BorderRadius.circular(20)),
      child: Text(text,
          style: TextStyle(
              color: color, fontSize: 11, fontWeight: FontWeight.w700)));
}

class _Select extends StatelessWidget {
  final String label;
  final String value;
  final Map<String, String> items;
  final ValueChanged<String> onChanged;
  const _Select(
      {required this.label,
      required this.value,
      required this.items,
      required this.onChanged});
  @override
  Widget build(BuildContext context) => SizedBox(
      width: 195,
      child: DropdownButtonFormField<String>(
          value: value,
          isExpanded: true,
          decoration: InputDecoration(
              labelText: label,
              isDense: true,
              border: const OutlineInputBorder()),
          items: [
            for (final item in items.entries)
              DropdownMenuItem(
                  value: item.key,
                  child: Text(item.value, overflow: TextOverflow.ellipsis))
          ],
          onChanged: (value) {
            if (value != null) onChanged(value);
          }));
}

Map<String, dynamic> _map(dynamic value) =>
    value is Map ? Map<String, dynamic>.from(value) : {};
List<Map<String, dynamic>> _rows(dynamic value) =>
    value is List ? value.map(_map).toList() : [];
int _number(dynamic value) => value is num ? value.toInt() : 0;
String _percent(dynamic value) {
  if (value is! num) return '—';
  return '${value.toStringAsFixed(value == value.roundToDouble() ? 0 : 1)}%';
}

String _statusLabel(dynamic value) =>
    const {
      'completed': 'Completed',
      'started': 'In progress',
      'pending': 'Not started',
      'overdue': 'Overdue'
    }[value] ??
    'Unknown';
String _date(dynamic value) {
  final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
  if (date == null) return 'Not recorded';
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec'
  ];
  return '${date.day} ${months[date.month - 1]} ${date.year}';
}
