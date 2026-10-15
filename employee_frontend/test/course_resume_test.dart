import 'package:employee_frontend/data/models/models.dart';
import 'package:employee_frontend/features/learning/course_resume.dart';
import 'package:flutter_test/flutter_test.dart';

Course course(Map<String, dynamic> progress, {bool quiz = true}) =>
    Course.fromPublishedJson({
      'course_id': 'resume',
      'course_name': 'Resume training',
      'modules': [
        for (final n in [1, 3, 7])
          {
            'module_number': n,
            'title': 'Module $n',
            'video_path': '',
            'quiz': quiz
                ? [
                    {
                      'question': 'Question',
                      'options': ['A', 'B']
                    }
                  ]
                : [],
          }
      ],
      'module_progress': progress,
    });

void main() {
  const complete = {'video_watched': true, 'quiz_passed': true};
  test('new course opens first module', () {
    expect(firstIncompleteModule(course({})), 0);
  });
  test('uses actual module numbers, not array indexes', () {
    expect(firstIncompleteModule(course({'1': complete, '3': complete})), 2);
  });
  test('video alone does not complete a quiz module', () {
    expect(
        firstIncompleteModule(course({
          '1': {'video_watched': true}
        })),
        0);
  });
  test('quiz pass without watched video is still incomplete', () {
    expect(
        firstIncompleteModule(course({
          '1': {'quiz_passed': true}
        })),
        0);
  });
  test('earliest incomplete gap wins over later completed module', () {
    expect(firstIncompleteModule(course({'3': complete, '7': complete})), 0);
  });
  test('video-only module completes when watched', () {
    expect(
        firstIncompleteModule(course({
          '1': {'video_watched': true}
        }, quiz: false)),
        1);
  });
  test('all complete opens completed-course view', () {
    expect(
        firstIncompleteModule(
            course({'1': complete, '3': complete, '7': complete})),
        isNull);
  });
  test('empty published list has no resume index', () {
    expect(
        firstIncompleteModule(
            Course.fromPublishedJson({'course_id': 'empty', 'modules': []})),
        isNull);
  });
}
