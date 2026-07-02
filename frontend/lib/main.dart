import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'theme.dart';
import 'widgets/dashboard_page.dart';

void main() {
  runApp(
    const ProviderScope(
      child: LMSApp(),
    ),
  );
}

class LMSApp extends StatelessWidget {
  const LMSApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PhillipCapital LMS',
      theme: AppTheme.lightTheme,
      debugShowCheckedModeBanner: false,
      home: const DashboardPage(),
    );
  }
}
