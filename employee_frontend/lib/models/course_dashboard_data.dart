import 'models.dart';

enum DashboardCourseStatus { pending, inProgress, passed, overdue }

class CourseDashboardData {
  const CourseDashboardData._();

  static DashboardCourseStatus statusFor(Course course, {DateTime? now}) {
    final referenceTime = now ?? DateTime.now();
    final modules = course.publishedModules;
    final hasStarted = course.employeeProgress.values.any(
      (progress) => progress.videoWatched || progress.quizPassed,
    );
    final isPassed = modules.isNotEmpty &&
        modules.every(
          (module) =>
              course.employeeProgress['${module.moduleNumber}']?.quizPassed ==
              true,
        );

    if (isPassed) return DashboardCourseStatus.passed;

    final deadline = _parseDate(course.deadline);
    if (deadline != null && deadline.isBefore(referenceTime)) {
      return DashboardCourseStatus.overdue;
    }

    return hasStarted
        ? DashboardCourseStatus.inProgress
        : DashboardCourseStatus.pending;
  }

  static double progressFor(Course course) {
    if (course.publishedModules.isEmpty) return 0;
    final completed = course.publishedModules
        .where(
          (module) =>
              course.employeeProgress['${module.moduleNumber}']?.quizPassed ==
              true,
        )
        .length;
    return completed / course.publishedModules.length;
  }

  static int watchedModulesFor(Course course) {
    return course.publishedModules
        .where(
          (module) =>
              course.employeeProgress['${module.moduleNumber}']?.videoWatched ==
              true,
        )
        .length;
  }

  static bool isDueSoon(Course course, {DateTime? now}) {
    final deadline = _parseDate(course.deadline);
    final referenceTime = now ?? DateTime.now();
    return deadline != null &&
        deadline.isAfter(referenceTime) &&
        deadline.isBefore(referenceTime.add(const Duration(days: 7)));
  }

  static bool isNewAssignment(Course course, {DateTime? now}) {
    final assignedAt = _parseDate(course.assignedAt);
    final referenceTime = now ?? DateTime.now();
    return assignedAt != null &&
        assignedAt.isAfter(referenceTime.subtract(const Duration(days: 7))) &&
        statusFor(course, now: referenceTime) == DashboardCourseStatus.pending;
  }

  static List<Course> orderedAssigned(List<Course> courses, {DateTime? now}) {
    final referenceTime = now ?? DateTime.now();
    final assigned = courses
        .where((course) =>
            statusFor(course, now: referenceTime) !=
            DashboardCourseStatus.passed)
        .toList();
    assigned.sort((a, b) {
      final statusOrder = _statusRank(statusFor(a, now: referenceTime))
          .compareTo(_statusRank(statusFor(b, now: referenceTime)));
      if (statusOrder != 0) return statusOrder;
      return (_parseDate(a.deadline) ?? DateTime(9999)).compareTo(
        _parseDate(b.deadline) ?? DateTime(9999),
      );
    });
    return assigned;
  }

  static List<Course> orderedAttempted(List<Course> courses, {DateTime? now}) {
    final referenceTime = now ?? DateTime.now();
    final attempted = courses.where((course) {
      final status = statusFor(course, now: referenceTime);
      return status == DashboardCourseStatus.passed ||
          status == DashboardCourseStatus.inProgress;
    }).toList();
    attempted
        .sort((a, b) => (_parseDate(b.assignedAt) ?? DateTime(0)).compareTo(
              _parseDate(a.assignedAt) ?? DateTime(0),
            ));
    return attempted;
  }

  static int _statusRank(DashboardCourseStatus status) {
    switch (status) {
      case DashboardCourseStatus.overdue:
        return 0;
      case DashboardCourseStatus.pending:
        return 1;
      case DashboardCourseStatus.inProgress:
        return 2;
      case DashboardCourseStatus.passed:
        return 3;
    }
  }

  static DateTime? _parseDate(String? value) =>
      value == null ? null : DateTime.tryParse(value);
}

class LearningMetrics {
  final int assigned;
  final int attempted;
  final int passed;
  final int pending;
  final int inProgress;

  const LearningMetrics({
    required this.assigned,
    required this.attempted,
    required this.passed,
    required this.pending,
    required this.inProgress,
  });

  factory LearningMetrics.fromCourses(List<Course> courses, {DateTime? now}) {
    final referenceTime = now ?? DateTime.now();
    final statuses = courses.map(
        (course) => CourseDashboardData.statusFor(course, now: referenceTime));
    final statusList = statuses.toList();
    final passed = statusList
        .where((status) => status == DashboardCourseStatus.passed)
        .length;
    final inProgress = statusList
        .where((status) => status == DashboardCourseStatus.inProgress)
        .length;
    final pending = statusList
        .where((status) =>
            status == DashboardCourseStatus.pending ||
            status == DashboardCourseStatus.overdue)
        .length;
    return LearningMetrics(
      assigned: courses.length - passed,
      attempted: passed + inProgress,
      passed: passed,
      pending: pending,
      inProgress: inProgress,
    );
  }
}
