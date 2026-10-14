import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:employee_frontend/core/theme/app_theme.dart';

class ReportFilterStyle {
  static const height = 60.0;
  static double controlHeight(BuildContext context) =>
      height * math.max(1.0, MediaQuery.textScalerOf(context).scale(13) / 13);
  static const label = TextStyle(
      fontSize: 11, fontWeight: FontWeight.w500, color: AppTheme.textSecondary);
  static const value = TextStyle(
      fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.primaryBlue);
}

/// Five filters stay together; narrow views scroll rather than wrapping.
class ReportFilterRow extends StatefulWidget {
  final List<Widget> Function(double width) builder;
  const ReportFilterRow({super.key, required this.builder});
  @override
  State<ReportFilterRow> createState() => _ReportFilterRowState();
}

class _ReportFilterRowState extends State<ReportFilterRow> {
  final controller = ScrollController();
  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) =>
      LayoutBuilder(builder: (context, constraints) {
        final minimumWidth = 210.0 *
            math.max(1.0, MediaQuery.textScalerOf(context).scale(13) / 13);
        final width = math.max(minimumWidth, (constraints.maxWidth - 48) / 5);
        return Scrollbar(
            controller: controller,
            thumbVisibility: width * 5 + 48 > constraints.maxWidth,
            child: SingleChildScrollView(
                controller: controller,
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final (index, child)
                          in widget.builder(width).indexed) ...[
                        if (index > 0) const SizedBox(width: 12),
                        child,
                      ],
                    ])));
      });
}

class JoinedDaysReportFilter extends StatelessWidget {
  final double width;
  final TextEditingController controller;
  final ValueChanged<String> onSubmitted;
  const JoinedDaysReportFilter(
      {super.key,
      required this.width,
      required this.controller,
      required this.onSubmitted});
  @override
  Widget build(BuildContext context) => Container(
      width: width,
      height: ReportFilterStyle.controlHeight(context),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFD2E0F0))),
      child: Row(children: [
        const Icon(Icons.event_outlined, size: 19, color: AppTheme.primaryBlue),
        const SizedBox(width: 10),
        Expanded(
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
              const Text('Joined within days', style: ReportFilterStyle.label),
              TextField(
                  controller: controller,
                  style: ReportFilterStyle.value,
                  keyboardType: TextInputType.number,
                  textInputAction: TextInputAction.done,
                  decoration: const InputDecoration(
                      isDense: true,
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      contentPadding: EdgeInsets.zero,
                      hintText: 'Enter days',
                      hintStyle: ReportFilterStyle.value),
                  onSubmitted: onSubmitted),
            ])),
      ]));
}
