import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/features/performance/course_detail_dialog.dart';

Map<String, dynamic> _detail() => {
      'course': {
        'course_name': 'Client Conversations',
        'assigned': 100,
        'completed': 40,
        'overdue': 18,
        'completion_rate': 40,
      },
      'modules': [
        {
          'module_number': 1,
          'title': 'Preparation',
          'assigned': 100,
          'watched': 70,
          'num_questions': 0,
          'passed': 0,
          'attempts': 0,
          'average_score': null,
        },
        {
          'module_number': 2,
          'title': 'Active listening',
          'assigned': 100,
          'watched': 70,
          'num_questions': 5,
          'passed': 40,
          'attempts': 139,
          'average_score': 63.1,
        },
        {
          'module_number': 3,
          'title': 'Follow-up',
          'assigned': 100,
          'watched': 40,
          'num_questions': 5,
          'passed': 40,
          'attempts': 79,
          'average_score': 80.4,
        },
      ],
    };

void main() {
  testWidgets('shows course learning path and opens employees', (tester) async {
    var openedEmployees = false;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: CourseDetailDialog(
          detail: Future.value(_detail()),
          onViewEmployees: () => openedEmployees = true,
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Client Conversations'), findsOneWidget);
    expect(find.text('Module outcomes'), findsOneWidget);
    expect(find.text('Preparation'), findsOneWidget);
    expect(find.text('Active listening'), findsOneWidget);
    expect(find.text('Follow-up'), findsOneWidget);
    expect(find.text('No quiz'), findsOneWidget);
    expect(find.text('40 passed'), findsNWidgets(2));
    expect(find.text('139 attempts'), findsOneWidget);
    expect(find.text('Average 63.1%'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('View employees'));
    expect(openedEmployees, isTrue);
  });

  testWidgets('fits the course detail on a narrow screen', (tester) async {
    tester.view.physicalSize = const Size(420, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: CourseDetailDialog(
          detail: Future.value(_detail()),
          onViewEmployees: () {},
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('40%'), findsOneWidget);
    expect(find.text('100 assigned'), findsOneWidget);
    expect(find.text('View employees'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
