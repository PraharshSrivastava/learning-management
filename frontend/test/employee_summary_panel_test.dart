import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/core/theme/app_theme.dart';
import 'package:frontend/features/performance/employee_summary_panel.dart';

const employee = <String, dynamic>{
  'employee_id': 'e1',
  'employee_name': 'Kavya Nair',
  'department': 'Sales',
  'assigned': 8,
  'completed': 5,
  'in_progress': 2,
  'not_started': 1,
  'completion_rate': 62.5,
  'overdue': 1,
  'due_soon': 2,
  'average_score': 78.0,
  'needs_attention': true,
  'repeated_failures': 1,
};

Widget screen(Widget child) =>
    MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child)));

void main() {
  testWidgets('employee summary opens detail at desktop and narrow widths',
      (tester) async {
    String? opened;
    for (final width in [1100.0, 375.0]) {
      tester.view.physicalSize = Size(width, 900);
      tester.view.devicePixelRatio = 1;
      await tester.pumpWidget(screen(EmployeeSummaryTable(
          rows: const [employee], onOpenEmployee: (id) => opened = id)));
      await tester.pumpAndSettle();
      expect(find.text('Kavya Nair'), findsOneWidget);
      expect(find.text('62.5%'), findsOneWidget);
      await tester.tap(find.text('Kavya Nair'));
      expect(opened, 'e1');
      expect(tester.takeException(), isNull);
    }
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  });

  testWidgets('employee search waits for Enter and uses submitted full name',
      (tester) async {
    final calls = <Map<String, String>>[];
    final exports = <Map<String, String>>[];
    await tester.pumpWidget(screen(EmployeeSummaryPanel(
      scopeKey: 'all',
      revision: '1',
      load: (params) async {
        calls.add(params);
        return {
          'rows': [employee],
          'total': 1,
          'page_size': 25,
          'summary': {
            'employees': 1,
            'assigned': 8,
            'completed': 5,
            'overdue': 1
          }
        };
      },
      onOpenEmployee: (_) {},
      onExport: (params) async => exports.add(params),
    )));
    await tester.pumpAndSettle();
    expect(calls.length, 1);
    await tester.tap(find.text('Export employees CSV'));
    await tester.pumpAndSettle();
    expect(exports.single.containsKey('search'), isFalse);
    await tester.enterText(find.byType(TextField), 'ka');
    await tester.pump(const Duration(seconds: 1));
    expect(calls.length, 1);
    await tester.tap(find.text('Export employees CSV'));
    await tester.pumpAndSettle();
    expect(exports.last.containsKey('search'), isFalse);
    await tester.enterText(find.byType(TextField), 'Kavya Nair');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();
    expect(calls.length, 2);
    expect(calls.last['search'], 'Kavya Nair');
    await tester.tap(find.text('Export employees CSV'));
    await tester.pumpAndSettle();
    expect(exports.last['search'], 'Kavya Nair');
    expect(exports.last.containsKey('page'), isFalse);
    await tester.tap(find.byType(DropdownButtonFormField<String>).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Needs attention').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Export employees CSV'));
    await tester.pumpAndSettle();
    expect(exports.last['search'], 'Kavya Nair');
    expect(exports.last['attention'], 'needs_attention');
    expect(tester.takeException(), isNull);
  });

  testWidgets('employee export is disabled during loading, errors and export',
      (tester) async {
    var response = Completer<Map<String, dynamic>>();
    final download = Completer<void>();
    final export = find.ancestor(
        of: find.text('Export employees CSV'),
        matching: find.byWidgetPredicate((widget) => widget is OutlinedButton));
    await tester.pumpWidget(screen(EmployeeSummaryPanel(
      scopeKey: 'all',
      revision: '1',
      load: (_) => response.future,
      onOpenEmployee: (_) {},
      onExport: (_) => download.future,
    )));
    await tester.pump();
    expect(tester.widget<OutlinedButton>(export).onPressed, isNull);
    response.completeError(Exception('Test network error'));
    await tester.pump();
    await tester.pump();
    expect(tester.widget<OutlinedButton>(export).onPressed, isNull);
    response = Completer<Map<String, dynamic>>();
    await tester.tap(find.text('Retry'));
    await tester.pump();
    response.complete({
      'rows': [employee],
      'total': 1,
      'summary': {}
    });
    await tester.pumpAndSettle();
    expect(tester.widget<OutlinedButton>(export).onPressed, isNotNull);
    await tester.tap(export);
    await tester.pump();
    expect(
        tester
            .widget<OutlinedButton>(find.ancestor(
                of: find.text('Exporting…'),
                matching: find
                    .byWidgetPredicate((widget) => widget is OutlinedButton)))
            .onPressed,
        isNull);
    download.complete();
    await tester.pumpAndSettle();
    expect(tester.widget<OutlinedButton>(export).onPressed, isNotNull);
    expect(tester.takeException(), isNull);
  });

  testWidgets('employee drawer shows course breakdown and opens assignment',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    String? opened;
    for (final width in [1000.0, 375.0]) {
      tester.view.physicalSize = Size(width, 1000);
      await tester.pumpWidget(MaterialApp(
          home: Scaffold(
              body: EmployeeDetailDrawer(
        detail: Future.value({
          'employee': employee,
          'assignments': [
            {
              'assignment_id': 'a1',
              'course_name': 'Client Conversations',
              'status': 'completed',
              'completed_modules': 3,
              'total_modules': 3,
              'completion_percent': 100,
              'average_score': 85.0,
              'deadline': '2026-09-22T12:00:00'
            },
          ]
        }),
        onOpenAssignment: (id) => opened = id,
      ))));
      await tester.pumpAndSettle();
      expect(find.text('Course breakdown'), findsOneWidget);
      expect(find.text('Learning snapshot'), findsOneWidget);
      expect(find.text('Repeated quiz failures · 1 course'), findsOneWidget);
      expect(find.textContaining('Quiz support needed'), findsNothing);
      expect(find.text('62.5%'), findsOneWidget);
      await tester.ensureVisible(find.text('Client Conversations'));
      await tester.tap(find.text('Client Conversations'));
      expect(opened, 'a1');
      expect(tester.takeException(), isNull);
    }
  });

  testWidgets(
      'healthy empty drawer uses neutral zero signals and no missing score',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: EmployeeDetailDrawer(
      detail: Future.value({
        'employee': {
          ...employee,
          'assigned': 0,
          'completed': 0,
          'completion_rate': 0,
          'overdue': 0,
          'due_soon': 0,
          'repeated_failures': 0,
          'average_score': null
        },
        'assignments': <Map<String, dynamic>>[],
      }),
      onOpenAssignment: (_) {},
    ))));
    await tester.pumpAndSettle();
    for (final label in [
      '0 overdue',
      '0 due soon',
      '0 inactive courses',
      'Repeated quiz failures · 0 courses'
    ]) {
      final text = tester.widget<Text>(find.text(label));
      expect(text.style!.color, AppTheme.textSecondary);
    }
    expect(find.text('—'), findsOneWidget);
    expect(find.text('No courses in the current reporting scope.'),
        findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
