import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:frontend/data/models/models.dart';
import 'package:frontend/state/trainer_providers.dart';
import 'package:frontend/core/theme/app_theme.dart';

class AssignmentPortal extends ConsumerWidget {
  final Course? selectedCourse;
  final bool isMobile;

  const AssignmentPortal({
    super.key,
    required this.selectedCourse,
    required this.isMobile,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignableCourses = ref.watch(assignableCourseListProvider).courses;
    final effectiveCourse = selectedCourse != null &&
            assignableCourses
                .any((course) => course.courseId == selectedCourse!.courseId)
        ? selectedCourse
        : null;

    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: SizedBox(
                height: 350,
                child:
                    _AssignableCoursesSidebar(selectedCourse: effectiveCourse),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: AssignmentRuleView(course: effectiveCourse),
            ),
          ],
        ),
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 380,
          child: Container(
            decoration: const BoxDecoration(
              border: Border(
                right: BorderSide(color: AppTheme.lightGray, width: 1),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: _AssignableCoursesSidebar(selectedCourse: effectiveCourse),
            ),
          ),
        ),
        Expanded(
          child: Container(
            color: AppTheme.lightGray.withAlpha(77),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: AssignmentRuleView(course: effectiveCourse),
            ),
          ),
        ),
      ],
    );
  }
}

class _AssignableCoursesSidebar extends ConsumerWidget {
  final Course? selectedCourse;

  const _AssignableCoursesSidebar({required this.selectedCourse});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final courseListState = ref.watch(assignableCourseListProvider);

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Assignable Courses',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                ),
                Text(
                  '${courseListState.courses.length} courses',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          const Divider(height: 1, color: AppTheme.lightGray),
          Expanded(
            child: courseListState.isLoading
                ? const Center(
                    child: CircularProgressIndicator(
                      valueColor:
                          AlwaysStoppedAnimation<Color>(AppTheme.primaryBlue),
                    ),
                  )
                : courseListState.error != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(
                                Icons.error_outline_rounded,
                                color: AppTheme.accentRed,
                                size: 32,
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Error loading courses',
                                style: GoogleFonts.barlow(
                                    fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                courseListState.error!,
                                textAlign: TextAlign.center,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                      )
                    : courseListState.courses.isEmpty
                        ? Center(
                            child: Padding(
                              padding: const EdgeInsets.all(32),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    Icons.assignment_turned_in_outlined,
                                    color: AppTheme.gray.withOpacity(0.5),
                                    size: 48,
                                  ),
                                  const SizedBox(height: 12),
                                  Text(
                                    'No courses ready to assign',
                                    textAlign: TextAlign.center,
                                    style: GoogleFonts.barlow(
                                      color: AppTheme.gray,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    'Generate all videos and quizzes before assigning a course.',
                                    textAlign: TextAlign.center,
                                    style:
                                        Theme.of(context).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                          )
                        : ListView.separated(
                            itemCount: courseListState.courses.length,
                            separatorBuilder: (context, index) => const Divider(
                                height: 1, color: AppTheme.lightGray),
                            itemBuilder: (context, index) {
                              final course = courseListState.courses[index];
                              final isSelected =
                                  selectedCourse?.courseId == course.courseId;

                              return ListTile(
                                selected: isSelected,
                                selectedTileColor:
                                    AppTheme.primaryBlue.withOpacity(0.05),
                                leading: Icon(
                                  Icons.menu_book,
                                  color: isSelected
                                      ? AppTheme.primaryBlue
                                      : AppTheme.gray,
                                ),
                                title: Text(
                                  course.courseName,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: GoogleFonts.barlow(
                                    fontWeight: isSelected
                                        ? FontWeight.bold
                                        : FontWeight.w500,
                                    color: isSelected
                                        ? AppTheme.primaryBlue
                                        : AppTheme.textBlack,
                                  ),
                                ),
                                subtitle: Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      course.courseDifficulty,
                                      style: Theme.of(context)
                                          .textTheme
                                          .bodySmall
                                          ?.copyWith(
                                            color: _difficultyColor(
                                              course.courseDifficulty,
                                            ),
                                            fontWeight: FontWeight.bold,
                                          ),
                                    ),
                                    Text(
                                      '${course.modules.length} module${course.modules.length == 1 ? '' : 's'}',
                                      style:
                                          Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ],
                                ),
                                onTap: () {
                                  ref
                                      .read(selectedCourseProvider.notifier)
                                      .state = course;
                                },
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }

  Color _difficultyColor(String difficulty) {
    switch (difficulty.toLowerCase()) {
      case 'easy':
      case 'beginner':
        return AppTheme.accentGreen;
      case 'medium':
      case 'intermediate':
        return AppTheme.accentOrange;
      case 'hard':
      case 'advanced':
        return AppTheme.accentRed;
      default:
        return AppTheme.gray;
    }
  }
}

class AssignmentRuleView extends ConsumerStatefulWidget {
  final Course? course;

  const AssignmentRuleView({super.key, required this.course});

  @override
  ConsumerState<AssignmentRuleView> createState() => _AssignmentRuleViewState();
}

class _AssignmentRuleViewState extends ConsumerState<AssignmentRuleView> {
  final TextEditingController _deadlineController = TextEditingController();
  String? _loadedCourseId;

  @override
  void dispose() {
    _deadlineController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final course = widget.course;
    final assignment = ref.watch(assignmentProvider);

    if (course == null) {
      return const _EmptyAssignmentState();
    }

    if (_loadedCourseId != course.courseId) {
      _loadedCourseId = course.courseId;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref.read(assignmentProvider.notifier).loadForCourse(course.courseId);
      });
    }

    final rule = assignment.rule;
    _syncNumberControllers(rule);

    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        decoration: BoxDecoration(
          border: Border.all(color: const Color(0xFFE6E9EF)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Assign Course',
                        style: GoogleFonts.barlow(
                          fontSize: 24,
                          fontWeight: FontWeight.w800,
                          color: AppTheme.textBlack,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        course.courseName,
                        style: const TextStyle(color: Color(0xFF667085)),
                      ),
                    ],
                  ),
                ),
                FilledButton.icon(
                  onPressed: assignment.isSaving || assignment.isPublishing
                      ? null
                      : () => ref
                          .read(assignmentProvider.notifier)
                          .save(course.courseId),
                  icon: const Icon(Icons.save_outlined, size: 18),
                  label: const Text('Save Rule'),
                  style: FilledButton.styleFrom(
                    backgroundColor: AppTheme.primaryBlue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8)),
                  ),
                ),
                const SizedBox(width: 10),
                IconButton.outlined(
                  tooltip: 'Refresh people and saved groups',
                  onPressed: assignment.isLoading ||
                          assignment.isSaving ||
                          assignment.isPublishing
                      ? null
                      : () => ref
                          .read(assignmentProvider.notifier)
                          .refreshOptionsAndGroups(),
                  icon: const Icon(Icons.refresh),
                ),
                const SizedBox(width: 10),
                FilledButton.icon(
                  onPressed: assignment.isSaving || assignment.isPublishing
                      ? null
                      : () => ref
                          .read(assignmentProvider.notifier)
                          .publish(course.courseId),
                  icon: const Icon(Icons.publish_outlined, size: 18),
                  label: const Text('Publish & Assign'),
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFF087443),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8)),
                  ),
                ),
                const SizedBox(width: 10),
                OutlinedButton.icon(
                  onPressed: assignment.isSaving ||
                          assignment.isPublishing ||
                          !assignment.rule.isActive
                      ? null
                      : () => ref
                          .read(assignmentProvider.notifier)
                          .disable(course.courseId),
                  icon: const Icon(Icons.visibility_off_outlined, size: 18),
                  label: const Text('Disable'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.accentRed,
                    side: const BorderSide(color: AppTheme.accentRed),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8)),
                  ),
                ),
              ],
            ),
            if (!assignment.rule.isActive) ...[
              const SizedBox(height: 16),
              const _Notice(
                text:
                    'This course is disabled for employees. Publish & Assign again to show it and reset due dates.',
                isError: false,
              ),
            ],
            if (assignment.error != null) ...[
              const SizedBox(height: 16),
              _Notice(text: assignment.error!, isError: true),
            ],
            if (assignment.message != null) ...[
              const SizedBox(height: 16),
              _Notice(text: assignment.message!, isError: false),
            ],
            const SizedBox(height: 24),
            _Section(
              title: 'Include',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('All active employees'),
                    subtitle: const Text(
                        'Start from everyone, then apply exclusions.'),
                    value: rule.includeAll,
                    onChanged: (value) =>
                        _update(rule.copyWith(includeAll: value)),
                  ),
                  if (!rule.includeAll) ...[
                    const SizedBox(height: 12),
                    _GroupList(
                      title: 'Include groups',
                      helper:
                          'Employees matching any include group are selected. Conditions inside a group are matched together.',
                      emptyLabel: 'Add include group',
                      groups: rule.includeGroups,
                      savedGroups: assignment.savedGroups
                          .where((group) => group.groupType == 'include')
                          .toList(),
                      options: assignment.options,
                      groupType: 'include',
                      onChanged: (groups) =>
                          _update(rule.copyWith(includeGroups: groups)),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 20),
            _Section(
              title: 'Exclude',
              child: _GroupList(
                title: 'Exclude groups',
                helper:
                    'Employees matching any exclude group are removed from the assignment.',
                emptyLabel: 'Add exclude group',
                groups: rule.excludeGroups,
                savedGroups: assignment.savedGroups
                    .where((group) => group.groupType == 'exclude')
                    .toList(),
                options: assignment.options,
                groupType: 'exclude',
                allowJoinedFilter: false,
                onChanged: (groups) =>
                    _update(rule.copyWith(excludeGroups: groups)),
              ),
            ),
            const SizedBox(height: 20),
            _Section(
              title: 'Deadline',
              child: SizedBox(
                width: 260,
                child: TextField(
                  controller: _deadlineController,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  decoration: const InputDecoration(
                    labelText: 'Due days after assignment',
                    border: OutlineInputBorder(),
                    isDense: true,
                  ),
                  onChanged: (value) => _update(
                    rule.copyWith(deadlineDays: int.tryParse(value) ?? 1),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 20),
            _PreviewCard(
              isLoading: assignment.isLoading,
              matchCount: assignment.matchCount,
              assignedCount: assignment.assignedCount,
              employees: assignment.previewEmployees,
            ),
          ],
        ),
      ),
    );
  }

  void _syncNumberControllers(AssignmentRule rule) {
    final deadline = rule.deadlineDays.toString();
    if (_deadlineController.text != deadline) {
      _deadlineController.text = deadline;
    }
  }

  void _update(AssignmentRule rule) {
    ref.read(assignmentProvider.notifier).updateRule(rule);
  }
}

class _Section extends StatelessWidget {
  final String title;
  final Widget child;

  const _Section({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFFE6E9EF)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style:
                  const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _MultiSelectDropdown extends StatelessWidget {
  final String title;
  final List<String> values;
  final List<String> selected;
  final ValueChanged<List<String>> onChanged;

  const _MultiSelectDropdown({
    required this.title,
    required this.values,
    required this.selected,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: values.isEmpty
              ? null
              : () async {
                  final next = await showDialog<List<String>>(
                    context: context,
                    builder: (context) => _MultiSelectDialog(
                      title: title,
                      values: values,
                      selected: selected,
                    ),
                  );
                  if (next != null) onChanged(next);
                },
          icon: const Icon(Icons.arrow_drop_down_circle_outlined, size: 18),
          label: Text(
            selected.isEmpty
                ? 'Select ${title.toLowerCase()}'
                : '${selected.length} selected',
          ),
        ),
        if (selected.isNotEmpty) ...[
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final value in selected)
                InputChip(
                  label: Text(value),
                  onDeleted: () => onChanged(
                    selected.where((item) => item != value).toList(),
                  ),
                ),
            ],
          ),
        ],
      ],
    );
  }
}

class _MultiSelectDialog extends StatefulWidget {
  final String title;
  final List<String> values;
  final List<String> selected;

  const _MultiSelectDialog({
    required this.title,
    required this.values,
    required this.selected,
  });

  @override
  State<_MultiSelectDialog> createState() => _MultiSelectDialogState();
}

class _MultiSelectDialogState extends State<_MultiSelectDialog> {
  late List<String> _selected;
  String _query = '';

  @override
  void initState() {
    super.initState();
    _selected = [...widget.selected];
  }

  @override
  Widget build(BuildContext context) {
    final filtered = widget.values.where((value) {
      return value.toLowerCase().contains(_query.toLowerCase());
    }).toList();
    return AlertDialog(
      title: Text('Select ${widget.title.toLowerCase()}'),
      content: SizedBox(
        width: 520,
        height: 460,
        child: Column(
          children: [
            TextField(
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                hintText: 'Search ${widget.title.toLowerCase()}',
                border: const OutlineInputBorder(),
              ),
              onChanged: (value) => setState(() => _query = value),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: ListView.builder(
                itemCount: filtered.length,
                itemBuilder: (context, index) {
                  final value = filtered[index];
                  final checked = _selected.contains(value);
                  return CheckboxListTile(
                    value: checked,
                    dense: true,
                    title: Text(value),
                    onChanged: (isChecked) {
                      setState(() {
                        if (isChecked == true && !checked) {
                          _selected.add(value);
                        } else {
                          _selected.remove(value);
                        }
                      });
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        TextButton(
          onPressed: () => setState(() => _selected = []),
          child: const Text('Clear'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(_selected),
          child: const Text('Apply'),
        ),
      ],
    );
  }
}

class _GroupList extends StatelessWidget {
  final String title;
  final String helper;
  final String emptyLabel;
  final List<AssignmentGroup> groups;
  final List<SavedAssignmentGroup> savedGroups;
  final AssignmentOptions options;
  final String groupType;
  final bool allowJoinedFilter;
  final ValueChanged<List<AssignmentGroup>> onChanged;

  const _GroupList({
    required this.title,
    required this.helper,
    required this.emptyLabel,
    required this.groups,
    required this.savedGroups,
    required this.options,
    required this.groupType,
    required this.onChanged,
    this.allowJoinedFilter = true,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        Text(helper,
            style: const TextStyle(color: Color(0xFF667085), fontSize: 13)),
        const SizedBox(height: 12),
        for (var index = 0; index < groups.length; index++) ...[
          _AssignmentGroupCard(
            index: index,
            group: groups[index],
            options: options,
            allowJoinedFilter: allowJoinedFilter,
            onChanged: (group) {
              final next = [...groups];
              next[index] = group;
              onChanged(next);
            },
            onDelete: () {
              final next = [...groups]..removeAt(index);
              onChanged(next);
            },
          ),
          const SizedBox(height: 12),
        ],
        Wrap(
          spacing: 10,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              onPressed: () => onChanged([
                ...groups,
                AssignmentGroup(
                  name:
                      '${groupType == 'include' ? 'Include' : 'Exclude'} group ${groups.length + 1}',
                ),
              ]),
              icon: const Icon(Icons.add),
              label: Text(emptyLabel),
            ),
            if (savedGroups.isNotEmpty)
              OutlinedButton.icon(
                onPressed: () async {
                  final selected = await showDialog<SavedAssignmentGroup>(
                    context: context,
                    builder: (context) =>
                        _SavedGroupPickerDialog(savedGroups: savedGroups),
                  );
                  if (selected != null) {
                    onChanged([...groups, selected.group]);
                  }
                },
                icon: const Icon(Icons.bookmark_add_outlined),
                label: const Text('Use saved group'),
              ),
          ],
        ),
      ],
    );
  }
}

class _AssignmentGroupCard extends StatefulWidget {
  final int index;
  final AssignmentGroup group;
  final AssignmentOptions options;
  final bool allowJoinedFilter;
  final ValueChanged<AssignmentGroup> onChanged;
  final VoidCallback onDelete;

  const _AssignmentGroupCard({
    required this.index,
    required this.group,
    required this.options,
    required this.allowJoinedFilter,
    required this.onChanged,
    required this.onDelete,
  });

  @override
  State<_AssignmentGroupCard> createState() => _AssignmentGroupCardState();
}

class _AssignmentGroupCardState extends State<_AssignmentGroupCard> {
  late final TextEditingController _joinedController;
  late final TextEditingController _nameController;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: _displayName);
    _joinedController = TextEditingController(
      text: widget.group.joinedLessThanDaysAgo?.toString() ?? '',
    );
  }

  @override
  void didUpdateWidget(covariant _AssignmentGroupCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    final name = _displayName;
    if (_nameController.text != name) {
      _nameController.text = name;
    }
    final next = widget.group.joinedLessThanDaysAgo?.toString() ?? '';
    if (_joinedController.text != next) {
      _joinedController.text = next;
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _joinedController.dispose();
    super.dispose();
  }

  String get _displayName => widget.group.name.trim().isNotEmpty
      ? widget.group.name
      : 'Group ${widget.index + 1}';

  @override
  Widget build(BuildContext context) {
    final group = widget.group;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFFE6E9EF)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _nameController,
                  decoration: const InputDecoration(
                    border: InputBorder.none,
                    isDense: true,
                    hintText: 'Group name',
                  ),
                  style: const TextStyle(fontWeight: FontWeight.w800),
                  onChanged: (value) =>
                      widget.onChanged(group.copyWith(name: value)),
                ),
              ),
              IconButton(
                tooltip: 'Remove group',
                onPressed: widget.onDelete,
                icon: const Icon(Icons.delete_outline),
              ),
            ],
          ),
          _EmployeeSelector(
            title: 'Specific employees',
            actionLabel: 'Add employee',
            employees: widget.options.employees,
            selectedIds: group.employeeIds,
            onChanged: (ids) =>
                widget.onChanged(group.copyWith(employeeIds: ids)),
          ),
          const SizedBox(height: 16),
          _MultiSelectDropdown(
            title: 'Departments',
            values: widget.options.departments,
            selected: group.departments,
            onChanged: (values) =>
                widget.onChanged(group.copyWith(departments: values)),
          ),
          const SizedBox(height: 16),
          _MultiSelectDropdown(
            title: 'Mailing lists',
            values: widget.options.mailingLists,
            selected: group.mailingLists,
            onChanged: (values) =>
                widget.onChanged(group.copyWith(mailingLists: values)),
          ),
          if (widget.allowJoinedFilter) ...[
            const SizedBox(height: 16),
            SizedBox(
              width: 280,
              child: TextField(
                controller: _joinedController,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                decoration: const InputDecoration(
                  labelText: 'Joined less than days ago',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
                onChanged: (value) => widget.onChanged(
                  group.copyWith(
                    joinedLessThanDaysAgo:
                        value.isEmpty ? null : int.tryParse(value),
                    clearJoinedLessThanDaysAgo: value.isEmpty,
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _SavedGroupPickerDialog extends StatefulWidget {
  final List<SavedAssignmentGroup> savedGroups;

  const _SavedGroupPickerDialog({required this.savedGroups});

  @override
  State<_SavedGroupPickerDialog> createState() =>
      _SavedGroupPickerDialogState();
}

class _SavedGroupPickerDialogState extends State<_SavedGroupPickerDialog> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final filtered = widget.savedGroups.where((group) {
      final haystack =
          '${group.name} ${group.group.departments.join(' ')} ${group.group.mailingLists.join(' ')}'
              .toLowerCase();
      return haystack.contains(_query.toLowerCase());
    }).toList();
    return AlertDialog(
      title: const Text('Use saved group'),
      content: SizedBox(
        width: 520,
        height: 420,
        child: Column(
          children: [
            TextField(
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search),
                hintText: 'Search saved groups',
                border: OutlineInputBorder(),
              ),
              onChanged: (value) => setState(() => _query = value),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: ListView.separated(
                itemCount: filtered.length,
                separatorBuilder: (context, index) => const Divider(height: 1),
                itemBuilder: (context, index) {
                  final savedGroup = filtered[index];
                  return ListTile(
                    title: Text(savedGroup.name),
                    subtitle: Text(_savedGroupSummary(savedGroup.group)),
                    onTap: () => Navigator.of(context).pop(savedGroup),
                  );
                },
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
      ],
    );
  }

  String _savedGroupSummary(AssignmentGroup group) {
    final parts = <String>[];
    if (group.employeeIds.isNotEmpty) {
      parts.add(
        '${group.employeeIds.length} employee${group.employeeIds.length == 1 ? '' : 's'}',
      );
    }
    if (group.departments.isNotEmpty) {
      parts.add(
        '${group.departments.length} department${group.departments.length == 1 ? '' : 's'}',
      );
    }
    if (group.mailingLists.isNotEmpty) {
      parts.add(
        '${group.mailingLists.length} mailing list${group.mailingLists.length == 1 ? '' : 's'}',
      );
    }
    if (group.joinedLessThanDaysAgo != null) {
      parts.add('joined under ${group.joinedLessThanDaysAgo} days');
    }
    return parts.isEmpty ? 'No criteria yet' : parts.join(' • ');
  }
}

class _EmployeeSelector extends StatelessWidget {
  final String title;
  final String actionLabel;
  final List<Employee> employees;
  final List<String> selectedIds;
  final ValueChanged<List<String>> onChanged;

  const _EmployeeSelector({
    required this.title,
    required this.actionLabel,
    required this.employees,
    required this.selectedIds,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final selectedEmployees = employees
        .where((employee) => selectedIds.contains(employee.employeeId))
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final employee in selectedEmployees)
              InputChip(
                label: Text('${employee.name} (${employee.employeeId})'),
                onDeleted: () => onChanged(selectedIds
                    .where((id) => id != employee.employeeId)
                    .toList()),
              ),
            ActionChip(
              avatar: const Icon(Icons.person_add_alt_1, size: 18),
              label: Text(actionLabel),
              onPressed: () async {
                final employee = await showDialog<Employee>(
                  context: context,
                  builder: (context) => _EmployeePickerDialog(
                    employees: employees
                        .where((employee) =>
                            !selectedIds.contains(employee.employeeId))
                        .toList(),
                  ),
                );
                if (employee != null) {
                  onChanged([...selectedIds, employee.employeeId]);
                }
              },
            ),
          ],
        ),
      ],
    );
  }
}

class _EmployeePickerDialog extends StatefulWidget {
  final List<Employee> employees;

  const _EmployeePickerDialog({required this.employees});

  @override
  State<_EmployeePickerDialog> createState() => _EmployeePickerDialogState();
}

class _EmployeePickerDialogState extends State<_EmployeePickerDialog> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final filtered = widget.employees.where((employee) {
      final haystack =
          '${employee.name} ${employee.employeeId} ${employee.department} ${employee.jobTitle} ${employee.mailingLists.join(' ')}'
              .toLowerCase();
      return haystack.contains(_query.toLowerCase());
    }).toList();
    return AlertDialog(
      title: const Text('Exclude employee'),
      content: SizedBox(
        width: 520,
        height: 460,
        child: Column(
          children: [
            TextField(
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search),
                hintText: 'Search employees',
                border: OutlineInputBorder(),
              ),
              onChanged: (value) => setState(() => _query = value),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: ListView.builder(
                itemCount: filtered.length,
                itemBuilder: (context, index) {
                  final employee = filtered[index];
                  return ListTile(
                    title: Text(employee.name),
                    subtitle:
                        Text('${employee.employeeId} • ${employee.department}'),
                    onTap: () => Navigator.of(context).pop(employee),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PreviewCard extends StatelessWidget {
  final bool isLoading;
  final int matchCount;
  final int? assignedCount;
  final List<Employee> employees;

  const _PreviewCard({
    required this.isLoading,
    required this.matchCount,
    required this.assignedCount,
    required this.employees,
  });

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Preview',
      child: isLoading
          ? const LinearProgressIndicator()
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$matchCount matching active employees',
                  style: const TextStyle(
                      fontSize: 18, fontWeight: FontWeight.w800),
                ),
                if (assignedCount != null) ...[
                  const SizedBox(height: 4),
                  Text('$assignedCount new employee assignments created.'),
                ],
                const SizedBox(height: 12),
                for (final employee in employees)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      '${employee.name} • ${employee.department} • ${employee.jobTitle}',
                      style: const TextStyle(color: Color(0xFF344054)),
                    ),
                  ),
              ],
            ),
    );
  }
}

class _Notice extends StatelessWidget {
  final String text;
  final bool isError;

  const _Notice({required this.text, required this.isError});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isError ? const Color(0xFFFFF1F3) : const Color(0xFFEFFAF3),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isError ? const Color(0xFFFFCCD5) : const Color(0xFFB7E4C7),
        ),
      ),
      child: Text(
        text,
        style: TextStyle(
            color: isError ? const Color(0xFFA11D33) : const Color(0xFF087443)),
      ),
    );
  }
}

class _EmptyAssignmentState extends StatelessWidget {
  const _EmptyAssignmentState();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text(
        'Select a course to configure assignment rules.',
        style: TextStyle(color: Color(0xFF667085)),
      ),
    );
  }
}
