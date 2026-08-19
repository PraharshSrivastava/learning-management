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
      home: const EmployeeHubGate(),
    );
  }
}

class EmployeeHubGate extends ConsumerWidget {
  const EmployeeHubGate({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(hubSessionProvider);
    if (session.isLoading) {
      return const _HubGateScaffold(
        title: 'Employee learning access',
        child: CircularProgressIndicator(),
      );
    }
    if (!session.isAuthenticated && !session.isLocalDevMode) {
      return _HubGateScaffold(
        title: 'Employee learning access',
        message: session.error ?? 'Open this application from the Hub dashboard.',
        onRefresh: () => ref.read(hubSessionProvider.notifier).refresh(),
      );
    }
    return const EmployeeAuthGate();
  }
}

class EmployeeAuthGate extends ConsumerWidget {
  const EmployeeAuthGate({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(employeeAuthProvider);
    return auth.isAuthenticated
        ? const EmployeeDashboardPage()
        : const EmployeeLoginPage();
  }
}

class _HubGateScaffold extends StatelessWidget {
  final String title;
  final Widget? child;
  final String? message;
  final VoidCallback? onRefresh;

  const _HubGateScaffold({
    required this.title,
    this.child,
    this.message,
    this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      backgroundColor: const Color(0xFFF4F6FA),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 44,
                  height: 44,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: const Color(0xFF102C77),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Text(
                    'PC',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                Text(title, style: theme.textTheme.headlineSmall),
                const SizedBox(height: 8),
                Text(
                  message ?? 'Checking Hub session...',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: const Color(0xFF667085),
                  ),
                ),
                if (child != null) ...[
                  const SizedBox(height: 24),
                  child!,
                ],
                if (onRefresh != null) ...[
                  const SizedBox(height: 24),
                  IconButton.filledTonal(
                    tooltip: 'Check again',
                    onPressed: onRefresh,
                    icon: const Icon(Icons.refresh),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
