part of '../employee_providers.dart';

class PerformanceFilter {
  final String? courseId;
  final String? employeeId;
  final String? department;
  final String? mailingList;
  final String? status;
  final int? joinedLessThanDaysAgo;

  const PerformanceFilter({
    this.courseId,
    this.employeeId,
    this.department,
    this.mailingList,
    this.status,
    this.joinedLessThanDaysAgo,
  });

  PerformanceFilter copyWith({
    String? courseId,
    String? employeeId,
    String? department,
    String? mailingList,
    String? status,
    int? joinedLessThanDaysAgo,
    bool clearCourse = false,
    bool clearEmployee = false,
    bool clearDepartment = false,
    bool clearMailingList = false,
    bool clearStatus = false,
    bool clearJoined = false,
  }) {
    return PerformanceFilter(
      courseId: clearCourse ? null : (courseId ?? this.courseId),
      employeeId: clearEmployee ? null : (employeeId ?? this.employeeId),
      department: clearDepartment ? null : (department ?? this.department),
      mailingList:
          clearMailingList ? null : (mailingList ?? this.mailingList),
      status: clearStatus ? null : (status ?? this.status),
      joinedLessThanDaysAgo: clearJoined
          ? null
          : (joinedLessThanDaysAgo ?? this.joinedLessThanDaysAgo),
    );
  }
}
