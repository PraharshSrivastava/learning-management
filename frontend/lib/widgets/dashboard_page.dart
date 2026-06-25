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
                  title: 'Courses',
                  isActive: activeTab == 1,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 1,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Lessons',
                  isActive: activeTab == 2,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 2,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Slides',
                  isActive: activeTab == 3,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 3,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Scripts',
                  isActive: activeTab == 4,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 4,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Quiz',
                  isActive: activeTab == 5,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 5,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Video',
                  isActive: activeTab == 6,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 6,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Training',
                  isActive: activeTab == 7,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 7,
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
                  : activeTab == 2
                      ? _buildLessonsPortal(context, ref, selectedCourse, isMobile)
                      : activeTab == 3
                          ? _buildSlidesPortal(context, ref, selectedCourse, isMobile)
                          : activeTab == 4
                              ? _buildScriptsPortal(context, ref, selectedCourse, isMobile)
                              : activeTab == 5
                                  ? _buildQuizPortal(context, ref, selectedCourse, isMobile)
                                  : activeTab == 6
                                      ? _buildVideoPortal(context, ref, selectedCourse, isMobile)
                                      : _buildTrainingPortal(context, ref, selectedCourse, isMobile),
        ),
        
        if (generationState.status == GenerationStatus.generating)
          const _LoadingOverlay(message: 'Running modular extraction pipeline...\nAnalyzing document metadata & curriculum outline using Qwen3-8B...'),

        if (updateState.isUpdating)
          const _LoadingOverlay(message: 'Saving course blueprint modifications...'),

        if (lessonGenState.status == LessonGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating lessons for all modules...\n'
                'Step 1: LLM extracts lessons per module.\n'
                'Step 2: Holistic bullet refinement across full course.\n'
                'This may take 4–6 minutes — please wait.',
          ),



        if (ref.watch(quizGenerationProvider).status == QuizGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating module quizzes...\n'
                'Applying difficulty scaling and creating multiple choice questions...\n'
                'This may take 1–2 minutes — please wait.',
          ),

        if (ref.watch(slideGenerationProvider).status == SlideGenStatus.generating)
          const _LoadingOverlay(
            message: 'Planning visual slide layouts...\n'
                'Slicing bullets and selecting best templates (grid, concept, steps, comparison)...\n'
                'This may take 1–3 minutes — please wait.',
          ),

        if (ref.watch(scriptGenerationProvider).status == ScriptGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating module narration scripts...\n'
                'Writing voice speaker notes and synthesizing Text-to-Speech (TTS) audio files...\n'
                'This may take 1–3 minutes — please wait.',
          ),

        if (ref.watch(videoGenerationProvider).status == VideoGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating course module video...\n'
                'Rendering layout frames with Pillow & stitching sound via FFmpeg...\n'
                'This may take 1–3 minutes — please wait.',
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
    return Container(
      color: Colors.black.withOpacity(0.65),
      child: Center(
        child: Container(
          width: 380,
          padding: const EdgeInsets.all(32),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: AppTheme.pShapeRadius,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.2),
                blurRadius: 15,
                offset: const Offset(0, 5),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(
                width: 48,
                height: 48,
                child: CircularProgressIndicator(
                  valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryBlue),
                  strokeWidth: 4.5,
                ),
              ),
              const SizedBox(height: 24),
              Text(
                message,
                textAlign: TextAlign.center,
                style: GoogleFonts.barlow(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textBlack,
                  height: 1.4,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
