import 'dart:convert';
import 'assignment_refresh_test.dart' show QuietAuth;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/state/trainer_providers.dart';
import 'package:frontend/data/models/models.dart';
import 'package:frontend/features/assignments/observer_include_panel.dart';

void main() {
  testWidgets(
      'Select all and Clear all update employee scope; searched Observer saves by ID',
      (tester) async {
    dotenv.loadFromString(envString: 'API_BASE_URL=http://localhost:8000');
    Map<String, dynamic>? savedPayload;
    final client = MockClient((r) async {
      if (r.url.path.endsWith('/options'))
        return http.Response(jsonEncode({'departments': []}), 200);
      if (r.method == 'PUT')
        savedPayload = jsonDecode(r.body) as Map<String, dynamic>;
      return http.Response(
          jsonEncode({
            'course_id': 'course',
            'revision': 1,
            'observers': [
              {
                'observer_employee_id': 'observer',
                'is_active': false,
                'pending': {
                  'employee_ids': ['a'],
                  'department_ids': []
                }
              }
            ]
          }),
          200);
    });
    await tester.pumpWidget(ProviderScope(
        overrides: [
          assignmentHttpClientProvider.overrideWithValue(client),
          trainerAuthProvider.overrideWith((ref) => QuietAuth()),
          trainerAuthHeadersProvider.overrideWithValue({'X-LMS-App': 'trainer'})
        ],
        child: MaterialApp(
            home: Scaffold(
                body: SingleChildScrollView(
                    child: ObserverIncludePanel(
                        course: Course.fromJson({
                          'course_id': 'course',
                          'course_name': 'Test',
                          'status': 'published'
                        }),
                        employees: [
              for (final id in ['observer', 'a', 'b', 'inactive'])
                Employee.fromJson({
                  'employee_id': id,
                  'name': id,
                  'status': id == 'inactive' ? 'inactive' : 'active'
                })
            ]))))));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Employees (1)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Select all'));
    await tester.pumpAndSettle();
    expect(find.text('3 selected'), findsOneWidget);
    expect(find.text('inactive ()'), findsNothing);
    await tester.tap(find.text('Clear all'));
    await tester.pumpAndSettle();
    expect(find.text('0 selected'), findsOneWidget);
    await tester.tap(find.text('Select all'));
    await tester.tap(find.text('Done'));
    await tester.pumpAndSettle();
    expect(find.text('Employees (3)'), findsOneWidget);
    await tester.tap(find.text('observer'));
    await tester.pumpAndSettle();
    expect(find.text('All observer options'), findsNothing);
    await tester.enterText(find.byType(TextField), 'b');
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ListTile, 'b'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Save Observers'));
    await tester.tap(find.text('Save Observers'));
    await tester.pumpAndSettle();
    final row = (savedPayload!['observers'] as List).single as Map;
    expect(row['observer_employee_id'], 'b');
    expect(row['employee_ids'], unorderedEquals(['observer', 'a', 'b']));
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets(
      'header refresh updates effective Observer status without discarding unsaved employee scope',
      (tester) async {
    dotenv.loadFromString(envString: 'API_BASE_URL=http://localhost:8000');
    int generation = 0, revision = 1, reads = 0;
    bool active = false;
    late StateSetter update;
    final client = MockClient((r) async {
      if (r.url.path.endsWith('/options'))
        return http.Response(jsonEncode({'departments': []}), 200);
      reads++;
      return http.Response(
          jsonEncode({
            'course_id': 'course',
            'revision': revision,
            'observers': [
              {
                'observer_employee_id': 'observer',
                'is_active': active,
                'active': {
                  'employee_ids': active ? ['a'] : [],
                  'department_ids': []
                },
                'pending': {
                  'employee_ids': ['a'],
                  'department_ids': []
                }
              }
            ]
          }),
          200);
    });
    final employees = [
      for (final id in ['observer', 'a', 'b'])
        Employee.fromJson({'employee_id': id, 'name': id, 'status': 'active'})
    ];
    await tester.pumpWidget(ProviderScope(
        overrides: [
          assignmentHttpClientProvider.overrideWithValue(client),
          trainerAuthProvider.overrideWith((ref) => QuietAuth()),
          trainerAuthHeadersProvider.overrideWithValue({'X-LMS-App': 'trainer'})
        ],
        child: MaterialApp(
            home: Scaffold(body: StatefulBuilder(builder: (context, setState) {
          update = setState;
          return ObserverIncludePanel(
              course: Course.fromJson({
                'course_id': 'course',
                'course_name': 'Test',
                'status': 'published'
              }),
              employees: employees,
              refreshGeneration: generation);
        })))));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Employees (1)'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(CheckboxListTile, 'b ()'));
    await tester.tap(find.text('Done'));
    await tester.pumpAndSettle();
    expect(find.text('Employees (2)'), findsOneWidget);
    active = true;
    revision = 2;
    update(() => generation++);
    await tester.pumpAndSettle();
    expect(reads, 2);
    expect(find.text('Employees (2)'), findsOneWidget);
    expect(find.textContaining('Active access:'), findsOneWidget);
    expect(find.textContaining('Your edits are preserved'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
  });
}
