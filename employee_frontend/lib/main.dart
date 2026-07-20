import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'theme.dart';
import 'widgets/employee_dashboard_page.dart';
import 'widgets/employee_login_page.dart';
import 'providers/employee_providers.dart';

import 'package:flutter_dotenv/flutter_dotenv.dart';

Future<void> main() async {
  await dotenv.load(fileName: ".env");
  runApp(
    const ProviderScope(
      child: EmployeeLMSApp(),
    ),
  );
}

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
