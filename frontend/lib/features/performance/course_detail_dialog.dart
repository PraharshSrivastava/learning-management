import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'package:frontend/core/theme/app_theme.dart';

/// Trainer view of a course's aggregate outcomes and module learning path.
class CourseDetailDialog extends StatelessWidget {
  final Future<Map<String, dynamic>> detail;
  final VoidCallback onViewLearners;

  const CourseDetailDialog({
    super.key,
    required this.detail,
    required this.onViewLearners,
  });

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    return Dialog(
      insetPadding: const EdgeInsets.all(16),
      backgroundColor: Colors.transparent,
      child: SizedBox(
        width: math.min(1040, size.width - 32),
        height: math.min(800, size.height - 32),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(24),
          child: Material(
            color: Colors.white,
            child: FutureBuilder<Map<String, dynamic>>(
              future: detail,
              builder: (context, snapshot) {
                if (snapshot.hasError) {
                  return _StateMessage(
                    icon: Icons.error_outline,
                    message: 'Could not load course detail',
                    detail: snapshot.error.toString(),
                  );
                }
                if (!snapshot.hasData) {
                  return const Center(child: CircularProgressIndicator());
                }
                return _CourseContent(
                  data: snapshot.data!,
                  onViewLearners: onViewLearners,
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _CourseContent extends StatelessWidget {
  final Map<String, dynamic> data;
  final VoidCallback onViewLearners;

  const _CourseContent({required this.data, required this.onViewLearners});

  @override
  Widget build(BuildContext context) {
    final course = _map(data['course']);
    final modules = _list(data['modules']);
    return Column(children: [
      Container(
        padding: const EdgeInsets.fromLTRB(28, 22, 18, 22),
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFFEAF4FC), Colors.white],
          ),
        ),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
              child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('COURSE DETAIL',
                  style: TextStyle(
                      color: AppTheme.brandBlue700,
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.4)),
              const SizedBox(height: 8),
              Text(course['course_name']?.toString() ?? 'Course',
                  style: const TextStyle(
                      color: AppTheme.textBlack,
                      fontSize: 27,
                      fontWeight: FontWeight.w800)),
            ],
          )),
          IconButton(
            tooltip: 'Close course detail',
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.close),
          ),
        ]),
      ),
      Expanded(
          child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: LayoutBuilder(builder: (context, constraints) {
          final summary = _CourseSummary(
            course: course,
            onViewLearners: onViewLearners,
          );
          final path = _ModulePath(modules: modules);
          if (constraints.maxWidth < 690) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [summary, const SizedBox(height: 22), path],
            );
          }
          return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(width: 215, child: summary),
            const SizedBox(width: 26),
            Expanded(child: path),
          ]);
        }),
      )),
    ]);
  }
}

class _CourseSummary extends StatelessWidget {
  final Map<String, dynamic> course;
  final VoidCallback onViewLearners;

  const _CourseSummary({required this.course, required this.onViewLearners});

  @override
  Widget build(BuildContext context) {
    final rate = _int(course['completion_rate']).clamp(0, 100);
    return LayoutBuilder(builder: (context, constraints) {
      final compact = constraints.maxWidth >= 290;
      final ring = SizedBox(
        width: compact ? 94 : 126,
        height: compact ? 94 : 126,
        child: Stack(alignment: Alignment.center, children: [
          Positioned.fill(
              child: Padding(
            padding: const EdgeInsets.all(4),
            child: CircularProgressIndicator(
              value: rate / 100,
              strokeWidth: 9,
              backgroundColor: AppTheme.brandBlue100,
              color: AppTheme.accentBlue,
            ),
          )),
          Column(mainAxisSize: MainAxisSize.min, children: [
            Text('$rate%',
                style: const TextStyle(
                    fontSize: 27,
                    fontWeight: FontWeight.w800,
                    color: AppTheme.textBlack)),
            const Text('complete',
                style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
          ]),
        ]),
      );
      final stats = [
        ('Assigned', course['assigned'], AppTheme.primaryBlue),
        ('Completed', course['completed'], AppTheme.accentGreen),
        ('Overdue', course['overdue'], AppTheme.accentRed),
      ];
      return Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: const Color(0xFFF8FBFE),
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: const Color(0xFFDDE6F1)),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (compact)
            Row(children: [
              ring,
              const SizedBox(width: 18),
              Expanded(
                  child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final stat in stats)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 3),
                      child: Text('${_int(stat.$2)} ${stat.$1.toLowerCase()}',
                          style: TextStyle(
                              color: stat.$3, fontWeight: FontWeight.w700)),
                    ),
                ],
              )),
            ])
          else ...[
            Center(child: ring),
            const SizedBox(height: 20),
            for (final stat in stats)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 7),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('${_int(stat.$2)}',
                          style: TextStyle(
                              fontSize: 22,
                              fontWeight: FontWeight.w800,
                              color: stat.$3)),
                      Text(stat.$1.toLowerCase(),
                          style:
                              const TextStyle(color: AppTheme.textSecondary)),
                    ]),
              ),
          ],
          const SizedBox(height: 18),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: onViewLearners,
              icon: const Icon(Icons.people_outline, size: 18),
              label: const Text('View learners'),
            ),
          ),
        ]),
      );
    });
  }
}

class _ModulePath extends StatelessWidget {
  final List<dynamic> modules;

  const _ModulePath({required this.modules});

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Module outcomes',
              style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textBlack)),
          const SizedBox(height: 4),
          Text('${modules.length} modules in this course',
              style:
                  const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 16),
          if (modules.isEmpty)
            const Text('No module outcomes are available for this course.',
                style: TextStyle(color: AppTheme.textSecondary)),
          for (var index = 0; index < modules.length; index++)
            _ModuleStep(
              module: _map(modules[index]),
              isLast: index == modules.length - 1,
            ),
        ],
      );
}

class _ModuleStep extends StatelessWidget {
  final Map<String, dynamic> module;
  final bool isLast;

  const _ModuleStep({required this.module, required this.isLast});

  @override
  Widget build(BuildContext context) {
    final assigned = _int(module['assigned']);
    final watched = _int(module['watched']);
    final rate = assigned == 0 ? 0.0 : (watched / assigned).clamp(0.0, 1.0);
    final hasQuiz = _int(module['num_questions']) > 0;
    return IntrinsicHeight(
        child: Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
            width: 34,
            child: Column(children: [
              CircleAvatar(
                radius: 16,
                backgroundColor: AppTheme.accentBlue,
                child: Text('${_int(module['module_number'])}',
                    style: const TextStyle(
                        color: Colors.white, fontWeight: FontWeight.w800)),
              ),
              if (!isLast)
                Expanded(
                    child: Container(width: 2, color: AppTheme.brandBlue100)),
            ])),
        const SizedBox(width: 12),
        Expanded(
            child: Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(13),
            border: Border.all(color: const Color(0xFFDDE6F1)),
          ),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(module['title']?.toString() ?? 'Module',
                style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    color: AppTheme.textBlack)),
            const SizedBox(height: 10),
            Row(children: [
              const Icon(Icons.play_circle_outline,
                  size: 17, color: AppTheme.primaryBlue),
              const SizedBox(width: 5),
              Text('$watched/$assigned watched',
                  style: const TextStyle(
                      fontSize: 12, color: AppTheme.textSecondary)),
            ]),
            const SizedBox(height: 6),
            LinearProgressIndicator(
              value: rate,
              minHeight: 6,
              borderRadius: BorderRadius.circular(6),
              color: AppTheme.accentBlue,
              backgroundColor: AppTheme.brandBlue100,
            ),
            const SizedBox(height: 12),
            Wrap(spacing: 10, runSpacing: 8, children: [
              _ModuleMeta(
                icon:
                    hasQuiz ? Icons.quiz_outlined : Icons.remove_circle_outline,
                label: hasQuiz ? '${_int(module['passed'])} passed' : 'No quiz',
                color: hasQuiz ? AppTheme.accentGreen : AppTheme.textSecondary,
              ),
              _ModuleMeta(
                icon: Icons.replay_outlined,
                label: '${_int(module['attempts'])} attempts',
              ),
              _ModuleMeta(
                icon: Icons.bar_chart_rounded,
                label: 'Average ${_score(module['average_score'])}',
              ),
            ]),
          ]),
        )),
      ],
    ));
  }
}

class _ModuleMeta extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color? color;

  const _ModuleMeta({required this.icon, required this.label, this.color});

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 15, color: color ?? AppTheme.textSecondary),
          const SizedBox(width: 4),
          Text(label,
              style: TextStyle(
                  fontSize: 11,
                  color: color ?? AppTheme.textSecondary,
                  fontWeight:
                      color == null ? FontWeight.normal : FontWeight.w700)),
        ],
      );
}

class _StateMessage extends StatelessWidget {
  final IconData icon;
  final String message, detail;

  const _StateMessage({
    required this.icon,
    required this.message,
    required this.detail,
  });

  @override
  Widget build(BuildContext context) => Center(
          child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 36, color: AppTheme.accentRed),
          const SizedBox(height: 12),
          Text(message, style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 6),
          Text(detail, textAlign: TextAlign.center),
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close')),
        ]),
      ));
}

Map<String, dynamic> _map(Object? value) =>
    value is Map<String, dynamic> ? value : <String, dynamic>{};
List<dynamic> _list(Object? value) => value is List ? value : const [];
int _int(Object? value) =>
    value is num ? value.toInt() : int.tryParse('$value') ?? 0;
String _score(Object? value) =>
    value is num ? '${value.toStringAsFixed(1)}%' : '—';
