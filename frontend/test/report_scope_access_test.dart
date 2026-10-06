import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/state/trainer_providers.dart';
import 'package:frontend/features/performance/report_access_guard.dart';

final accessContext = StateProvider<String>((ref) => 'account-1:observed:v1');

void main() {
  testWidgets('Open detail hides data when identity or permissions change', (tester) async {
    await tester.pumpWidget(ProviderScope(overrides: [
      reportContextProvider.overrideWith((ref) => ref.watch(accessContext)),
    ], child: const MaterialApp(home: ReportAccessGuard(
      expected: 'account-1:observed:v1', child: Text('Private employee detail'),
    ))));
    expect(find.text('Private employee detail'), findsOneWidget);
    final container = ProviderScope.containerOf(tester.element(find.byType(ReportAccessGuard)));
    container.read(accessContext.notifier).state = 'account-2:observed:v2';
    await tester.pump();
    expect(find.text('Private employee detail'), findsNothing);
    expect(find.text('Performance access changed'), findsOneWidget);
  });

  test('Selecting another view clears previous report rows and filters', () {
    final container = ProviderContainer(overrides: [
      performanceReportProvider.overrideWith((ref) => _Report(ref)),
    ]);
    addTearDown(container.dispose);
    final report = container.read(performanceReportProvider.notifier) as _Report;
    report.seed();
    report.setReportView('observed');
    final state = container.read(performanceReportProvider);
    expect(state.reportView, 'observed');
    expect(state.overview, isEmpty);
    expect(state.assignments, isEmpty);
    expect(state.filter.department, isNull);
    expect(state.page, 1);
  });
}

class _Report extends PerformanceReportNotifier {
  _Report(super.ref);
  void seed() { state = const PerformanceReportState(
    filter: PerformanceFilter(department: 'Finance'), page: 3,
    overview: {'private': 'old cohort'}, assignments: {'rows': ['old cohort']},
  ); }
  @override
  Future<void> refresh() async {}
}
