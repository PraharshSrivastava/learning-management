import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../theme.dart';
import '../models/models.dart';
import '../providers/employee_providers.dart';

class TakeQuizPage extends ConsumerStatefulWidget {
  final String courseId;
  final int moduleNumber;
  final List<PublishedQuizQuestion> quiz;
  final double passMark;
  final bool isFinalModule;

  const TakeQuizPage({
    super.key,
    required this.courseId,
    required this.moduleNumber,
    required this.quiz,
    required this.passMark,
    this.isFinalModule = false,
  });

  @override
  ConsumerState<TakeQuizPage> createState() => _TakeQuizPageState();
}

class _TakeQuizPageState extends ConsumerState<TakeQuizPage> {
  final Map<int, String> _selectedAnswers = {};
  bool _submitted = false;

  void _submitQuiz() async {
    if (_selectedAnswers.length < widget.quiz.length) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please answer all questions before submitting.')),
      );
      return;
    }

    setState(() {
      _submitted = true;
    });

    int correctCount = 0;
    for (int i = 0; i < widget.quiz.length; i++) {
      if (_selectedAnswers[i] == widget.quiz[i].correct) {
        correctCount++;
      }
    }

    final double score = widget.quiz.isEmpty ? 1.0 : correctCount / widget.quiz.length;
    final bool passed = score >= widget.passMark;

    await ref.read(employeeCourseListProvider.notifier).updateModuleProgress(
      widget.courseId,
      widget.moduleNumber,
      {
        "quiz_passed": passed,
        "quiz_score": score,
        if (!passed) "video_watched": false, // Reset video requirement if failed
      },
    );

    if (!mounted) return;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: Text(
          passed ? (widget.isFinalModule ? 'Course Completed!' : 'Quiz Passed!') : 'Quiz Failed', 
          style: TextStyle(color: passed ? AppTheme.accentGreen : AppTheme.accentRed)
        ),
        content: Text(
          passed 
            ? 'You scored ${(score * 100).toStringAsFixed(1)}%. ${widget.isFinalModule ? "You have successfully finished the course." : "The next module is now unlocked!"}'
            : 'You scored ${(score * 100).toStringAsFixed(1)}%. You need ${(widget.passMark * 100).toStringAsFixed(1)}% to pass.\n\nYou must re-watch the video lesson to try the quiz again.',
        ),
        actions: [
          TextButton(
            onPressed: () {
              if (passed && widget.isFinalModule) {
                Navigator.of(context).popUntil((route) => route.isFirst);
              } else {
                Navigator.pop(context); // close dialog
                Navigator.pop(context); // close quiz page
              }
            },
            child: Text(passed && widget.isFinalModule ? 'Return to Dashboard' : 'Return to Course'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.lightGray,
      appBar: AppBar(
        title: Text(
          'Module ${widget.moduleNumber} Quiz',
          style: GoogleFonts.barlow(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.primaryBlue),
        ),
        iconTheme: IconThemeData(color: AppTheme.primaryBlue),
      ),
      body: widget.quiz.isEmpty
          ? const Center(child: Text('No questions available.'))
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: widget.quiz.length + 1,
              itemBuilder: (context, index) {
                if (index == widget.quiz.length) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 32),
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primaryBlue,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                      ),
                      onPressed: _submitted ? null : _submitQuiz,
                      child: Text(
                        _submitted ? 'Submitted' : 'Submit Quiz',
                        style: const TextStyle(fontSize: 18, color: Colors.white),
                      ),
                    ),
                  );
                }

                final q = widget.quiz[index];
                final isCorrect = _submitted && _selectedAnswers[index] == q.correct;
                final isWrong = _submitted && _selectedAnswers[index] != q.correct;

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
                          '${index + 1}. ${q.question}',
                          style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 12),
                        ...q.options.map((optionText) {
                          // Extract 'A', 'B', 'C', 'D' if it's prepended, but our schema just has text in 'options' and 'correct' is 'A'.
                          // Wait, the backend exporter strips the 'A' key and just lists options.
                          // But 'correct' is "A". This means we need to match option index to A,B,C,D.
                          final optIndex = q.options.indexOf(optionText);
                          final optKey = String.fromCharCode(65 + optIndex); // 0 -> A, 1 -> B
                          
                          Color? bgColor;
                          if (_submitted) {
                            if (optKey == q.correct) bgColor = AppTheme.accentGreen.withValues(alpha: 0.2);
                            else if (_selectedAnswers[index] == optKey) bgColor = AppTheme.accentRed.withValues(alpha: 0.2);
                          }

                          return Container(
                            color: bgColor,
                            child: RadioListTile<String>(
                              title: Text(optionText),
                              value: optKey,
                              groupValue: _selectedAnswers[index],
                              onChanged: _submitted ? null : (val) {
                                setState(() {
                                  _selectedAnswers[index] = val!;
                                });
                              },
                            ),
                          );
                        }),
                        if (_submitted)
                          Padding(
                            padding: const EdgeInsets.only(top: 8.0),
                            child: Text(
                              'Explanation: ${q.explanation}',
                              style: TextStyle(
                                fontStyle: FontStyle.italic,
                                color: isCorrect ? AppTheme.accentGreen : AppTheme.accentRed,
                              ),
                            ),
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
