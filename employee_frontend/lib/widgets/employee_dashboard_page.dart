import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants.dart';
import '../models/course_dashboard_data.dart';
import '../models/dashboard_preview_data.dart';
import '../models/models.dart';
import '../providers/employee_providers.dart';
import '../theme.dart';
import 'course_playback_page.dart';

class EmployeeDashboardPage extends ConsumerStatefulWidget {
  const EmployeeDashboardPage({super.key});

  @override
  ConsumerState<EmployeeDashboardPage> createState() =>
      _EmployeeDashboardPageState();
}

class _EmployeeDashboardPageState extends ConsumerState<EmployeeDashboardPage> {
  bool _navigationExpanded = true;
  String _selectedFilter = 'Assigned';
  int _activeNavigationIndex = 0;
  Course? _openCourse;
  final Set<String> _seenNotifications = <String>{};

  @override
  Widget build(BuildContext context) {
    final courseState = ref.watch(employeeCourseListProvider);
    final width = MediaQuery.sizeOf(context).width;
    final isCompact = width < 840;
    final usingPreviewData = courseState.courses.isEmpty;
    final courses =
        usingPreviewData ? DashboardPreviewData.courses() : courseState.courses;
    final metrics = LearningMetrics.fromCourses(courses);
    final unreadCourses = courses
        .where((course) =>
            CourseDashboardData.isNewAssignment(course) &&
            !_seenNotifications.contains(course.id))
        .toList();

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      drawer: isCompact
          ? Drawer(
              child: _LmsNavigation(
                expanded: true,
                selectedIndex: _activeNavigationIndex,
                onSelect: _handleNavigation,
                onToggle: () => Navigator.of(context).pop(),
              ),
            )
          : null,
      body: Row(
        children: [
          if (!isCompact)
            _LmsNavigation(
              expanded: _navigationExpanded,
              selectedIndex: _activeNavigationIndex,
              onSelect: _handleNavigation,
              onToggle: () =>
                  setState(() => _navigationExpanded = !_navigationExpanded),
            ),
          Expanded(
            child: Column(
              children: [
                Builder(
                  builder: (scaffoldContext) => _DashboardAppBar(
                    isCompact: isCompact,
                    activeIndex: _activeNavigationIndex,
                    unreadCount: unreadCourses.length,
                    onMenu: () => Scaffold.of(scaffoldContext).openDrawer(),
                    onNotifications: () => _showNotifications(unreadCourses),
                  ),
                ),
                Expanded(
                  child: _openCourse == null
                      ? _buildActiveView(
                          courses: courses,
                          metrics: metrics,
                          isLoading: courseState.isLoading,
                          error: courseState.error,
                          usingPreviewData: usingPreviewData,
                        )
                      : CoursePlaybackView(
                          course: _openCourse!,
                          onBack: () => setState(() => _openCourse = null),
                        ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _handleNavigation(int index) {
    setState(() => _activeNavigationIndex = index);
    if (Navigator.of(context).canPop()) Navigator.of(context).pop();
  }

  Widget _buildActiveView({
    required List<Course> courses,
    required LearningMetrics metrics,
    required bool isLoading,
    required String? error,
    required bool usingPreviewData,
  }) {
    switch (_activeNavigationIndex) {
      case 1:
        return _CourseLibraryView(
            courses: courses, onCourseAction: _showCourseAction);
      case 2:
        return _NotificationsView(
          courses: courses,
          onOpenNotifications: () => _showNotifications(
            courses
                .where((course) => CourseDashboardData.isNewAssignment(course))
                .toList(),
          ),
        );
      default:
        return _DashboardBody(
          courses: courses,
          metrics: metrics,
          isLoading: isLoading && !usingPreviewData,
          error: usingPreviewData ? null : error,
          selectedFilter: _selectedFilter,
          onFilterChanged: (filter) => setState(() => _selectedFilter = filter),
          onCourseAction: _showCourseAction,
          usingPreviewData: usingPreviewData,
        );
    }
  }

  void _showCourseAction(Course course) {
    setState(() => _openCourse = course);
  }

  Future<void> _showNotifications(List<Course> courses) async {
    if (courses.isNotEmpty) {
      setState(
          () => _seenNotifications.addAll(courses.map((course) => course.id)));
    }
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Learning notifications'),
        content: SizedBox(
          width: 360,
          child: courses.isEmpty
              ? const Text(
                  'You are up to date. New course assignments will appear here.')
              : ListView.separated(
                  shrinkWrap: true,
                  itemCount: courses.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final course = courses[index];
                    return ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: const CircleAvatar(
                        backgroundColor: Color(0xFFE7EFFF),
                        child: Icon(Icons.school_outlined,
                            color: AppTheme.primaryBlue),
                      ),
                      title: Text('New course: ${course.courseName}'),
                      subtitle: Text(_formatAssignedDate(course.assignedAt)),
                    );
                  },
                ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Close'))
        ],
      ),
    );
  }

  String _formatAssignedDate(String? assignedAt) {
    final date = assignedAt == null ? null : DateTime.tryParse(assignedAt);
    if (date == null) return 'Recently assigned';
    return 'Assigned ${date.day}/${date.month}/${date.year}';
  }
}

class _DashboardAppBar extends StatelessWidget {
  final bool isCompact;
  final int activeIndex;
  final int unreadCount;
  final VoidCallback onMenu;
  final VoidCallback onNotifications;

  const _DashboardAppBar({
    required this.isCompact,
    required this.activeIndex,
    required this.unreadCount,
    required this.onMenu,
    required this.onNotifications,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      child: Container(
        height: isCompact ? 80 : 72,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: Color(0xFFE6E9EF)))),
        child: Row(
          children: [
            if (isCompact) ...[
              IconButton(
                  onPressed: onMenu,
                  icon: const Icon(Icons.menu),
                  tooltip: 'Open navigation'),
              const SizedBox(width: 8),
            ],
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Learning Management System',
                      style:
                          TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 2),
                  Text(_appBarLabels[activeIndex],
                      style: const TextStyle(
                          fontSize: 13, color: Color(0xFF667085))),
                ],
              ),
            ),
            Tooltip(
              message: unreadCount == 0
                  ? 'Notifications'
                  : '$unreadCount unread notifications',
              child: Badge.count(
                count: unreadCount,
                isLabelVisible: unreadCount > 0,
                backgroundColor: AppTheme.accentRed,
                child: IconButton(
                  onPressed: onNotifications,
                  icon: Icon(unreadCount > 0
                      ? Icons.notifications
                      : Icons.notifications_none),
                  color: unreadCount > 0
                      ? AppTheme.primaryBlue
                      : const Color(0xFF344054),
                ),
              ),
            ),
            const SizedBox(width: 8),
            const CircleAvatar(
              radius: 18,
              backgroundColor: Color(0xFFE7EFFF),
              child: Text('PS',
                  style: TextStyle(
                      color: AppTheme.primaryBlue,
                      fontWeight: FontWeight.w700)),
            ),
          ],
        ),
      ),
    );
  }
}

const _appBarLabels = ['Dashboard', 'My Courses', 'Notifications'];

class _LmsNavigation extends StatelessWidget {
  final bool expanded;
  final int selectedIndex;
  final ValueChanged<int> onSelect;
  final VoidCallback onToggle;

  const _LmsNavigation({
    required this.expanded,
    required this.selectedIndex,
    required this.onSelect,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final destinations = <({IconData icon, String label})>[
      (icon: Icons.dashboard_outlined, label: 'Dashboard'),
      (icon: Icons.menu_book_outlined, label: 'My Courses'),
      (icon: Icons.notifications_outlined, label: 'Notifications'),
    ];
    return Container(
      width: expanded ? 262 : 76,
      color: const Color(0xFF06245A),
      child: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: EdgeInsets.fromLTRB(
                  expanded ? 20 : 12, 18, expanded ? 12 : 12, 22),
              child: Row(
                children: [
                  SizedBox(
                    height: 40,
                    width: expanded ? 154 : 40,
                    child: Image.asset('assets/logos/Type=Primary.png',
                        fit: BoxFit.contain, alignment: Alignment.centerLeft),
                  ),
                  if (expanded)
                    IconButton(
                      onPressed: onToggle,
                      tooltip: 'Collapse navigation',
                      icon: const Icon(Icons.keyboard_double_arrow_left,
                          color: Colors.white70),
                    ),
                ],
              ),
            ),
            if (expanded)
              const Padding(
                padding: EdgeInsets.fromLTRB(22, 0, 22, 20),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text('Learning Management System',
                      style: TextStyle(
                          color: Color(0xFFD0DBF4),
                          fontSize: 12,
                          fontWeight: FontWeight.w600)),
                ),
              ),
            if (!expanded)
              IconButton(
                onPressed: onToggle,
                tooltip: 'Expand navigation',
                icon: const Icon(Icons.keyboard_double_arrow_right,
                    color: Colors.white70),
              ),
            const Divider(height: 1, color: Color(0xFF204276)),
            const SizedBox(height: 14),
            for (var index = 0; index < destinations.length; index++)
              _NavigationItem(
                icon: destinations[index].icon,
                label: destinations[index].label,
                expanded: expanded,
                selected: selectedIndex == index,
                onTap: () => onSelect(index),
              ),
            const Spacer(),
            Padding(
              padding: const EdgeInsets.all(14),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFF12356E),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFF294A7D)),
                ),
                child: expanded
                    ? const Row(
                        children: [
                          Icon(Icons.lock_outline,
                              color: Color(0xFFD0DBF4), size: 18),
                          SizedBox(width: 10),
                          Expanded(
                              child: Text('Employee learning',
                                  style: TextStyle(
                                      color: Color(0xFFD0DBF4), fontSize: 12))),
                        ],
                      )
                    : const Icon(Icons.lock_outline,
                        color: Color(0xFFD0DBF4), size: 18),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavigationItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool expanded;
  final bool selected;
  final VoidCallback onTap;

  const _NavigationItem(
      {required this.icon,
      required this.label,
      required this.expanded,
      required this.selected,
      required this.onTap});

  @override
  Widget build(BuildContext context) {
    final item = Padding(
      padding:
          EdgeInsets.symmetric(horizontal: expanded ? 12 : 10, vertical: 3),
      child: Material(
        color: selected ? Colors.white : Colors.transparent,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(8),
          child: SizedBox(
            height: 48,
            child: Row(
              mainAxisAlignment:
                  expanded ? MainAxisAlignment.start : MainAxisAlignment.center,
              children: [
                SizedBox(width: expanded ? 18 : null),
                Icon(icon,
                    color: selected
                        ? AppTheme.primaryBlue
                        : const Color(0xFFD0DBF4),
                    size: 21),
                if (expanded) ...[
                  const SizedBox(width: 14),
                  Text(label,
                      style: TextStyle(
                          color: selected ? AppTheme.primaryBlue : Colors.white,
                          fontWeight: FontWeight.w600)),
                ],
              ],
            ),
          ),
        ),
      ),
    );
    return expanded ? item : Tooltip(message: label, child: item);
  }
}

class _DashboardBody extends StatelessWidget {
  final List<Course> courses;
  final LearningMetrics metrics;
  final bool isLoading;
  final String? error;
  final String selectedFilter;
  final ValueChanged<String> onFilterChanged;
  final ValueChanged<Course> onCourseAction;
  final bool usingPreviewData;

  const _DashboardBody({
    required this.courses,
    required this.metrics,
    required this.isLoading,
    required this.error,
    required this.selectedFilter,
    required this.onFilterChanged,
    required this.onCourseAction,
    required this.usingPreviewData,
  });

  @override
  Widget build(BuildContext context) {
    final filteredCourses = _coursesForSelectedMetric(courses, selectedFilter);
    final attempted = CourseDashboardData.orderedAttempted(courses);
    final isWide = MediaQuery.sizeOf(context).width >= 1220;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1480),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('My learning',
                  style: TextStyle(
                      fontSize: 30,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF101828))),
              const SizedBox(height: 6),
              Text(
                metrics.pending > 0
                    ? 'You have ${metrics.pending} course${metrics.pending == 1 ? '' : 's'} ready for your attention.'
                    : 'Your learning activity is up to date.',
                style: const TextStyle(fontSize: 15, color: Color(0xFF667085)),
              ),
              const SizedBox(height: 24),
              if (usingPreviewData) ...[
                const _PreviewDataNotice(),
                const SizedBox(height: 20),
              ],
              _MetricsGrid(
                metrics: metrics,
                selectedFilter: selectedFilter,
                onFilterChanged: onFilterChanged,
              ),
              const SizedBox(height: 32),
              if (error != null && courses.isNotEmpty)
                _ConnectionNotice(message: error!),
              if (error != null && courses.isNotEmpty)
                const SizedBox(height: 20),
              if (isLoading && courses.isEmpty)
                const _DashboardLoading()
              else if (error != null && courses.isEmpty)
                _DashboardMessage(
                    icon: Icons.cloud_off_outlined,
                    title: 'Unable to load your learning',
                    subtitle: error!)
              else if (courses.isEmpty)
                const _DashboardMessage(
                    icon: Icons.school_outlined,
                    title: 'No courses assigned yet',
                    subtitle:
                        'New assigned courses will appear here when they are ready.')
              else if (isWide)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: _CourseContent(
                        courses: filteredCourses,
                        attempted: attempted,
                        selectedFilter: selectedFilter,
                        onCourseAction: onCourseAction,
                      ),
                    ),
                    const SizedBox(width: 24),
                    const SizedBox(width: 312, child: _LeaderboardPanel()),
                  ],
                )
              else ...[
                _CourseContent(
                  courses: filteredCourses,
                  attempted: attempted,
                  selectedFilter: selectedFilter,
                  onCourseAction: onCourseAction,
                ),
                const SizedBox(height: 24),
                const _LeaderboardPanel(),
              ],
            ],
          ),
        ),
      ),
    );
  }

  List<Course> _coursesForSelectedMetric(List<Course> courses, String filter) {
    final now = DateTime.now();
    switch (filter) {
      case 'Attempted':
        return CourseDashboardData.orderedAttempted(courses, now: now);
      case 'Passed':
        return courses
            .where((course) =>
                CourseDashboardData.statusFor(course, now: now) ==
                DashboardCourseStatus.passed)
            .toList();
      case 'Pending':
        return CourseDashboardData.orderedAssigned(courses, now: now)
            .where((course) {
          final status = CourseDashboardData.statusFor(course, now: now);
          return status == DashboardCourseStatus.pending ||
              status == DashboardCourseStatus.overdue;
        }).toList();
      case 'In progress':
        return CourseDashboardData.orderedAssigned(courses, now: now)
            .where((course) =>
                CourseDashboardData.statusFor(course, now: now) ==
                DashboardCourseStatus.inProgress)
            .toList();
      case 'Assigned':
      default:
        return CourseDashboardData.orderedAssigned(courses, now: now);
    }
  }
}

class _PreviewDataNotice extends StatelessWidget {
  const _PreviewDataNotice();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFEAF2FF),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFC7D7F6)),
      ),
      child: const Row(
        children: [
          Icon(Icons.visibility_outlined,
              size: 18, color: AppTheme.primaryBlue),
          SizedBox(width: 8),
          Expanded(
            child: Text(
              'Preview data is shown while no live courses are assigned.',
              style: TextStyle(fontSize: 13, color: AppTheme.primaryBlue),
            ),
          ),
        ],
      ),
    );
  }
}

class _CourseLibraryView extends StatelessWidget {
  final List<Course> courses;
  final ValueChanged<Course> onCourseAction;

  const _CourseLibraryView(
      {required this.courses, required this.onCourseAction});

  @override
  Widget build(BuildContext context) {
    final activeCourses = CourseDashboardData.orderedAssigned(courses);
    return _SimplePageFrame(
      title: 'My courses',
      subtitle:
          'Pick up where you left off or start your next assigned course.',
      child:
          _CourseGrid(courses: activeCourses, onCourseAction: onCourseAction),
    );
  }
}

class _NotificationsView extends StatelessWidget {
  final List<Course> courses;
  final VoidCallback onOpenNotifications;

  const _NotificationsView(
      {required this.courses, required this.onOpenNotifications});

  @override
  Widget build(BuildContext context) {
    final notifications = courses
        .where((course) => CourseDashboardData.isNewAssignment(course))
        .toList();
    return _SimplePageFrame(
      title: 'Notifications',
      subtitle:
          'Keep track of new learning assignments and important due dates.',
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFFE6E9EF)),
        ),
        child: ListView.separated(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: notifications.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final course = notifications[index];
            return ListTile(
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
              leading: const CircleAvatar(
                backgroundColor: Color(0xFFE7EFFF),
                child: Icon(Icons.school_outlined, color: AppTheme.primaryBlue),
              ),
              title: Text('New course assigned: ${course.courseName}'),
              subtitle: const Text(
                  'Open your notification center to review this assignment.'),
              trailing: IconButton(
                onPressed: onOpenNotifications,
                tooltip: 'Open notification',
                icon: const Icon(Icons.arrow_forward),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _SimplePageFrame extends StatelessWidget {
  final String title;
  final String subtitle;
  final Widget child;

  const _SimplePageFrame(
      {required this.title, required this.subtitle, required this.child});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1480),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: const TextStyle(
                      fontSize: 30,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF101828))),
              const SizedBox(height: 6),
              Text(subtitle,
                  style:
                      const TextStyle(fontSize: 15, color: Color(0xFF667085))),
              const SizedBox(height: 24),
              child,
            ],
          ),
        ),
      ),
    );
  }
}

class _MetricsGrid extends StatelessWidget {
  final LearningMetrics metrics;
  final String selectedFilter;
  final ValueChanged<String> onFilterChanged;

  const _MetricsGrid({
    required this.metrics,
    required this.selectedFilter,
    required this.onFilterChanged,
  });

  @override
  Widget build(BuildContext context) {
    final items = [
      (
        label: 'Assigned',
        value: metrics.assigned,
        icon: Icons.assignment_outlined,
        color: AppTheme.primaryBlue
      ),
      (
        label: 'Attempted',
        value: metrics.attempted,
        icon: Icons.play_circle_outline,
        color: AppTheme.accentCyan
      ),
      (
        label: 'Passed',
        value: metrics.passed,
        icon: Icons.verified_outlined,
        color: AppTheme.accentGreen
      ),
      (
        label: 'Pending',
        value: metrics.pending,
        icon: Icons.schedule_outlined,
        color: AppTheme.accentOrange
      ),
      (
        label: 'In progress',
        value: metrics.inProgress,
        icon: Icons.trending_up_outlined,
        color: const Color(0xFF6750A4)
      ),
    ];
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth >= 1040
            ? 5
            : constraints.maxWidth >= 620
                ? 3
                : 2;
        final childAspectRatio = columns >= 3 ? 2.2 : 1.9;
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: items.length,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            childAspectRatio: childAspectRatio,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
          ),
          itemBuilder: (context, index) => _MetricTile(
            label: items[index].label,
            value: items[index].value,
            icon: items[index].icon,
            color: items[index].color,
            isSelected: selectedFilter == items[index].label,
            onTap: () => onFilterChanged(items[index].label),
          ),
        );
      },
    );
  }
}

class _MetricTile extends StatelessWidget {
  final String label;
  final int value;
  final IconData icon;
  final Color color;
  final bool isSelected;
  final VoidCallback onTap;

  const _MetricTile(
      {required this.label,
      required this.value,
      required this.icon,
      required this.color,
      required this.isSelected,
      required this.onTap});

  @override
  Widget build(BuildContext context) {
    final foreground = isSelected ? Colors.white : const Color(0xFF101828);
    return Semantics(
      button: true,
      selected: isSelected,
      label: 'Show $label courses',
      child: Material(
        color: isSelected ? color : Colors.white,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(10),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                  color: isSelected ? color : const Color(0xFFE1E7EF)),
              boxShadow: isSelected
                  ? [
                      BoxShadow(
                        color: color.withValues(alpha: 0.24),
                        blurRadius: 16,
                        offset: const Offset(0, 7),
                      )
                    ]
                  : const [
                      BoxShadow(
                        color: Color(0x0A101828),
                        blurRadius: 10,
                        offset: Offset(0, 3),
                      )
                    ],
            ),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: isSelected
                        ? Colors.white.withValues(alpha: 0.18)
                        : color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(icon,
                      color: isSelected ? Colors.white : color, size: 21),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('$value',
                          style: TextStyle(
                              fontSize: 26,
                              fontWeight: FontWeight.w700,
                              height: 1,
                              color: foreground)),
                      const SizedBox(height: 5),
                      Text(label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
                              color: isSelected
                                  ? Colors.white.withValues(alpha: 0.82)
                                  : const Color(0xFF667085))),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _CourseContent extends StatelessWidget {
  final List<Course> courses;
  final List<Course> attempted;
  final String selectedFilter;
  final ValueChanged<Course> onCourseAction;

  const _CourseContent(
      {required this.courses,
      required this.attempted,
      required this.selectedFilter,
      required this.onCourseAction});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(
          title: _sectionTitle(selectedFilter),
          trailing: const SizedBox.shrink(),
        ),
        const SizedBox(height: 16),
        if (courses.isEmpty)
          _InlineEmpty(
              message: 'No ${selectedFilter.toLowerCase()} courses to show.')
        else
          _CourseGrid(courses: courses, onCourseAction: onCourseAction),
        if (selectedFilter == 'Assigned') ...[
          const SizedBox(height: 36),
          const _SectionHeader(
            title: 'Already attempted',
            trailing: SizedBox.shrink(),
          ),
          const SizedBox(height: 16),
          if (attempted.isEmpty)
            const _InlineEmpty(
                message: 'Courses you start or complete will appear here.')
          else
            _CourseGrid(
                courses: attempted.take(4).toList(),
                onCourseAction: onCourseAction),
        ],
      ],
    );
  }

  String _sectionTitle(String filter) {
    switch (filter) {
      case 'Attempted':
        return 'Attempted courses';
      case 'Passed':
        return 'Passed courses';
      case 'Pending':
        return 'Pending courses';
      case 'In progress':
        return 'Courses in progress';
      default:
        return 'Assigned to you';
    }
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final Widget trailing;

  const _SectionHeader({required this.title, required this.trailing});

  @override
  Widget build(BuildContext context) {
    return Wrap(
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.center,
      runSpacing: 10,
      children: [
        Text(title,
            style: const TextStyle(
                fontSize: 21,
                fontWeight: FontWeight.w700,
                color: Color(0xFF101828))),
        trailing,
      ],
    );
  }
}

class _CourseGrid extends StatelessWidget {
  final List<Course> courses;
  final ValueChanged<Course> onCourseAction;

  const _CourseGrid({required this.courses, required this.onCourseAction});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth >= 820
            ? 3
            : constraints.maxWidth >= 520
                ? 2
                : 1;
        final cardExtent = columns == 1
            ? 510.0
            : columns == 2
                ? 512.0
                : 520.0;
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: courses.length,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            mainAxisExtent: cardExtent,
            crossAxisSpacing: 16,
            mainAxisSpacing: 16,
          ),
          itemBuilder: (context, index) => _CourseCard(
              course: courses[index],
              onAction: () => onCourseAction(courses[index])),
        );
      },
    );
  }
}

class _CourseCard extends StatelessWidget {
  final Course course;
  final VoidCallback onAction;

  const _CourseCard({required this.course, required this.onAction});

  @override
  Widget build(BuildContext context) {
    final status = CourseDashboardData.statusFor(course);
    final progress = CourseDashboardData.progressFor(course);
    final moduleCount = course.publishedModules.length;
    final statusInfo =
        _statusInfo(status, CourseDashboardData.isDueSoon(course));
    final actionColor = _actionColor(status);
    return Card(
      clipBehavior: Clip.antiAlias,
      elevation: 0,
      margin: EdgeInsets.zero,
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: const BorderSide(color: Color(0xFFE6E9EF))),
      child: InkWell(
        onTap: onAction,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _CourseThumbnail(course: course),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _StatusChip(
                        label: statusInfo.label,
                        icon: statusInfo.icon,
                        color: statusInfo.color),
                    const SizedBox(height: 10),
                    SizedBox(
                      height: 40,
                      child: Text(
                        course.courseName,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          height: 1.25,
                        ),
                      ),
                    ),
                    const SizedBox(height: 6),
                    SizedBox(
                      height: 36,
                      child: Text(
                        course.courseDescription.isEmpty
                            ? 'Structured learning designed for your role.'
                            : course.courseDescription,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 13,
                          height: 1.35,
                          color: Color(0xFF667085),
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    if (moduleCount > 0) ...[
                      Row(
                        children: [
                          Expanded(
                              child: Text(
                                  '${CourseDashboardData.watchedModulesFor(course)} of $moduleCount modules',
                                  style: const TextStyle(
                                      fontSize: 12, color: Color(0xFF667085)))),
                          Text('${(progress * 100).round()}%',
                              style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.primaryBlue)),
                        ],
                      ),
                      const SizedBox(height: 7),
                      LinearProgressIndicator(
                          value: progress,
                          minHeight: 5,
                          borderRadius: BorderRadius.circular(3),
                          backgroundColor: const Color(0xFFE6E9EF),
                          color: AppTheme.primaryBlue),
                      const SizedBox(height: 13),
                    ],
                    const Spacer(),
                    if (course.deadline != null) ...[
                      Row(
                        children: [
                          const Icon(
                            Icons.calendar_today_outlined,
                            size: 14,
                            color: Color(0xFF667085),
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              'Due ${_dateLabel(course.deadline!)}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontSize: 12,
                                color: Color(0xFF667085),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                    ],
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: onAction,
                        icon: Icon(
                            status == DashboardCourseStatus.passed
                                ? Icons.visibility_outlined
                                : Icons.arrow_forward,
                            size: 18),
                        label: Text(_actionLabel(status)),
                        style: FilledButton.styleFrom(
                          backgroundColor: actionColor,
                          foregroundColor: Colors.white,
                          elevation: 0,
                          padding: const EdgeInsets.symmetric(vertical: 11),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _dateLabel(String value) {
    final date = DateTime.tryParse(value);
    return date == null
        ? value.split('T').first
        : '${date.day}/${date.month}/${date.year}';
  }

  String _actionLabel(DashboardCourseStatus status) {
    switch (status) {
      case DashboardCourseStatus.passed:
        return 'Review';
      case DashboardCourseStatus.inProgress:
        return 'Continue';
      case DashboardCourseStatus.overdue:
      case DashboardCourseStatus.pending:
        return 'Start';
    }
  }

  Color _actionColor(DashboardCourseStatus status) {
    switch (status) {
      case DashboardCourseStatus.inProgress:
        return const Color(0xFF087E8B);
      case DashboardCourseStatus.passed:
        return const Color(0xFF596273);
      case DashboardCourseStatus.overdue:
      case DashboardCourseStatus.pending:
        return AppTheme.primaryBlue;
    }
  }
}

class _CourseThumbnail extends StatelessWidget {
  final Course course;

  const _CourseThumbnail({required this.course});

  @override
  Widget build(BuildContext context) {
    final imagePath = course.images.isEmpty ? '' : course.images.first.filePath;
    return AspectRatio(
      aspectRatio: 16 / 9,
      child: imagePath.isEmpty
          ? Container(
              color: AppTheme.primaryBlue,
              child: Stack(
                children: [
                  Positioned(
                      right: 18,
                      top: 18,
                      child: Icon(Icons.auto_stories_outlined,
                          color: Colors.white.withValues(alpha: 0.82),
                          size: 42)),
                  const Positioned(
                      left: 16,
                      bottom: 14,
                      child: Text('LEARNING',
                          style: TextStyle(
                              color: Colors.white,
                              letterSpacing: 1.2,
                              fontSize: 11,
                              fontWeight: FontWeight.w700))),
                ],
              ),
            )
          : imagePath.startsWith('assets/')
              ? Image.asset(
                  imagePath,
                  fit: BoxFit.cover,
                )
              : Image.network(
                  AppConstants.videoAssetUrl(imagePath),
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => Container(
                      color: AppTheme.primaryBlue,
                      child: const Icon(Icons.image_not_supported_outlined,
                          color: Colors.white)),
                  loadingBuilder: (context, child, loadingProgress) =>
                      loadingProgress == null
                          ? child
                          : Container(color: const Color(0xFFE7EFFF)),
                ),
    );
  }
}

class _StatusInfo {
  final String label;
  final IconData icon;
  final Color color;
  const _StatusInfo(this.label, this.icon, this.color);
}

_StatusInfo _statusInfo(DashboardCourseStatus status, bool dueSoon) {
  if (status == DashboardCourseStatus.passed) {
    return const _StatusInfo(
        'Passed', Icons.verified_outlined, AppTheme.accentGreen);
  }
  if (status == DashboardCourseStatus.inProgress) {
    return const _StatusInfo(
        'In progress', Icons.play_circle_outline, AppTheme.primaryBlue);
  }
  if (status == DashboardCourseStatus.overdue) {
    return const _StatusInfo(
        'Overdue', Icons.error_outline, AppTheme.accentRed);
  }
  if (dueSoon) {
    return const _StatusInfo(
        'Due soon', Icons.schedule_outlined, AppTheme.accentOrange);
  }
  return const _StatusInfo(
      'New', Icons.fiber_new_outlined, AppTheme.primaryBlue);
}

class _StatusChip extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  const _StatusChip(
      {required this.label, required this.icon, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
          color: color.withValues(alpha: 0.11),
          borderRadius: BorderRadius.circular(16)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 4),
        Text(label,
            style: TextStyle(
                fontSize: 11, color: color, fontWeight: FontWeight.w700))
      ]),
    );
  }
}

class _LeaderboardPanel extends StatelessWidget {
  const _LeaderboardPanel();

  @override
  Widget build(BuildContext context) {
    const entries = [
      ('Ananya Mehta', 18),
      ('Rohit Khanna', 16),
      ('Sneha Iyer', 14),
      ('Vikram Shah', 12),
      ('Neha Kapoor', 11),
    ];
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFFE6E9EF))),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(children: [
            Icon(Icons.leaderboard_outlined, color: AppTheme.primaryBlue),
            SizedBox(width: 9),
            Text('Leaderboard',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700))
          ]),
          const SizedBox(height: 5),
          const Text('Most courses passed',
              style: TextStyle(fontSize: 13, color: Color(0xFF667085))),
          const SizedBox(height: 14),
          for (var index = 0; index < entries.length; index++)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Row(
                children: [
                  SizedBox(
                      width: 24,
                      child: Text('${index + 1}',
                          style: TextStyle(
                              fontWeight: FontWeight.w700,
                              color: index < 3
                                  ? AppTheme.primaryBlue
                                  : const Color(0xFF667085)))),
                  CircleAvatar(
                      radius: 15,
                      backgroundColor: const Color(0xFFE7EFFF),
                      child: Text(
                          entries[index]
                              .$1
                              .split(' ')
                              .map((part) => part[0])
                              .join(),
                          style: const TextStyle(
                              fontSize: 10,
                              color: AppTheme.primaryBlue,
                              fontWeight: FontWeight.w700))),
                  const SizedBox(width: 9),
                  Expanded(
                      child: Text(entries[index].$1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                              fontSize: 13, fontWeight: FontWeight.w600))),
                  Text('${entries[index].$2}',
                      style: const TextStyle(
                          fontSize: 13, color: Color(0xFF667085))),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _ConnectionNotice extends StatelessWidget {
  final String message;
  const _ConnectionNotice({required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
          color: const Color(0xFFFFF7E8),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFFF3D19C))),
      child: Row(children: [
        const Icon(Icons.wifi_off_outlined, color: Color(0xFF8A5A00)),
        const SizedBox(width: 10),
        Expanded(
            child: Text('Showing the latest available learning data. $message',
                style: const TextStyle(color: Color(0xFF704A00), fontSize: 13)))
      ]),
    );
  }
}

class _DashboardLoading extends StatelessWidget {
  const _DashboardLoading();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.symmetric(vertical: 72),
        child: Center(
            child: Column(children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('Loading your learning dashboard...')
        ])),
      );
}

class _DashboardMessage extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  const _DashboardMessage(
      {required this.icon, required this.title, required this.subtitle});

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(48),
        decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: const Color(0xFFE6E9EF))),
        child: Column(children: [
          Icon(icon, size: 44, color: AppTheme.primaryBlue),
          const SizedBox(height: 14),
          Text(title,
              style:
                  const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          Text(subtitle,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Color(0xFF667085)))
        ]),
      );
}

class _InlineEmpty extends StatelessWidget {
  final String message;
  const _InlineEmpty({required this.message});

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: const Color(0xFFE6E9EF))),
        child: Text(message, style: const TextStyle(color: Color(0xFF667085))),
      );
}
