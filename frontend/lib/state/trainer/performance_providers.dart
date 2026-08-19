part of '../trainer_providers.dart';

class PerformanceFilter {
  final String? courseId;
  final String? employeeId;
  final String? department;
  final String? jobTitle;
  final String? status;
  final int? joinedLessThanDaysAgo;

  const PerformanceFilter({
    this.courseId,
    this.employeeId,
    this.department,
    this.jobTitle,
    this.status,
    this.joinedLessThanDaysAgo,
  });

  PerformanceFilter copyWith({
    String? courseId,
    String? employeeId,
    String? department,
    String? jobTitle,
    String? status,
    int? joinedLessThanDaysAgo,
    bool clearCourse = false,
    bool clearEmployee = false,
    bool clearDepartment = false,
    bool clearJobTitle = false,
    bool clearStatus = false,
    bool clearJoined = false,
  }) {
    return PerformanceFilter(
      courseId: clearCourse ? null : (courseId ?? this.courseId),
      employeeId: clearEmployee ? null : (employeeId ?? this.employeeId),
      department: clearDepartment ? null : (department ?? this.department),
      jobTitle: clearJobTitle ? null : (jobTitle ?? this.jobTitle),
      status: clearStatus ? null : (status ?? this.status),
      joinedLessThanDaysAgo: clearJoined
          ? null
          : (joinedLessThanDaysAgo ?? this.joinedLessThanDaysAgo),
    );
  }
}

class PerformanceState {
  final PerformanceDashboard dashboard;
  final PerformanceFilter filter;
  final bool isLoading;
  final String? error;

  const PerformanceState({
    this.dashboard = const PerformanceDashboard(),
    this.filter = const PerformanceFilter(),
    this.isLoading = false,
    this.error,
  });

  PerformanceState copyWith({
    PerformanceDashboard? dashboard,
    PerformanceFilter? filter,
    bool? isLoading,
    String? error,
  }) {
    return PerformanceState(
      dashboard: dashboard ?? this.dashboard,
      filter: filter ?? this.filter,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

class PerformanceNotifier extends StateNotifier<PerformanceState> {
  final Ref ref;

  PerformanceNotifier(this.ref) : super(const PerformanceState()) {
    fetch();
  }

  Future<void> fetch() async {
    state = state.copyWith(isLoading: true);
    try {
      final params = <String, String>{};
      final filter = state.filter;
      if (filter.courseId != null) params['course_id'] = filter.courseId!;
      if (filter.employeeId != null) params['employee_id'] = filter.employeeId!;
      if (filter.department != null) params['department'] = filter.department!;
      if (filter.jobTitle != null) params['job_title'] = filter.jobTitle!;
      if (filter.status != null) params['status'] = filter.status!;
      if (filter.joinedLessThanDaysAgo != null) {
        params['joined_less_than_days_ago'] =
            filter.joinedLessThanDaysAgo!.toString();
      }
      final uri = Uri.parse(AppConstants.trainerPerformanceEndpoint)
          .replace(queryParameters: params.isEmpty ? null : params);
      final response = await http.get(
        uri,
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode == 200) {
        state = state.copyWith(
          dashboard: PerformanceDashboard.fromJson(
            jsonDecode(response.body) as Map<String, dynamic>,
          ),
          isLoading: false,
        );
      } else {
        state = state.copyWith(
          isLoading: false,
          error: 'Server returned ${response.statusCode}',
        );
      }
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  void updateFilter(PerformanceFilter filter) {
    state = state.copyWith(filter: filter, error: null);
    fetch();
  }

  void clearFilters() {
    state = state.copyWith(filter: const PerformanceFilter(), error: null);
    fetch();
  }
}

final performanceProvider =
    StateNotifierProvider<PerformanceNotifier, PerformanceState>((ref) {
  return PerformanceNotifier(ref);
});
