import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:frontend/core/theme/app_theme.dart';
import 'package:frontend/data/models/models.dart';
import 'package:frontend/state/trainer_providers.dart';
import 'package:frontend/features/documents/document_portal.dart';
import 'package:frontend/features/courses/course_portal.dart';
import 'package:frontend/features/training/training_portal.dart';
import 'package:frontend/features/assignments/assignment_portal.dart';
import 'package:frontend/features/performance/performance_portal.dart';

class DashboardPage extends ConsumerStatefulWidget {
  const DashboardPage({super.key});

  @override
  ConsumerState<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends ConsumerState<DashboardPage> {
  String? _bootstrappedTrainerId;

  @override
  Widget build(BuildContext context) {
    final trainerAuth = ref.watch(trainerAuthProvider);
    if (!trainerAuth.isAuthenticated) {
      _bootstrappedTrainerId = null;
      return _TrainerLoginPage(auth: trainerAuth);
    }
    final trainerId = trainerAuth.trainer?.trainerId;
    if (trainerId != null && _bootstrappedTrainerId != trainerId) {
      _bootstrappedTrainerId = trainerId;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        final currentTrainerId =
            ref.read(trainerAuthProvider).trainer?.trainerId;
        if (currentTrainerId != trainerId) return;
        _bootstrapTrainerData(ref);
      });
    }

    final activeTab = ref.watch(currentTabProvider);
    final selectedFile = ref.watch(selectedFileProvider);
    final selectedCourse = ref.watch(selectedCourseProvider);
    final isMobile = MediaQuery.of(context).size.width < 900;

    final generationState = ref.watch(courseGenerationProvider);
    final updateState = ref.watch(courseUpdateProvider);
    final fullCourseGenState = ref.watch(fullCourseGenerationProvider);
    final isPublishingAssignment = activeTab == 3 &&
        ref.watch(assignmentProvider.select((state) => state.isPublishing));

    return Stack(
      children: [
        Scaffold(
          backgroundColor: Colors.transparent,
          appBar: AppBar(
            toolbarHeight: 72,
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
                Container(
                  height: 24,
                  width: 1,
                  color: AppTheme.lightGray,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        _TabHeaderButton(
                          title: 'Documents',
                          isActive: activeTab == 0,
                          onTap: () => _activateTrainerTab(ref, 0),
                        ),
                        const SizedBox(width: 8),
                        _TabHeaderButton(
                          title: 'Blueprint',
                          isActive: activeTab == 1,
                          onTap: () => _activateTrainerTab(ref, 1),
                        ),
                        const SizedBox(width: 8),
                        _TabHeaderButton(
                          title: 'Courses',
                          isActive: activeTab == 2,
                          onTap: () => _activateTrainerTab(ref, 2),
                        ),
                        const SizedBox(width: 8),
                        _TabHeaderButton(
                          title: 'Assign',
                          isActive: activeTab == 3,
                          onTap: () => _activateTrainerTab(ref, 3),
                        ),
                        const SizedBox(width: 8),
                        _TabHeaderButton(
                          title: 'Performance',
                          isActive: activeTab == 4,
                          onTap: () => _activateTrainerTab(ref, 4),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
            actions: [
              Padding(
                padding: const EdgeInsets.only(right: 6),
                child: Center(
                  child: Text(
                    trainerAuth.trainer?.name ?? '',
                    style: GoogleFonts.barlow(
                      color: AppTheme.primaryBlue,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.refresh, color: AppTheme.primaryBlue),
                onPressed: () {
                  ref.read(fileListProvider.notifier).fetchFiles();
                  ref.read(courseListProvider.notifier).fetchCourses();
                  ref
                      .read(assignableCourseListProvider.notifier)
                      .fetchCourses();
                  ref.read(performanceProvider.notifier).fetch();
                },
                tooltip: 'Refresh All Data',
              ),
              const SizedBox(width: 16),
            ],
            bottom: const PreferredSize(
              preferredSize: Size.fromHeight(1),
              child: Divider(height: 1),
            ),
          ),
          body: Container(
            decoration: AppTheme.pageBackground(),
            child: IndexedStack(
              index: activeTab,
              children: [
                _buildDocumentsPortal(context, ref, selectedFile, isMobile),
                _buildCoursesPortal(context, ref, selectedCourse, isMobile),
                _buildTrainingPortal(context, ref, selectedCourse, isMobile),
                AssignmentPortal(
                  selectedCourse: selectedCourse,
                  isMobile: isMobile,
                ),
                const PerformancePortal(),
              ],
            ),
          ),
        ),
        if (generationState.status == GenerationStatus.generating)
          const Positioned.fill(
            child: _LoadingOverlay(message: 'Creating your course outline'),
          ),
        if (fullCourseGenState.status == FullCourseGenStatus.generating)
          const Positioned.fill(
            child: _LoadingOverlay(
              message: 'Generating course content',
            ),
          ),
        if (updateState.isUpdating)
          const Positioned.fill(
            child: _LoadingOverlay(
                message: 'Saving course blueprint modifications...'),
          ),
        if (ref.watch(quizGenerationProvider).status ==
            QuizGenStatus.generating)
          const Positioned.fill(
            child: _LoadingOverlay(
              message: 'Generating quizzes',
            ),
          ),
        if (ref.watch(slideGenerationProvider).status ==
            SlideGenStatus.generating)
          const Positioned.fill(
            child: _LoadingOverlay(
              message: 'Generating slides',
            ),
          ),
        if (ref.watch(scriptGenerationProvider).status ==
            ScriptGenStatus.generating)
          const Positioned.fill(
            child: _LoadingOverlay(
              message: 'Generating narration',
            ),
          ),
        if (ref.watch(videoGenerationProvider).status ==
            VideoGenStatus.generating)
          const Positioned.fill(
            child: _LoadingOverlay(
              message: 'Generating video',
            ),
          ),
        if (isPublishingAssignment)
          const Positioned.fill(
            child: _LoadingOverlay(
              message: 'Publishing assignment...\n'
                  'Publishing may take up to 2 minutes.',
            ),
          ),
      ],
    );
  }

  Widget _buildTrainingPortal(BuildContext context, WidgetRef ref,
      Course? selectedCourse, bool isMobile) {
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
          child: Padding(
            padding: const EdgeInsets.all(20.0),
            child: CoursesSidebar(selectedCourse: selectedCourse),
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(24, 20, 24, 24),
            child: selectedCourse == null
                ? const EmptyCourseView()
                : TrainingView(course: selectedCourse),
          ),
        ),
      ],
    );
  }

  Widget _buildDocumentsPortal(BuildContext context, WidgetRef ref,
      PDFFile? selectedFile, bool isMobile) {
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
        Expanded(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(24, 20, 24, 24),
            child: PDFViewerCard(selectedFile: selectedFile),
          ),
        ),
      ],
    );
  }

  Widget _buildCoursesPortal(BuildContext context, WidgetRef ref,
      Course? selectedCourse, bool isMobile) {
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
          child: Padding(
            padding: const EdgeInsets.all(20.0),
            child: CoursesSidebar(selectedCourse: selectedCourse),
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(24, 20, 24, 24),
            child: selectedCourse == null
                ? const EmptyCourseView()
                : CourseDetailsView(course: selectedCourse),
          ),
        ),
      ],
    );
  }
}

void _bootstrapTrainerData(WidgetRef ref) {
  ref.read(fileListProvider.notifier).fetchFiles();
  ref.read(courseListProvider.notifier).ensureLoaded();
  ref.read(assignableCourseListProvider.notifier).ensureLoaded();
  ref.read(performanceProvider.notifier).fetch();
}

Future<void> _activateTrainerTab(WidgetRef ref, int tabIndex) async {
  ref.read(currentTabProvider.notifier).state = tabIndex;
  switch (tabIndex) {
    case 0:
      await ref.read(fileListProvider.notifier).fetchFiles();
      break;
    case 1:
    case 2:
      await ref.read(courseListProvider.notifier).ensureLoaded();
      _syncSelectedCourseFromList(ref);
      break;
    case 3:
      await ref.read(assignableCourseListProvider.notifier).ensureLoaded();
      _syncSelectedCourseFromAssignableList(ref);
      break;
    case 4:
      await ref.read(performanceProvider.notifier).fetch();
      break;
  }
}

void _syncSelectedCourseFromList(WidgetRef ref) {
  final selected = ref.read(selectedCourseProvider);
  if (selected == null) return;
  final matches = ref
      .read(courseListProvider)
      .courses
      .where((course) => course.courseId == selected.courseId)
      .toList();
  if (matches.isNotEmpty) {
    ref.read(selectedCourseProvider.notifier).state = matches.first;
  }
}

void _syncSelectedCourseFromAssignableList(WidgetRef ref) {
  final selected = ref.read(selectedCourseProvider);
  if (selected == null) return;
  final matches = ref
      .read(assignableCourseListProvider)
      .courses
      .where((course) => course.courseId == selected.courseId)
      .toList();
  if (matches.isNotEmpty) {
    ref.read(selectedCourseProvider.notifier).state = matches.first;
  }
}

class _TrainerLoginPage extends ConsumerWidget {
  final TrainerAuthState auth;

  const _TrainerLoginPage({required this.auth});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Container(
        decoration: AppTheme.pageBackground(),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          color: AppTheme.primaryBlue,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Center(
                          child: Text(
                            'PC',
                            style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Trainer access',
                            style: GoogleFonts.inter(
                              fontSize: 26,
                              fontWeight: FontWeight.w800,
                              color: AppTheme.textBlack,
                            ),
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            'Select a synced employee to test trainer access locally.',
                            style: TextStyle(color: Color(0xFF667085)),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  if (auth.isLoading && auth.trainers.isEmpty)
                    const Center(child: CircularProgressIndicator())
                  else
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        for (final trainer in auth.trainers)
                          SizedBox(
                            width: 235,
                            child: Card(
                              elevation: 0,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10),
                                side:
                                    const BorderSide(color: Color(0xFFE6E9EF)),
                              ),
                              child: InkWell(
                                borderRadius: BorderRadius.circular(10),
                                onTap: auth.isLoading
                                    ? null
                                    : () async {
                                        await ref
                                            .read(trainerAuthProvider.notifier)
                                            .login(trainer);
                                        if (ref
                                            .read(trainerAuthProvider)
                                            .isAuthenticated) {
                                          ref
                                              .read(fileListProvider.notifier)
                                              .fetchFiles();
                                          ref
                                              .read(courseListProvider.notifier)
                                              .ensureLoaded();
                                          ref
                                              .read(assignableCourseListProvider
                                                  .notifier)
                                              .ensureLoaded();
                                          ref
                                              .read(
                                                  performanceProvider.notifier)
                                              .fetch();
                                        }
                                      },
                                child: Padding(
                                  padding: const EdgeInsets.all(16),
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        trainer.name,
                                        style: GoogleFonts.barlow(
                                          fontSize: 17,
                                          fontWeight: FontWeight.w800,
                                          color: AppTheme.primaryBlue,
                                        ),
                                      ),
                                      const SizedBox(height: 6),
                                      Text(
                                        trainer.status,
                                        style: const TextStyle(
                                            color: Color(0xFF667085)),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        trainer.trainerId,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                          color: Color(0xFF98A2B3),
                                          fontSize: 12,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ),
                      ],
                    ),
                  if (auth.error != null) ...[
                    const SizedBox(height: 16),
                    Text(
                      auth.error!,
                      style: const TextStyle(color: AppTheme.accentRed),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
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
      borderRadius: BorderRadius.circular(999),
      child: Container(
        constraints: const BoxConstraints(minHeight: 44),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
        decoration: BoxDecoration(
          color: isActive ? AppTheme.brandBlue100 : Colors.transparent,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: isActive ? AppTheme.brandBlueLight : Colors.transparent,
          ),
        ),
        child: Text(
          title,
          style: GoogleFonts.barlow(
            fontSize: 15,
            fontWeight: isActive ? FontWeight.bold : FontWeight.w600,
            color: isActive ? AppTheme.primaryBlue : AppTheme.textSecondary,
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

    return Stack(
      children: [
        ModalBarrier(
          dismissible: false,
          color: const Color(0xFF101828).withOpacity(0.52),
        ),
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Material(
              color: Colors.white,
              elevation: 18,
              shadowColor: Colors.black.withOpacity(0.22),
              borderRadius: BorderRadius.circular(18),
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 58,
                      height: 58,
                      decoration: BoxDecoration(
                        color: AppTheme.brandBlue100,
                        borderRadius: BorderRadius.circular(16),
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
      ],
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

    if (lower.contains('publishing assignment')) {
      return const _LoadingOverlayContent(
        icon: Icons.publish_outlined,
        title: 'Publishing assignment',
        message:
            'We are assigning this course to the selected employee groups.',
        expectation: 'Publishing may take up to 2 minutes.',
      );
    }
    if (lower.contains('course content') || lower.contains('entire course')) {
      return const _LoadingOverlayContent(
        icon: Icons.school_outlined,
        title: 'Generating course content',
        message:
            'We are preparing quizzes, slides, narration, and videos for this course.',
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
    if (lower.contains('quiz')) {
      return const _LoadingOverlayContent(
        icon: Icons.quiz_outlined,
        title: 'Generating quizzes',
        message:
            'We are creating assessment questions for the selected module.',
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
        message:
            'We are preparing the speaking notes and audio for this module.',
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
