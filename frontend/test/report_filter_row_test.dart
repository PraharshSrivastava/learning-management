import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/features/performance/report_filter_row.dart';
import 'package:frontend/features/performance/searchable_report_filter.dart';

void main() {
  testWidgets('five filters stay aligned and scroll on narrow screens',
      (tester) async {
    tester.view.resetPhysicalSize();
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(1500, 600);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: ReportFilterRow(
                builder: (width) => [
                      for (var i = 0; i < 5; i++)
                        SizedBox(
                            key: ValueKey(i),
                            width: width,
                            height: ReportFilterStyle.height,
                            child: Text('Filter $i')),
                    ]))));
    final first = tester.getTopLeft(find.byKey(const ValueKey(0)));
    for (var i = 1; i < 5; i++) {
      expect(tester.getTopLeft(find.byKey(ValueKey(i))).dy, first.dy);
    }
    expect(tester.getBottomRight(find.byKey(const ValueKey(4))).dx,
        lessThanOrEqualTo(1500));
    tester.view.physicalSize = const Size(500, 600);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.drag(
        find.byType(SingleChildScrollView), const Offset(-800, 0));
    await tester.pumpAndSettle();
    expect(tester.getBottomRight(find.byKey(const ValueKey(4))).dx,
        lessThanOrEqualTo(500));
  });

  testWidgets('matching control heights survive large text and day entry',
      (tester) async {
    final days = TextEditingController();
    addTearDown(days.dispose);
    String? submitted;
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: MediaQuery(
      data: const MediaQueryData(textScaler: TextScaler.linear(2)),
      child: ReportFilterRow(
          builder: (width) => [
                for (final label in [
                  'Course availability',
                  'Course',
                  'Department',
                  'Mailing list'
                ])
                  SearchableReportFilter(
                      label: label,
                      width: width,
                      value: 'all',
                      allowAll: false,
                      icon: Icons.search,
                      items: const {'all': 'All courses'},
                      onChanged: (_) {}),
                JoinedDaysReportFilter(
                    width: width,
                    controller: days,
                    onSubmitted: (text) => submitted = text),
              ]),
    ))));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    final button = tester.getSize(find.byType(OutlinedButton).first);
    expect(button.height, 120);
    await tester.drag(
        find.byType(SingleChildScrollView), const Offset(-2000, 0));
    await tester.pumpAndSettle();
    expect(
        tester.getTopLeft(find.byType(TextField)).dy, greaterThanOrEqualTo(0));
    await tester.enterText(find.byType(TextField), '30');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    expect(submitted, '30');
    expect(tester.takeException(), isNull);
  });
}
