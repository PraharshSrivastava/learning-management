import 'package:employee_frontend/data/models/models.dart';
import 'package:employee_frontend/state/employee_providers.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('module pass mark defaults to exact two thirds', () {
    final module = PublishedCourseModule.fromJson({
      'module_number': 1,
      'video_path': 'module.mp4',
      'quiz': <dynamic>[],
    });

    expect(module.passMark, closeTo(2 / 3, 0.000000001));
  });

  test('parses the authoritative backend grading response', () {
    final result = QuizSubmissionResult.fromJson({
      'quiz_passed': true,
      'quiz_score': 2 / 3,
      'correct_count': 2,
      'total_questions': 3,
      'pass_mark': 2 / 3,
      'correct_answers': {'0': 'A', '1': 'B', '2': 'C'},
      'explanations': {'0': 'First explanation'},
    });

    expect(result.passed, isTrue);
    expect(result.correctCount, 2);
    expect(result.totalQuestions, 3);
    expect(result.correctAnswers, {0: 'A', 1: 'B', 2: 'C'});
    expect(result.explanations, {0: 'First explanation'});
  });
}
