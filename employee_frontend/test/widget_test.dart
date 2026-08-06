import 'package:employee_frontend/app/employee_app.dart';
import 'package:employee_frontend/data/models/models.dart';
import 'package:employee_frontend/features/dashboard/employee_dashboard_page.dart';
import 'package:employee_frontend/state/employee_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

final _employeeOne = Employee(
  employeeId: 'emp_test_1',
  name: 'Aarav Mehta',
  department: 'Sales',
  jobTitle: 'Associate',
  joinDate: '2026-01-01',
  status: 'active',
);

final _employeeTwo = Employee(
  employeeId: 'emp_test_2',
  name: 'Priya Rao',
  department: 'Compliance',
  jobTitle: 'Manager',
  joinDate: '2025-10-01',
  status: 'active',
);

class FakeDemoAuthNotifier extends DemoAuthNotifier {
  FakeDemoAuthNotifier(DemoAuthState initialState) : super(autoFetch: false) {
    state = initialState;
  }

  @override
  Future<void> fetchEmployees() async {}

  @override
  Future<void> login(Employee employee) async {
    state = state.copyWith(employee: employee, token: 'fake-token');
  }
}

class FakeEmployeeCourseListNotifier extends EmployeeCourseListNotifier {
  FakeEmployeeCourseListNotifier(EmployeeCourseListState initialState)
      : super(token: null) {
    state = initialState;
  }
}

Widget _buildApp({
  required DemoAuthState authState,
  EmployeeCourseListState? courseState,
}) {
  return ProviderScope(
    overrides: [
      demoAuthProvider.overrideWith((ref) => FakeDemoAuthNotifier(authState)),
      if (courseState != null)
        employeeCourseListProvider.overrideWith(
          (ref) => FakeEmployeeCourseListNotifier(courseState),
        ),
    ],
    child: const EmployeeLMSApp(),
  );
}

void main() {
  testWidgets('employee login screen lists demo employees', (tester) async {
    await tester.pumpWidget(
      _buildApp(
        authState: DemoAuthState(employees: [_employeeOne, _employeeTwo]),
      ),
    );
    await tester.pump();

    expect(find.text('Employee learning access'), findsOneWidget);
    expect(find.text('Aarav Mehta'), findsOneWidget);
    expect(find.text('emp_test_1'), findsOneWidget);
    expect(find.text('Priya Rao'), findsOneWidget);
  });

  testWidgets('employee login search filters employees', (tester) async {
    await tester.pumpWidget(
      _buildApp(
        authState: DemoAuthState(employees: [_employeeOne, _employeeTwo]),
      ),
    );
    await tester.pump();

    await tester.enterText(find.byType(TextField), 'compliance');
    await tester.pump();

    expect(find.text('Aarav Mehta'), findsNothing);
    expect(find.text('Priya Rao'), findsOneWidget);
  });

  testWidgets('authenticated employee sees dashboard shell', (tester) async {
    await tester.pumpWidget(
      _buildApp(
        authState: DemoAuthState(
          employees: [_employeeOne, _employeeTwo],
          employee: _employeeOne,
          token: 'fake-token',
        ),
        courseState: EmployeeCourseListState(courses: const [], isLoading: false),
      ),
    );
    await tester.pump();

    expect(find.byType(EmployeeDashboardPage), findsOneWidget);
  });
}
