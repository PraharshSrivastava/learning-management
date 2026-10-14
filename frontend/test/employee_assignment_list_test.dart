import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/features/performance/employee_assignment_list.dart';

final _rows = <Map<String, dynamic>>[
  {
    'assignment_id': 'assignment-1',
    'employee_name': 'Kavya Nair',
    'department': 'Sales',
    'course_name': 'Client Conversations',
    'completed_modules': 2,
    'total_modules': 3,
    'average_score': 75.0,
    'deadline': '2026-09-19T00:00:00',
    'last_learner_activity_at': '2026-09-17T00:00:00',
    'status': 'overdue',
    'due_soon': false,
  },
  {
    'assignment_id': 'assignment-2',
    'employee_name': 'Neha Bose',
    'department': 'Operations',
    'course_name': 'Product Knowledge',
    'completed_modules': 3,
    'total_modules': 3,
    'average_score': 80.0,
    'deadline': '2026-09-25T00:00:00',
    'last_learner_activity_at': '2026-09-22T00:00:00',
    'status': 'completed',
    'due_soon': false,
  },
];

void main() {
  testWidgets('shows scannable columns and opens assignment', (tester) async {
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    String? opened;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: EmployeeAssignmentList(
            rows: _rows,
            onOpenAssignment: (id) => opened = id,
          ),
        ),
      ),
    ));

    expect(find.text('EMPLOYEE'), findsOneWidget);
    expect(find.text('QUIZ SCORE'), findsOneWidget);
    expect(find.text('Kavya Nair'), findsOneWidget);
    expect(find.text('2/3 modules'), findsOneWidget);
    expect(find.text('75.0%'), findsOneWidget);
    expect(find.text('19 Sep 2026'), findsOneWidget);
    expect(find.text('Overdue'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('Kavya Nair'));
    expect(opened, 'assignment-1');
  });

  testWidgets('stacks assignment details at narrow width', (tester) async {
    tester.view.physicalSize = const Size(420, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: EmployeeAssignmentList(
            rows: _rows,
            onOpenAssignment: (_) {},
          ),
        ),
      ),
    ));

    expect(find.text('QUIZ SCORE'), findsNothing);
    expect(find.text('Client Conversations'), findsOneWidget);
    expect(find.text('Score 75.0%'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
