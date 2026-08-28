import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:video_player/video_player.dart';

import 'package:employee_frontend/core/theme/app_theme.dart';
import 'package:employee_frontend/data/models/models.dart';
import 'package:employee_frontend/state/employee_providers.dart';
import 'package:employee_frontend/core/config/app_constants.dart';

class CoursePlaybackView extends ConsumerStatefulWidget {
  final Course course;
  final VoidCallback? onBack;

  const CoursePlaybackView({super.key, required this.course, this.onBack});

  @override
  ConsumerState<CoursePlaybackView> createState() => _CoursePlaybackViewState();
}

class _CoursePlaybackViewState extends ConsumerState<CoursePlaybackView> {
  int _activeModuleIndex = 0;
  final Map<int, String> _selectedAnswers = {};
  final Set<int> _locallyWatchedModules = <int>{};
  final Set<int> _locallyPassedModules = <int>{};
  final Map<int, double> _localQuizScores = {};
  final GlobalKey _quizSectionKey = GlobalKey();
  bool _isQuizSubmitted = false;

  @override
  void initState() {
    super.initState();
    _loadProgressForCurrentModule();
  }

  @override
  void didUpdateWidget(covariant CoursePlaybackView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.course.courseId != widget.course.courseId) {
      setState(() {
        _activeModuleIndex = 0;
        _locallyWatchedModules.clear();
        _locallyPassedModules.clear();
        _localQuizScores.clear();
        _loadProgressForCurrentModule();
      });
    } else {
      _loadProgressForCurrentModule();
    }
  }

  void _onModuleChanged(int newIndex) {
    setState(() {
      _activeModuleIndex = newIndex;
      _loadProgressForCurrentModule();
    });
  }

  void _loadProgressForCurrentModule() {
    _selectedAnswers.clear();
    _isQuizSubmitted = false;

    if (widget.course.publishedModules.isEmpty) return;

    final currModuleStr = widget
        .course.publishedModules[_activeModuleIndex].moduleNumber
        .toString();
    final currProgress = widget.course.moduleProgress[currModuleStr];

    if (currProgress != null && currProgress.selectedAnswers != null) {
      _selectedAnswers.addAll(currProgress.selectedAnswers!);
      // If there are answers, it was submitted at least once
      _isQuizSubmitted = true;
    }
  }

  bool _isVideoUnlocked(int moduleIndex) {
    if (moduleIndex == 0) return true;
    final prevModule = widget.course.publishedModules[moduleIndex - 1];
    final prevModuleStr = prevModule.moduleNumber.toString();
    final prevProgress = widget.course.moduleProgress[prevModuleStr];
    final prevModuleNumber = prevModule.moduleNumber;
    if (prevModule.quiz.isEmpty) {
      return prevProgress?.videoWatched == true ||
          _locallyWatchedModules.contains(prevModuleNumber);
    }
    return prevProgress?.quizPassed == true ||
        _locallyPassedModules.contains(prevModuleNumber);
  }

  bool _isQuizUnlocked(int moduleIndex) {
    final currModuleStr =
        widget.course.publishedModules[moduleIndex].moduleNumber.toString();
    final currProgress = widget.course.moduleProgress[currModuleStr];
    final currModuleNumber =
        widget.course.publishedModules[moduleIndex].moduleNumber;
    return currProgress?.videoWatched == true ||
        _locallyWatchedModules.contains(currModuleNumber);
  }

  @override
  Widget build(BuildContext context) {
    final isMobile = MediaQuery.of(context).size.width < 900;

    if (widget.course.publishedModules.isEmpty) {
      return Center(
        child: Container(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.school_outlined, size: 64, color: AppTheme.gray),
              const SizedBox(height: 16),
              Text(
                'No Modules Available',
                style: GoogleFonts.inter(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryBlue,
                ),
              ),
            ],
          ),
        ),
      );
    }

    if (isMobile) {
      return _buildMobileLayout();
    } else {
      return _buildDesktopLayout();
    }
  }

  Widget _buildDesktopLayout() {
    final module = widget.course.publishedModules[_activeModuleIndex];

    return Column(
      children: [
        _buildCourseWorkspaceHeader(),
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                flex: 7,
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(28, 28, 28, 44),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _buildHeaderSection(module),
                      const SizedBox(height: 20),
                      _buildVideoPlayerSection(module),
                      const SizedBox(height: 20),
                      _buildNotesSection(module),
                      const SizedBox(height: 32),
                      const Divider(color: AppTheme.lightGray, height: 1),
                      const SizedBox(height: 28),
                      KeyedSubtree(
                        key: _quizSectionKey,
                        child: _buildQuizSection(module),
                      ),
                    ],
                  ),
                ),
              ),
              SizedBox(
                width: 330,
                child: Container(
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    border: Border(left: BorderSide(color: Color(0xFFE6E9EF))),
                  ),
                  padding: const EdgeInsets.fromLTRB(18, 24, 14, 20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Course content',
                        style: TextStyle(
                            fontSize: 16, fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${widget.course.publishedModules.length} modules',
                        style: const TextStyle(
                            fontSize: 13, color: Color(0xFF667085)),
                      ),
                      const SizedBox(height: 18),
                      Expanded(child: _buildModuleList()),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildCourseWorkspaceHeader() {
    final total = widget.course.publishedModules.length;
    final passed = widget.course.publishedModules.where((module) {
      return widget
              .course.moduleProgress['${module.moduleNumber}']?.quizPassed ==
          true;
    }).length;
    final progress = total == 0 ? 0.0 : passed / total;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 16),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: Color(0xFFE6E9EF))),
      ),
      child: Row(
        children: [
          IconButton(
            onPressed: widget.onBack,
            tooltip: 'Back to dashboard',
            icon: const Icon(Icons.arrow_back),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(widget.course.courseName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 18, fontWeight: FontWeight.w700)),
                const SizedBox(height: 3),
                Text(
                  '$passed of $total modules completed',
                  style:
                      const TextStyle(fontSize: 13, color: Color(0xFF667085)),
                ),
              ],
            ),
          ),
          SizedBox(
            width: 160,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text('${(progress * 100).round()}%',
                    style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        color: AppTheme.primaryBlue)),
                const SizedBox(height: 7),
                LinearProgressIndicator(
                  value: progress,
                  minHeight: 6,
                  borderRadius: BorderRadius.circular(4),
                  backgroundColor: const Color(0xFFE6E9EF),
                  color: AppTheme.primaryBlue,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMobileLayout() {
    final module = widget.course.publishedModules[_activeModuleIndex];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildCourseWorkspaceHeader(),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.grey.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.lightGray),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<int>(
                value: _activeModuleIndex,
                isExpanded: true,
                icon: const Icon(Icons.keyboard_arrow_down,
                    color: AppTheme.primaryBlue),
                items:
                    List.generate(widget.course.publishedModules.length, (idx) {
                  final m = widget.course.publishedModules[idx];
                  final unlocked = _isVideoUnlocked(idx);
                  return DropdownMenuItem<int>(
                    value: idx,
                    enabled: unlocked,
                    child: Text(
                      'Module ${m.moduleNumber}: ${m.title}',
                      style: GoogleFonts.barlow(
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                        color: unlocked ? AppTheme.primaryBlue : AppTheme.gray,
                      ),
                    ),
                  );
                }),
                onChanged: (val) {
                  if (val != null) {
                    _onModuleChanged(val);
                  }
                },
              ),
            ),
          ),
          const SizedBox(height: 20),
          _buildHeaderSection(module),
          const SizedBox(height: 16),
          _buildVideoPlayerSection(module),
          const SizedBox(height: 16),
          _buildNotesSection(module),
          const SizedBox(height: 24),
          const Divider(color: AppTheme.lightGray),
          const SizedBox(height: 20),
          KeyedSubtree(
            key: _quizSectionKey,
            child: _buildQuizSection(module),
          ),
        ],
      ),
    );
  }

  Widget _buildHeaderSection(PublishedCourseModule module) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: AppTheme.primaryBlue.withOpacity(0.08),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                'MODULE ${module.moduleNumber}',
                style: GoogleFonts.barlow(
                  fontWeight: FontWeight.bold,
                  fontSize: 11,
                  color: AppTheme.primaryBlue,
                  letterSpacing: 1.0,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Text(
          module.title,
          style: GoogleFonts.inter(
            fontSize: 22,
            fontWeight: FontWeight.bold,
            color: AppTheme.textBlack,
          ),
        ),
      ],
    );
  }

  Widget _buildVideoPlayerSection(PublishedCourseModule module) {
    final hasVideo = module.videoPath.isNotEmpty;
    if (!hasVideo) {
      return Container(
        height: 400,
        decoration: BoxDecoration(
          color: Colors.grey.shade50,
          borderRadius: AppTheme.pShapeRadius,
          border: Border.all(color: AppTheme.lightGray),
        ),
        child: const Center(
          child: Text('Video unavailable.'),
        ),
      );
    }

    final moduleStr = module.moduleNumber.toString();
    final progress = widget.course.moduleProgress[moduleStr];
    final bool initiallyWatched = progress?.videoWatched == true ||
        _locallyWatchedModules.contains(module.moduleNumber);

    return Container(
      decoration: BoxDecoration(
        color: Colors.black, // Set to black but do not constrain height
        borderRadius: AppTheme.pShapeRadius,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.12),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: EmployeeVideoPlayer(
        courseId: widget.course.courseId,
        moduleNumber: module.moduleNumber,
        videoFilename: module.videoPath,
        initiallyWatched: initiallyWatched,
        onVideoCompleted: () => _handleVideoCompleted(module.moduleNumber),
        key: ValueKey(
            '${widget.course.courseId}_${module.moduleNumber}_$initiallyWatched'),
      ),
    );
  }

  Widget _buildNotesSection(PublishedCourseModule module) {
    final notes = module.notes.trim().isNotEmpty
        ? module.notes.trim()
        : widget.course.courseDescription.trim().isNotEmpty
            ? widget.course.courseDescription.trim()
            : 'Complete the video lesson, then use the quiz to confirm your understanding of this module.';

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFE1E7EF)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppTheme.accentCyan.withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.notes_outlined, color: AppTheme.accentCyan),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Notes',
                    style:
                        TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                const SizedBox(height: 6),
                Text(notes,
                    style: const TextStyle(
                        fontSize: 14, height: 1.55, color: Color(0xFF475467))),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuizSection(PublishedCourseModule module) {
    final isQuizUnlocked = _isQuizUnlocked(_activeModuleIndex);

    if (!isQuizUnlocked) {
      return Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: const Color(0xFFFFF8E8),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: const Color(0xFFF3D19C)),
        ),
        child: const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.lock_outline, color: Color(0xFF8A5A00)),
            SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Quiz locked',
                      style: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF704A00))),
                  SizedBox(height: 4),
                  Text(
                      'Finish the video lesson to unlock this knowledge check.',
                      style: TextStyle(fontSize: 13, color: Color(0xFF704A00))),
                ],
              ),
            ),
          ],
        ),
      );
    }

    final questionsList = module.quiz;
    if (questionsList.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFFEFFAF3),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: const Color(0xFFB7E4C7)),
        ),
        child: const Row(
          children: [
            Icon(Icons.check_circle_outline, color: Color(0xFF087443)),
            SizedBox(width: 12),
            Expanded(
              child: Text(
                'No quiz is required for this module. Finish the video lesson to continue.',
                style: TextStyle(
                  color: Color(0xFF087443),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      );
    }

    final moduleStr = module.moduleNumber.toString();
    final progress = widget.course.moduleProgress[moduleStr];
    final bool isAlreadyPassed = progress?.quizPassed == true ||
        _locallyPassedModules.contains(module.moduleNumber);
    final quizScore = progress?.quizScore?.toDouble() ??
        _localQuizScores[module.moduleNumber] ??
        0.0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Module Quiz',
              style: GoogleFonts.inter(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppTheme.primaryBlue,
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: AppTheme.accentGreen.withOpacity(0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                '${_selectedAnswers.length}/${questionsList.length} answered',
                style: GoogleFonts.inter(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.accentGreen,
                ),
              ),
            ),
          ],
        ),
        if (isAlreadyPassed)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.accentGreen.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.accentGreen),
              ),
              child: Row(
                children: [
                  const Icon(Icons.check_circle, color: AppTheme.accentGreen),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'You have already passed this quiz with a score of ${(quizScore * 100).toStringAsFixed(1)}%. You can review the questions below.',
                      style: GoogleFonts.inter(
                          color: AppTheme.accentGreen,
                          fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
            ),
          ),
        const SizedBox(height: 20),
        ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: questionsList.length + 1,
          itemBuilder: (context, index) {
            if (index == questionsList.length) {
              if (isAlreadyPassed) return const SizedBox.shrink();
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryBlue,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: _isQuizSubmitted ||
                          _selectedAnswers.length < questionsList.length
                      ? null
                      : () => _submitQuiz(module),
                  child: Text(
                    _isQuizSubmitted ? 'Submitted' : 'Submit Quiz',
                    style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: Colors.white),
                  ),
                ),
              );
            }

            final q = questionsList[index];
            return _buildQuestionCard(index, q, isAlreadyPassed);
          },
        ),
      ],
    );
  }

  Widget _buildQuestionCard(
      int questionIndex, PublishedQuizQuestion question, bool isAlreadyPassed) {
    final selectedAnswer = _selectedAnswers[questionIndex];
    final isSubmitted = _isQuizSubmitted || isAlreadyPassed;

    return Container(
      margin: const EdgeInsets.only(bottom: 20),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'QUESTION ${questionIndex + 1}',
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: AppTheme.gray,
              letterSpacing: 1.0,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            question.question,
            style: GoogleFonts.inter(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppTheme.textBlack,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 16),
          Column(
            children: question.options.map((optionText) {
              final optIndex = question.options.indexOf(optionText);
              final optKey = String.fromCharCode(65 + optIndex); // A, B, C, D
              final isOptSelected = selectedAnswer == optKey;

              final isCorrectOpt = question.correct == optKey;

              Color cardBorderColor = AppTheme.lightGray;
              Color cardBgColor = Colors.white;
              Widget? suffixIcon;

              if (isSubmitted) {
                if (isCorrectOpt) {
                  cardBorderColor = AppTheme.accentGreen;
                  cardBgColor = AppTheme.accentGreen.withOpacity(0.08);
                  suffixIcon = const Icon(Icons.check_circle_rounded,
                      color: AppTheme.accentGreen, size: 18);
                } else if (isOptSelected && !isAlreadyPassed) {
                  cardBorderColor = AppTheme.accentRed;
                  cardBgColor = AppTheme.accentRed.withOpacity(0.08);
                  suffixIcon = const Icon(Icons.cancel_rounded,
                      color: AppTheme.accentRed, size: 18);
                } else {
                  cardBgColor = Colors.grey.shade50;
                }
              } else if (isOptSelected) {
                cardBorderColor = AppTheme.primaryBlue;
                cardBgColor = AppTheme.primaryBlue.withOpacity(0.05);
              }

              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                decoration: BoxDecoration(
                  color: cardBgColor,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                      color: cardBorderColor,
                      width: isOptSelected || (isSubmitted && isCorrectOpt)
                          ? 2
                          : 1),
                ),
                child: RadioListTile<String>(
                  groupValue:
                      isAlreadyPassed ? question.correct : selectedAnswer,
                  onChanged: isSubmitted
                      ? null
                      : (val) {
                          if (val != null) {
                            setState(
                              () => _selectedAnswers[questionIndex] = val,
                            );
                          }
                        },
                  title: Text(
                    optionText,
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      color: isSubmitted && isCorrectOpt
                          ? AppTheme.accentGreen
                          : AppTheme.textBlack,
                      fontWeight: isOptSelected || (isSubmitted && isCorrectOpt)
                          ? FontWeight.w600
                          : FontWeight.normal,
                    ),
                  ),
                  value: optKey,
                  activeColor: isSubmitted && isCorrectOpt
                      ? AppTheme.accentGreen
                      : AppTheme.primaryBlue,
                  secondary: suffixIcon,
                ),
              );
            }).toList(),
          ),
          if (isSubmitted && question.explanation.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 12.0),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.lightGray.withOpacity(0.5),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.lightbulb_outline,
                        size: 18, color: AppTheme.accentOrange),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        question.explanation,
                        style: GoogleFonts.inter(
                          fontSize: 13,
                          fontStyle: FontStyle.italic,
                          color: AppTheme.textBlack.withOpacity(0.8),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  void _submitQuiz(PublishedCourseModule module) async {
    if (_selectedAnswers.length < module.quiz.length) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Please answer all questions before submitting.')),
      );
      return;
    }

    setState(() {
      _isQuizSubmitted = true;
    });

    int correctCount = 0;
    for (int i = 0; i < module.quiz.length; i++) {
      if (_selectedAnswers[i] == module.quiz[i].correct) {
        correctCount++;
      }
    }

    final double score =
        module.quiz.isEmpty ? 1.0 : correctCount / module.quiz.length;
    final bool passed = score >= module.passMark;

    final formattedAnswers =
        _selectedAnswers.map((key, value) => MapEntry(key.toString(), value));

    await ref.read(employeeCourseListProvider.notifier).updateModuleProgress(
      widget.course.courseId,
      module.moduleNumber,
      {
        "quiz_passed": passed,
        "quiz_score": score,
        "selected_answers": passed ? formattedAnswers : null,
        if (!passed)
          "video_watched": false, // Reset video requirement if failed
      },
    );

    if (!mounted) return;

    final isFinalModule =
        _activeModuleIndex == widget.course.publishedModules.length - 1;

    if (passed) {
      setState(() {
        _locallyPassedModules.add(module.moduleNumber);
        _locallyWatchedModules.add(module.moduleNumber);
        _localQuizScores[module.moduleNumber] = score;
      });

      if (!isFinalModule) {
        final nextModule =
            widget.course.publishedModules[_activeModuleIndex + 1];
        _showLearningSuccessSnackBar(
          context,
          message: 'Quiz passed. Opening Module ${nextModule.moduleNumber}.',
          icon: Icons.verified_rounded,
        );
        _onModuleChanged(_activeModuleIndex + 1);
        return;
      }
    } else {
      setState(() {
        _locallyWatchedModules.remove(module.moduleNumber);
      });
    }

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: Text(
            passed
                ? (isFinalModule ? 'Course Completed!' : 'Quiz Passed!')
                : 'Quiz Failed',
            style: TextStyle(
                color: passed ? AppTheme.accentGreen : AppTheme.accentRed)),
        content: Text(
          passed
              ? 'You scored ${(score * 100).toStringAsFixed(1)}%. ${isFinalModule ? "You have successfully finished the course." : "The next module is now unlocked!"}'
              : 'You scored ${(score * 100).toStringAsFixed(1)}%. You need ${(module.passMark * 100).toStringAsFixed(1)}% to pass.\n\nYou must re-watch the video lesson to try the quiz again.',
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context); // close dialog
              if (!passed) {
                // If failed, they have to rewatch the video
                setState(() {
                  _isQuizSubmitted = false;
                  _selectedAnswers.clear();
                });
              }
            },
            child: Text(passed && isFinalModule
                ? 'Finish'
                : (passed ? 'Continue' : 'Try Again')),
          ),
        ],
      ),
    );
  }

  void _handleVideoCompleted(int moduleNumber) {
    setState(() => _locallyWatchedModules.add(moduleNumber));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final quizContext = _quizSectionKey.currentContext;
      if (!mounted || quizContext == null) return;
      Scrollable.ensureVisible(
        quizContext,
        duration: const Duration(milliseconds: 450),
        curve: Curves.easeOutCubic,
        alignment: 0.12,
      );
    });
  }

  bool _isModuleVideoWatched(PublishedCourseModule module) {
    final progress =
        widget.course.moduleProgress[module.moduleNumber.toString()];
    return progress?.videoWatched == true ||
        _locallyWatchedModules.contains(module.moduleNumber);
  }

  bool _isModuleQuizPassed(PublishedCourseModule module) {
    final progress =
        widget.course.moduleProgress[module.moduleNumber.toString()];
    if (module.quiz.isEmpty) {
      return progress?.videoWatched == true ||
          _locallyWatchedModules.contains(module.moduleNumber);
    }
    return progress?.quizPassed == true ||
        _locallyPassedModules.contains(module.moduleNumber);
  }

  ({IconData icon, Color color, Color background, String label}) _moduleStatus(
      PublishedCourseModule module, bool unlocked) {
    final videoWatched = _isModuleVideoWatched(module);
    final quizPassed = _isModuleQuizPassed(module);
    if (!unlocked) {
      return (
        icon: Icons.lock_outline_rounded,
        color: const Color(0xFF667085),
        background: const Color(0xFFF2F4F7),
        label: 'Locked'
      );
    }
    if (quizPassed) {
      return (
        icon: Icons.verified_rounded,
        color: const Color(0xFF087E5B),
        background: const Color(0xFFE7F7F0),
        label: 'Completed'
      );
    }
    if (videoWatched) {
      return (
        icon: Icons.assignment_turned_in_rounded,
        color: const Color(0xFF087E5B),
        background: const Color(0xFFE7F7F0),
        label: 'Quiz ready'
      );
    }
    return (
      icon: Icons.play_circle_outline_rounded,
      color: AppTheme.primaryBlue,
      background: const Color(0xFFE7EFFF),
      label: 'In progress'
    );
  }

  Widget _buildModuleList() {
    return ListView.builder(
      itemCount: widget.course.publishedModules.length,
      itemBuilder: (context, index) {
        final m = widget.course.publishedModules[index];
        final isSelected = _activeModuleIndex == index;
        final unlocked = _isVideoUnlocked(index);
        final status = _moduleStatus(m, unlocked);

        return InkWell(
          onTap: unlocked ? () => _onModuleChanged(index) : null,
          borderRadius: BorderRadius.circular(8),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isSelected
                  ? AppTheme.primaryBlue.withOpacity(0.06)
                  : Colors.white,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: isSelected ? AppTheme.primaryBlue : AppTheme.lightGray,
                width: isSelected ? 1.5 : 1,
              ),
            ),
            child: Row(
              children: [
                Tooltip(
                  message: status.label,
                  child: Container(
                    width: 34,
                    height: 34,
                    decoration: BoxDecoration(
                      color: status.background,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(status.icon, color: status.color, size: 20),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Opacity(
                    opacity: unlocked ? 1.0 : 0.62,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'MODULE ${m.moduleNumber}',
                          style: GoogleFonts.barlow(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: isSelected
                                ? AppTheme.primaryBlue
                                : const Color(0xFF667085),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          m.title,
                          style: GoogleFonts.inter(
                            fontSize: 13,
                            fontWeight:
                                isSelected ? FontWeight.bold : FontWeight.w600,
                            color: isSelected
                                ? AppTheme.primaryBlue
                                : AppTheme.textBlack,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 5),
                        Text(
                          status.label,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: status.color,
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
      },
    );
  }
}

void _showLearningSuccessSnackBar(
  BuildContext context, {
  required String message,
  required IconData icon,
}) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      behavior: SnackBarBehavior.floating,
      elevation: 8,
      margin: const EdgeInsets.fromLTRB(24, 0, 24, 24),
      backgroundColor: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: Color(0xFFD6E8E2)),
      ),
      content: Row(
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: const BoxDecoration(
              color: Color(0xFFE7F7F0),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: const Color(0xFF087E5B), size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                color: Color(0xFF101828),
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
      duration: const Duration(seconds: 3),
    ),
  );
}

class EmployeeVideoPlayer extends ConsumerStatefulWidget {
  final String courseId;
  final int moduleNumber;
  final String videoFilename;
  final bool initiallyWatched;
  final VoidCallback? onVideoCompleted;

  const EmployeeVideoPlayer({
    super.key,
    required this.courseId,
    required this.moduleNumber,
    required this.videoFilename,
    required this.initiallyWatched,
    this.onVideoCompleted,
  });

  @override
  ConsumerState<EmployeeVideoPlayer> createState() =>
      _EmployeeVideoPlayerState();
}

class _EmployeeVideoPlayerState extends ConsumerState<EmployeeVideoPlayer> {
  late VideoPlayerController _controller;
  bool _isError = false;
  late bool _markedWatched;
  bool _isHovering = false;
  String? _errorMsg;
  double _playbackMultiplier = 1.0;
  bool _showingFullscreen = false;

  @override
  void initState() {
    super.initState();
    _markedWatched = widget.initiallyWatched;
    _initializeController();
  }

  void _initializeController() {
    final videoUrl = AppConstants.videoAssetUrl(widget.videoFilename);
    final controller = VideoPlayerController.networkUrl(Uri.parse(videoUrl));
    _controller = controller;
    controller.addListener(_handleProgress);
    controller.initialize().then((_) {
      if (mounted && identical(_controller, controller)) setState(() {});
    }).catchError((error) {
      if (mounted && identical(_controller, controller)) {
        setState(() {
          _isError = true;
          _errorMsg = error.toString();
        });
      }
    });
  }

  void _handleProgress() {
    final value = _controller.value;
    final isNearEnd = value.duration.inMilliseconds > 0 &&
        value.position.inMilliseconds >= value.duration.inMilliseconds - 350;
    if (value.isInitialized && isNearEnd && !_markedWatched) {
      _markWatched();
    }
  }

  Future<void> _markWatched() async {
    if (_markedWatched) return;
    _markedWatched = true;

    await ref.read(employeeCourseListProvider.notifier).updateModuleProgress(
      widget.courseId,
      widget.moduleNumber,
      {"video_watched": true},
    );

    if (mounted) {
      widget.onVideoCompleted?.call();
      _showLearningSuccessSnackBar(
        context,
        message: 'Video completed. Quiz unlocked.',
        icon: Icons.assignment_turned_in_rounded,
      );
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  String _formatDuration(Duration d) {
    String minutes = d.inMinutes.toString().padLeft(2, '0');
    String seconds = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  Future<void> _enterFullscreen() async {
    if (_showingFullscreen) return;
    setState(() => _showingFullscreen = true);
    await Future<void>.delayed(const Duration(milliseconds: 16));
    if (!mounted) return;
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (context) => FullscreenVideoPlayer(controller: _controller),
    ));
    if (mounted) setState(() => _showingFullscreen = false);
  }

  Future<void> _setPlaybackMultiplier(double value) async {
    await _controller.setPlaybackSpeed(value);
    if (mounted) setState(() => _playbackMultiplier = value);
  }

  Future<void> _seekBy(Duration offset) async {
    final duration = _controller.value.duration;
    final requested = _controller.value.position + offset;
    final milliseconds = requested.inMilliseconds
        .clamp(0, duration.inMilliseconds)
        .toInt();
    await _controller.seekTo(Duration(milliseconds: milliseconds));
  }

  Future<void> _retryInitialization() async {
    await _controller.dispose();
    if (!mounted) return;
    _isError = false;
    _errorMsg = null;
    _initializeController();
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    if (_isError && _errorMsg != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded,
                  color: AppTheme.accentRed, size: 48),
              const SizedBox(height: 16),
              Text(
                'Failed to load video player',
                style: GoogleFonts.inter(
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                    fontSize: 16),
              ),
              const SizedBox(height: 8),
              Text(
                _errorMsg!,
                textAlign: TextAlign.center,
                style: GoogleFonts.barlow(color: Colors.white70, fontSize: 13),
              ),
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: _retryInitialization,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Retry video'),
              ),
            ],
          ),
        ),
      );
    }

    if (!_controller.value.isInitialized) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(32.0),
          child: CircularProgressIndicator(
            valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
          ),
        ),
      );
    }

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovering = true),
      onExit: (_) => setState(() => _isHovering = false),
      child: Stack(
        alignment: Alignment.bottomCenter,
        children: [
          Center(
            child: AspectRatio(
              aspectRatio: _controller.value.aspectRatio,
              child: _showingFullscreen
                  ? const SizedBox.expand()
                  : VideoPlayer(_controller),
            ),
          ),
          ValueListenableBuilder<VideoPlayerValue>(
            valueListenable: _controller,
            builder: (context, value, child) => value.isBuffering
                ? const Center(
                    child: CircularProgressIndicator(
                      valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                    ),
                  )
                : const SizedBox.shrink(),
          ),
          AnimatedOpacity(
            opacity: _isHovering || !_controller.value.isPlaying ? 1.0 : 0.0,
            duration: const Duration(milliseconds: 250),
            child: Container(
              color: Colors.black.withOpacity(0.55),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  VideoProgressIndicator(
                    _controller,
                    allowScrubbing: true,
                    colors: const VideoProgressColors(
                      playedColor: AppTheme.accentCyan,
                      bufferedColor: Colors.white24,
                      backgroundColor: Colors.white10,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          IconButton(
                            icon: Icon(
                              _controller.value.isPlaying
                                  ? Icons.pause_rounded
                                  : Icons.play_arrow_rounded,
                              color: Colors.white,
                            ),
                            onPressed: () {
                              setState(() {
                                if (_controller.value.isPlaying) {
                                  _controller.pause();
                                } else {
                                  _controller.play();
                                }
                              });
                            },
                          ),
                          IconButton(
                            tooltip: 'Back 10 seconds',
                            icon: const Icon(Icons.replay_10_rounded,
                                color: Colors.white),
                            onPressed: () =>
                                _seekBy(const Duration(seconds: -10)),
                          ),
                          IconButton(
                            tooltip: 'Forward 10 seconds',
                            icon: const Icon(Icons.forward_10_rounded,
                                color: Colors.white),
                            onPressed: () =>
                                _seekBy(const Duration(seconds: 10)),
                          ),
                          const SizedBox(width: 4),
                          ValueListenableBuilder(
                            valueListenable: _controller,
                            builder: (context, VideoPlayerValue value, child) {
                              return Text(
                                '${_formatDuration(value.position)} / ${_formatDuration(_controller.value.duration)}',
                                style: GoogleFonts.barlow(
                                    color: Colors.white, fontSize: 13),
                              );
                            },
                          ),
                        ],
                      ),
                      Row(
                        children: [
                          Icon(
                            _controller.value.volume == 0
                                ? Icons.volume_off_rounded
                                : Icons.volume_up_rounded,
                            color: Colors.white,
                            size: 20,
                          ),
                          const SizedBox(width: 4),
                          SizedBox(
                            width: 100,
                            child: SliderTheme(
                              data: SliderTheme.of(context).copyWith(
                                trackHeight: 3,
                                thumbShape: const RoundSliderThumbShape(
                                    enabledThumbRadius: 6),
                                activeTrackColor: Colors.white,
                                inactiveTrackColor: Colors.white24,
                                thumbColor: Colors.white,
                              ),
                              child: Slider(
                                value: _controller.value.volume,
                                min: 0,
                                max: 1,
                                onChanged: (val) {
                                  setState(() {
                                    _controller.setVolume(val);
                                  });
                                },
                              ),
                            ),
                          ),
                          PopupMenuButton<double>(
                            tooltip: 'Playback speed',
                            initialValue: _playbackMultiplier,
                            onSelected: _setPlaybackMultiplier,
                            itemBuilder: (_) => const [
                              PopupMenuItem(value: 0.5, child: Text('0.5x')),
                              PopupMenuItem(value: 0.75, child: Text('0.75x')),
                              PopupMenuItem(value: 1.0, child: Text('1x')),
                              PopupMenuItem(value: 1.25, child: Text('1.25x')),
                              PopupMenuItem(value: 1.5, child: Text('1.5x')),
                              PopupMenuItem(value: 2.0, child: Text('2x')),
                            ],
                            child: Text('${_playbackMultiplier}x',
                                style: const TextStyle(color: Colors.white)),
                          ),
                          IconButton(
                            icon: const Icon(Icons.fullscreen_rounded,
                                color: Colors.white),
                            onPressed: _enterFullscreen,
                            tooltip: 'Fullscreen View',
                          ),
                        ],
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class FullscreenVideoPlayer extends StatefulWidget {
  final VideoPlayerController controller;

  const FullscreenVideoPlayer({super.key, required this.controller});

  @override
  State<FullscreenVideoPlayer> createState() => _FullscreenVideoPlayerState();
}

class _FullscreenVideoPlayerState extends State<FullscreenVideoPlayer> {
  bool _isHovering = false;

  String _formatDuration(Duration d) {
    String minutes = d.inMinutes.toString().padLeft(2, '0');
    String seconds = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  Future<void> _seekBy(Duration offset) async {
    final duration = widget.controller.value.duration;
    final requested = widget.controller.value.position + offset;
    final milliseconds = requested.inMilliseconds
        .clamp(0, duration.inMilliseconds)
        .toInt();
    await widget.controller.seekTo(Duration(milliseconds: milliseconds));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: MouseRegion(
        onEnter: (_) => setState(() => _isHovering = true),
        onExit: (_) => setState(() => _isHovering = false),
        child: Stack(
          alignment: Alignment.center,
          children: [
            Center(
              child: AspectRatio(
                aspectRatio: widget.controller.value.aspectRatio,
                child: VideoPlayer(widget.controller),
              ),
            ),

            ValueListenableBuilder<VideoPlayerValue>(
              valueListenable: widget.controller,
              builder: (context, value, child) => value.isBuffering
                  ? const CircularProgressIndicator(
                      valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                    )
                  : const SizedBox.shrink(),
            ),

            // Exit button top-right
            Positioned(
              top: 24,
              right: 24,
              child: AnimatedOpacity(
                opacity: _isHovering || !widget.controller.value.isPlaying
                    ? 1.0
                    : 0.0,
                duration: const Duration(milliseconds: 200),
                child: FloatingActionButton(
                  backgroundColor: Colors.black.withOpacity(0.5),
                  mini: true,
                  child: const Icon(Icons.fullscreen_exit_rounded,
                      color: Colors.white),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ),
            ),

            // Controls bottom
            Positioned(
              bottom: 0,
              left: 0,
              right: 0,
              child: AnimatedOpacity(
                opacity: _isHovering || !widget.controller.value.isPlaying
                    ? 1.0
                    : 0.0,
                duration: const Duration(milliseconds: 200),
                child: Container(
                  color: Colors.black.withOpacity(0.6),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      VideoProgressIndicator(
                        widget.controller,
                        allowScrubbing: true,
                        colors: const VideoProgressColors(
                          playedColor: AppTheme.accentCyan,
                          bufferedColor: Colors.white30,
                          backgroundColor: Colors.white12,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              IconButton(
                                iconSize: 28,
                                icon: Icon(
                                  widget.controller.value.isPlaying
                                      ? Icons.pause_rounded
                                      : Icons.play_arrow_rounded,
                                  color: Colors.white,
                                ),
                                onPressed: () {
                                  setState(() {
                                    if (widget.controller.value.isPlaying) {
                                      widget.controller.pause();
                                    } else {
                                      widget.controller.play();
                                    }
                                  });
                                },
                              ),
                              IconButton(
                                tooltip: 'Back 10 seconds',
                                icon: const Icon(Icons.replay_10_rounded,
                                    color: Colors.white),
                                onPressed: () =>
                                    _seekBy(const Duration(seconds: -10)),
                              ),
                              IconButton(
                                tooltip: 'Forward 10 seconds',
                                icon: const Icon(Icons.forward_10_rounded,
                                    color: Colors.white),
                                onPressed: () =>
                                    _seekBy(const Duration(seconds: 10)),
                              ),
                              const SizedBox(width: 8),
                              ValueListenableBuilder(
                                valueListenable: widget.controller,
                                builder:
                                    (context, VideoPlayerValue value, child) {
                                  return Text(
                                    '${_formatDuration(value.position)} / ${_formatDuration(widget.controller.value.duration)}',
                                    style: GoogleFonts.barlow(
                                        color: Colors.white, fontSize: 14),
                                  );
                                },
                              ),
                            ],
                          ),
                          IconButton(
                            iconSize: 28,
                            icon: const Icon(Icons.fullscreen_exit_rounded,
                                color: Colors.white),
                            onPressed: () => Navigator.of(context).pop(),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
