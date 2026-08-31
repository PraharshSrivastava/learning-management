import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:video_player/video_player.dart';

import 'package:employee_frontend/core/theme/app_theme.dart';
import 'package:employee_frontend/core/video/hls_video_player.dart';
import 'package:employee_frontend/data/models/models.dart';
import 'package:employee_frontend/state/trainer_preview_providers.dart';
import 'package:employee_frontend/core/config/app_constants.dart';

class TrainingView extends ConsumerStatefulWidget {
  final Course course;

  const TrainingView({super.key, required this.course});

  @override
  ConsumerState<TrainingView> createState() => _TrainingViewState();
}

class _TrainingViewState extends ConsumerState<TrainingView> {
  int _activeModuleIndex = 0;
  final Map<String, String> _selectedOptions = {};
  final Map<String, bool> _submittedQuestions = {};

  @override
  void didUpdateWidget(covariant TrainingView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.course.courseId != widget.course.courseId) {
      setState(() {
        _activeModuleIndex = 0;
        _selectedOptions.clear();
        _submittedQuestions.clear();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.course.modules.isEmpty) {
      return Center(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 500),
          padding: const EdgeInsets.all(32),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: AppTheme.pShapeRadius,
            border: Border.all(color: AppTheme.lightGray),
          ),
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
              const SizedBox(height: 8),
              Text(
                'Please generate the course outline and modules first to start training.',
                textAlign: TextAlign.center,
                style: GoogleFonts.barlow(color: AppTheme.gray),
              ),
            ],
          ),
        ),
      );
    }

    final isMobile = MediaQuery.of(context).size.width < 900;
    if (isMobile) {
      return _buildMobileLayout();
    } else {
      return _buildDesktopLayout();
    }
  }

  Widget _buildDesktopLayout() {
    final module = widget.course.modules[_activeModuleIndex];

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Main Content Area (Left side)
        Expanded(
          flex: 7,
          child: SingleChildScrollView(
            padding: const EdgeInsets.only(right: 24, bottom: 40),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _buildHeaderSection(module),
                const SizedBox(height: 20),
                _buildVideoPlayerSection(module),
                const SizedBox(height: 16),
                _buildNotesSection(module),
                const SizedBox(height: 32),
                const Divider(color: AppTheme.lightGray, height: 1),
                const SizedBox(height: 28),
                _buildQuizSection(module, _activeModuleIndex),
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
            padding: const EdgeInsets.only(left: 20),
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
    final module = widget.course.modules[_activeModuleIndex];

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Module Dropdown Selector
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
                items: List.generate(widget.course.modules.length, (idx) {
                  final m = widget.course.modules[idx];
                  return DropdownMenuItem<int>(
                    value: idx,
                    child: Text(
                      'Module ${m.moduleNumber}: ${m.title}',
                      style: GoogleFonts.barlow(
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                        color: AppTheme.primaryBlue,
                      ),
                    ),
                  );
                }),
                onChanged: (val) {
                  if (val != null) {
                    setState(() {
                      _activeModuleIndex = val;
                    });
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
          _buildQuizSection(module, _activeModuleIndex),
        ],
      ),
    );
  }

  Widget _buildHeaderSection(CourseModule module) {
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

  Widget _buildVideoPlayerSection(CourseModule module) {
    final hasVideo = module.videoPath != null && module.videoPath!.isNotEmpty;
    if (!hasVideo) {
      return Container(
        height: 400,
        decoration: BoxDecoration(
          color: Colors.grey.shade50,
          borderRadius: AppTheme.pShapeRadius,
          border: Border.all(color: AppTheme.lightGray),
        ),
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.video_library_outlined,
                  size: 56, color: AppTheme.gray),
              const SizedBox(height: 16),
              Text(
                'No Video Compiled Yet',
                style: GoogleFonts.inter(
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: AppTheme.primaryBlue,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Generate the slides and video compilation first to watch.',
                style: GoogleFonts.barlow(color: AppTheme.gray),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: () {
                  ref.read(videoGenerationProvider.notifier).generateVideo(
                        widget.course.courseId,
                        module.moduleNumber,
                        ref,
                      );
                },
                icon: const Icon(Icons.bolt, size: 16),
                label: const Text('Compile Module Video'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.accentOrange,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(6)),
                ),
              ),
            ],
          ),
        ),
      );
    }

    final videoUrl = '${AppConstants.apiBaseUrl}/${module.videoPath!}';
    return Container(
      height: 450,
      decoration: BoxDecoration(
        color: Colors.black,
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
      child: HlsVideoPlayer(
        hlsUrl: AppConstants.hlsVideoAssetUrl(module.videoPath!),
        fallbackUrl: videoUrl,
        key: ValueKey(videoUrl),
      ),
    );
  }

  Widget _buildNotesSection(CourseModule module) {
    final notes = module.notes.trim().isNotEmpty
        ? module.notes.trim()
        : 'Generate narration scripts to create learner notes for this module.';
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFFF7FBFF),
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Icon(Icons.notes_outlined, color: AppTheme.accentCyan),
        const SizedBox(width: 10),
        Expanded(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Module notes',
              style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryBlue)),
          const SizedBox(height: 6),
          Text(notes,
              style: GoogleFonts.barlow(
                  fontSize: 14, height: 1.45, color: AppTheme.gray)),
        ])),
      ]),
    );
  }

  Widget _buildQuizSection(CourseModule module, int moduleIndex) {
    final hasQuiz = module.quiz != null &&
        module.quiz!['questions'] != null &&
        (module.quiz!['questions'] as List).isNotEmpty;

    if (!hasQuiz) {
      return Container(
        padding: const EdgeInsets.all(32),
        decoration: BoxDecoration(
          color: Colors.grey.shade50,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.lightGray),
        ),
        child: Column(
          children: [
            const Icon(Icons.quiz_outlined, size: 48, color: AppTheme.gray),
            const SizedBox(height: 12),
            Text(
              'No Quiz Available for this Module',
              style: GoogleFonts.inter(
                fontWeight: FontWeight.bold,
                fontSize: 15,
                color: AppTheme.primaryBlue,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Define the questions count and generate the module quiz to test your learning outcomes.',
              textAlign: TextAlign.center,
              style: GoogleFonts.barlow(color: AppTheme.gray, fontSize: 13),
            ),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: () async {
                await ref.read(quizGenerationProvider.notifier).generateQuiz(
                      widget.course.courseId,
                      ref,
                    );
              },
              icon: const Icon(Icons.auto_awesome, size: 16),
              label: const Text('Generate Quiz Now'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(6)),
              ),
            ),
          ],
        ),
      );
    }

    final questionsList = module.quiz!['questions'] as List;

    int submittedCount = 0;
    int correctCount = 0;
    for (int i = 0; i < questionsList.length; i++) {
      final key = "$moduleIndex-$i";
      if (_submittedQuestions[key] == true) {
        submittedCount++;
        final qJson = questionsList[i] as Map<String, dynamic>;
        final correctOpt = qJson['correct_option']?.toString() ?? '';
        if (_selectedOptions[key] == correctOpt) {
          correctCount++;
        }
      }
    }

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
        const SizedBox(height: 20),
        ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: questionsList.length + 1,
          itemBuilder: (context, index) {
            if (index == questionsList.length) {
              return _buildSummaryCard(moduleIndex, questionsList.length,
                  submittedCount, correctCount);
            }

            final qJson = questionsList[index] as Map<String, dynamic>;
            final question = QuizQuestion.fromJson(qJson);

            return _buildQuestionCard(moduleIndex, index, question);
          },
        ),
      ],
    );
  }

  Widget _buildQuestionCard(
      int moduleIndex, int questionIndex, QuizQuestion question) {
    final key = "$moduleIndex-$questionIndex";
    final selectedOption = _selectedOptions[key];
    final isSubmitted = _submittedQuestions[key] == true;

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
            question.questionText,
            style: GoogleFonts.inter(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppTheme.textBlack,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 16),
          ...question.options.map((opt) {
            final optKey = opt.key;
            final isOptSelected = selectedOption == optKey;
            final isCorrectOpt = question.correctOption == optKey;

            Color cardBorderColor = AppTheme.lightGray;
            Color cardBgColor = Colors.white;
            Widget? suffixIcon;

            if (isSubmitted) {
              if (isCorrectOpt) {
                cardBorderColor = AppTheme.accentGreen;
                cardBgColor = AppTheme.accentGreen.withOpacity(0.08);
                suffixIcon = const Icon(Icons.check_circle_rounded,
                    color: AppTheme.accentGreen, size: 18);
              } else if (isOptSelected) {
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
              child: InkWell(
                onTap: isSubmitted
                    ? null
                    : () {
                        setState(() {
                          _selectedOptions[key] = optKey;
                        });
                      },
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: cardBgColor,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: cardBorderColor,
                      width: isOptSelected || (isSubmitted && isCorrectOpt)
                          ? 1.5
                          : 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 22,
                        height: 22,
                        decoration: BoxDecoration(
                          color: isOptSelected
                              ? (isSubmitted
                                  ? (isCorrectOpt
                                      ? AppTheme.accentGreen
                                      : AppTheme.accentRed)
                                  : AppTheme.primaryBlue)
                              : (isSubmitted && isCorrectOpt
                                  ? AppTheme.accentGreen
                                  : Colors.grey.shade100),
                          shape: BoxShape.circle,
                          border: Border.all(
                            color:
                                isOptSelected || (isSubmitted && isCorrectOpt)
                                    ? Colors.transparent
                                    : Colors.grey.shade300,
                          ),
                        ),
                        child: Center(
                          child: Text(
                            optKey,
                            style: GoogleFonts.inter(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color:
                                  isOptSelected || (isSubmitted && isCorrectOpt)
                                      ? Colors.white
                                      : AppTheme.textBlack,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          opt.text,
                          style: GoogleFonts.inter(
                            fontSize: 13.5,
                            fontWeight: isOptSelected
                                ? FontWeight.w600
                                : FontWeight.w500,
                            color:
                                isSubmitted && !isCorrectOpt && !isOptSelected
                                    ? AppTheme.gray
                                    : AppTheme.textBlack,
                          ),
                        ),
                      ),
                      if (suffixIcon != null) ...[
                        const SizedBox(width: 10),
                        suffixIcon,
                      ],
                    ],
                  ),
                ),
              ),
            );
          }).toList(),
          const SizedBox(height: 12),
          if (!isSubmitted)
            Align(
              alignment: Alignment.centerRight,
              child: ElevatedButton(
                onPressed: selectedOption == null
                    ? null
                    : () {
                        setState(() {
                          _submittedQuestions[key] = true;
                        });
                      },
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryBlue,
                  foregroundColor: Colors.white,
                  disabledBackgroundColor: Colors.grey.shade200,
                  disabledForegroundColor: Colors.grey.shade400,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(6)),
                  elevation: 0,
                ),
                child: const Text('Check Answer'),
              ),
            )
          else ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.grey.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.grey.shade200),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.info_outline_rounded,
                    color: AppTheme.primaryBlue.withOpacity(0.8),
                    size: 18,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Explanation',
                          style: GoogleFonts.inter(
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                            color: AppTheme.textBlack,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          question.explanation,
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            color: AppTheme.gray,
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSummaryCard(int moduleIndex, int totalQuestions,
      int submittedCount, int correctCount) {
    final isFinished = submittedCount == totalQuestions;

    return Container(
      margin: const EdgeInsets.only(top: 8, bottom: 20),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.primaryBlue,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Quiz Progress',
                    style: GoogleFonts.inter(
                      color: Colors.white70,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    isFinished ? 'Completed!' : 'In Progress',
                    style: GoogleFonts.inter(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.15),
                  shape: BoxShape.circle,
                ),
                child: Text(
                  '$correctCount / $totalQuestions',
                  style: GoogleFonts.inter(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: LinearProgressIndicator(
              value: totalQuestions > 0 ? (submittedCount / totalQuestions) : 0,
              backgroundColor: Colors.white24,
              valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
              minHeight: 6,
            ),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              OutlinedButton.icon(
                onPressed: () {
                  setState(() {
                    for (int i = 0; i < totalQuestions; i++) {
                      final key = "$moduleIndex-$i";
                      _selectedOptions.remove(key);
                      _submittedQuestions.remove(key);
                    }
                  });
                },
                icon: const Icon(Icons.refresh_rounded, size: 14),
                label: const Text('Reset Quiz'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Colors.white60),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(6)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildModuleList() {
    return ListView.builder(
      itemCount: widget.course.modules.length,
      itemBuilder: (context, index) {
        final m = widget.course.modules[index];
        final isSelected = _activeModuleIndex == index;
        final hasVideo = m.videoPath != null && m.videoPath!.isNotEmpty;
        final hasQuiz = m.quiz != null &&
            m.quiz!['questions'] != null &&
            (m.quiz!['questions'] as List).isNotEmpty;

        return InkWell(
          onTap: () {
            setState(() {
              _activeModuleIndex = index;
            });
          },
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
                        color:
                            isSelected ? AppTheme.primaryBlue : AppTheme.gray,
                      ),
                    ),
                    const Spacer(),
                    if (hasVideo)
                      const Icon(Icons.play_circle_fill,
                          color: AppTheme.accentGreen, size: 14)
                    else
                      const Icon(Icons.video_call,
                          color: AppTheme.gray, size: 14),
                    const SizedBox(width: 6),
                    if (hasQuiz)
                      const Icon(Icons.assignment_turned_in,
                          color: AppTheme.accentGreen, size: 14)
                    else
                      const Icon(Icons.assignment_outlined,
                          color: AppTheme.gray, size: 14),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  m.title,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: isSelected ? FontWeight.bold : FontWeight.w600,
                    color:
                        isSelected ? AppTheme.primaryBlue : AppTheme.textBlack,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class TrainingVideoPlayer extends StatefulWidget {
  final String url;

  const TrainingVideoPlayer({super.key, required this.url});

  @override
  State<TrainingVideoPlayer> createState() => _TrainingVideoPlayerState();
}

class _TrainingVideoPlayerState extends State<TrainingVideoPlayer> {
  late VideoPlayerController _controller;
  bool _isHovering = false;
  String? _errorMsg;
  double _playbackMultiplier = 1.0;
  bool _showingFullscreen = false;

  @override
  void initState() {
    super.initState();
    _controller = VideoPlayerController.networkUrl(Uri.parse(widget.url))
      ..initialize().then((_) {
        setState(() {});
      }).catchError((err) {
        setState(() {
          _errorMsg = err.toString();
        });
      });
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

  @override
  Widget build(BuildContext context) {
    if (_errorMsg != null) {
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
            ],
          ),
        ),
      );
    }

    if (!_controller.value.isInitialized) {
      return const Center(
        child: CircularProgressIndicator(
          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
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

          // Controls Overlay
          AnimatedOpacity(
            opacity: _isHovering || !_controller.value.isPlaying ? 1.0 : 0.0,
            duration: const Duration(milliseconds: 200),
            child: Container(
              color: Colors.black.withOpacity(0.55),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  VideoProgressIndicator(
                    _controller,
                    allowScrubbing: true,
                    colors: VideoProgressColors(
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
                          const SizedBox(width: 8),
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
                            width: 80,
                            child: SliderTheme(
                              data: SliderTheme.of(context).copyWith(
                                trackHeight: 2.5,
                                thumbShape: const RoundSliderThumbShape(
                                    enabledThumbRadius: 5),
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
                        colors: VideoProgressColors(
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
                              const SizedBox(width: 12),
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
