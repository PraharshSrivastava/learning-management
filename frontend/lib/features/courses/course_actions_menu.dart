import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:frontend/core/config/app_constants.dart';
import 'package:frontend/data/models/models.dart';
import 'package:frontend/state/trainer_providers.dart';

final courseAvailabilityFilterProvider = StateProvider<String>((ref) => 'all');

class CourseActionsMenu extends ConsumerStatefulWidget {
  final Course course;
  final Color? foregroundColor;
  final Future<void> Function()? onEnable;
  const CourseActionsMenu(
      {super.key, required this.course, this.onEnable, this.foregroundColor});
  @override
  ConsumerState<CourseActionsMenu> createState() => _CourseActionsMenuState();
}

class _CourseActionsMenuState extends ConsumerState<CourseActionsMenu> {
  bool busy = false;
  @override
  Widget build(BuildContext context) {
    final c = widget.course;
    final owner =
        ref.watch(trainerAuthProvider).trainer?.trainerId == c.trainerId;
    if (!owner) return const SizedBox.shrink();
    final state = c.lifecycleState;
    final actions = <String>[
      if (state == 'active') 'Disable',
      if (state == 'disabled') 'Enable',
      if (c.canDelete) 'Delete',
    ];
    return PopupMenuButton<String>(
      tooltip: 'Course actions',
      enabled: !busy &&
          actions.isNotEmpty &&
          c.generationStatus != 'pending' &&
          c.generationStatus != 'running',
      onSelected: _act,
      itemBuilder: (_) =>
          actions.map((a) => PopupMenuItem(value: a, child: Text(a))).toList(),
      child: Padding(
          padding: const EdgeInsets.all(10),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text(busy ? 'Working…' : 'Actions',
                style: TextStyle(color: widget.foregroundColor)),
            Icon(Icons.expand_more, color: widget.foregroundColor),
          ])),
    );
  }

  Future<void> _act(String action) async {
    if (busy) return;
    final c = widget.course;
    final auth = ref.read(trainerAuthProvider);
    if (action == 'Enable') {
      if (widget.onEnable != null) {
        await widget.onEnable!();
      } else {
        ref.read(selectedCourseProvider.notifier).state = c;
        ref.read(currentTabProvider.notifier).state = 3;
      }
      return;
    }
    setState(() => busy = true);
    bool changed = false;
    try {
      final descriptions = {
        'Disable':
            'Employees lose course access and Observers are suspended. Progress and completed results are preserved. You can Enable this course again.',
        'Delete':
            'Permanently delete this unused course and generated content. The source document is retained. Type DELETE to confirm.',
      };
      String impact = '';
      if (action == 'Disable') {
        final responses = await Future.wait([
          http.get(Uri.parse(AppConstants.courseAssignmentEndpoint(c.courseId)),
              headers: ref.read(trainerAuthHeadersProvider)),
          http.get(
              Uri.parse(
                  '${AppConstants.courseDetailEndpoint(c.courseId)}/observers'),
              headers: ref.read(trainerAuthHeadersProvider)),
        ]);
        if (responses.any((r) => r.statusCode != 200))
          throw Exception(
              'Could not load the action preview. Refresh and try again.');
        if (!mounted ||
            auth.token != ref.read(trainerAuthProvider).token ||
            auth.trainer?.trainerId !=
                ref.read(trainerAuthProvider).trainer?.trainerId ||
            widget.course.courseId != c.courseId) return;
        final assignments =
            jsonDecode(responses[0].body) as Map<String, dynamic>;
        final observers = jsonDecode(responses[1].body) as Map<String, dynamic>;
        if (assignments['lifecycle_revision'] != c.lifecycleRevision)
          throw Exception(
              'Course availability changed. Refresh before continuing.');
        final applied = (observers['observers'] as List? ?? [])
            .where((o) => o['is_active'] == true)
            .length;
        impact =
            '${assignments['total_assigned_count'] ?? 0} current employee assignments; $applied Observer selections are applied.\n\n';
      }
      final approved = await showDialog<bool>(
          context: context,
          builder: (_) => _CourseActionConfirmation(
              action: action,
              courseName: c.courseName,
              description: impact + descriptions[action]!));
      if (approved != true ||
          !mounted ||
          auth.token != ref.read(trainerAuthProvider).token ||
          auth.trainer?.trainerId !=
              ref.read(trainerAuthProvider).trainer?.trainerId ||
          widget.course.courseId != c.courseId) return;
      final headers = {
        'Content-Type': 'application/json',
        ...ref.read(trainerAuthHeadersProvider)
      };
      final response = action == 'Delete'
          ? await http.delete(
              Uri.parse(AppConstants.deleteCourseEndpoint(c.courseId)).replace(
                  queryParameters: {
                    'expected_revision': '${c.lifecycleRevision}'
                  }),
              headers: headers)
          : await http.post(
              Uri.parse(
                  '${AppConstants.courseDetailEndpoint(c.courseId)}/lifecycle'),
              headers: headers,
              body: jsonEncode({
                'action': action.toLowerCase(),
                'expected_revision': c.lifecycleRevision
              }));
      if (response.statusCode != 200 && response.statusCode != 204) {
        final data = jsonDecode(response.body);
        throw Exception(data['detail']?.toString() ??
            'Course action failed. Refresh and try again.');
      }
      changed = true;
      if (!mounted ||
          auth.token != ref.read(trainerAuthProvider).token ||
          auth.trainer?.trainerId !=
              ref.read(trainerAuthProvider).trainer?.trainerId ||
          widget.course.courseId != c.courseId) return;
      await ref.read(courseListProvider.notifier).fetchCourses();
      await ref.read(assignableCourseListProvider.notifier).fetchCourses();
      if (action != 'Delete')
        await ref.read(assignmentProvider.notifier).loadForCourse(c.courseId);
      await ref.read(performanceReportProvider.notifier).refresh();
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$action completed.')));
    } catch (error) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(changed
                ? 'Action completed. Refresh course and report data to see the result.'
                : error.toString())));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }
}

class _CourseActionConfirmation extends StatefulWidget {
  final String action, courseName, description;
  const _CourseActionConfirmation(
      {required this.action,
      required this.courseName,
      required this.description});
  @override
  State<_CourseActionConfirmation> createState() =>
      _CourseActionConfirmationState();
}

class _CourseActionConfirmationState extends State<_CourseActionConfirmation> {
  final controller = TextEditingController();
  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: Text('${widget.action} ${widget.courseName}?'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(widget.description),
          if (widget.action == 'Delete')
            TextField(
                controller: controller,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(labelText: 'Type DELETE'))
        ]),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed:
                  widget.action == 'Delete' && controller.text != 'DELETE'
                      ? null
                      : () => Navigator.pop(context, true),
              child: Text(widget.action))
        ],
      );
}

class CourseLifecycleBadge extends StatelessWidget {
  final Course course;
  const CourseLifecycleBadge({super.key, required this.course});
  @override
  Widget build(BuildContext context) {
    final state =
        course.lifecycleState.isEmpty ? course.status : course.lifecycleState;
    if (state.isEmpty) return const SizedBox.shrink();
    final color = state == 'active'
        ? const Color(0xFF087F68)
        : state == 'archived'
            ? const Color(0xFF667085)
            : const Color(0xFF175CD3);
    return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
            color: color.withOpacity(0.1),
            borderRadius: BorderRadius.circular(20)),
        child: Text('${state[0].toUpperCase()}${state.substring(1)}',
            style: TextStyle(
                color: color, fontSize: 11, fontWeight: FontWeight.w700)));
  }
}
