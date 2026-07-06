import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../theme.dart';
import '../models/models.dart';
import '../providers/employee_providers.dart';
import 'video_player_page.dart';
import 'take_quiz_page.dart';

class CoursePlaybackPage extends ConsumerWidget {
  final String courseId;

  const CoursePlaybackPage({super.key, required this.courseId});

  bool _isVideoUnlocked(Course course, int moduleIndex) {
    if (moduleIndex == 0) return true;
    final prevModuleStr = course.publishedModules[moduleIndex - 1].moduleNumber.toString();
    final prevProgress = course.employeeProgress[prevModuleStr];
    return prevProgress?.quizPassed == true;
  }

  bool _isQuizUnlocked(Course course, int moduleIndex) {
    final currModuleStr = course.publishedModules[moduleIndex].moduleNumber.toString();
    final currProgress = course.employeeProgress[currModuleStr];
    return currProgress?.videoWatched == true;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final courseState = ref.watch(employeeCourseListProvider);
    final course = courseState.courses.firstWhere(
      (c) => c.id == courseId,
      orElse: () => throw Exception('Course not found'),
    );

    return Scaffold(
      backgroundColor: AppTheme.lightGray,
      appBar: AppBar(
        title: Text(
          course.courseName,
          style: GoogleFonts.barlow(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: AppTheme.primaryBlue,
          ),
        ),
        iconTheme: IconThemeData(color: AppTheme.primaryBlue),
      ),
      body: course.publishedModules.isEmpty
          ? const Center(child: Text('No modules available.'))
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: course.publishedModules.length,
              itemBuilder: (context, index) {
                final module = course.publishedModules[index];
                final videoUnlocked = _isVideoUnlocked(course, index);
                final quizUnlocked = _isQuizUnlocked(course, index);
                final moduleStr = module.moduleNumber.toString();
                final progress = course.employeeProgress[moduleStr];

                return Card(
                  margin: const EdgeInsets.only(bottom: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  elevation: 2,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Module ${module.moduleNumber}: ${module.title}',
                          style: GoogleFonts.barlow(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.primaryBlue,
                          ),
                        ),
                        const SizedBox(height: 16),
                        
                        // Video Button
                        _PlaybackActionRow(
                          icon: Icons.play_circle_fill,
                          label: 'Watch Video Lesson',
                          isUnlocked: videoUnlocked,
                          isCompleted: progress?.videoWatched == true,
                          onTap: () {
                            if (!videoUnlocked) return;
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => VideoPlayerPage(
                                  courseId: course.id,
                                  moduleNumber: module.moduleNumber,
                                  videoFilename: module.videoUrl,
                                ),
                              ),
                            );
                          },
                        ),
                        
                        const Divider(height: 32),
                        
                        // Quiz Button
                        _PlaybackActionRow(
                          icon: Icons.quiz,
                          label: 'Take Module Quiz',
                          isUnlocked: quizUnlocked,
                          isCompleted: progress?.quizPassed == true,
                          onTap: () {
                            if (!quizUnlocked) return;
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => TakeQuizPage(
                                  courseId: course.id,
                                  moduleNumber: module.moduleNumber,
                                  quiz: module.quiz,
                                  passMark: module.passMark,
                                  isFinalModule: index == course.publishedModules.length - 1,
                                ),
                              ),
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
    );
  }
}

class _PlaybackActionRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isUnlocked;
  final bool isCompleted;
  final VoidCallback onTap;

  const _PlaybackActionRow({
    required this.icon,
    required this.label,
    required this.isUnlocked,
    required this.isCompleted,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    Color iconColor = isCompleted ? AppTheme.accentGreen : (isUnlocked ? AppTheme.primaryBlue : AppTheme.gray);
    Color textColor = isUnlocked ? Colors.black87 : AppTheme.gray;

    return InkWell(
      onTap: isUnlocked ? onTap : null,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 4.0),
        child: Row(
          children: [
            Icon(isUnlocked ? icon : Icons.lock, color: iconColor, size: 28),
            const SizedBox(width: 16),
            Expanded(
              child: Text(
                label,
                style: GoogleFonts.inter(
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                  color: textColor,
                ),
              ),
            ),
            if (isCompleted)
              Icon(Icons.check_circle, color: AppTheme.accentGreen, size: 24)
            else if (isUnlocked)
              Icon(Icons.arrow_forward_ios, color: AppTheme.primaryBlue, size: 16),
          ],
        ),
      ),
    );
  }
}
