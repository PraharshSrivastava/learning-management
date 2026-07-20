import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../models/models.dart';
import '../providers/providers.dart';
import '../theme.dart';

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
            assignableCourses.any((course) => course.id == selectedCourse!.id)
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
                child: _AssignableCoursesSidebar(selectedCourse: effectiveCourse),
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
                      valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryBlue),
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
                                style: GoogleFonts.barlow(fontWeight: FontWeight.bold),
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
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                          )
                        : ListView.separated(
                            itemCount: courseListState.courses.length,
                            separatorBuilder: (context, index) =>
                                const Divider(height: 1, color: AppTheme.lightGray),
                            itemBuilder: (context, index) {
                              final course = courseListState.courses[index];
                              final isSelected = selectedCourse?.id == course.id;

                              return ListTile(
                                selected: isSelected,
                                selectedTileColor: AppTheme.primaryBlue.withOpacity(0.05),
                                leading: Icon(
                                  Icons.menu_book,
                                  color: isSelected ? AppTheme.primaryBlue : AppTheme.gray,
                                ),
                                title: Text(
                                  course.courseName,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: GoogleFonts.barlow(
                                    fontWeight:
                                        isSelected ? FontWeight.bold : FontWeight.w500,
                                    color:
                                        isSelected ? AppTheme.primaryBlue : AppTheme.textBlack,
                                  ),
                                ),
                                subtitle: Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      course.courseDifficulty,
                                      style:
                                          Theme.of(context).textTheme.bodySmall?.copyWith(
                                                color: _difficultyColor(
                                                  course.courseDifficulty,
                                                ),
                                                fontWeight: FontWeight.bold,
                                              ),
                                    ),
                                    Text(
                                      '${course.modules.length} module${course.modules.length == 1 ? '' : 's'}',
                                      style: Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ],
                                ),
                                onTap: () {
                                  ref.read(selectedCourseProvider.notifier).state = course;
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

    if (_loadedCourseId != course.id) {
      _loadedCourseId = course.id;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref.read(assignmentProvider.notifier).loadForCourse(course.id);
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
                      : () => ref.read(assignmentProvider.notifier).save(course.id),
                  icon: const Icon(Icons.save_outlined, size: 18),
                  label: const Text('Save Rule'),
                  style: FilledButton.styleFrom(
                    backgroundColor: AppTheme.primaryBlue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                ),
                const SizedBox(width: 10),
                FilledButton.icon(
                  onPressed: assignment.isSaving || assignment.isPublishing
                      ? null
                      : () => ref.read(assignmentProvider.notifier).publish(course.id),
                  icon: const Icon(Icons.publish_outlined, size: 18),
                  label: const Text('Publish & Assign'),
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFF087443),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                ),
              ],
            ),
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
                    subtitle: const Text('Start from everyone, then apply exclusions.'),
                    value: rule.includeAll,
                    onChanged: (value) => _update(rule.copyWith(includeAll: value)),
                  ),
                  if (!rule.includeAll) ...[
                    const SizedBox(height: 12),
                    _GroupList(
                      title: 'Include groups',
                      helper:
                          'Employees matching any include group are selected. Conditions inside a group are matched together.',
                      emptyLabel: 'Add include group',
                      groups: rule.includeGroups,
                      options: assignment.options,
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
                options: assignment.options,
                allowJoinedFilter: false,
                onChanged: (groups) => _update(rule.copyWith(excludeGroups: groups)),
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
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _ChoiceChips extends StatelessWidget {
  final String title;
  final List<String> values;
  final List<String> selected;
  final ValueChanged<List<String>> onChanged;

  const _ChoiceChips({
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
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final value in values)
              FilterChip(
                label: Text(value),
                selected: selected.contains(value),
                onSelected: (isSelected) {
                  final next = [...selected];
                  isSelected ? next.add(value) : next.remove(value);
                  onChanged(next);
                },
              ),
          ],
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
  final AssignmentOptions options;
  final bool allowJoinedFilter;
  final ValueChanged<List<AssignmentGroup>> onChanged;

  const _GroupList({
    required this.title,
    required this.helper,
    required this.emptyLabel,
    required this.groups,
    required this.options,
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
        Text(helper, style: const TextStyle(color: Color(0xFF667085), fontSize: 13)),
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
        OutlinedButton.icon(
          onPressed: () => onChanged([...groups, const AssignmentGroup()]),
          icon: const Icon(Icons.add),
          label: Text(emptyLabel),
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

  @override
  void initState() {
    super.initState();
    _joinedController = TextEditingController(
      text: widget.group.joinedLessThanDaysAgo?.toString() ?? '',
    );
  }

  @override
  void didUpdateWidget(covariant _AssignmentGroupCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    final next = widget.group.joinedLessThanDaysAgo?.toString() ?? '';
    if (_joinedController.text != next) {
      _joinedController.text = next;
    }
  }

  @override
  void dispose() {
    _joinedController.dispose();
    super.dispose();
  }

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
                child: Text(
                  'Group ${widget.index + 1}',
                  style: const TextStyle(fontWeight: FontWeight.w800),
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
            onChanged: (ids) => widget.onChanged(group.copyWith(employeeIds: ids)),
          ),
          const SizedBox(height: 16),
          _ChoiceChips(
            title: 'Departments',
            values: widget.options.departments,
            selected: group.departments,
            onChanged: (values) => widget.onChanged(group.copyWith(departments: values)),
          ),
          const SizedBox(height: 16),
          _ChoiceChips(
            title: 'Roles',
            values: widget.options.roles,
            selected: group.roles,
            onChanged: (values) => widget.onChanged(group.copyWith(roles: values)),
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
                    joinedLessThanDaysAgo: value.isEmpty ? null : int.tryParse(value),
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
    final selectedEmployees =
        employees.where((employee) => selectedIds.contains(employee.id)).toList();
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
                label: Text('${employee.name} (${employee.employeeCode})'),
                onDeleted: () =>
                    onChanged(selectedIds.where((id) => id != employee.id).toList()),
              ),
            ActionChip(
              avatar: const Icon(Icons.person_add_alt_1, size: 18),
              label: Text(actionLabel),
              onPressed: () async {
                final employee = await showDialog<Employee>(
                  context: context,
                  builder: (context) => _EmployeePickerDialog(
                    employees: employees
                        .where((employee) => !selectedIds.contains(employee.id))
                        .toList(),
                  ),
                );
                if (employee != null) {
                  onChanged([...selectedIds, employee.id]);
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
          '${employee.name} ${employee.employeeCode} ${employee.department} ${employee.role}'
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
                    subtitle: Text(
                        '${employee.employeeCode} • ${employee.department} • ${employee.role}'),
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
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
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
                      '${employee.name} • ${employee.department} • ${employee.role}',
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
        style: TextStyle(color: isError ? const Color(0xFFA11D33) : const Color(0xFF087443)),
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
