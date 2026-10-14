import 'package:flutter/material.dart';
import 'package:frontend/core/theme/app_theme.dart';

/// Course search is local to this view; employee/report scope stays unchanged.
class CourseReportBrowser extends StatefulWidget {
  final List<Map<String, dynamic>> courses;
  final Widget Function(Map<String, dynamic>) itemBuilder;
  final String scopeKey;
  final int resetVersion;
  final bool isLoading;
  const CourseReportBrowser(
      {super.key,
      required this.courses,
      required this.itemBuilder,
      required this.scopeKey,
      required this.resetVersion,
      this.isLoading = false});
  @override
  State<CourseReportBrowser> createState() => _CourseReportBrowserState();
}

class _CourseReportBrowserState extends State<CourseReportBrowser> {
  final search = TextEditingController();
  int page = 1;
  static const pageSize = 12;
  @override
  void didUpdateWidget(covariant CourseReportBrowser oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.scopeKey != widget.scopeKey ||
        oldWidget.resetVersion != widget.resetVersion) {
      page = 1;
      search.clear();
    }
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final words = search.text.trim().toLowerCase().split(RegExp(r'\s+'));
    final matches = widget.courses
        .where((course) => words.every((word) =>
            '${course['course_name']} ${course['course_id']}'
                .toLowerCase()
                .contains(word)))
        .toList();
    final pages = (matches.length / pageSize).ceil().clamp(1, 1000000);
    if (!widget.isLoading) page = page.clamp(1, pages);
    final shown = matches.skip((page - 1) * pageSize).take(pageSize).toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      TextField(
          controller: search,
          onChanged: (_) => setState(() => page = 1),
          decoration: InputDecoration(
              hintText: 'Search courses by name or ID',
              prefixIcon: const Icon(Icons.search, color: AppTheme.primaryBlue),
              suffixIcon: search.text.isEmpty
                  ? null
                  : IconButton(
                      tooltip: 'Clear course search',
                      icon: const Icon(Icons.close),
                      onPressed: () => setState(() {
                            search.clear();
                            page = 1;
                          })),
              filled: true,
              fillColor: Colors.white,
              border:
                  OutlineInputBorder(borderRadius: BorderRadius.circular(12)))),
      const SizedBox(height: 10),
      Text(
          widget.isLoading
              ? 'Loading courses…'
              : '${matches.length} matching courses',
          style: const TextStyle(color: AppTheme.textSecondary)),
      const SizedBox(height: 12),
      if (matches.isEmpty && !widget.isLoading)
        const Padding(
            padding: EdgeInsets.all(24),
            child: Text('No courses match your search and selected filters.')),
      LayoutBuilder(builder: (_, constraints) {
        final columns = constraints.maxWidth >= 850 ? 2 : 1;
        final width = (constraints.maxWidth - 12 * (columns - 1)) / columns;
        return Wrap(spacing: 12, runSpacing: 12, children: [
          for (final course in shown)
            SizedBox(width: width, child: widget.itemBuilder(course))
        ]);
      }),
      if (matches.length > pageSize)
        Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Wrap(
                spacing: 10,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(
                      'Showing ${(page - 1) * pageSize + 1}–${((page - 1) * pageSize + shown.length)} of ${matches.length}'),
                  IconButton(
                      tooltip: 'Previous course page',
                      onPressed: page > 1 ? () => setState(() => page--) : null,
                      icon: const Icon(Icons.chevron_left)),
                  Text('Page $page of $pages'),
                  IconButton(
                      tooltip: 'Next course page',
                      onPressed:
                          page < pages ? () => setState(() => page++) : null,
                      icon: const Icon(Icons.chevron_right)),
                ])),
    ]);
  }
}
