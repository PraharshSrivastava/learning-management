part of '../trainer_providers.dart';

class PerformanceReportState {
  final PerformanceFilter filter;
  final int view;
  final String? status;
  final String search;
  final String sort;
  final bool descending;
  final int page;
  final int trendDays;
  final bool isLoading;
  final String? error;
  final Map<String, dynamic> options;
  final Map<String, dynamic> overview;
  final Map<String, dynamic> courses;
  final Map<String, dynamic> assignments;

  const PerformanceReportState({
    this.filter = const PerformanceFilter(),
    this.view = 0,
    this.status,
    this.search = '',
    this.sort = 'deadline',
    this.descending = false,
    this.page = 1,
    this.trendDays = 30,
    this.isLoading = false,
    this.error,
    this.options = const {},
    this.overview = const {},
    this.courses = const {},
    this.assignments = const {},
  });

  PerformanceReportState copyWith({
    PerformanceFilter? filter,
    int? view,
    String? status,
    bool clearStatus = false,
    String? search,
    String? sort,
    bool? descending,
    int? page,
    int? trendDays,
    bool? isLoading,
    String? error,
    Map<String, dynamic>? options,
    Map<String, dynamic>? overview,
    Map<String, dynamic>? courses,
    Map<String, dynamic>? assignments,
  }) =>
      PerformanceReportState(
        filter: filter ?? this.filter,
        view: view ?? this.view,
        status: clearStatus ? null : status ?? this.status,
        search: search ?? this.search,
        sort: sort ?? this.sort,
        descending: descending ?? this.descending,
        page: page ?? this.page,
        trendDays: trendDays ?? this.trendDays,
        isLoading: isLoading ?? this.isLoading,
        error: error,
        options: options ?? this.options,
        overview: overview ?? this.overview,
        courses: courses ?? this.courses,
        assignments: assignments ?? this.assignments,
      );
}

class PerformanceReportNotifier extends StateNotifier<PerformanceReportState> {
  final Ref ref;
  int _request = 0;
  Timer? _searchTimer;

  PerformanceReportNotifier(this.ref) : super(const PerformanceReportState());

  Map<String, String> get _scope {
    final filter = state.filter;
    return {
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
          .replace(queryParameters: params.isEmpty ? null : params);

  Future<Map<String, dynamic>> _get(
      String path, Map<String, String> params) async {
    final response = await http.get(_uri(path, params),
        headers: ref.read(trainerAuthHeadersProvider));
    if (response.statusCode != 200) {
      throw Exception(
          'Unable to load performance data (${response.statusCode})');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<void> refresh() async {
    final request = ++_request;
    state = state.copyWith(isLoading: true, error: null);
    try {
      final scope = _scope;
      final result = await Future.wait([
        _get('options', const {}),
        _get('overview', {...scope, 'trend_days': '${state.trendDays}'}),
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

  void setView(int view) => state = state.copyWith(view: view);

  void openLinkedReport({String? courseId, String? status}) {
    state = state.copyWith(
      filter: PerformanceFilter(courseId: courseId),
      status: status,
      clearStatus: status == null,
      view: 2,
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
        status: status, clearStatus: status == null, view: 2, page: 1);
    refresh();
  }

  void setSearch(String search) {
    state = state.copyWith(search: search, page: 1);
    _searchTimer?.cancel();
    _searchTimer = Timer(const Duration(milliseconds: 350), refresh);
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

  void setTrendDays(int days) {
    state = state.copyWith(trendDays: days);
    refresh();
  }

  void clearFilters() {
    state = state.copyWith(
        filter: const PerformanceFilter(),
        clearStatus: true,
        search: '',
        page: 1);
    refresh();
  }

  Future<Map<String, dynamic>> assignmentDetail(String id) =>
      _get('assignments/${Uri.encodeComponent(id)}', const {});

  Future<Map<String, dynamic>> courseDetail(String id) {
    final scope = _scope;
    scope.remove('course_id');
    return _get('courses/${Uri.encodeComponent(id)}', scope);
  }

  Future<String> exportCsv() async {
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
    return response.body;
  }

  @override
  void dispose() {
    _searchTimer?.cancel();
    super.dispose();
  }
}

final performanceReportProvider =
    StateNotifierProvider<PerformanceReportNotifier, PerformanceReportState>(
        (ref) {
  ref.watch(trainerAuthProvider.select((state) => state.trainer?.trainerId));
  return PerformanceReportNotifier(ref);
});
