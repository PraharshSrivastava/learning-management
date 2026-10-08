import 'dart:convert';
import 'package:frontend/features/performance/searchable_report_filter.dart';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:frontend/core/config/app_constants.dart';
import 'package:frontend/data/models/models.dart';
import 'package:frontend/state/trainer_providers.dart';

class ObserverIncludePanel extends ConsumerStatefulWidget {
  final Course course;
  final int refreshGeneration;
  final bool isAssignmentActive;
  final List<Employee> employees;
  const ObserverIncludePanel(
      {super.key,
      required this.course,
      required this.employees,
      this.refreshGeneration = 0,
      this.isAssignmentActive = true});
  @override
  ConsumerState<ObserverIncludePanel> createState() =>
      _ObserverIncludePanelState();
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
  void initState() {
    super.initState();
    Future.microtask(load);
  }

  @override
  void didUpdateWidget(covariant ObserverIncludePanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.refreshGeneration != widget.refreshGeneration) {
      Future.microtask(() => load(preserveDraft: true));
    }
  }

  Uri uri(String suffix) => Uri.parse('${AppConstants.apiBaseUrl}/api/$suffix');
  Future<Map<String, dynamic>> response(http.Response result) async {
    if (result.statusCode == 401 || result.statusCode == 403) {
      throw const AssignmentSessionExpired();
    }
    final body = jsonDecode(result.body) as Map<String, dynamic>;
    if (result.statusCode != 200) {
      throw Exception(body['detail'] ?? 'Unable to update observers');
    }
    return body;
  }

  void accept(Map<String, dynamic> config) {
    dirty = false;
    effective = {
      for (final raw in config['observers'] as List)
        '${raw['observer_employee_id']}': Map<String, dynamic>.from(raw)
    };
    revision = (config['revision'] as num).toInt();
    selections = (config['observers'] as List).map((raw) {
      final row = raw as Map;
      final pending = row['pending'] as Map;
      return <String, dynamic>{
        'observer_employee_id': row['observer_employee_id'],
        'employee_ids': List<String>.from(pending['employee_ids'] as List),
        'department_ids': List<String>.from(pending['department_ids'] as List)
      };
    }).toList();
  }

  Future<void> load({bool preserveDraft = false}) async {
    final serial = ++request;
    if (mounted) {
      setState(() {
        busy = true;
        message = null;
      });
    }
    try {
      final headers = ref.read(trainerAuthHeadersProvider);
      final results = await Future.wait([
        ref.read(assignmentHttpClientProvider).get(
            uri('courses/${widget.course.courseId}/observers'),
            headers: headers),
        ref
            .read(assignmentHttpClientProvider)
            .get(uri('observer/options'), headers: headers),
      ]);
      final config = await response(results[0]);
      final options = await response(results[1]);
      if (!mounted || serial != request) return;
      setState(() {
        if (!preserveDraft || !dirty) {
          accept(config);
        } else {
          effective = {
            for (final raw in config['observers'] as List)
              '${raw['observer_employee_id']}': Map<String, dynamic>.from(raw)
          };
          if ((config['revision'] as num).toInt() != revision) {
            message =
                'Observer configuration changed. Your edits are preserved. Review the saved version before saving; your earlier revision cannot overwrite it.';
          }
        }
        departments = List<Map<String, dynamic>>.from(options['departments']);
        busy = false;
      });
      notifyDraftObservers();
    } catch (error) {
      if (mounted && serial == request) {
        setState(() {
          busy = false;
          if (error is AssignmentSessionExpired) {
            selections = [];
            effective = {};
            departments = [];
            dirty = false;
          }
          message = error is AssignmentSessionExpired
              ? 'Observer access changed. Sign in again.'
              : '$error';
        });
      }
    }
  }

  Future<void> save({bool apply = false}) async {
    if (!apply) {
      final ids = selections.map((s) => s['observer_employee_id']).toSet();
      if (ids.length != selections.length ||
          selections.any((s) =>
              s['observer_employee_id'] == null ||
              ((s['employee_ids'] as List).isEmpty &&
                  (s['department_ids'] as List).isEmpty))) {
        setState(() => message =
            'Choose each observer once and select at least one employee or department.');
        return;
      }
    }
    setState(() {
      busy = true;
      message = null;
    });
    try {
      final headers = {
        ...ref.read(trainerAuthHeadersProvider),
        'Content-Type': 'application/json'
      };
      final result = apply
          ? await ref.read(assignmentHttpClientProvider).post(
              uri('courses/${widget.course.courseId}/observers/apply'),
              headers: headers,
              body: jsonEncode({'revision': revision}))
          : await ref.read(assignmentHttpClientProvider).put(
              uri('courses/${widget.course.courseId}/observers'),
              headers: headers,
              body:
                  jsonEncode({'revision': revision, 'observers': selections}));
      final config = await response(result);
      if (!mounted) return;
      setState(() {
        accept(config);
        busy = false;
        message = apply
            ? 'Observer access applied.'
            : 'Saved. Restrictions take effect now; additions need Apply Observers after publication.';
      });
      notifyDraftObservers();
    } catch (error) {
      if (mounted) {
        setState(() {
          busy = false;
          message = '$error';
        });
      }
    }
  }

  void notifyDraftObservers() {
    ref.read(assignmentProvider.notifier).updateDraftObservers(selections
        .map((s) => s['observer_employee_id'])
        .whereType<String>()
        .toList());
  }

  Future<void> choose(Map<String, dynamic> selection, String field) async {
    final picked = Set<String>.from(selection[field] as List);
    final options = field == 'employee_ids'
        ? widget.employees
            .where((e) => e.status == 'active')
            .map((e) =>
                {'id': e.employeeId, 'label': '${e.name} (${e.department})'})
            .toList()
        : departments
            .map(
                (d) => {'id': '${d['department_id']}', 'label': '${d['name']}'})
            .toList();
    await showDialog<void>(
        context: context,
        builder: (context) => StatefulBuilder(
            builder: (context, update) => AlertDialog(
                  title: Text(field == 'employee_ids'
                      ? 'Employees to observe'
                      : 'Departments to observe'),
                  content: SizedBox(
                      width: 520,
                      height: 380,
                      child: Column(children: [
                        if (field == 'employee_ids')
                          Wrap(spacing: 8, children: [
                            TextButton.icon(
                                onPressed: options.isEmpty ||
                                        options.every(
                                            (o) => picked.contains(o['id']))
                                    ? null
                                    : () => update(() => picked
                                        .addAll(options.map((o) => o['id']!))),
                                icon: const Icon(Icons.done_all, size: 18),
                                label: const Text('Select all')),
                            TextButton(
                                onPressed: picked.isEmpty
                                    ? null
                                    : () => update(picked.clear),
                                child: const Text('Clear all')),
                            Text('${picked.length} selected'),
                          ]),
                        Expanded(
                            child: ListView.builder(
                                itemCount: options.length,
                                itemBuilder: (_, index) {
                                  final option = options[index];
                                  return CheckboxListTile(
                                      title: Text(option['label']!),
                                      value: picked.contains(option['id']),
                                      onChanged: (value) => update(() {
                                            if (value == true) {
                                              picked.add(option['id']!);
                                            } else {
                                              picked.remove(option['id']);
                                            }
                                          }));
                                })),
                      ])),
                  actions: [
                    TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Done'))
                  ],
                )));
    if (mounted) {
      setState(() {
        selection[field] = picked.toList();
        dirty = true;
        Future.microtask(notifyDraftObservers);
      });
      notifyDraftObservers();
    }
  }

  int previewCount(Map<String, dynamic> selection) {
    final names = departments
        .where((d) =>
            (selection['department_ids'] as List).contains(d['department_id']))
        .map((d) => d['name'])
        .toSet();
    return widget.employees
        .where((e) =>
            e.status == 'active' &&
            ((selection['employee_ids'] as List).contains(e.employeeId) ||
                names.contains(e.department)))
        .map((e) => e.employeeId)
        .toSet()
        .length;
  }

  @override
  Widget build(BuildContext context) {
    final candidates =
        widget.employees.where((e) => e.status == 'active').toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SizedBox(height: 8),
      _observerNotice(
          'Observers can view performance only. They are not enrolled as learners.',
          warning: false),
      if (dirty)
        _observerNotice('Save your changes before applying Observer access.',
            warning: true),
      if (widget.course.status != 'published' || !widget.isAssignmentActive)
        _observerNotice(
            'Publish and assign the course before applying observers.',
            warning: true),
      if (busy) const LinearProgressIndicator(),
      if (message != null) _observerNotice(message!, warning: true),
      if (dirty && message?.contains('changed') == true)
        TextButton(
            onPressed: busy
                ? null
                : () async {
                    final discard = await showDialog<bool>(
                        context: context,
                        builder: (context) => AlertDialog(
                                title: const Text(
                                    'Reload saved Observer selections?'),
                                content: const Text(
                                    'Your unsaved Observer edits will be discarded.'),
                                actions: [
                                  TextButton(
                                      onPressed: () =>
                                          Navigator.pop(context, false),
                                      child: const Text('Keep editing')),
                                  FilledButton(
                                      onPressed: () =>
                                          Navigator.pop(context, true),
                                      child:
                                          const Text('Reload saved selections'))
                                ]));
                    if (discard == true && mounted) await load();
                  },
            child: const Text('Reload saved Observer selections')),
      for (final selection in selections)
        Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Wrap(
                spacing: 12,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  SearchableReportFilter(
                      label: 'Observer',
                      value: selection['observer_employee_id'] as String?,
                      items: {
                        for (final employee in candidates)
                          employee.employeeId: employee.name
                      },
                      icon: Icons.search,
                      width: 260,
                      allowAll: false,
                      enabled: !busy,
                      onChanged: (value) => setState(() {
                            selection['observer_employee_id'] = value;
                            dirty = true;
                            Future.microtask(notifyDraftObservers);
                          })),
                  OutlinedButton(
                      onPressed: busy
                          ? null
                          : () => choose(selection, 'department_ids'),
                      child: Text(
                          'Departments (${(selection['department_ids'] as List).length})')),
                  OutlinedButton(
                      onPressed:
                          busy ? null : () => choose(selection, 'employee_ids'),
                      child: Text(
                          'Employees (${(selection['employee_ids'] as List).length})')),
                  _observerAccessBadge(
                      effective[selection['observer_employee_id']]),
                  Text(
                      'Pending selection: ${previewCount(selection)} active directory employees; reports include only assigned learners on this course.'),
                  IconButton(
                      tooltip: 'Remove observer',
                      onPressed: busy
                          ? null
                          : () => setState(() {
                                selections.remove(selection);
                                dirty = true;
                                Future.microtask(notifyDraftObservers);
                              }),
                      icon: const Icon(Icons.close)),
                ])),
      Wrap(spacing: 12, children: [
        TextButton.icon(
            onPressed: busy || candidates.isEmpty
                ? null
                : () => setState(() {
                      dirty = true;
                      Future.microtask(notifyDraftObservers);
                      selections.add({
                        'observer_employee_id': candidates.first.employeeId,
                        'employee_ids': <String>[],
                        'department_ids': <String>[]
                      });
                    }),
            icon: const Icon(Icons.add),
            label: const Text('Add observer')),
        OutlinedButton(
            onPressed: busy ? null : () => save(),
            child: const Text('Save Observers')),
        FilledButton(
            onPressed: busy ||
                    dirty ||
                    widget.course.status != 'published' ||
                    !widget.isAssignmentActive
                ? null
                : () => save(apply: true),
            child: const Text('Apply Observers')),
        IconButton(
            tooltip: 'Refresh observer configuration',
            onPressed: busy ? null : () => load(preserveDraft: true),
            icon: const Icon(Icons.refresh)),
      ]),
    ]);
  }
}

Widget _observerNotice(String text, {required bool warning}) => Container(
    margin: const EdgeInsets.only(bottom: 8),
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
        color: warning ? const Color(0xFFFFF8E8) : const Color(0xFFEDF5FF),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
            color:
                warning ? const Color(0xFFF1D99B) : const Color(0xFFC6DDF8))),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(warning ? Icons.warning_amber_rounded : Icons.info_outline,
          size: 20,
          color: warning ? const Color(0xFF805300) : const Color(0xFF103B78)),
      const SizedBox(width: 8),
      Expanded(
          child: Text(text,
              style: TextStyle(
                  color: warning
                      ? const Color(0xFF805300)
                      : const Color(0xFF103B78))))
    ]));

Widget _observerAccessBadge(Map<String, dynamic>? access) {
  final active = access?['is_active'] == true;
  final text = active
      ? 'Active access: ${(access!['active']['department_ids'] as List).length} departments, ${(access['active']['employee_ids'] as List).length} selected employees'
      : 'Access not active';
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    decoration: BoxDecoration(
      color: active ? const Color(0xFFEAF5EE) : const Color(0xFFF1F3F6),
      borderRadius: BorderRadius.circular(16),
    ),
    child: Text(text,
        style: TextStyle(
          color: active ? const Color(0xFF256640) : const Color(0xFF536174),
          fontSize: 12,
          fontWeight: FontWeight.w600,
        )),
  );
}
