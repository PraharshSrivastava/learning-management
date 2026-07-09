import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:video_player/video_player.dart';

import '../theme.dart';
import '../models/models.dart';
import '../providers/employee_providers.dart';
import '../constants.dart';

class CoursePlaybackView extends ConsumerStatefulWidget {
  final Course course;
  const CoursePlaybackView({super.key, required this.course});

  @override
  ConsumerState<CoursePlaybackView> createState() => _CoursePlaybackViewState();
}

class _CoursePlaybackViewState extends ConsumerState<CoursePlaybackView> {
  int _activeModuleIndex = 0;
  final Map<int, String> _selectedAnswers = {};
  bool _isQuizSubmitted = false;

  @override
  void initState() {
    super.initState();
    _loadProgressForCurrentModule();
  }

  @override
  void didUpdateWidget(covariant CoursePlaybackView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.course.id != widget.course.id) {
      setState(() {
        _activeModuleIndex = 0;
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
    
    final currModuleStr = widget.course.publishedModules[_activeModuleIndex].moduleNumber.toString();
    final currProgress = widget.course.employeeProgress[currModuleStr];
    
    if (currProgress != null && currProgress.selectedAnswers != null) {
      _selectedAnswers.addAll(currProgress.selectedAnswers!);
      // If there are answers, it was submitted at least once
      _isQuizSubmitted = true;
    }
  }

  bool _isVideoUnlocked(int moduleIndex) {
    if (moduleIndex == 0) return true;
    final prevModuleStr = widget.course.publishedModules[moduleIndex - 1].moduleNumber.toString();
    final prevProgress = widget.course.employeeProgress[prevModuleStr];
    return prevProgress?.quizPassed == true;
  }

  bool _isQuizUnlocked(int moduleIndex) {
    final currModuleStr = widget.course.publishedModules[moduleIndex].moduleNumber.toString();
    final currProgress = widget.course.employeeProgress[currModuleStr];
    return currProgress?.videoWatched == true;
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

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Main Content Area (Left side)
        Expanded(
          flex: 7,
          child: SingleChildScrollView(
            padding: const EdgeInsets.only(right: 24, bottom: 40, left: 24, top: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _buildHeaderSection(module),
                const SizedBox(height: 20),
                _buildVideoPlayerSection(module),
                const SizedBox(height: 32),
                const Divider(color: AppTheme.lightGray, height: 1),
                const SizedBox(height: 28),
                _buildQuizSection(module),
              ],
            ),
          ),
        ),
        // Sidebar (Right side)
        SizedBox(
          width: 340,
          child: Container(
            decoration: const BoxDecoration(
              border: Border(
                left: BorderSide(color: AppTheme.lightGray, width: 1),
              ),
            ),
            padding: const EdgeInsets.only(left: 20, top: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: Text(
                    'COURSE CONTENT',
                    style: GoogleFonts.barlow(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.gray,
                      letterSpacing: 1.5,
                    ),
                  ),
                ),
                Expanded(
                  child: _buildModuleList(),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildMobileLayout() {
    final module = widget.course.publishedModules[_activeModuleIndex];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
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
                icon: const Icon(Icons.keyboard_arrow_down, color: AppTheme.primaryBlue),
                items: List.generate(widget.course.publishedModules.length, (idx) {
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
          const SizedBox(height: 24),
          const Divider(color: AppTheme.lightGray),
          const SizedBox(height: 20),
          _buildQuizSection(module),
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
    final hasVideo = module.videoUrl.isNotEmpty;
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
    final progress = widget.course.employeeProgress[moduleStr];
    final bool initiallyWatched = progress?.videoWatched == true;

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
        courseId: widget.course.id,
        moduleNumber: module.moduleNumber,
        videoFilename: module.videoUrl,
        initiallyWatched: initiallyWatched,
        key: ValueKey('${widget.course.id}_${module.moduleNumber}_$initiallyWatched'),
      ),
    );
  }

  Widget _buildQuizSection(PublishedCourseModule module) {
    final isQuizUnlocked = _isQuizUnlocked(_activeModuleIndex);
    
    if (!isQuizUnlocked) {
      return Container(
        padding: const EdgeInsets.all(32),
        decoration: BoxDecoration(
          color: Colors.grey.shade50,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.lightGray),
        ),
        child: Column(
          children: [
            const Icon(Icons.lock_outline, size: 48, color: AppTheme.gray),
            const SizedBox(height: 12),
            Text(
              'Quiz Locked',
              style: GoogleFonts.inter(
                fontWeight: FontWeight.bold,
                fontSize: 15,
                color: AppTheme.gray,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'You must watch the entire video lesson to unlock the quiz.',
              textAlign: TextAlign.center,
              style: GoogleFonts.barlow(color: AppTheme.gray, fontSize: 13),
            ),
          ],
        ),
      );
    }

    final questionsList = module.quiz;
    if (questionsList.isEmpty) {
      return const Center(child: Text('No quiz available.'));
    }

    final moduleStr = module.moduleNumber.toString();
    final progress = widget.course.employeeProgress[moduleStr];
    final bool isAlreadyPassed = progress?.quizPassed == true;

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
                '${questionsList.length} Questions',
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
                      'You have already passed this quiz with a score of ${((progress!.quizScore ?? 0) * 100).toStringAsFixed(1)}%. You can review the questions below.',
                      style: GoogleFonts.inter(color: AppTheme.accentGreen, fontWeight: FontWeight.bold),
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
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: _isQuizSubmitted ? null : () => _submitQuiz(module),
                  child: Text(
                    _isQuizSubmitted ? 'Submitted' : 'Submit Quiz',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
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

  Widget _buildQuestionCard(int questionIndex, PublishedQuizQuestion question, bool isAlreadyPassed) {
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
          ...question.options.map((optionText) {
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
                suffixIcon = const Icon(Icons.check_circle_rounded, color: AppTheme.accentGreen, size: 18);
              } else if (isOptSelected && !isAlreadyPassed) {
                cardBorderColor = AppTheme.accentRed;
                cardBgColor = AppTheme.accentRed.withOpacity(0.08);
                suffixIcon = const Icon(Icons.cancel_rounded, color: AppTheme.accentRed, size: 18);
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
                border: Border.all(color: cardBorderColor, width: isOptSelected || (isSubmitted && isCorrectOpt) ? 2 : 1),
              ),
              child: RadioListTile<String>(
                title: Text(
                  optionText,
                  style: GoogleFonts.inter(
                    fontSize: 14,
                    color: isSubmitted && isCorrectOpt ? AppTheme.accentGreen : AppTheme.textBlack,
                    fontWeight: isOptSelected || (isSubmitted && isCorrectOpt) ? FontWeight.w600 : FontWeight.normal,
                  ),
                ),
                value: optKey,
                groupValue: isAlreadyPassed ? question.correct : selectedAnswer,
                activeColor: isSubmitted && isCorrectOpt ? AppTheme.accentGreen : AppTheme.primaryBlue,
                onChanged: isSubmitted
                    ? null
                    : (val) {
                        setState(() {
                          _selectedAnswers[questionIndex] = val!;
                        });
                      },
                secondary: suffixIcon,
              ),
            );
          }),
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
                    const Icon(Icons.lightbulb_outline, size: 18, color: AppTheme.accentOrange),
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
        const SnackBar(content: Text('Please answer all questions before submitting.')),
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

    final double score = module.quiz.isEmpty ? 1.0 : correctCount / module.quiz.length;
    final bool passed = score >= module.passMark;

    final formattedAnswers = _selectedAnswers.map((key, value) => MapEntry(key.toString(), value));

    await ref.read(employeeCourseListProvider.notifier).updateModuleProgress(
      widget.course.id,
      module.moduleNumber,
      {
        "quiz_passed": passed,
        "quiz_score": score,
        "selected_answers": passed ? formattedAnswers : null,
        if (!passed) "video_watched": false, // Reset video requirement if failed
      },
    );

    if (!mounted) return;

    final isFinalModule = _activeModuleIndex == widget.course.publishedModules.length - 1;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: Text(
          passed ? (isFinalModule ? 'Course Completed!' : 'Quiz Passed!') : 'Quiz Failed', 
          style: TextStyle(color: passed ? AppTheme.accentGreen : AppTheme.accentRed)
        ),
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
            child: Text(passed && isFinalModule ? 'Finish' : (passed ? 'Continue' : 'Try Again')),
          ),
        ],
      ),
    );
  }

  Widget _buildModuleList() {
    return ListView.builder(
      itemCount: widget.course.publishedModules.length,
      itemBuilder: (context, index) {
        final m = widget.course.publishedModules[index];
        final isSelected = _activeModuleIndex == index;
        final hasVideo = m.videoUrl.isNotEmpty;
        final hasQuiz = m.quiz.isNotEmpty;
        final unlocked = _isVideoUnlocked(index);

        return InkWell(
          onTap: unlocked ? () {
            setState(() {
              _activeModuleIndex = index;
              _selectedAnswers.clear();
              _isQuizSubmitted = false;
            });
          } : null,
          borderRadius: BorderRadius.circular(8),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isSelected ? AppTheme.primaryBlue.withOpacity(0.06) : Colors.white,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: isSelected ? AppTheme.primaryBlue : AppTheme.lightGray,
                width: isSelected ? 1.5 : 1,
              ),
            ),
            child: Opacity(
              opacity: unlocked ? 1.0 : 0.5,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        'MODULE ${m.moduleNumber}',
                        style: GoogleFonts.barlow(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: isSelected ? AppTheme.primaryBlue : AppTheme.gray,
                        ),
                      ),
                      const Spacer(),
                      if (hasVideo)
                        const Icon(Icons.play_circle_fill, color: AppTheme.accentGreen, size: 14)
                      else
                        const Icon(Icons.video_call, color: AppTheme.gray, size: 14),
                      const SizedBox(width: 6),
                      if (hasQuiz)
                        const Icon(Icons.assignment_turned_in, color: AppTheme.accentGreen, size: 14)
                      else
                        const Icon(Icons.assignment_outlined, color: AppTheme.gray, size: 14),
                      if (!unlocked) ...[
                        const SizedBox(width: 6),
                        const Icon(Icons.lock, color: AppTheme.accentRed, size: 12),
                      ],
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    m.title,
                    style: GoogleFonts.inter(
                      fontSize: 13,
                      fontWeight: isSelected ? FontWeight.bold : FontWeight.w600,
                      color: isSelected ? AppTheme.primaryBlue : AppTheme.textBlack,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class EmployeeVideoPlayer extends ConsumerStatefulWidget {
  final String courseId;
  final int moduleNumber;
  final String videoFilename;
  final bool initiallyWatched;

  const EmployeeVideoPlayer({
    super.key,
    required this.courseId,
    required this.moduleNumber,
    required this.videoFilename,
    required this.initiallyWatched,
  });

  @override
  ConsumerState<EmployeeVideoPlayer> createState() => _EmployeeVideoPlayerState();
}

class _EmployeeVideoPlayerState extends ConsumerState<EmployeeVideoPlayer> {
  late VideoPlayerController _controller;
  bool _isError = false;
  late bool _markedWatched;
  bool _isHovering = false;
  String? _errorMsg;

  @override
  void initState() {
    super.initState();
    _markedWatched = widget.initiallyWatched;
    final videoUrl = AppConstants.videoAssetUrl(widget.videoFilename);
    _controller = VideoPlayerController.networkUrl(Uri.parse(videoUrl))
      ..initialize().then((_) {
        setState(() {});
        // removed auto-play!
      }).catchError((error) {
        setState(() {
          _isError = true;
          _errorMsg = error.toString();
        });
      });

    _controller.addListener(() {
      if (_controller.value.isInitialized && 
          !_controller.value.isPlaying && 
          _controller.value.duration == _controller.value.position &&
          !_markedWatched) {
        _markWatched();
      }
    });
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
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Video completed! Quiz unlocked.', style: TextStyle(color: Colors.white)), backgroundColor: AppTheme.accentGreen),
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

  void _enterFullscreen() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => FullscreenVideoPlayer(controller: _controller),
      ),
    );
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
              const Icon(Icons.error_outline_rounded, color: AppTheme.accentRed, size: 48),
              const SizedBox(height: 16),
              Text(
                'Failed to load video player',
                style: GoogleFonts.inter(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 16),
              ),
              const SizedBox(height: 8),
              Text(
                _errorMsg!,
                textAlign: TextAlign.center,
                style: GoogleFonts.barlow(color: Colors.white70, fontSize: 13),
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
              child: VideoPlayer(_controller),
            ),
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
                              _controller.value.isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded,
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
                          const SizedBox(width: 8),
                          ValueListenableBuilder(
                            valueListenable: _controller,
                            builder: (context, VideoPlayerValue value, child) {
                              return Text(
                                '${_formatDuration(value.position)} / ${_formatDuration(_controller.value.duration)}',
                                style: GoogleFonts.barlow(color: Colors.white, fontSize: 13),
                              );
                            },
                          ),
                        ],
                      ),
                      Row(
                        children: [
                          IconButton(
                            icon: const Icon(Icons.fullscreen_rounded, color: Colors.white),
                            onPressed: _enterFullscreen,
                            tooltip: 'Fullscreen View',
                          ),
                          const SizedBox(width: 8),
                          Icon(
                            _controller.value.volume == 0 ? Icons.volume_off_rounded : Icons.volume_up_rounded,
                            color: Colors.white,
                            size: 20,
                          ),
                          const SizedBox(width: 4),
                          SizedBox(
                            width: 100,
                            child: SliderTheme(
                              data: SliderTheme.of(context).copyWith(
                                trackHeight: 3,
                                thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
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
            
            // Exit button top-right
            Positioned(
              top: 24,
              right: 24,
              child: AnimatedOpacity(
                opacity: _isHovering || !widget.controller.value.isPlaying ? 1.0 : 0.0,
                duration: const Duration(milliseconds: 200),
                child: FloatingActionButton(
                  backgroundColor: Colors.black.withOpacity(0.5),
                  mini: true,
                  child: const Icon(Icons.fullscreen_exit_rounded, color: Colors.white),
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
                opacity: _isHovering || !widget.controller.value.isPlaying ? 1.0 : 0.0,
                duration: const Duration(milliseconds: 200),
                child: Container(
                  color: Colors.black.withOpacity(0.6),
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
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
                                  widget.controller.value.isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded,
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
                              const SizedBox(width: 12),
                              ValueListenableBuilder(
                                valueListenable: widget.controller,
                                builder: (context, VideoPlayerValue value, child) {
                                  return Text(
                                    '${_formatDuration(value.position)} / ${_formatDuration(widget.controller.value.duration)}',
                                    style: GoogleFonts.barlow(color: Colors.white, fontSize: 14),
                                  );
                                },
                              ),
                            ],
                          ),
                          IconButton(
                            iconSize: 28,
                            icon: const Icon(Icons.fullscreen_exit_rounded, color: Colors.white),
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
