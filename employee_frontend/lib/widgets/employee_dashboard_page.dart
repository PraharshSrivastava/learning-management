import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../theme.dart';
import '../models/models.dart';

import '../providers/employee_providers.dart';
import 'course_playback_page.dart';

class EmployeeDashboardPage extends ConsumerStatefulWidget {
  const EmployeeDashboardPage({super.key});

  @override
  ConsumerState<EmployeeDashboardPage> createState() => _EmployeeDashboardPageState();
}

class _EmployeeDashboardPageState extends ConsumerState<EmployeeDashboardPage> {
  Course? _selectedCourse;
  String _selectedFilter = 'All';

  @override
  Widget build(BuildContext context) {
    final courseState = ref.watch(employeeCourseListProvider);
    final activeTab = ref.watch(currentEmployeeTabProvider);
    final isMobile = MediaQuery.of(context).size.width < 900;

    if (_selectedCourse != null && courseState.courses.isNotEmpty) {
      _selectedCourse = courseState.courses.firstWhere(
        (c) => c.id == _selectedCourse!.id,
        orElse: () => _selectedCourse!,
      );
    }

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: Row(
          children: [
            Text(
              'PhillipCapital',
              style: GoogleFonts.inter(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: AppTheme.primaryBlue,
                letterSpacing: -0.5,
              ),
            ),
            const SizedBox(width: 8),
            Container(height: 20, width: 1, color: AppTheme.lightGray),
            const SizedBox(width: 12),
            _TabHeaderButton(
              title: 'Home',
              isActive: activeTab == 0,
              onTap: () => ref.read(currentEmployeeTabProvider.notifier).state = 0,
            ),
            const SizedBox(width: 8),
            _TabHeaderButton(
              title: 'Courses',
              isActive: activeTab == 1,
              onTap: () => ref.read(currentEmployeeTabProvider.notifier).state = 1,
            ),
            const SizedBox(width: 8),
            _TabHeaderButton(
              title: 'Completed',
              isActive: activeTab == 2,
              onTap: () => ref.read(currentEmployeeTabProvider.notifier).state = 2,
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: AppTheme.primaryBlue),
            onPressed: () {
              // Note: WebSocket manages data in Employee app, this is for UI consistency with frontend
            },
            tooltip: 'Refresh All Data',
          ),
          const SizedBox(width: 16),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(
            color: AppTheme.lightGray,
            height: 1,
          ),
        ),
      ),
      body: courseState.isLoading && courseState.courses.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : courseState.error != null && courseState.courses.isEmpty
              ? Center(child: Text('Error: ${courseState.error}', style: const TextStyle(color: Colors.red)))
              : activeTab == 0
                  ? _buildDashboardPortal(courseState.courses, isMobile)
                  : activeTab == 1
                      ? _buildTrainingPortal(courseState.courses, isMobile)
                      : _buildCompletedPortal(courseState.courses, isMobile),
    );
  }

  String _getCourseStatus(Course course) {
    bool isCompleted = true;
    bool hasStarted = false;
    for (var m in course.publishedModules) {
      final moduleStr = m.moduleNumber.toString();
      final progress = course.employeeProgress[moduleStr];
      if (progress?.videoWatched == true || progress?.quizPassed == true) {
        hasStarted = true;
      }
      if (progress?.quizPassed != true) {
        isCompleted = false;
      }
    }
    if (course.publishedModules.isEmpty) {
      isCompleted = false;
    }

    if (isCompleted) return 'COMPLETED';
    if (hasStarted) return 'STARTED';
    if (course.deadline != null && DateTime.tryParse(course.deadline!)?.isBefore(DateTime.now()) == true) {
      return 'OVERDUE';
    }
    return 'PENDING';
  }

  void _sortCoursesByDeadline(List<Course> list) {
    list.sort((a, b) {
      if (a.deadline == null && b.deadline == null) return 0;
      if (a.deadline == null) return 1;
      if (b.deadline == null) return -1;
      final da = DateTime.tryParse(a.deadline!);
      final db = DateTime.tryParse(b.deadline!);
      if (da == null && db == null) return 0;
      if (da == null) return 1;
      if (db == null) return -1;
      return da.compareTo(db);
    });
  }

  Widget _buildDashboardPortal(List<Course> courses, bool isMobile) {
    final nonCompleted = courses.where((c) => _getCourseStatus(c) != 'COMPLETED').toList();

    final filtered = nonCompleted.where((c) {
      if (_selectedFilter == 'All') return true;
      if (_selectedFilter == 'Started' && _getCourseStatus(c) == 'STARTED') return true;
      if (_selectedFilter == 'Pending' && _getCourseStatus(c) == 'PENDING') return true;
      if (_selectedFilter == 'Overdue' && _getCourseStatus(c) == 'OVERDUE') return true;
      return false;
    }).toList();

    _sortCoursesByDeadline(filtered);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(32.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'Assigned Courses',
                style: GoogleFonts.inter(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textBlack,
                  letterSpacing: -0.5,
                ),
              ),
              const Spacer(),
              DropdownButton<String>(
                value: _selectedFilter,
                underline: const SizedBox(),
                icon: const Icon(Icons.filter_list, color: AppTheme.gray),
                items: ['All', 'Started', 'Pending', 'Overdue'].map((String value) {
                  return DropdownMenuItem<String>(
                    value: value,
                    child: Text(value, style: GoogleFonts.barlow(fontWeight: FontWeight.w600, color: AppTheme.textBlack)),
                  );
                }).toList(),
                onChanged: (val) {
                  if (val != null) {
                    setState(() {
                      _selectedFilter = val;
                    });
                  }
                },
              ),
            ],
          ),
          const SizedBox(height: 24),
          if (filtered.isEmpty)
            Center(
              child: Text(
                'No courses found.',
                style: GoogleFonts.barlow(fontSize: 16, color: AppTheme.gray),
              ),
            )
          else
            _buildCourseList(filtered, isMobile),
        ],
      ),
    );
  }

  Widget _buildCompletedPortal(List<Course> courses, bool isMobile) {
    final completed = courses.where((c) => _getCourseStatus(c) == 'COMPLETED').toList();
    _sortCoursesByDeadline(completed);
    
    return SingleChildScrollView(
      padding: const EdgeInsets.all(32.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSectionHeader('Completed Courses'),
          const SizedBox(height: 24),
          if (completed.isEmpty)
            Center(
              child: Text(
                'No completed courses yet.',
                style: GoogleFonts.barlow(fontSize: 16, color: AppTheme.gray),
              ),
            )
          else
            _buildCourseList(completed, isMobile),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Text(
      title,
      style: GoogleFonts.inter(
        fontSize: 24,
        fontWeight: FontWeight.bold,
        color: AppTheme.textBlack,
        letterSpacing: -0.5,
      ),
    );
  }

  Widget _buildCourseList(List<Course> list, bool isMobile) {
    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: list.length,
      itemBuilder: (context, index) {
        return _buildDashboardCourseCard(list[index]);
      },
    );
  }

  Widget _buildDashboardCourseCard(Course course) {
    // determine status
    bool isCompleted = true;
    bool hasStarted = false;
    for (var m in course.publishedModules) {
      final moduleStr = m.moduleNumber.toString();
      final progress = course.employeeProgress[moduleStr];
      if (progress?.videoWatched == true || progress?.quizPassed == true) {
        hasStarted = true;
      }
      if (progress?.quizPassed != true) {
        isCompleted = false;
      }
    }
    if (course.publishedModules.isEmpty) {
      isCompleted = false;
    }

    String statusText = 'PENDING';
    Color statusColor = AppTheme.gray;
    Color statusBg = AppTheme.lightGray.withOpacity(0.5);

    if (isCompleted) {
      statusText = 'COMPLETED';
      statusColor = AppTheme.accentGreen;
      statusBg = AppTheme.accentGreen.withOpacity(0.12);
    } else if (hasStarted) {
      statusText = 'STARTED';
      statusColor = AppTheme.primaryBlue;
      statusBg = AppTheme.primaryBlue.withOpacity(0.12);
    } else if (course.deadline != null && DateTime.tryParse(course.deadline!)?.isBefore(DateTime.now()) == true) {
      statusText = 'OVERDUE';
      statusColor = AppTheme.accentRed;
      statusBg = AppTheme.accentRed.withOpacity(0.12);
    } else {
      statusText = 'PENDING';
      statusColor = AppTheme.accentOrange;
      statusBg = AppTheme.accentOrange.withOpacity(0.12);
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.lightGray),
      ),
      padding: const EdgeInsets.all(20),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  course.courseName,
                  style: GoogleFonts.inter(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textBlack,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: statusBg,
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Text(
                        statusText,
                        style: GoogleFonts.barlow(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: statusColor,
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    if (course.deadline != null)
                      Row(
                        children: [
                          Icon(Icons.calendar_today_outlined, size: 16, color: AppTheme.gray.withOpacity(0.8)),
                          const SizedBox(width: 6),
                          Text(
                            'Due: ${course.deadline!.split(' ')[0]}',
                            style: GoogleFonts.barlow(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.gray.withOpacity(0.8),
                            ),
                          ),
                        ],
                      ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          ElevatedButton(
            onPressed: () {
              setState(() {
                _selectedCourse = course;
              });
              ref.read(currentEmployeeTabProvider.notifier).state = 1;
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryBlue,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
              elevation: 0,
            ),
            child: Text(
              isCompleted ? 'Review Course' : (hasStarted ? 'Continue Course' : 'Start Course'),
              style: GoogleFonts.barlow(fontWeight: FontWeight.bold, fontSize: 14),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTrainingPortal(List<Course> courses, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 300,
                child: _buildSidebar(courses),
              ),
            ),
            if (_selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: CoursePlaybackView(course: _selectedCourse!),
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
              padding: const EdgeInsets.all(20.0),
              child: _buildSidebar(courses),
            ),
          ),
        ),
        Expanded(
          child: _selectedCourse == null
              ? const _EmptyCourseView()
              : CoursePlaybackView(course: _selectedCourse!),
        ),
      ],
    );
  }

  Widget _buildSidebar(List<Course> courses) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Active Courses',
          style: GoogleFonts.inter(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: AppTheme.primaryBlue,
          ),
        ),
        const SizedBox(height: 16),
        Expanded(
          child: courses.isEmpty
              ? Center(
                  child: Text(
                    'No active courses.',
                    style: GoogleFonts.barlow(
                      fontSize: 14,
                      color: AppTheme.gray,
                    ),
                  ),
                )
              : ListView.builder(
                  itemCount: courses.length,
                  itemBuilder: (context, index) {
                    final course = courses[index];
                    return _buildSidebarCourseCard(course);
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildSidebarCourseCard(Course course) {
    bool isSelected = _selectedCourse?.id == course.id;

    // determine status
    bool isCompleted = true;
    bool hasStarted = false;
    for (var m in course.publishedModules) {
      final moduleStr = m.moduleNumber.toString();
      final progress = course.employeeProgress[moduleStr];
      if (progress?.videoWatched == true || progress?.quizPassed == true) {
        hasStarted = true;
      }
      if (progress?.quizPassed != true) {
        isCompleted = false;
      }
    }
    if (course.publishedModules.isEmpty) {
      isCompleted = false;
    }

    String statusText = 'PENDING';
    Color statusColor = AppTheme.gray;
    Color statusBg = AppTheme.lightGray.withOpacity(0.5);

    if (isCompleted) {
      statusText = 'COMPLETED';
      statusColor = AppTheme.accentGreen;
      statusBg = AppTheme.accentGreen.withOpacity(0.12);
    } else if (hasStarted) {
      statusText = 'STARTED';
      statusColor = AppTheme.primaryBlue;
      statusBg = AppTheme.primaryBlue.withOpacity(0.12);
    } else if (course.deadline != null && DateTime.tryParse(course.deadline!)?.isBefore(DateTime.now()) == true) {
      statusText = 'OVERDUE';
      statusColor = AppTheme.accentRed;
      statusBg = AppTheme.accentRed.withOpacity(0.12);
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {
            setState(() {
              _selectedCourse = course;
            });
          },
          borderRadius: BorderRadius.circular(12),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: isSelected ? AppTheme.primaryBlue.withOpacity(0.04) : Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: isSelected ? AppTheme.primaryBlue.withOpacity(0.3) : AppTheme.lightGray,
                width: 1,
              ),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryBlue.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.school, color: AppTheme.primaryBlue, size: 24),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(
                              course.courseName,
                              style: GoogleFonts.inter(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.primaryBlue,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: statusBg,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              statusText,
                              style: GoogleFonts.barlow(
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                color: statusColor,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        course.courseDescription,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.barlow(
                          fontSize: 13,
                          color: AppTheme.gray,
                          height: 1.4,
                        ),
                      ),
                      if (course.deadline != null) ...[
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            Icon(Icons.calendar_today_outlined, size: 14, color: AppTheme.gray.withOpacity(0.8)),
                            const SizedBox(width: 6),
                            Text(
                              'Deadline: ${course.deadline!.split(' ')[0]}',
                              style: GoogleFonts.barlow(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.gray.withOpacity(0.8),
                              ),
                            ),
                          ],
                        ),
                      ],
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

class _EmptyCourseView extends StatelessWidget {
  const _EmptyCourseView();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.video_library_outlined, size: 64, color: AppTheme.lightGray),
          const SizedBox(height: 16),
          Text(
            'Select a Course to Begin',
            style: GoogleFonts.inter(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: AppTheme.gray,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Choose a course from the active courses list to view its modules and quizzes.',
            textAlign: TextAlign.center,
            style: GoogleFonts.barlow(color: AppTheme.gray, fontSize: 14),
          ),
        ],
      ),
    );
  }
}

class _TabHeaderButton extends StatelessWidget {
  final String title;
  final bool isActive;
  final VoidCallback onTap;

  const _TabHeaderButton({
    required this.title,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isActive ? AppTheme.primaryBlue.withOpacity(0.08) : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          title,
          style: GoogleFonts.barlow(
            fontSize: 15,
            fontWeight: isActive ? FontWeight.bold : FontWeight.w600,
            color: isActive ? AppTheme.primaryBlue : AppTheme.gray,
          ),
        ),
      ),
    );
  }
}
