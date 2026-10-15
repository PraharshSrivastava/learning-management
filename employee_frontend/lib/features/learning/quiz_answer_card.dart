import 'package:flutter/material.dart';
import 'package:employee_frontend/core/theme/app_theme.dart';
import 'package:employee_frontend/data/models/models.dart';

/// A review can mark the submitted choice, never a different answer option.
class QuizAnswerCard extends StatelessWidget {
  final int questionIndex;
  final PublishedQuizQuestion question;
  final String? selectedAnswer;
  final bool submitted;
  final bool? answerCorrect;
  final ValueChanged<String>? onChanged;

  const QuizAnswerCard(
      {super.key,
      required this.questionIndex,
      required this.question,
      required this.selectedAnswer,
      required this.submitted,
      required this.answerCorrect,
      this.onChanged});

  @override
  Widget build(BuildContext context) {
    final statusColor = answerCorrect == true
        ? AppTheme.accentGreen
        : answerCorrect == false
            ? AppTheme.accentRed
            : AppTheme.gray;
    final card = Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.lightGray)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
              child: Text('QUESTION ${questionIndex + 1}',
                  style: const TextStyle(fontSize: 11, color: AppTheme.gray))),
          if (submitted)
            Text(
                answerCorrect == true
                    ? '✓ Correct'
                    : answerCorrect == false
                        ? '✕ Incorrect'
                        : 'Result unavailable',
                style:
                    TextStyle(color: statusColor, fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 10),
        Text(question.question,
            style: const TextStyle(
                fontSize: 14, fontWeight: FontWeight.w600, height: 1.5)),
        const SizedBox(height: 14),
        for (final entry in question.options.asMap().entries)
          Builder(builder: (context) {
            final key = String.fromCharCode(65 + entry.key);
            final selected = selectedAnswer == key;
            final gradedSelection =
                submitted && selected && answerCorrect != null;
            final color = gradedSelection
                ? statusColor
                : !submitted && selected
                    ? AppTheme.primaryBlue
                    : AppTheme.lightGray;
            return Container(
              key: ValueKey('question-$questionIndex-option-$key'),
              margin: const EdgeInsets.only(bottom: 8),
              decoration: BoxDecoration(
                  color: gradedSelection
                      ? statusColor.withValues(alpha: .08)
                      : Colors.white,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: color, width: selected ? 2 : 1)),
              child: RadioListTile<String>(
                value: key,
                groupValue: selectedAnswer,
                onChanged: submitted || onChanged == null
                    ? null
                    : (value) {
                        if (value != null) onChanged!(value);
                      },
                title: Text('$key. ${entry.value}',
                    style: const TextStyle(fontSize: 13)),
                subtitle: submitted && selected
                    ? Text(
                        answerCorrect == true
                            ? 'Your answer · Correct ✓'
                            : answerCorrect == false
                                ? 'Your answer · Incorrect ✕'
                                : 'Your answer · Result unavailable',
                        style: TextStyle(
                            color: statusColor, fontWeight: FontWeight.w600))
                    : null,
                activeColor: submitted ? statusColor : AppTheme.primaryBlue,
              ),
            );
          }),
        if (submitted && selectedAnswer == null)
          const Text('Your saved answer is unavailable.',
              style: TextStyle(color: AppTheme.gray)),
      ]),
    );
    return submitted
        ? Semantics(container: true, explicitChildNodes: true, child: card)
        : card;
  }
}
