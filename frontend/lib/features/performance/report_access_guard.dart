import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:frontend/state/trainer_providers.dart';

class ReportAccessGuard extends ConsumerWidget {
  final String expected;
  final Widget child;
  const ReportAccessGuard({super.key, required this.expected, required this.child});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (ref.watch(reportContextProvider) != expected) {
      return AlertDialog(title: const Text('Performance access changed'),
        content: const Text('Close this detail and refresh your current view.'),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))]);
    }
    return child;
  }
}
