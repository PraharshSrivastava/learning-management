part of '../employee_providers.dart';

class EmployeeCourseListState {
  final List<Course> courses;
  final bool isLoading;
  final String? error;

  EmployeeCourseListState({
    this.courses = const [],
    this.isLoading = false,
    this.error,
  });
}

class EmployeeCourseListNotifier
    extends StateNotifier<EmployeeCourseListState> {
  final String? token;
  WebSocketChannel? _channel;
  bool _isDisposed = false;

  EmployeeCourseListNotifier({required this.token})
      : super(EmployeeCourseListState()) {
    if (token != null) {
      fetchCourses();
      _connectWebSocket();
    }
  }

  void _connectWebSocket() {
    if (_isDisposed || token == null) return;

    state = EmployeeCourseListState(courses: state.courses, isLoading: true);
    try {
      final wsUrl = Uri.parse(AppConstants.myCoursesWsEndpoint(token!));
      _channel = WebSocketChannel.connect(wsUrl);

      _channel!.stream.listen(
        (message) {
          try {
            final decoded = jsonDecode(message) as List<dynamic>;
            final courseList = decoded
                .map((item) =>
                    Course.fromPublishedJson(item as Map<String, dynamic>))
                .toList();
            if (!_isDisposed) {
              state = EmployeeCourseListState(
                  courses: courseList, isLoading: false);
            }
          } catch (_) {
            if (!_isDisposed) {
              state = EmployeeCourseListState(
                courses: state.courses,
                isLoading: false,
                error: 'Failed to parse learning data',
              );
            }
          }
        },
        onError: (error) {
          if (!_isDisposed) {
            state = EmployeeCourseListState(
              courses: state.courses,
              isLoading: false,
              error: 'WebSocket error: $error',
            );
          }
          _scheduleReconnect();
        },
        onDone: _scheduleReconnect,
      );
    } catch (e) {
      if (!_isDisposed) {
        state = EmployeeCourseListState(
          courses: state.courses,
          isLoading: false,
          error: e.toString(),
        );
      }
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_isDisposed || token == null) return;
    Future.delayed(const Duration(seconds: 5), () {
      _connectWebSocket();
    });
  }

  Future<void> fetchCourses() async {
    if (token == null) return;
    state = EmployeeCourseListState(courses: state.courses, isLoading: true);
    try {
      final response = await http.get(
        Uri.parse(AppConstants.myCoursesEndpoint),
        headers: _authHeaders(token!),
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body) as List<dynamic>;
        final courseList = decoded
            .map((item) =>
                Course.fromPublishedJson(item as Map<String, dynamic>))
            .toList();
        state = EmployeeCourseListState(courses: courseList, isLoading: false);
      } else {
        state = EmployeeCourseListState(
          courses: state.courses,
          isLoading: false,
          error: 'Server returned ${response.statusCode}',
        );
      }
    } catch (e) {
      state = EmployeeCourseListState(
        courses: state.courses,
        isLoading: false,
        error: e.toString(),
      );
    }
  }

  Future<void> updateModuleProgress(
    String courseId,
    int moduleNumber,
    Map<String, dynamic> payload,
  ) async {
    if (token == null) return;
    try {
      final response = await http.put(
        Uri.parse(AppConstants.updateMyModuleProgressEndpoint(
            courseId, moduleNumber)),
        headers: _authHeaders(token!),
        body: jsonEncode(payload),
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to update module progress: ${response.body}');
      }
      await fetchCourses();
    } catch (e) {
      debugPrint('Error updating module progress: $e');
    }
  }

  Future<void> updateCourseStatus(String courseId, String status) async {
    if (token == null) return;
    final response = await http.put(
      Uri.parse(AppConstants.updateMyCourseStatusEndpoint(courseId)),
      headers: _authHeaders(token!),
      body: jsonEncode({'status': status}),
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to update status');
    }
    await fetchCourses();
  }

  @override
  void dispose() {
    _isDisposed = true;
    _channel?.sink.close();
    super.dispose();
  }
}

final employeeCourseListProvider =
    StateNotifierProvider<EmployeeCourseListNotifier, EmployeeCourseListState>(
        (ref) {
  final token = ref.watch(demoAuthProvider.select((state) => state.token));
  return EmployeeCourseListNotifier(token: token);
});
