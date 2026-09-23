import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'package:frontend/core/theme/app_theme.dart';

/// A focused learner journey for one employee-course assignment.
class AssignmentDetailDialog extends StatelessWidget {
  final Future<Map<String, dynamic>> detail;

  const AssignmentDetailDialog({super.key, required this.detail});

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    return Dialog(
      insetPadding: const EdgeInsets.all(16),
      backgroundColor: Colors.transparent,
      child: SizedBox(
        width: math.min(1080, size.width - 32),
        height: math.min(800, size.height - 32),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(24),
          child: Material(
            color: Colors.white,
            child: FutureBuilder<Map<String, dynamic>>(
              future: detail,
              builder: (context, snapshot) {
                if (snapshot.hasError) {
                  return _Message(
                    icon: Icons.error_outline,
                    title: 'Could not load assignment',
                    detail: snapshot.error.toString(),
                  );
                }
                if (!snapshot.hasData) {
                  return const Center(child: CircularProgressIndicator());
                }
                return _AssignmentContent(data: snapshot.data!);
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _AssignmentContent extends StatelessWidget {
  final Map<String, dynamic> data;

  const _AssignmentContent({required this.data});

  @override
  Widget build(BuildContext context) {
    final row = _map(data['assignment']);
    final modules = _list(data['modules']);
    final attempts = _list(data['attempts']);
    final titles = {
      for (final module in modules)
        _map(module)['module_id']?.toString():
            _map(module)['title']?.toString() ?? 'Module'
    };
    final progress = _int(row['completion_percent']).clamp(0, 100);
    final status = _status(row);
    final statusColor = status == 'Overdue'
        ? AppTheme.accentRed
        : status == 'Completed'
            ? const Color(0xFF087F68)
            : AppTheme.primaryBlue;

    return Column(children: [
      Expanded(
        child: SingleChildScrollView(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(
              padding: const EdgeInsets.fromLTRB(28, 22, 20, 24),
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFFEAF4FC), Color(0xFFFFFFFF)],
                ),
              ),
              child: LayoutBuilder(builder: (context, constraints) {
                final identity = Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('ASSIGNMENT DETAIL',
                        style: TextStyle(
                            color: AppTheme.brandBlue700,
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1.4)),
                    const SizedBox(height: 10),
                    Text(row['employee_name']?.toString() ?? 'Learner',
                        style: const TextStyle(
                            fontSize: 29,
                            fontWeight: FontWeight.w800,
                            color: AppTheme.textBlack)),
                    Text(row['course_name']?.toString() ?? 'Course',
                        style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.primaryBlue)),
                    const SizedBox(height: 7),
                    Text(
                        '${_int(row['completed_modules'])}/${_int(row['total_modules'])} modules completed',
                        style: const TextStyle(color: AppTheme.textSecondary)),
                  ],
                );
                final outcome = Row(mainAxisSize: MainAxisSize.min, children: [
                  _StatusPill(label: status, color: statusColor),
                  const SizedBox(width: 14),
                  SizedBox(
                    width: 64,
                    height: 64,
                    child: Stack(alignment: Alignment.center, children: [
                      Positioned.fill(
                        child: Padding(
                          padding: const EdgeInsets.all(3),
                          child: CircularProgressIndicator(
                              value: progress / 100,
                              strokeWidth: 7,
                              backgroundColor: AppTheme.brandBlue100,
                              color: statusColor),
                        ),
                      ),
                      Text('$progress%',
                          style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              color: AppTheme.textBlack)),
                    ]),
                  ),
                ]);
                final close = IconButton(
                    tooltip: 'Close assignment detail',
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close));
                if (constraints.maxWidth < 570) {
                  return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(child: identity),
                              close,
                            ]),
                        const SizedBox(height: 14),
                        outcome,
                      ]);
                }
                return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: identity),
                      outcome,
                      close,
                    ]);
              }),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    LayoutBuilder(builder: (context, constraints) {
                      final width = constraints.maxWidth >= 700
                          ? (constraints.maxWidth - 20) / 3
                          : constraints.maxWidth >= 420
                              ? (constraints.maxWidth - 10) / 2
                              : constraints.maxWidth;
                      return Wrap(spacing: 10, runSpacing: 10, children: [
                        _Metric(
                            width: width,
                            icon: Icons.event_outlined,
                            label: 'Due date',
                            value: _date(row['deadline'])),
                        _Metric(
                            width: width,
                            icon: Icons.schedule_outlined,
                            label: 'Last learner activity',
                            value: _date(row['last_learner_activity_at'])),
                        _Metric(
                            width: width,
                            icon: Icons.bar_chart_rounded,
                            label: 'Average quiz score',
                            value: _score(row['average_score'])),
                      ]);
                    }),
                    const SizedBox(height: 18),
                    LayoutBuilder(builder: (context, constraints) {
                      final path = _Panel(
                        title: 'Learning path',
                        subtitle:
                            '${modules.length} modules in this assignment',
                        child: modules.isEmpty
                            ? const Text(
                                'No modules are available for this course.')
                            : Column(children: [
                                for (var index = 0;
                                    index < modules.length;
                                    index++)
                                  _ModuleStep(
                                      module: _map(modules[index]),
                                      isLast: index == modules.length - 1),
                              ]),
                      );
                      final performance = _Panel(
                        title: 'Quiz performance',
                        subtitle: '${attempts.length} recorded attempts',
                        child: attempts.isEmpty
                            ? const Text('No quiz attempts recorded yet.',
                                style: TextStyle(color: AppTheme.textSecondary))
                            : Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  if (attempts.length > 6)
                                    const Padding(
                                      padding: EdgeInsets.only(bottom: 8),
                                      child: Text('Latest attempts',
                                          style: TextStyle(
                                              color: AppTheme.textSecondary,
                                              fontSize: 12)),
                                    ),
                                  for (final attempt in attempts.take(20))
                                    _AttemptRow(
                                        attempt: _map(attempt),
                                        title: titles[_map(attempt)['module_id']
                                                ?.toString()] ??
                                            'Module',
                                        compact: attempts.length > 6),
                                  if (attempts.length > 20)
                                    Padding(
                                      padding: const EdgeInsets.only(top: 8),
                                      child: Text(
                                          'Showing the latest 20 of ${attempts.length} attempts.',
                                          style: const TextStyle(
                                              fontSize: 12,
                                              color: AppTheme.textSecondary)),
                                    ),
                                  const SizedBox(height: 8),
                                  const Text(
                                    'History is available from the reporting upgrade onward.',
                                    style: TextStyle(
                                        fontSize: 11,
                                        color: AppTheme.textSecondary),
                                  ),
                                ],
                              ),
                      );
                      if (constraints.maxWidth < 760) {
                        return Column(children: [
                          path,
                          const SizedBox(height: 12),
                          performance,
                        ]);
                      }
                      return Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(child: path),
                            const SizedBox(width: 12),
                            Expanded(child: performance),
                          ]);
                    }),
                    const SizedBox(height: 14),
                    _Panel(
                      title: 'Key dates',
                      child: LayoutBuilder(builder: (context, constraints) {
                        final dates = [
                          ('Assigned', row['assigned_at']),
                          ('Started', row['started_at']),
                          ('Completed', row['completed_at']),
                        ];
                        if (constraints.maxWidth < 520) {
                          return Column(children: [
                            for (final date in dates)
                              Padding(
                                  padding:
                                      const EdgeInsets.symmetric(vertical: 5),
                                  child: _DateStep(date.$1, date.$2)),
                          ]);
                        }
                        return Row(children: [
                          for (final date in dates)
                            Expanded(child: _DateStep(date.$1, date.$2)),
                        ]);
                      }),
                    ),
                  ]),
            ),
          ]),
        ),
      ),
    ]);
  }
}

class _Metric extends StatelessWidget {
  final double width;
  final IconData icon;
  final String label, value;

  const _Metric(
      {required this.width,
      required this.icon,
      required this.label,
      required this.value});

  @override
  Widget build(BuildContext context) => Container(
        width: width,
        padding: const EdgeInsets.all(14),
        decoration: _card(),
        child: Row(children: [
          CircleAvatar(
              radius: 20,
              backgroundColor: AppTheme.brandBlue100,
              child: Icon(icon, color: AppTheme.primaryBlue, size: 20)),
          const SizedBox(width: 10),
          Expanded(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                      fontSize: 12, color: AppTheme.textSecondary)),
              Text(value,
                  style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                      color: AppTheme.textBlack)),
            ]),
          ),
        ]),
      );
}

class _Panel extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget child;

  const _Panel({required this.title, this.subtitle, required this.child});

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: _card(),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title,
              style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textBlack)),
          if (subtitle != null)
            Text(subtitle!,
                style: const TextStyle(
                    fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 13),
          child,
        ]),
      );
}

class _ModuleStep extends StatelessWidget {
  final Map<String, dynamic> module;
  final bool isLast;

  const _ModuleStep({required this.module, required this.isLast});

  @override
  Widget build(BuildContext context) {
    final watched = module['video_watched'] == true;
    final hasQuiz = _int(module['num_questions']) > 0;
    final passed = module['quiz_passed'] == true;
    final complete = watched && (!hasQuiz || passed);
    final color = complete ? const Color(0xFF087F68) : AppTheme.accentOrange;
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SizedBox(
        width: 34,
        child: Column(children: [
          CircleAvatar(
            radius: 16,
            backgroundColor:
                complete ? const Color(0xFFE6F7F2) : AppTheme.accentLightOrange,
            child: complete
                ? Icon(Icons.check, size: 18, color: color)
                : Text('${_int(module['module_number'])}',
                    style:
                        TextStyle(color: color, fontWeight: FontWeight.w800)),
          ),
          if (!isLast)
            Container(width: 2, height: 68, color: AppTheme.lightGray),
        ]),
      ),
      const SizedBox(width: 10),
      Expanded(
        child: Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(12),
          decoration: _card(radius: 12),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(module['title']?.toString() ?? 'Module',
                style: const TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 7),
            Wrap(spacing: 8, runSpacing: 5, children: [
              _Meta(Icons.play_circle_outline,
                  watched ? 'Video watched' : 'Video pending'),
              _Meta(
                  Icons.quiz_outlined,
                  !hasQuiz
                      ? 'No quiz'
                      : passed
                          ? 'Quiz passed'
                          : 'Quiz pending'),
              if (hasQuiz)
                _Meta(Icons.replay_outlined,
                    '${_int(module['attempt_count'])} attempts'),
              if (module['latest_score'] != null)
                _Meta(Icons.bar_chart, _score(module['latest_score'])),
            ]),
          ]),
        ),
      ),
    ]);
  }
}

class _AttemptRow extends StatelessWidget {
  final Map<String, dynamic> attempt;
  final String title;
  final bool compact;

  const _AttemptRow(
      {required this.attempt, required this.title, required this.compact});

  @override
  Widget build(BuildContext context) {
    final passed = attempt['passed'] == true;
    final color = passed ? const Color(0xFF087F68) : AppTheme.accentRed;
    final score = attempt['score'];
    final fraction = score is num ? (score / 100).clamp(0.0, 1.0) : 0.0;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: _card(radius: 11),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w700)),
              Text(_dateTime(attempt['occurred_at']),
                  style: const TextStyle(
                      fontSize: 11, color: AppTheme.textSecondary)),
            ]),
          ),
          const SizedBox(width: 6),
          Text(_score(score),
              style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(width: 7),
          _StatusPill(label: passed ? 'Passed' : 'Failed', color: color),
        ]),
        if (!compact) ...[
          const SizedBox(height: 8),
          LinearProgressIndicator(
            value: fraction,
            minHeight: 6,
            borderRadius: BorderRadius.circular(6),
            color: color,
            backgroundColor: AppTheme.lightGray,
          ),
        ],
      ]),
    );
  }
}

class _DateStep extends StatelessWidget {
  final String label;
  final Object? date;

  const _DateStep(this.label, this.date);

  @override
  Widget build(BuildContext context) {
    final available = date != null;
    return Column(children: [
      CircleAvatar(
        radius: 16,
        backgroundColor:
            available ? AppTheme.brandBlue100 : AppTheme.surfaceSecondary,
        child: Icon(available ? Icons.check : Icons.more_horiz,
            size: 18, color: available ? AppTheme.primaryBlue : AppTheme.gray),
      ),
      const SizedBox(height: 5),
      Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
      Text(available ? _date(date) : 'Not yet',
          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
    ]);
  }
}

class _Meta extends StatelessWidget {
  final IconData icon;
  final String label;

  const _Meta(this.icon, this.label);

  @override
  Widget build(BuildContext context) =>
      Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 15, color: AppTheme.textSecondary),
        const SizedBox(width: 3),
        Text(label,
            style:
                const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
      ]);
}

class _StatusPill extends StatelessWidget {
  final String label;
  final Color color;

  const _StatusPill({required this.label, required this.color});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
            color: color.withOpacity(0.10),
            borderRadius: BorderRadius.circular(20)),
        child: Text(label,
            style: TextStyle(
                color: color, fontSize: 11, fontWeight: FontWeight.w800)),
      );
}

class _Message extends StatelessWidget {
  final IconData icon;
  final String title, detail;

  const _Message(
      {required this.icon, required this.title, required this.detail});

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 34, color: AppTheme.accentRed),
            const SizedBox(height: 12),
            Text(title,
                style:
                    const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text(detail, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Close')),
          ]),
        ),
      );
}

BoxDecoration _card({double radius = 14}) => BoxDecoration(
      color: Colors.white,
      border: Border.all(color: AppTheme.lightGray),
      borderRadius: BorderRadius.circular(radius),
    );

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
      : '${_date(value)} ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
}

String _status(Map<String, dynamic> row) {
  if (row['status'] == 'completed') return 'Completed';
  if (row['status'] == 'overdue') return 'Overdue';
  if (row['due_soon'] == true) return 'Due soon';
  if (row['status'] == 'started') return 'In progress';
  return 'Pending';
}
