import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../theme.dart';
import '../models/models.dart';
import '../providers/providers.dart';

class QuizView extends ConsumerStatefulWidget {
  final Course course;

  const QuizView({super.key, required this.course});

  @override
  ConsumerState<QuizView> createState() => _QuizViewState();
}

class _QuizViewState extends ConsumerState<QuizView> {
  int? _selectedModuleIndex;
  
  final Map<String, String> _selectedOptions = {};
  final Map<String, bool> _submittedQuestions = {};

  @override
  void initState() {
    super.initState();
    _initSelection();
  }

  @override
  void didUpdateWidget(covariant QuizView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.course.id != widget.course.id) {
      _initSelection();
      _selectedOptions.clear();
      _submittedQuestions.clear();
    }
  }

  void _initSelection() {
    _selectedModuleIndex = widget.course.modules.isEmpty ? null : 0;
  }

  bool get _hasAnyQuiz => widget.course.modules.isNotEmpty;

  List<int> get _quizModuleIndices {
    return List<int>.generate(widget.course.modules.length, (index) => index);
  }

  @override
  Widget build(BuildContext context) {
    if (!_hasAnyQuiz) {
      return _buildEmptyState(context);
    }

    final isMobile = MediaQuery.of(context).size.width < 900;
    if (isMobile) {
      return _buildMobileLayout(context);
    } else {
      return _buildDesktopLayout(context);
    }
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Container(
        constraints: const BoxConstraints(maxWidth: 550),
        padding: const EdgeInsets.all(40),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: AppTheme.pShapeRadius,
          border: Border.all(color: AppTheme.lightGray, width: 1),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.02),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.primaryBlue.withOpacity(0.08),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.quiz_rounded,
                size: 64,
                color: AppTheme.primaryBlue,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'No Quizzes Generated Yet',
              style: GoogleFonts.inter(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: AppTheme.primaryBlue,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(
              'Test learning outcomes with multiple-choice questions customized to your course difficulty level.\n\nTo generate quizzes:\n1. Go to the Courses tab\n2. Set "Quiz questions" count for each module\n3. Click Save Blueprint\n4. Generate Lessons (if not done already)\n5. Click "Generate Quiz" in the Lessons or Quiz tab',
              style: GoogleFonts.barlow(
                fontSize: 14,
                color: AppTheme.gray,
                height: 1.5,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                ElevatedButton.icon(
                  onPressed: () async {
                    await ref.read(quizGenerationProvider.notifier).generateQuiz(
                          widget.course.id,
                          ref,
                        );
                    if (context.mounted) {
                      final state = ref.read(quizGenerationProvider);
                      if (state.status == QuizGenStatus.success) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Quiz generated successfully!'),
                            backgroundColor: AppTheme.accentGreen,
                          ),
                        );
                      } else if (state.status == QuizGenStatus.error) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text('Quiz generation failed: ${state.error}'),
                            backgroundColor: AppTheme.accentRed,
                          ),
                        );
                      }
                    }
                  },
                  icon: const Icon(Icons.auto_awesome, size: 16),
                  label: const Text('Generate Quiz Now'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryBlue,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                    elevation: 0,
                  ),
                ),
                const SizedBox(width: 12),
                OutlinedButton.icon(
                  onPressed: () {
                    ref.read(currentTabProvider.notifier).state = 1;
                  },
                  icon: const Icon(Icons.arrow_forward_rounded, size: 16),
                  label: const Text('Go to Course Outline'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.primaryBlue,
                    side: const BorderSide(color: AppTheme.primaryBlue),
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDesktopLayout(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 320,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Quiz Modules',
                style: GoogleFonts.inter(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryBlue,
                ),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: _buildModuleList(context, isMobile: false),
              ),
            ],
          ),
        ),
        const SizedBox(width: 24),
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: AppTheme.pShapeRadius,
              border: Border.all(color: AppTheme.lightGray, width: 1),
            ),
            child: _buildQuizDetailPane(context),
          ),
        ),
      ],
    );
  }

  Widget _buildMobileLayout(BuildContext context) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Select Module Quiz',
            style: GoogleFonts.inter(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: AppTheme.primaryBlue,
            ),
          ),
          const SizedBox(height: 8),
          _buildModuleList(context, isMobile: true),
          const SizedBox(height: 16),
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: AppTheme.pShapeRadius,
              border: Border.all(color: AppTheme.lightGray, width: 1),
            ),
            child: _buildQuizDetailPane(context),
          ),
        ],
      ),
    );
  }

  Widget _buildModuleList(BuildContext context, {required bool isMobile}) {
    final indices = _quizModuleIndices;
    return ListView.builder(
      shrinkWrap: isMobile,
      physics: isMobile ? const NeverScrollableScrollPhysics() : const ClampingScrollPhysics(),
      itemCount: indices.length,
      itemBuilder: (context, index) {
        final modIndex = indices[index];
        final m = widget.course.modules[modIndex];
        final isSelected = _selectedModuleIndex == modIndex;
        final qList = _questionsFor(m);

        int completedCount = 0;
        int correctCount = 0;
        for (int qIdx = 0; qIdx < qList.length; qIdx++) {
          final key = "$modIndex-$qIdx";
          if (_submittedQuestions[key] == true) {
            completedCount++;
            final qJson = qList[qIdx] as Map<String, dynamic>;
            final correctOpt = qJson['correct_option']?.toString() ?? '';
            if (_selectedOptions[key] == correctOpt) {
              correctCount++;
            }
          }
        }

        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          decoration: BoxDecoration(
            color: isSelected ? AppTheme.primaryBlue.withOpacity(0.06) : Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: isSelected ? AppTheme.primaryBlue : AppTheme.lightGray,
              width: isSelected ? 1.5 : 1,
            ),
          ),
          child: ListTile(
            dense: true,
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            title: Text(
              'Module ${m.moduleNumber}',
              style: GoogleFonts.inter(
                fontWeight: FontWeight.bold,
                fontSize: 12,
                color: isSelected ? AppTheme.primaryBlue : AppTheme.gray,
              ),
            ),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 4),
                Text(
                  m.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                    color: AppTheme.textBlack,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '${qList.length} MCQ questions',
                      style: GoogleFonts.barlow(
                        fontSize: 12,
                        color: AppTheme.gray,
                      ),
                    ),
                    if (completedCount > 0)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: completedCount == qList.length
                              ? AppTheme.accentGreen.withOpacity(0.12)
                              : AppTheme.accentOrange.withOpacity(0.12),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          completedCount == qList.length
                              ? 'Score: $correctCount/${qList.length}'
                              : '$completedCount/${qList.length} Done',
                          style: GoogleFonts.barlow(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: completedCount == qList.length
                                ? AppTheme.accentGreen
                                : AppTheme.accentOrange,
                          ),
                        ),
                      ),
                  ],
                ),
              ],
            ),
            onTap: () {
              setState(() {
                _selectedModuleIndex = modIndex;
              });
            },
          ),
        );
      },
    );
  }

  Widget _buildQuizDetailPane(BuildContext context) {
    if (_selectedModuleIndex == null) {
      return const Center(child: Padding(
        padding: EdgeInsets.all(24.0),
        child: Text('Select a module quiz to begin.'),
      ));
    }

    final moduleIndex = _selectedModuleIndex!;
    final module = widget.course.modules[moduleIndex];

    final questionsList = _questionsFor(module);

    if (questionsList.isEmpty) {
      return _buildMissingQuizPane(context, module);
    }

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
        Container(
          padding: const EdgeInsets.all(20),
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: AppTheme.lightGray, width: 1)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Module ${module.moduleNumber} Quiz',
                      style: GoogleFonts.inter(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      module.title,
                      style: GoogleFonts.barlow(
                        fontSize: 14,
                        color: AppTheme.gray,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: _getDifficultyColor(widget.course.courseDifficulty).withOpacity(0.12),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  widget.course.courseDifficulty.toUpperCase(),
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: _getDifficultyColor(widget.course.courseDifficulty),
                  ),
                ),
              ),
            ],
          ),
        ),

        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(20),
            itemCount: questionsList.length + 1,
            itemBuilder: (context, index) {
              if (index == questionsList.length) {
                return _buildSummaryCard(moduleIndex, questionsList.length, submittedCount, correctCount);
              }

              final qJson = questionsList[index] as Map<String, dynamic>;
              final question = QuizQuestion.fromJson(qJson);

              return _buildQuestionCard(moduleIndex, index, question);
            },
          ),
        ),
      ],
    );
  }

  List _questionsFor(CourseModule module) {
    final quiz = module.quiz;
    if (quiz == null || quiz['questions'] is! List) return const [];
    return quiz['questions'] as List;
  }

  Widget _buildMissingQuizPane(BuildContext context, CourseModule module) {
    final canSkip = module.numQuestions <= 0;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                canSkip ? Icons.check_circle_outline : Icons.quiz_outlined,
                size: 56,
                color: canSkip ? AppTheme.accentGreen : AppTheme.primaryBlue,
              ),
              const SizedBox(height: 16),
              Text(
                canSkip ? 'Quiz disabled for this module' : 'No quiz questions yet',
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryBlue,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                canSkip
                    ? 'This module is set to 0 questions, so it can be published without a quiz once the video is ready.'
                    : 'If generation still fails after retries, create the MCQ quiz manually or set this module to 0 questions in the Course Outline before publishing.',
                textAlign: TextAlign.center,
                style: GoogleFonts.barlow(
                  fontSize: 14,
                  color: AppTheme.gray,
                  height: 1.45,
                ),
              ),
              const SizedBox(height: 24),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                alignment: WrapAlignment.center,
                children: [
                  ElevatedButton.icon(
                    onPressed: () => _openManualQuizDialog(module),
                    icon: const Icon(Icons.edit_outlined, size: 16),
                    label: const Text('Create Quiz Manually'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primaryBlue,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 13),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: () async {
                      await ref.read(quizGenerationProvider.notifier).generateQuiz(
                            widget.course.id,
                            ref,
                          );
                    },
                    icon: const Icon(Icons.auto_awesome, size: 16),
                    label: const Text('Retry Generation'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppTheme.primaryBlue,
                      side: const BorderSide(color: AppTheme.primaryBlue),
                      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 13),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                  TextButton.icon(
                    onPressed: () => ref.read(currentTabProvider.notifier).state = 1,
                    icon: const Icon(Icons.format_list_numbered, size: 16),
                    label: const Text('Set Questions to 0'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _openManualQuizDialog(CourseModule module) async {
    final questions = await showDialog<List<Map<String, dynamic>>>(
      context: context,
      barrierDismissible: false,
      builder: (context) => _ManualQuizDialog(module: module),
    );
    if (questions == null || questions.isEmpty) return;

    final success = await ref.read(courseUpdateProvider.notifier).saveModuleQuiz(
          widget.course.id,
          module.moduleNumber,
          questions,
          ref,
        );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(success ? 'Manual quiz saved.' : 'Could not save manual quiz.'),
        backgroundColor: success ? AppTheme.accentGreen : AppTheme.accentRed,
      ),
    );
  }

  Widget _buildQuestionCard(int moduleIndex, int questionIndex, QuizQuestion question) {
    final key = "$moduleIndex-$questionIndex";
    final selectedOption = _selectedOptions[key];
    final isSubmitted = _submittedQuestions[key] == true;

    return Container(
      margin: const EdgeInsets.only(bottom: 24),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.lightGray, width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.01),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'QUESTION ${questionIndex + 1}',
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: AppTheme.primaryBlue.withOpacity(0.7),
              letterSpacing: 1.0,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            question.questionText,
            style: GoogleFonts.inter(
              fontSize: 15,
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
                suffixIcon = const Icon(Icons.check_circle_rounded, color: AppTheme.accentGreen, size: 18);
              } else if (isOptSelected) {
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
              margin: const EdgeInsets.only(bottom: 10),
              child: InkWell(
                onTap: isSubmitted
                    ? null
                    : () {
                        setState(() {
                          _selectedOptions[key] = optKey;
                        });
                      },
                borderRadius: BorderRadius.circular(8),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: cardBgColor,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: cardBorderColor,
                      width: isOptSelected || (isSubmitted && isCorrectOpt) ? 1.5 : 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 24,
                        height: 24,
                        decoration: BoxDecoration(
                          color: isOptSelected
                              ? (isSubmitted
                                  ? (isCorrectOpt ? AppTheme.accentGreen : AppTheme.accentRed)
                                  : AppTheme.primaryBlue)
                              : (isSubmitted && isCorrectOpt
                                  ? AppTheme.accentGreen
                                  : Colors.grey.shade100),
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: isOptSelected || (isSubmitted && isCorrectOpt)
                                ? Colors.transparent
                                : Colors.grey.shade300,
                          ),
                        ),
                        child: Center(
                          child: Text(
                            optKey,
                            style: GoogleFonts.inter(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: isOptSelected || (isSubmitted && isCorrectOpt)
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
                            fontSize: 14,
                            fontWeight: isOptSelected ? FontWeight.w600 : FontWeight.w500,
                            color: isSubmitted && !isCorrectOpt && !isOptSelected
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
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                  elevation: 0,
                ),
                child: const Text('Check Answer'),
              ),
            )
          else ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(16),
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
                    size: 20,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Explanation',
                          style: GoogleFonts.inter(
                            fontWeight: FontWeight.bold,
                            fontSize: 13,
                            color: AppTheme.textBlack,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          question.explanation,
                          style: GoogleFonts.inter(
                            fontSize: 13,
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

  Widget _buildSummaryCard(int moduleIndex, int totalQuestions, int submittedCount, int correctCount) {
    final isFinished = submittedCount == totalQuestions;

    return Container(
      margin: const EdgeInsets.only(top: 8, bottom: 40),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [AppTheme.primaryBlue, AppTheme.primaryBlue.withOpacity(0.85)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primaryBlue.withOpacity(0.2),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
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
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    isFinished ? 'Completed!' : 'In Progress',
                    style: GoogleFonts.inter(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.15),
                  shape: BoxShape.circle,
                ),
                child: Text(
                  '$correctCount / $totalQuestions',
                  style: GoogleFonts.inter(
                    color: Colors.white,
                    fontSize: 22,
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
              minHeight: 8,
            ),
          ),
          const SizedBox(height: 20),
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
                icon: const Icon(Icons.refresh_rounded, size: 16),
                label: const Text('Reset Quiz'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Colors.white60),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Color _getDifficultyColor(String difficulty) {
    switch (difficulty.toLowerCase()) {
      case 'easy':
        return AppTheme.accentGreen;
      case 'medium':
        return AppTheme.accentOrange;
      case 'hard':
        return AppTheme.accentRed;
      default:
        return AppTheme.gray;
    }
  }
}

class _ManualQuizDialog extends StatefulWidget {
  final CourseModule module;

  const _ManualQuizDialog({required this.module});

  @override
  State<_ManualQuizDialog> createState() => _ManualQuizDialogState();
}

class _ManualQuizDialogState extends State<_ManualQuizDialog> {
  final _formKey = GlobalKey<FormState>();
  late final List<_ManualQuestionControllers> _questions;

  @override
  void initState() {
    super.initState();
    final count = widget.module.numQuestions > 0 ? widget.module.numQuestions : 3;
    _questions = List.generate(
      count,
      (_) => _ManualQuestionControllers(),
    );
  }

  @override
  void dispose() {
    for (final question in _questions) {
      question.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Create quiz for Module ${widget.module.moduleNumber}'),
      content: SizedBox(
        width: 720,
        height: 620,
        child: Form(
          key: _formKey,
          child: ListView.separated(
            itemCount: _questions.length,
            separatorBuilder: (_, __) => const Divider(height: 32),
            itemBuilder: (context, index) {
              final question = _questions[index];
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Question ${index + 1}',
                    style: GoogleFonts.inter(
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primaryBlue,
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextFormField(
                    controller: question.question,
                    maxLines: 2,
                    decoration: const InputDecoration(
                      labelText: 'Question text',
                      border: OutlineInputBorder(),
                    ),
                    validator: _required,
                  ),
                  const SizedBox(height: 12),
                  for (final optionKey in ['A', 'B', 'C', 'D']) ...[
                    TextFormField(
                      controller: question.options[optionKey],
                      decoration: InputDecoration(
                        labelText: 'Option $optionKey',
                        border: const OutlineInputBorder(),
                      ),
                      validator: _required,
                    ),
                    const SizedBox(height: 10),
                  ],
                  DropdownButtonFormField<String>(
                    value: question.correctOption,
                    decoration: const InputDecoration(
                      labelText: 'Correct option',
                      border: OutlineInputBorder(),
                    ),
                    items: const [
                      DropdownMenuItem(value: 'A', child: Text('A')),
                      DropdownMenuItem(value: 'B', child: Text('B')),
                      DropdownMenuItem(value: 'C', child: Text('C')),
                      DropdownMenuItem(value: 'D', child: Text('D')),
                    ],
                    onChanged: (value) {
                      if (value != null) {
                        setState(() => question.correctOption = value);
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: question.explanation,
                    maxLines: 2,
                    decoration: const InputDecoration(
                      labelText: 'Explanation',
                      border: OutlineInputBorder(),
                    ),
                    validator: _required,
                  ),
                ],
              );
            },
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton.icon(
          onPressed: _save,
          icon: const Icon(Icons.save_outlined, size: 18),
          label: const Text('Save Quiz'),
        ),
      ],
    );
  }

  String? _required(String? value) {
    return value == null || value.trim().isEmpty ? 'Required' : null;
  }

  void _save() {
    if (!(_formKey.currentState?.validate() ?? false)) return;

    Navigator.of(context).pop(
      _questions.map((question) {
        return {
          'question_text': question.question.text.trim(),
          'options': [
            for (final optionKey in ['A', 'B', 'C', 'D'])
              {
                'key': optionKey,
                'text': question.options[optionKey]!.text.trim(),
              }
          ],
          'correct_option': question.correctOption,
          'explanation': question.explanation.text.trim(),
        };
      }).toList(),
    );
  }
}

class _ManualQuestionControllers {
  final TextEditingController question = TextEditingController();
  final Map<String, TextEditingController> options = {
    'A': TextEditingController(),
    'B': TextEditingController(),
    'C': TextEditingController(),
    'D': TextEditingController(),
  };
  final TextEditingController explanation = TextEditingController();
  String correctOption = 'A';

  void dispose() {
    question.dispose();
    for (final controller in options.values) {
      controller.dispose();
    }
    explanation.dispose();
  }
}
