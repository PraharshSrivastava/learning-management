import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/features/performance/assignment_detail_dialog.dart';

Map<String, dynamic> _detail({bool completed = true}) => {
      'assignment': {
        'employee_name': 'Aarav Desai',
        'course_name': 'Compliance Essentials',
        'status': completed ? 'completed' : 'overdue',
        'completion_percent': completed ? 100 : 33,
        'completed_modules': completed ? 3 : 1,
        'total_modules': 3,
        'assigned_at': '2026-08-22T10:00:00',
        'deadline': '2026-09-14T10:00:00',
        'started_at': '2026-08-28T10:00:00',
        'completed_at': completed ? '2026-09-11T10:00:00' : null,
        'last_learner_activity_at': '2026-09-11T10:00:00',
        'average_score': completed ? 70.0 : 30.0,
      },
      'modules': [
        {
          'module_id': 'm1',
          'module_number': 1,
          'title': 'Policies and conduct',
          'num_questions': 0,
          'video_watched': true,
          'quiz_passed': false,
          'attempt_count': 0,
          'latest_score': null,
        },
        {
          'module_id': 'm2',
          'module_number': 2,
          'title': 'KYC checks',
          'num_questions': 5,
          'video_watched': completed,
          'quiz_passed': completed,
          'attempt_count': 2,
          'latest_score': completed ? 70.0 : 30.0,
        },
      ],
      'attempts': [
        {
          'module_id': 'm2',
          'occurred_at': '2026-09-11T14:46:00',
          'score': 30.0,
          'passed': false,
        },
        if (completed)
          {
            'module_id': 'm2',
            'occurred_at': '2026-09-11T14:46:00',
            'score': 70.0,
            'passed': true,
          },
      ],
    };

void main() {
  testWidgets('shows the learning path and quiz results', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: AssignmentDetailDialog(detail: Future.value(_detail())),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Aarav Desai'), findsOneWidget);
    expect(find.text('Learning path'), findsOneWidget);
    expect(find.text('Quiz performance'), findsOneWidget);
    expect(find.text('Key dates'), findsOneWidget);
    expect(find.text('Completed'), findsWidgets);
    expect(find.text('70.0%'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('keeps status visible on a narrow screen', (tester) async {
    tester.view.physicalSize = const Size(420, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: AssignmentDetailDialog(
            detail: Future.value(_detail(completed: false))),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Overdue'), findsOneWidget);
    expect(find.text('33%'), findsOneWidget);
    expect(find.text('No quiz'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
