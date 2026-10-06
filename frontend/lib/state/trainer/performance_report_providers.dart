part of '../trainer_providers.dart';

class PerformanceReportState {
  final PerformanceFilter filter;
  final String reportView;
  final int view;
  final String? status;
  final String search;
  final String sort;
  final bool descending;
  final int page;
  final bool isLoading;
  final String? error;
  final Map<String, dynamic> options;
  final Map<String, dynamic> overview;
  final Map<String, dynamic> courses;
  final Map<String, dynamic> assignments;
  final bool employeeSummary;
  final int employeeResetVersion;

  const PerformanceReportState({
    this.filter = const PerformanceFilter(),
    this.reportView = 'all_courses',
    this.view = 0,
    this.status,
    this.search = '',
    this.sort = 'deadline',
    this.descending = false,
    this.page = 1,
    this.isLoading = false,
    this.error,
    this.options = const {},
    this.overview = const {},
    this.courses = const {},
    this.assignments = const {},
    this.employeeSummary = true,
    this.employeeResetVersion = 0,
  });

  PerformanceReportState copyWith({
    PerformanceFilter? filter,
    String? reportView,
    int? view,
    String? status,
    bool clearStatus = false,
    String? search,
    String? sort,
    bool? descending,
    int? page,
    bool? isLoading,
    String? error,
    Map<String, dynamic>? options,
    Map<String, dynamic>? overview,
    Map<String, dynamic>? courses,
    Map<String, dynamic>? assignments,
    bool? employeeSummary,
    int? employeeResetVersion,
  }) =>
      PerformanceReportState(
        filter: filter ?? this.filter,
        reportView: reportView ?? this.reportView,
        view: view ?? this.view,
        status: clearStatus ? null : status ?? this.status,
        search: search ?? this.search,
        sort: sort ?? this.sort,
        descending: descending ?? this.descending,
        page: page ?? this.page,
        isLoading: isLoading ?? this.isLoading,
        error: error,
        options: options ?? this.options,
        overview: overview ?? this.overview,
        courses: courses ?? this.courses,
        assignments: assignments ?? this.assignments,
        employeeSummary: employeeSummary ?? this.employeeSummary,
        employeeResetVersion: employeeResetVersion ?? this.employeeResetVersion,
      );
}

class PerformanceReportNotifier extends StateNotifier<PerformanceReportState> {
  final Ref ref;
  int _request = 0;

  PerformanceReportNotifier(this.ref) : super(const PerformanceReportState());

  Map<String, String> get _scope {
    final filter = state.filter;
    return {
      'view': state.reportView,
      if (filter.courseId != null) 'course_id': filter.courseId!,
      if (filter.employeeId != null) 'employee_id': filter.employeeId!,
      if (filter.department != null) 'department': filter.department!,
      if (filter.mailingList != null) 'mailing_list': filter.mailingList!,
      if (filter.joinedLessThanDaysAgo != null)
        'joined_less_than_days_ago': '${filter.joinedLessThanDaysAgo}',
    };
  }

  Uri _uri(String path, Map<String, String> params) =>
      Uri.parse('${AppConstants.trainerPerformanceEndpoint}/$path')
          .replace(queryParameters: {'view': state.reportView, ...params});

  Future<Map<String, dynamic>> _get(
      String path, Map<String, String> params) async {
    final serial = _request;
    final view = state.reportView;
    final response = await http.get(_uri(path, params),
        headers: ref.read(trainerAuthHeadersProvider));
    if (response.statusCode != 200) {
      if (response.statusCode == 401 || response.statusCode == 403) {
        ref.read(lmsAccessProvider.notifier).refresh();
      }
      throw Exception(
          'Unable to load performance data (${response.statusCode})');
    }
    if (!mounted || serial != _request || view != state.reportView) throw StateError('Report access changed. Refresh the view.');
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<void> refresh() async {
    final request = ++_request;
    state = state.copyWith(isLoading: true, error: null, overview: const {}, courses: const {}, assignments: const {}, options: const {});
    try {
      final scope = _scope;
      final result = await Future.wait([
        _get('options', const {}),
        _get('overview', scope),
        _get('courses', scope),
        _get('assignments', {
          ...scope,
          if (state.status != null) 'status': state.status!,
          if (state.search.isNotEmpty) 'search': state.search,
          'sort': state.sort,
          'descending': '${state.descending}',
          'page': '${state.page}',
        }),
      ]);
      if (!mounted || request != _request) return;
      state = state.copyWith(
        options: result[0],
        overview: result[1],
        courses: result[2],
        assignments: result[3],
        isLoading: false,
        error: null,
      );
    } catch (error) {
      if (!mounted || request != _request) return;
      state = state.copyWith(isLoading: false, error: error.toString());
    }
  }

  void setReportView(String view) {
    _request++;
    state = PerformanceReportState(reportView: view, employeeResetVersion: state.employeeResetVersion + 1);
    refresh();
  }

  void setView(int view) => state = state.copyWith(view: view);

  void openLinkedReport({String? courseId, String? status}) {
    state = state.copyWith(
      filter: PerformanceFilter(courseId: courseId),
      status: status,
      clearStatus: status == null,
      view: 2,
      employeeSummary: false,
      page: 1,
    );
    refresh();
  }

  void setFilter(PerformanceFilter filter) {
    state = state.copyWith(filter: filter, page: 1);
    refresh();
  }

  void setStatus(String? status) {
    state = state.copyWith(
        status: status,
        clearStatus: status == null,
        view: 2,
        page: 1,
        employeeSummary: false);
    refresh();
  }

  void setSearch(String search) {
    state = state.copyWith(search: search.trim(), page: 1);
    refresh();
  }

  void setSort(String sort) {
    state = state.copyWith(sort: sort, page: 1);
    refresh();
  }

  void toggleSortDirection() {
    state = state.copyWith(descending: !state.descending, page: 1);
    refresh();
  }

  void setPage(int page) {
    state = state.copyWith(page: page);
    refresh();
  }

  void clearFilters() {
    state = state.copyWith(
        filter: const PerformanceFilter(),
        clearStatus: true,
        search: '',
        employeeResetVersion: state.employeeResetVersion + 1,
        page: 1);
    refresh();
  }

  Future<Map<String, dynamic>> assignmentDetail(String id) =>
      _get('assignments/${Uri.encodeComponent(id)}', const {});

  void setEmployeeSummary(bool summary) =>
      state = state.copyWith(employeeSummary: summary);

  Future<Map<String, dynamic>> employeeList(Map<String, String> params) {
    final scope = _scope..remove('employee_id');
    return _get('employees', {...scope, ...params});
  }

  Future<Map<String, dynamic>> employeeDetail(String id) {
    final scope = _scope..remove('employee_id');
    return _get('employees/${Uri.encodeComponent(id)}', scope);
  }

  Future<Map<String, dynamic>> courseDetail(String id) {
    final scope = _scope;
    scope.remove('course_id');
    return _get('courses/${Uri.encodeComponent(id)}', scope);
  }

  Future<String> exportCsv() async {
    final serial = _request;
    final response = await http.get(
        _uri('export', {
          ..._scope,
          if (state.status != null) 'status': state.status!,
          if (state.search.isNotEmpty) 'search': state.search,
          'sort': state.sort,
          'descending': '${state.descending}',
        }),
        headers: ref.read(trainerAuthHeadersProvider));
    if (response.statusCode != 200) {
      throw Exception('Unable to export report (${response.statusCode})');
    }
    if (!mounted || serial != _request) throw StateError('Report access changed. Export again.');
    return response.body;
  }

  Future<String> exportEmployeeCsv(Map<String, String> params) async {
    final scope = _scope..remove('employee_id');
    final serial = _request;
    final response = await http.get(
        _uri('employees/export', {
          ...scope,
          if (params['search'] != null) 'search': params['search']!,
          if (params['attention'] != null) 'attention': params['attention']!,
          'sort': params['sort'] ?? 'employee',
          'descending': params['descending'] ?? 'false',
        }),
        headers: ref.read(trainerAuthHeadersProvider));
    if (response.statusCode != 200) {
      throw Exception('Unable to export employees (${response.statusCode})');
    }
    if (!mounted || serial != _request) throw StateError('Report access changed. Export again.');
    return response.body;
  }
}

final performanceReportProvider =
    StateNotifierProvider<PerformanceReportNotifier, PerformanceReportState>(
        (ref) {
  ref.watch(trainerAuthProvider.select((state) => state.trainer?.trainerId));
  ref.watch(trainerAuthProvider.select((state) => state.token));
  ref.watch(lmsAccessProvider.select((s) => s['permissions_version']));
  ref.watch(lmsAccessProvider.select((s) => s['report_scope_version']));
  return PerformanceReportNotifier(ref);
});

final reportContextProvider = Provider<String>((ref) {
  final auth = ref.watch(trainerAuthProvider);
  final access = ref.watch(lmsAccessProvider);
  final report = ref.watch(performanceReportProvider);
  return jsonEncode([auth.trainer?.trainerId, auth.token, access['permissions_version'], access['report_scope_version'], report.reportView,
    report.filter.courseId, report.filter.employeeId, report.filter.department, report.filter.mailingList]);
});
