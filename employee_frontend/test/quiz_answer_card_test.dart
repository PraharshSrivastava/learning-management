import 'package:employee_frontend/core/theme/app_theme.dart';
import 'package:employee_frontend/data/models/models.dart';
import 'package:employee_frontend/features/learning/quiz_answer_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

PublishedQuizQuestion question() => PublishedQuizQuestion(
      questionId: 'q',
      question: 'What is the next step?',
      options: ['First choice', 'Second choice'],
      correct: 'B',
      explanation: 'ANSWER KEY MUST NOT APPEAR',
    );

BoxDecoration optionDecoration(WidgetTester tester, String key) => tester
    .widget<Container>(find.byKey(ValueKey('question-0-option-$key')))
    .decoration! as BoxDecoration;

void main() {
  testWidgets('wrong selection is red; correct alternative stays neutral',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: QuizAnswerCard(
      questionIndex: 0,
      question: question(),
      selectedAnswer: 'A',
      submitted: true,
      answerCorrect: false,
    ))));
    expect(find.text('Your answer · Incorrect ✕'), findsOneWidget);
    expect(find.textContaining('Correct answer:'), findsNothing);
    expect(find.textContaining('ANSWER KEY'), findsNothing);
    expect((optionDecoration(tester, 'A').border! as Border).top.color,
        AppTheme.accentRed);
    expect((optionDecoration(tester, 'B').border! as Border).top.color,
        AppTheme.lightGray);
  });
  testWidgets('only a correct selected option is green', (tester) async {
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: QuizAnswerCard(
      questionIndex: 0,
      question: question(),
      selectedAnswer: 'B',
      submitted: true,
      answerCorrect: true,
    ))));
    expect((optionDecoration(tester, 'B').border! as Border).top.color,
        AppTheme.accentGreen);
    expect((optionDecoration(tester, 'A').border! as Border).top.color,
        AppTheme.lightGray);
    expect(find.text('Your answer · Correct ✓'), findsOneWidget);
  });
  testWidgets('missing result never falls back to legacy answer key',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: QuizAnswerCard(
      questionIndex: 0,
      question: question(),
      selectedAnswer: 'B',
      submitted: true,
      answerCorrect: null,
    ))));
    expect(find.text('Your answer · Result unavailable'), findsOneWidget);
    expect((optionDecoration(tester, 'B').border! as Border).top.color,
        AppTheme.lightGray);
  });
}
