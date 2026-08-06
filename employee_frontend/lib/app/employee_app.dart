import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:employee_frontend/core/theme/app_theme.dart';
import 'package:employee_frontend/features/auth/employee_login_page.dart';
import 'package:employee_frontend/features/dashboard/employee_dashboard_page.dart';
import 'package:employee_frontend/state/employee_providers.dart';

class EmployeeLMSApp extends StatelessWidget {
  const EmployeeLMSApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PhillipCapital Employee LMS',
      theme: AppTheme.lightTheme,
      debugShowCheckedModeBanner: false,
      home: const EmployeeAuthGate(),
    );
  }
}

class EmployeeAuthGate extends ConsumerWidget {
  const EmployeeAuthGate({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(demoAuthProvider);
    return auth.isAuthenticated
        ? const EmployeeDashboardPage()
        : const EmployeeLoginPage();
  }
}
