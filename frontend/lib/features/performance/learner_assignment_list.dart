import 'package:flutter/material.dart';

import 'package:frontend/core/theme/app_theme.dart';

/// Scannable assignment rows for the trainer's Learners report.
class LearnerAssignmentList extends StatelessWidget {
  final List<Map<String, dynamic>> rows;
  final ValueChanged<String> onOpenAssignment;

  const LearnerAssignmentList({
    super.key,
    required this.rows,
    required this.onOpenAssignment,
  });

  @override
  Widget build(BuildContext context) => LayoutBuilder(
        builder: (context, constraints) {
          final table = constraints.maxWidth >= 940;
          return Column(children: [
            if (table) const _TableHeader(),
            for (final row in rows)
              table
                  ? _TableRow(
                      row: row,
                      onTap: () => onOpenAssignment(
                          row['assignment_id']?.toString() ?? ''),
                    )
                  : _CompactRow(
                      row: row,
                      onTap: () => onOpenAssignment(
                          row['assignment_id']?.toString() ?? ''),
                    ),
          ]);
        },
      );
}

class _TableHeader extends StatelessWidget {
  const _TableHeader();

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: const Color(0xFFF3F7FC),
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Row(children: [
          Expanded(flex: 25, child: _HeaderLabel('LEARNER')),
          Expanded(flex: 22, child: _HeaderLabel('COURSE')),
          Expanded(flex: 15, child: _HeaderLabel('PROGRESS')),
          Expanded(flex: 12, child: _HeaderLabel('QUIZ SCORE')),
          Expanded(flex: 14, child: _HeaderLabel('DUE DATE')),
          Expanded(flex: 14, child: _HeaderLabel('LAST ACTIVE')),
          Expanded(flex: 13, child: _HeaderLabel('STATUS')),
          SizedBox(width: 18),
        ]),
      );
}

class _HeaderLabel extends StatelessWidget {
  final String label;
  const _HeaderLabel(this.label);

  @override
  Widget build(BuildContext context) => Text(label,
      overflow: TextOverflow.ellipsis,
      style: const TextStyle(
          fontSize: 10,
          letterSpacing: 0.5,
          color: AppTheme.textSecondary,
          fontWeight: FontWeight.w800));
}

class _TableRow extends StatelessWidget {
  final Map<String, dynamic> row;
  final VoidCallback onTap;

  const _TableRow({required this.row, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final status = _status(row);
    final name = row['employee_name']?.toString() ?? 'Learner';
    return Material(
      color: Colors.white,
      child: InkWell(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: Color(0xFFE6EDF5)))),
          child: Row(children: [
            Expanded(
                flex: 25,
                child: Row(children: [
                  _Avatar(name: name),
                  const SizedBox(width: 10),
                  Expanded(
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                        Text(name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style:
                                const TextStyle(fontWeight: FontWeight.w800)),
                        if ((row['department']?.toString() ?? '').isNotEmpty)
                          Text(row['department'].toString(),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                  fontSize: 11, color: AppTheme.textSecondary)),
                      ])),
                ])),
            Expanded(
                flex: 22,
                child: Text(row['course_name']?.toString() ?? 'Course',
                    maxLines: 2, overflow: TextOverflow.ellipsis)),
            Expanded(flex: 15, child: _Progress(row: row)),
            Expanded(
                flex: 12,
                child: Text(_score(row['average_score']),
                    style: const TextStyle(fontWeight: FontWeight.w700))),
            Expanded(
                flex: 14,
                child: Text(_date(row['deadline']),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                        color: status.color == AppTheme.accentRed ||
                                status.color == AppTheme.accentOrange
                            ? status.color
                            : AppTheme.textBlack,
                        fontWeight: FontWeight.w600))),
            Expanded(
                flex: 14,
                child: Text(_date(row['last_learner_activity_at']),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: AppTheme.textSecondary))),
            Expanded(
                flex: 13,
                child: Align(
                    alignment: Alignment.centerLeft,
                    child: _StatusPill(status: status))),
            const Icon(Icons.chevron_right,
                size: 18, color: AppTheme.textSecondary),
          ]),
        ),
      ),
    );
  }
}

class _CompactRow extends StatelessWidget {
  final Map<String, dynamic> row;
  final VoidCallback onTap;

  const _CompactRow({required this.row, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final name = row['employee_name']?.toString() ?? 'Learner';
    final status = _status(row);
    return Material(
      color: Colors.white,
      child: InkWell(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 4),
          decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: Color(0xFFE6EDF5)))),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              _Avatar(name: name),
              const SizedBox(width: 10),
              Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    Text(name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w800)),
                    Text(row['course_name']?.toString() ?? 'Course',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            color: AppTheme.textSecondary, fontSize: 12)),
                  ])),
              _StatusPill(status: status),
              const SizedBox(width: 2),
              const Icon(Icons.chevron_right,
                  size: 18, color: AppTheme.textSecondary),
            ]),
            const SizedBox(height: 10),
            Wrap(
                spacing: 16,
                runSpacing: 6,
                children: [
                  Text(
                      '${_int(row['completed_modules'])}/${_int(row['total_modules'])} modules'),
                  Text('Score ${_score(row['average_score'])}'),
                  Text('Due ${_date(row['deadline'])}'),
                  Text('Active ${_date(row['last_learner_activity_at'])}'),
                ]
                    .map((widget) => DefaultTextStyle.merge(
                        style: const TextStyle(
                            color: AppTheme.textSecondary, fontSize: 11),
                        child: widget))
                    .toList()),
          ]),
        ),
      ),
    );
  }
}

class _Avatar extends StatelessWidget {
  final String name;
  const _Avatar({required this.name});

  @override
  Widget build(BuildContext context) {
    final initials = name
        .trim()
        .split(RegExp(r'\s+'))
        .take(2)
        .where((part) => part.isNotEmpty)
        .map((part) => part[0].toUpperCase())
        .join();
    return CircleAvatar(
      radius: 19,
      backgroundColor: AppTheme.brandBlue100,
      child: Text(initials,
          style: const TextStyle(
              color: AppTheme.primaryBlue,
              fontSize: 12,
              fontWeight: FontWeight.w800)),
    );
  }
}

class _Progress extends StatelessWidget {
  final Map<String, dynamic> row;
  const _Progress({required this.row});

  @override
  Widget build(BuildContext context) {
    final completed = _int(row['completed_modules']);
    final total = _int(row['total_modules']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('$completed/$total modules',
          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700)),
      const SizedBox(height: 6),
      SizedBox(
        width: 82,
        child: LinearProgressIndicator(
          value: total == 0 ? 0 : (completed / total).clamp(0.0, 1.0),
          minHeight: 5,
          borderRadius: BorderRadius.circular(5),
          color: AppTheme.accentBlue,
          backgroundColor: AppTheme.brandBlue100,
        ),
      ),
    ]);
  }
}

class _Status {
  final String label;
  final Color color;
  const _Status(this.label, this.color);
}

_Status _status(Map<String, dynamic> row) {
  if (row['status'] == 'overdue') {
    return const _Status('Overdue', AppTheme.accentRed);
  }
  if (row['due_soon'] == true) {
    return const _Status('Due soon', AppTheme.accentOrange);
  }
  if (row['status'] == 'completed') {
    return const _Status('Completed', AppTheme.accentGreen);
  }
  if (row['repeated_failures'] == true) {
    return const _Status('Quiz difficulty', AppTheme.accentOrange);
  }
  if (row['inactive'] == true) {
    return const _Status('Inactive', AppTheme.accentOrange);
  }
  if (row['status'] == 'started') {
    return const _Status('Started', AppTheme.accentBlue);
  }
  return const _Status('Pending', AppTheme.textSecondary);
}

class _StatusPill extends StatelessWidget {
  final _Status status;
  const _StatusPill({required this.status});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
        decoration: BoxDecoration(
            color: Color.lerp(Colors.white, status.color, 0.1),
            borderRadius: BorderRadius.circular(20)),
        child: Text(status.label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w800,
                color: status.color)),
      );
}

int _int(Object? value) =>
    value is num ? value.toInt() : int.tryParse('$value') ?? 0;
String _score(Object? value) =>
    value is num ? '${value.toStringAsFixed(1)}%' : '—';
String _date(Object? value) {
  final date = DateTime.tryParse(value?.toString() ?? '');
  if (date == null) return '—';
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
