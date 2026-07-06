import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../theme.dart';
import '../models/models.dart';
import '../providers/employee_providers.dart';
import 'course_playback_page.dart';

class EmployeeDashboardPage extends ConsumerWidget {
  const EmployeeDashboardPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(employeeCourseListProvider);

    return Scaffold(
      backgroundColor: AppTheme.lightGray,
      appBar: AppBar(
        title: Row(
          children: [
            Image.asset(
              'assets/logos/Type=Primary.png',
              height: 28,
              errorBuilder: (context, error, stackTrace) {
                return Text(
                  'PHILLIPCAPITAL',
                  style: GoogleFonts.inter(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.primaryBlue,
                    letterSpacing: 1.5,
                  ),
                );
              },
            ),
            const SizedBox(width: 8),
            Container(
              height: 20,
              width: 1,
              color: AppTheme.gray.withValues(alpha: 0.5),
            ),
            const SizedBox(width: 12),
            Text(
              'Employee Training Portal',
              style: GoogleFonts.barlow(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.primaryBlue,
              ),
            ),
          ],
        ),
      ),
      body: state.isLoading && state.courses.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : state.error != null
              ? Center(child: Text('Error: ${state.error}'))
              : _buildDashboardContent(context, state.courses),
    );
  }

  Widget _buildDashboardContent(BuildContext context, List<Course> courses) {
    final activeCourses = courses.where((c) => c.employeeStatus == 'pending' || c.employeeStatus == 'started').toList();
    final overdueCourses = courses.where((c) => c.employeeStatus == 'overdue').toList();
    final completedCourses = courses.where((c) => c.employeeStatus == 'completed').toList();

    return CustomScrollView(
      slivers: [
        if (activeCourses.isNotEmpty) ...[
          _buildSectionHeader('Active Courses', AppTheme.primaryBlue),
          _buildCourseList(activeCourses),
        ],
        if (overdueCourses.isNotEmpty) ...[
          _buildSectionHeader('Overdue', AppTheme.accentRed),
          _buildCourseList(overdueCourses),
        ],
        if (completedCourses.isNotEmpty) ...[
          _buildSectionHeader('Completed', AppTheme.accentGreen),
          _buildCourseList(completedCourses),
        ],
        if (courses.isEmpty)
          const SliverFillRemaining(
            child: Center(
              child: Text('No courses available.'),
            ),
          ),
      ],
    );
  }

  Widget _buildSectionHeader(String title, Color color) {
    return SliverToBoxAdapter(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
        child: Text(
          title,
          style: GoogleFonts.inter(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
      ),
    );
  }

  Widget _buildCourseList(List<Course> courses) {
    return SliverList(
      delegate: SliverChildBuilderDelegate(
        (context, index) {
          final course = courses[index];
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: InkWell(
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => CoursePlaybackPage(courseId: course.id),
                  ),
                );
              },
              borderRadius: BorderRadius.circular(12),
              child: Card(
                margin: EdgeInsets.zero,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 2,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              course.courseName,
                              style: GoogleFonts.barlow(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.primaryBlue),
                            ),
                          ),
                          _buildStatusBadge(course.employeeStatus ?? 'unknown'),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(course.courseDescription, maxLines: 2, overflow: TextOverflow.ellipsis),
                      const SizedBox(height: 12),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Deadline: ${course.deadline?.substring(0, 10) ?? "N/A"}',
                            style: TextStyle(
                              color: course.employeeStatus == 'overdue' ? AppTheme.accentRed : AppTheme.gray,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Icon(Icons.arrow_forward_ios, size: 16, color: AppTheme.primaryBlue),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
        childCount: courses.length,
      ),
    );
  }

  Widget _buildStatusBadge(String status) {
    Color color;
    switch (status) {
      case 'pending':
        color = AppTheme.accentOrange;
        break;
      case 'started':
        color = AppTheme.accentBlue;
        break;
      case 'completed':
        color = AppTheme.accentGreen;
        break;
      case 'overdue':
        color = AppTheme.accentRed;
        break;
      default:
        color = AppTheme.gray;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color),
      ),
      child: Text(
        status.toUpperCase(),
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
}
