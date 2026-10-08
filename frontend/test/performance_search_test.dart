import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/features/performance/searchable_report_filter.dart';
import 'package:frontend/features/performance/course_report_browser.dart';
import 'package:frontend/features/performance/employee_summary_panel.dart';

Widget screen(Widget child) =>
    MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child)));

void main() {
  for (final label in ['Course', 'Department', 'Mailing list']) {
    testWidgets(
        '$label picker searches beyond the visible rows and clears only on selection',
        (tester) async {
      tester.view.physicalSize = const Size(375, 700);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      String? picked = 'untouched';
      await tester.pumpWidget(screen(SearchableReportFilter(
          label: label,
          value: 'id0',
          width: 300,
          icon: Icons.search,
          items: {for (var i = 0; i < 200; i++) 'id$i': '$label option $i'},
          onChanged: (value) => picked = value)));
      await tester.tap(find.byType(OutlinedButton));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), '$label option 199');
      await tester.pumpAndSettle();
      expect(
          find.widgetWithText(ListTile, '$label option 199'), findsOneWidget);
      expect(find.text('1 matching options'), findsOneWidget);
      expect(picked, 'untouched');
      await tester.tap(find.widgetWithText(ListTile, '$label option 199'));
      await tester.pumpAndSettle();
      expect(picked, 'id199');
      await tester.tap(find.byType(OutlinedButton));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'no such item');
      await tester.pumpAndSettle();
      expect(find.text('No matching options.'), findsOneWidget);
      await tester.tap(find.text('All ${label.toLowerCase()} options'));
      await tester.pumpAndSettle();
      expect(picked, isNull);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets(
      'course search finds every page, clears and opens the correct course at narrow width',
      (tester) async {
    tester.view.physicalSize = const Size(375, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    String? opened;
    await tester.pumpWidget(screen(CourseReportBrowser(
        scopeKey: 'all',
        resetVersion: 0,
        courses: [
          for (var i = 0; i < 30; i++)
            {'course_id': 'c$i', 'course_name': 'Course $i'}
        ],
        itemBuilder: (course) => TextButton(
            onPressed: () => opened = course['course_id'] as String,
            child: Text(course['course_name'] as String)))));
    await tester.pumpAndSettle();
    expect(find.text('Course 29'), findsNothing);
    await tester.ensureVisible(find.byTooltip('Next course page'));
    await tester.tap(find.byTooltip('Next course page'));
    await tester.pumpAndSettle();
    expect(find.text('Page 2 of 3'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'c29');
    await tester.pumpAndSettle();
    expect(find.text('Course 29'), findsOneWidget);
    await tester.tap(find.text('Course 29'));
    expect(opened, 'c29');
    await tester.tap(find.byTooltip('Clear course search'));
    await tester.pumpAndSettle();
    expect(find.text('Page 1 of 3'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'employee typing is debounced and clearing returns to the full filtered list',
      (tester) async {
    final calls = <Map<String, String>>[];
    await tester.pumpWidget(screen(EmployeeSummaryPanel(
        scopeKey: 'all',
        revision: '1',
        load: (params) async {
          calls.add(params);
          return {'rows': [], 'total': 0};
        },
        onOpenEmployee: (_) {})));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Ad');
    await tester.pump(const Duration(milliseconds: 200));
    await tester.enterText(find.byType(TextField), 'Aditya');
    await tester.pump(const Duration(milliseconds: 200));
    expect(calls.length, 1);
    await tester.pump(const Duration(milliseconds: 160));
    await tester.pumpAndSettle();
    expect(calls.length, 2);
    expect(calls.last['search'], 'Aditya');
    expect(calls.last['page'], '1');
    await tester.tap(find.byTooltip('Clear employee search'));
    await tester.pumpAndSettle();
    expect(calls.last.containsKey('search'), isFalse);
    expect(tester.takeException(), isNull);
  });
}
