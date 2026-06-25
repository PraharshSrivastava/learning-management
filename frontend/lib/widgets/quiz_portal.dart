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
    _selectedModuleIndex = null;
    for (int i = 0; i < widget.course.modules.length; i++) {
      final m = widget.course.modules[i];
      if (m.quiz != null && m.quiz!['questions'] != null && (m.quiz!['questions'] as List).isNotEmpty) {
        _selectedModuleIndex = i;
        break;
      }
    }
  }

  bool get _hasAnyQuiz => widget.course.modules.any((m) =>
      m.quiz != null && m.quiz!['questions'] != null && (m.quiz!['questions'] as List).isNotEmpty);

  List<int> get _quizModuleIndices {
    final indices = <int>[];
    for (int i = 0; i < widget.course.modules.length; i++) {
      final m = widget.course.modules[i];
      if (m.quiz != null && m.quiz!['questions'] != null && (m.quiz!['questions'] as List).isNotEmpty) {
        indices.add(i);
      }
    }
    return indices;
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
            ElevatedButton.icon(
              onPressed: () {
                ref.read(currentTabProvider.notifier).state = 1;
              },
              icon: const Icon(Icons.arrow_forward_rounded, size: 16),
              label: const Text('Go to Course Outline'),
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
        final qList = m.quiz!['questions'] as List;

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

    if (module.quiz == null || module.quiz!['questions'] == null) {
      return const Center(child: Padding(
        padding: EdgeInsets.all(24.0),
        child: Text('No quiz questions for this module.'),
      ));
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
