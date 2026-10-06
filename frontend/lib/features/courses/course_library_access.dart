import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:frontend/core/config/app_constants.dart';
import 'package:frontend/core/theme/app_theme.dart';
import 'package:frontend/data/models/models.dart';
import 'package:frontend/features/training/training_portal.dart';
import 'package:frontend/state/trainer_providers.dart';

class CourseLibraryAccess extends ConsumerStatefulWidget {
  final Widget ownPortal;
  const CourseLibraryAccess({super.key, required this.ownPortal});
  @override
  ConsumerState<CourseLibraryAccess> createState() => _CourseLibraryAccessState();
}
class _CourseLibraryAccessState extends ConsumerState<CourseLibraryAccess> {
  bool all = false;
  @override
  Widget build(BuildContext context) {
    final access = ref.watch(lmsAccessProvider);
    if ((access['capabilities'] as Map?)?['can_view_other_trainers_courses'] != true) return widget.ownPortal;
    return Column(children: [
      Padding(padding: const EdgeInsets.fromLTRB(24, 12, 24, 0), child: Row(children: [
        ChoiceChip(label: const Text('My Courses'), selected: !all, onSelected: (_) => setState(() => all = false)),
        const SizedBox(width: 12),
        ChoiceChip(label: const Text('All Courses'), selected: all, onSelected: (_) => setState(() => all = true)),
        const SizedBox(width: 12), const Expanded(child: Text('Other creators’ courses are read-only.')),
      ])),
      Expanded(child: all ? CourseLibraryInspector(key: ValueKey('${access['employee_id']}:${access['permissions_version']}')) : widget.ownPortal),
    ]);
  }
}
class CourseLibraryInspector extends ConsumerStatefulWidget {
  const CourseLibraryInspector({super.key});
  @override
  ConsumerState<CourseLibraryInspector> createState() => _CourseLibraryInspectorState();
}
class _CourseLibraryInspectorState extends ConsumerState<CourseLibraryInspector> {
  final search = TextEditingController();
  List<Map<String, dynamic>> items = [];
  Map<String, dynamic>? detail;
  Map<String, dynamic>? assignment;
  int offset = 0, total = 0, request = 0;
  bool busy = true;
  String? status, error;
  @override
  void initState() { super.initState(); Future.microtask(load); }
  @override
  void dispose() { request++; search.dispose(); super.dispose(); }
  Future<Map<String, dynamic>> get(String path, [Map<String, String>? query]) async {
    final response = await http.get(Uri.parse('${AppConstants.apiBaseUrl}/api/$path').replace(queryParameters: query), headers: ref.read(trainerAuthHeadersProvider));
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    if (response.statusCode != 200) {
      if (response.statusCode == 401 || response.statusCode == 403 || response.statusCode == 404) ref.read(lmsAccessProvider.notifier).refresh();
      throw Exception(body['detail'] ?? 'Unable to load course');
    }
    return body;
  }
  Future<void> load() async {
    final serial = ++request;
    setState(() { busy = true; error = null; detail = null; assignment = null; items = []; });
    try {
      final page = await get('trainer/course-library', {'scope': 'all', 'limit': '25', 'offset': '$offset', if (status != null) 'status': status!, if (search.text.trim().isNotEmpty) 'search': search.text.trim()});
      if (!mounted || serial != request) return;
      setState(() { items = List<Map<String, dynamic>>.from(page['items']); total = (page['total'] as num).toInt(); busy = false; });
    } catch (e) { if (mounted && serial == request) setState(() { busy = false; error = '$e'; }); }
  }
  Future<void> open(String id) async {
    final serial = ++request;
    setState(() { busy = true; error = null; detail = null; assignment = null; });
    try {
      final result = await Future.wait([get('courses/$id'), get('courses/$id/assignment')]);
      if (!mounted || serial != request) return;
      setState(() { detail = result[0]; assignment = result[1]; busy = false; });
    } catch (e) { if (mounted && serial == request) setState(() { busy = false; error = '$e'; }); }
  }
  @override
  Widget build(BuildContext context) {
    return ListView(padding: const EdgeInsets.all(24), children: [
      Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.center, children: [
        SizedBox(width: 300, child: TextField(controller: search, decoration: const InputDecoration(labelText: 'Find a course', prefixIcon: Icon(Icons.search)), onSubmitted: (_) { offset = 0; load(); })),
        DropdownButton<String>(value: status, hint: const Text('All statuses'), items: const [DropdownMenuItem(value: null, child: Text('All statuses')), DropdownMenuItem(value: 'draft', child: Text('Draft')), DropdownMenuItem(value: 'ready', child: Text('Ready')), DropdownMenuItem(value: 'published', child: Text('Published')), DropdownMenuItem(value: 'archived', child: Text('Archived'))], onChanged: (s) { status = s; offset = 0; load(); }),
        OutlinedButton.icon(onPressed: busy ? null : load, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
        Text('$total courses'),
      ]),
      if (busy) const LinearProgressIndicator(),
      if (error != null) Padding(padding: const EdgeInsets.all(16), child: Text(error!, style: const TextStyle(color: AppTheme.accentRed))),
      if (detail == null) ...[
        for (final item in items) Card(child: ListTile(title: Text('${item['course_name']}'), subtitle: Text('Created by ${item['creator_name'] ?? item['trainer_id']} · ${item['status']} · ${item['generation_status'] ?? 'Not generated'}'), trailing: const Icon(Icons.visibility_outlined), onTap: busy ? null : () => open('${item['course_id']}'))),
        Row(children: [TextButton(onPressed: busy || offset == 0 ? null : () { offset -= 25; load(); }, child: const Text('Previous')), TextButton(onPressed: busy || offset + 25 >= total ? null : () { offset += 25; load(); }, child: const Text('Next'))]),
      ] else ...[
        TextButton.icon(onPressed: () => setState(() { detail = null; assignment = null; }), icon: const Icon(Icons.arrow_back), label: const Text('Back to library')),
        Text('${detail!['course_name']}', style: Theme.of(context).textTheme.headlineSmall),
        Text('Created by ${detail!['creator_name'] ?? detail!['trainer_id']}'),
        const SizedBox(height: 12),
        Text(detail!['read_only_reason']?.toString() ?? 'Manage your own course from My Courses.'),
        if (detail!['can_manage'] != true) Wrap(spacing: 8, children: ['Edit', 'Regenerate', 'Assign', 'Disable', 'Delete'].map((label) => Tooltip(message: '${detail!['read_only_reason']}', child: OutlinedButton(onPressed: null, child: Text(label)))).toList()),
        const SizedBox(height: 16),
        OutlinedButton.icon(onPressed: () { ref.read(currentTabProvider.notifier).state = 4; ref.read(performanceReportProvider.notifier).openLinkedReport(courseId: '${detail!['course_id']}'); }, icon: const Icon(Icons.analytics_outlined), label: const Text('View Performance')),
        Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Blueprint', style: TextStyle(fontWeight: FontWeight.bold)),
          SelectableText('${detail!['course_description']}'),
          SelectableText('${detail!['course_objective']}'),
          for (final module in (detail!['modules'] as List? ?? [])) ExpansionTile(title: Text('${module['title']}'), children: [Padding(padding: const EdgeInsets.all(12), child: SelectableText('${module['source_text'] ?? ''}'))]),
        ]))),
        Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Assignment settings (read-only)', style: TextStyle(fontWeight: FontWeight.bold)),
          Text('Deadline: ${(assignment?['rule'] as Map?)?['deadline_days'] ?? 7} days'),
          Text('Status: ${(assignment?['rule'] as Map?)?['is_active'] == true ? 'Active' : 'Disabled'}'),
          Text('Include: ${(assignment?['rule'] as Map?)?['include_all'] == true ? 'All active employees' : 'Selected employee groups'}'),
          Text('Matched learners: ${assignment?['match_count'] ?? 0}'),
        ]))),
        if (detail!['generation'] != null) ExpansionTile(title: const Text('Generation status'), children: [Text('Status: ${(detail!['generation'] as Map)['status']}'), Text('Stage: ${(detail!['generation'] as Map)['current_checkpoint'] ?? ''}'), if ((detail!['generation'] as Map)['error'] != null) Text('${(detail!['generation'] as Map)['error']}')]),
        SizedBox(height: 640, child: TrainingView(readOnly: true, course: Course.fromJson(detail!))),
      ],
    ]);
  }
}
