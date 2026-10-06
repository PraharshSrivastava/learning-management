import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:frontend/core/config/app_constants.dart';
import 'package:frontend/data/models/models.dart';
import 'package:frontend/state/trainer_providers.dart';

class ObserverIncludePanel extends ConsumerStatefulWidget {
  final Course course;
  final List<Employee> employees;
  const ObserverIncludePanel({super.key, required this.course, required this.employees});
  @override
  ConsumerState<ObserverIncludePanel> createState() => _ObserverIncludePanelState();
}

class _ObserverIncludePanelState extends ConsumerState<ObserverIncludePanel> {
  int revision = 0;
  int request = 0;
  bool busy = true;
  bool dirty = false;
  String? message;
  List<Map<String, dynamic>> selections = [];
  List<Map<String, dynamic>> departments = [];
  Map<String, Map<String, dynamic>> effective = {};
  @override
  void initState() { super.initState(); Future.microtask(load); }
  Uri uri(String suffix) => Uri.parse('${AppConstants.apiBaseUrl}/api/$suffix');
  Future<Map<String, dynamic>> response(http.Response result) async {
    final body = jsonDecode(result.body) as Map<String, dynamic>;
    if (result.statusCode != 200) throw Exception(body['detail'] ?? 'Unable to update observers');
    return body;
  }
  void accept(Map<String, dynamic> config) {
    dirty = false;
    effective = {for (final raw in config['observers'] as List) '${raw['observer_employee_id']}': Map<String, dynamic>.from(raw)};
    revision = (config['revision'] as num).toInt();
    selections = (config['observers'] as List).map((raw) {
      final row = raw as Map;
      final pending = row['pending'] as Map;
      return <String, dynamic>{'observer_employee_id': row['observer_employee_id'],
        'employee_ids': List<String>.from(pending['employee_ids'] as List),
        'department_ids': List<String>.from(pending['department_ids'] as List)};
    }).toList();
  }
  Future<void> load() async {
    final serial = ++request;
    if (mounted) setState(() { busy = true; message = null; });
    try {
      final headers = ref.read(trainerAuthHeadersProvider);
      final results = await Future.wait([
        http.get(uri('courses/${widget.course.courseId}/observers'), headers: headers),
        http.get(uri('observer/options'), headers: headers),
      ]);
      final config = await response(results[0]);
      final options = await response(results[1]);
      if (!mounted || serial != request) return;
      setState(() { accept(config); departments = List<Map<String, dynamic>>.from(options['departments']); busy = false; });
    } catch (error) { if (mounted && serial == request) setState(() { busy = false; message = '$error'; }); }
  }
  Future<void> save({bool apply = false}) async {
    if (!apply) {
      final ids = selections.map((s) => s['observer_employee_id']).toSet();
      if (ids.length != selections.length || selections.any((s) => s['observer_employee_id'] == null || ((s['employee_ids'] as List).isEmpty && (s['department_ids'] as List).isEmpty))) {
        setState(() => message = 'Choose each observer once and select at least one employee or department.');
        return;
      }
    }
    setState(() { busy = true; message = null; });
    try {
      final headers = {...ref.read(trainerAuthHeadersProvider), 'Content-Type': 'application/json'};
      final result = apply
        ? await http.post(uri('courses/${widget.course.courseId}/observers/apply'), headers: headers, body: jsonEncode({'revision': revision}))
        : await http.put(uri('courses/${widget.course.courseId}/observers'), headers: headers, body: jsonEncode({'revision': revision, 'observers': selections}));
      final config = await response(result);
      if (!mounted) return;
      setState(() { accept(config); busy = false; message = apply ? 'Observer access applied.' : 'Saved. Restrictions take effect now; additions need Apply Observers after publication.'; });
    } catch (error) { if (mounted) setState(() { busy = false; message = '$error'; }); }
  }
  Future<void> choose(Map<String, dynamic> selection, String field) async {
    final picked = Set<String>.from(selection[field] as List);
    final options = field == 'employee_ids'
      ? widget.employees.where((e) => e.status == 'active').map((e) => {'id': e.employeeId, 'label': '${e.name} (${e.department})'}).toList()
      : departments.map((d) => {'id': '${d['department_id']}', 'label': '${d['name']}'}).toList();
    await showDialog<void>(context: context, builder: (context) => StatefulBuilder(builder: (context, update) => AlertDialog(
      title: Text(field == 'employee_ids' ? 'Employees to observe' : 'Departments to observe'),
      content: SizedBox(width: 520, height: 380, child: ListView(children: options.map((o) => CheckboxListTile(
        title: Text(o['label']!), value: picked.contains(o['id']),
        onChanged: (value) => update(() { if (value == true) { picked.add(o['id']!); } else { picked.remove(o['id']); } }),
      )).toList())),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Done'))],
    )));
    if (mounted) setState(() { selection[field] = picked.toList(); dirty = true; });
  }
  int previewCount(Map<String, dynamic> selection) {
    final names = departments.where((d) => (selection['department_ids'] as List).contains(d['department_id'])).map((d) => d['name']).toSet();
    return widget.employees.where((e) => e.status == 'active' && ((selection['employee_ids'] as List).contains(e.employeeId) || names.contains(e.department))).map((e) => e.employeeId).toSet().length;
  }
  @override
  Widget build(BuildContext context) {
    final candidates = widget.employees.where((e) => e.status == 'active').toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Divider(height: 32),
      const Text('Observers', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 17)),
      const SizedBox(height: 8),
      const Text('Observe selected employees or departments on this course. Observers are not enrolled as learners.'),
      if (dirty) const Text('Save your changes before applying Observer access.'),
      if (busy) const LinearProgressIndicator(),
      if (message != null) Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(message!)),
      for (final selection in selections) Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Wrap(
        spacing: 12, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
          DropdownButton<String>(value: candidates.any((e) => e.employeeId == selection['observer_employee_id']) ? selection['observer_employee_id'] as String : null,
            hint: const Text('Choose observer'),
            items: candidates.map((e) => DropdownMenuItem(value: e.employeeId, child: Text(e.name))).toList(),
            onChanged: busy ? null : (v) => setState(() { selection['observer_employee_id'] = v; dirty = true; })),
          OutlinedButton(onPressed: busy ? null : () => choose(selection, 'department_ids'), child: Text('Departments (${(selection['department_ids'] as List).length})')),
          OutlinedButton(onPressed: busy ? null : () => choose(selection, 'employee_ids'), child: Text('Employees (${(selection['employee_ids'] as List).length})')),
          Text(effective[selection['observer_employee_id']]?['is_active'] == true ? 'Active access: ${(effective[selection['observer_employee_id']]!['active']['department_ids'] as List).length} departments, ${(effective[selection['observer_employee_id']]!['active']['employee_ids'] as List).length} selected employees' : 'Access not active'),
          Text('Pending selection: ${previewCount(selection)} active directory employees; reports include only assigned learners on this course.'),
          IconButton(tooltip: 'Remove observer', onPressed: busy ? null : () => setState(() { selections.remove(selection); dirty = true; }), icon: const Icon(Icons.close)),
        ])),
      Wrap(spacing: 12, children: [
        TextButton.icon(onPressed: busy || candidates.isEmpty ? null : () => setState(() { dirty = true; selections.add({'observer_employee_id': candidates.first.employeeId, 'employee_ids': <String>[], 'department_ids': <String>[]}); }), icon: const Icon(Icons.add), label: const Text('Add observer')),
        OutlinedButton(onPressed: busy ? null : () => save(), child: const Text('Save Observers')),
        FilledButton(onPressed: busy || dirty || widget.course.status != 'published' ? null : () => save(apply: true), child: const Text('Apply Observers')),
        IconButton(tooltip: 'Refresh observer configuration', onPressed: busy ? null : load, icon: const Icon(Icons.refresh)),
      ]),
    ]);
  }
}
