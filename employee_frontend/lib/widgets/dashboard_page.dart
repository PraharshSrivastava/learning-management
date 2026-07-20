import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../theme.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import 'document_portal.dart';
import 'course_portal.dart';
import 'lesson_portal.dart';
import 'quiz_portal.dart';
import 'slides_portal.dart';
import 'scripts_portal.dart';
import 'video_portal.dart';
import 'training_portal.dart';


class DashboardPage extends ConsumerWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final activeTab = ref.watch(currentTabProvider);
    final selectedFile = ref.watch(selectedFileProvider);
    final selectedCourse = ref.watch(selectedCourseProvider);
    final isMobile = MediaQuery.of(context).size.width < 900;

    final generationState = ref.watch(courseGenerationProvider);
    final updateState = ref.watch(courseUpdateProvider);
    final lessonGenState = ref.watch(lessonGenerationProvider);
    final fullCourseGenState = ref.watch(fullCourseGenerationProvider);

    return Stack(
      children: [
        Scaffold(
          backgroundColor: Colors.white,
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
                  color: AppTheme.gray.withOpacity(0.5),
                ),
                const SizedBox(width: 12),
                _TabHeaderButton(
                  title: 'Documents',
                  isActive: activeTab == 0,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 0,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Blueprint',
                  isActive: activeTab == 1,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 1,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Courses',
                  isActive: activeTab == 2,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 2,
                ),
              ],
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh, color: AppTheme.primaryBlue),
                onPressed: () {
                  ref.read(fileListProvider.notifier).fetchFiles();
                  ref.read(courseListProvider.notifier).fetchCourses();
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
          body: activeTab == 0
              ? _buildDocumentsPortal(context, ref, selectedFile, isMobile)
              : activeTab == 1
                  ? _buildCoursesPortal(context, ref, selectedCourse, isMobile)
                  : _buildTrainingPortal(context, ref, selectedCourse, isMobile),
        ),
        
        if (generationState.status == GenerationStatus.generating)
          const _LoadingOverlay(message: 'Creating your course outline'),

        if (fullCourseGenState.status == FullCourseGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating course content',
          ),

        if (updateState.isUpdating)
          const _LoadingOverlay(message: 'Saving course blueprint modifications...'),

        if (lessonGenState.status == LessonGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating lessons',
          ),



        if (ref.watch(quizGenerationProvider).status == QuizGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating quizzes',
          ),

        if (ref.watch(slideGenerationProvider).status == SlideGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating slides',
          ),

        if (ref.watch(scriptGenerationProvider).status == ScriptGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating narration',
          ),

        if (ref.watch(videoGenerationProvider).status == VideoGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating video',
          ),
      ],
    );
  }

  Widget _buildLessonsPortal(BuildContext context, WidgetRef ref, Course? selectedCourse, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 300,
                child: CoursesSidebar(selectedCourse: selectedCourse),
              ),
            ),
            if (selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: LessonsView(course: selectedCourse),
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
              child: CoursesSidebar(selectedCourse: selectedCourse),
            ),
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: selectedCourse == null
                ? const EmptyCourseView()
                : LessonsView(course: selectedCourse),
          ),
        ),
      ],
    );
  }

  Widget _buildQuizPortal(BuildContext context, WidgetRef ref, Course? selectedCourse, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 300,
                child: CoursesSidebar(selectedCourse: selectedCourse),
              ),
            ),
            if (selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: QuizView(course: selectedCourse),
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
              child: CoursesSidebar(selectedCourse: selectedCourse),
            ),
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: selectedCourse == null
                ? const EmptyCourseView()
                : QuizView(course: selectedCourse),
          ),
        ),
      ],
    );
  }

  Widget _buildVideoPortal(BuildContext context, WidgetRef ref, Course? selectedCourse, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 300,
                child: CoursesSidebar(selectedCourse: selectedCourse),
              ),
            ),
            if (selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: VideoView(course: selectedCourse),
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
              child: CoursesSidebar(selectedCourse: selectedCourse),
            ),
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: selectedCourse == null
                ? const EmptyCourseView()
                : VideoView(course: selectedCourse),
          ),
        ),
      ],
    );
  }

  Widget _buildTrainingPortal(BuildContext context, WidgetRef ref, Course? selectedCourse, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 300,
                child: CoursesSidebar(selectedCourse: selectedCourse),
              ),
            ),
            if (selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: TrainingView(course: selectedCourse),
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
              child: CoursesSidebar(selectedCourse: selectedCourse),
            ),
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: selectedCourse == null
                ? const EmptyCourseView()
                : TrainingView(course: selectedCourse),
          ),
        ),
      ],
    );
  }


  Widget _buildSlidesPortal(BuildContext context, WidgetRef ref, Course? selectedCourse, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 300,
                child: CoursesSidebar(selectedCourse: selectedCourse),
              ),
            ),
            if (selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: SlidesView(course: selectedCourse),
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
              child: CoursesSidebar(selectedCourse: selectedCourse),
            ),
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: selectedCourse == null
                ? const EmptyCourseView()
                : SlidesView(course: selectedCourse),
          ),
        ),
      ],
    );
  }

  Widget _buildDocumentsPortal(BuildContext context, WidgetRef ref, PDFFile? selectedFile, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.all(16.0),
              child: UploadCard(),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              child: DocumentListCard(selectedFile: selectedFile),
            ),
            if (selectedFile != null)
              Padding(
                padding: const EdgeInsets.all(16.0),
                child: SizedBox(
                  height: 600,
                  child: PDFViewerCard(selectedFile: selectedFile),
                ),
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
            child: Column(
              children: [
                const Padding(
                  padding: EdgeInsets.all(20.0),
                  child: UploadCard(),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20.0),
                    child: DocumentListCard(selectedFile: selectedFile),
                  ),
                ),
                const SizedBox(height: 20),
              ],
            ),
          ),
        ),
        Expanded(
          child: Container(
            color: AppTheme.lightGray.withOpacity(0.3),
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: PDFViewerCard(selectedFile: selectedFile),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildCoursesPortal(BuildContext context, WidgetRef ref, Course? selectedCourse, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 350,
                child: CoursesSidebar(selectedCourse: selectedCourse),
              ),
            ),
            if (selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: CourseDetailsView(course: selectedCourse),
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
              child: CoursesSidebar(selectedCourse: selectedCourse),
            ),
          ),
        ),
        Expanded(
          child: Container(
            color: AppTheme.lightGray.withOpacity(0.3),
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: selectedCourse == null
                  ? const EmptyCourseView()
                  : CourseDetailsView(course: selectedCourse),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildScriptsPortal(BuildContext context, WidgetRef ref, Course? selectedCourse, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 300,
                child: CoursesSidebar(selectedCourse: selectedCourse),
              ),
            ),
            if (selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: ScriptsView(course: selectedCourse),
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
              child: CoursesSidebar(selectedCourse: selectedCourse),
            ),
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: selectedCourse == null
                ? const EmptyCourseView()
                : ScriptsView(course: selectedCourse),
          ),
        ),
      ],
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

class _LoadingOverlay extends StatelessWidget {
  final String message;

  const _LoadingOverlay({required this.message});

  @override
  Widget build(BuildContext context) {
    final content = _LoadingOverlayContent.fromMessage(message);

    return Container(
      color: const Color(0xFF101828).withOpacity(0.52),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Material(
            color: Colors.white,
            elevation: 18,
            shadowColor: Colors.black.withOpacity(0.22),
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.all(28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 58,
                    height: 58,
                    decoration: BoxDecoration(
                      color: const Color(0xFFE7EFFF),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        const SizedBox(
                          width: 48,
                          height: 48,
                          child: CircularProgressIndicator(
                            valueColor: AlwaysStoppedAnimation<Color>(
                              AppTheme.primaryBlue,
                            ),
                            strokeWidth: 3.8,
                          ),
                        ),
                        Icon(
                          content.icon,
                          color: AppTheme.primaryBlue,
                          size: 22,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 22),
                  Text(
                    content.title,
                    textAlign: TextAlign.center,
                    style: GoogleFonts.manrope(
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                      color: const Color(0xFF101828),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    content.message,
                    textAlign: TextAlign.center,
                    style: GoogleFonts.dmSans(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: const Color(0xFF475467),
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 18),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 10,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF5F7FA),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFFE6E9EF)),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.schedule_outlined,
                          color: AppTheme.primaryBlue,
                          size: 18,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            content.expectation,
                            style: GoogleFonts.dmSans(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: const Color(0xFF344054),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _LoadingOverlayContent {
  final IconData icon;
  final String title;
  final String message;
  final String expectation;

  const _LoadingOverlayContent({
    required this.icon,
    required this.title,
    required this.message,
    required this.expectation,
  });

  factory _LoadingOverlayContent.fromMessage(String rawMessage) {
    final lower = rawMessage.toLowerCase();

    if (lower.contains('course content') || lower.contains('entire course')) {
      return const _LoadingOverlayContent(
        icon: Icons.school_outlined,
        title: 'Generating course content',
        message:
            'We are preparing lessons, quizzes, slides, narration, and videos for this course.',
        expectation: 'This may take a while, up to 60 minutes.',
      );
    }
    if (lower.contains('course outline') ||
        lower.contains('modular extraction') ||
        lower.contains('qwen')) {
      return const _LoadingOverlayContent(
        icon: Icons.auto_stories_outlined,
        title: 'Creating your course outline',
        message:
            'We are reading the document and shaping it into a course blueprint.',
        expectation: 'This may take up to 5 minutes.',
      );
    }
    if (lower.contains('lesson')) {
      return const _LoadingOverlayContent(
        icon: Icons.menu_book_outlined,
        title: 'Generating lessons',
        message: 'We are building lesson content for each module.',
        expectation: 'This may take up to 5 minutes.',
      );
    }
    if (lower.contains('quiz')) {
      return const _LoadingOverlayContent(
        icon: Icons.quiz_outlined,
        title: 'Generating quizzes',
        message: 'We are creating assessment questions for the selected module.',
        expectation: 'This may take up to 5 minutes.',
      );
    }
    if (lower.contains('slide')) {
      return const _LoadingOverlayContent(
        icon: Icons.slideshow_outlined,
        title: 'Generating slides',
        message: 'We are turning module content into a presentation deck.',
        expectation: 'This may take up to 5 minutes.',
      );
    }
    if (lower.contains('narration') || lower.contains('script')) {
      return const _LoadingOverlayContent(
        icon: Icons.record_voice_over_outlined,
        title: 'Generating narration',
        message: 'We are preparing the speaking notes and audio for this module.',
        expectation: 'This may take up to 5 minutes.',
      );
    }
    if (lower.contains('video')) {
      return const _LoadingOverlayContent(
        icon: Icons.ondemand_video_outlined,
        title: 'Generating video',
        message:
            'We are creating the module video from the prepared course material.',
        expectation: 'This may take up to 5 minutes.',
      );
    }
    if (lower.contains('saving')) {
      return const _LoadingOverlayContent(
        icon: Icons.save_outlined,
        title: 'Saving changes',
        message: 'We are updating the course blueprint.',
        expectation: 'This should only take a moment.',
      );
    }

    return _LoadingOverlayContent(
      icon: Icons.hourglass_top_outlined,
      title: 'Working on it',
      message: rawMessage.split('\n').first,
      expectation: 'This may take a few minutes.',
    );
  }
}
