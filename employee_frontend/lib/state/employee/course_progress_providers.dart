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
    fetchCourses();
    if (token != null) {
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

  Future<void> fetchCourses({bool showLoading = true}) async {
    if (showLoading) {
      state = EmployeeCourseListState(courses: state.courses, isLoading: true);
    }
    try {
      final response = await http.get(
        Uri.parse(AppConstants.myCoursesEndpoint),
        headers: _authHeaders(token),
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
    _applyModuleProgress(courseId, moduleNumber, payload);
    try {
      final response = await http.put(
        Uri.parse(AppConstants.updateMyModuleProgressEndpoint(
            courseId, moduleNumber)),
        headers: _authHeaders(token),
        body: jsonEncode(payload),
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to update module progress: ${response.body}');
      }
      unawaited(fetchCourses(showLoading: false));
    } catch (e) {
      debugPrint('Error updating module progress: $e');
      unawaited(fetchCourses(showLoading: false));
    }
  }

  void _applyModuleProgress(
    String courseId,
    int moduleNumber,
    Map<String, dynamic> payload,
  ) {
    final moduleKey = moduleNumber.toString();
    final nextCourses = state.courses.map((course) {
      if (course.courseId != courseId) return course;

      final progress = Map<String, EmployeeModuleProgress>.from(
        course.moduleProgress,
      );
      final existing = progress[moduleKey] ?? EmployeeModuleProgress();
      final selectedAnswersPayload = payload['selected_answers'];
      Map<int, String>? selectedAnswers;
      var clearSelectedAnswers = false;

      if (payload.containsKey('selected_answers')) {
        if (selectedAnswersPayload is Map) {
          selectedAnswers = {};
          selectedAnswersPayload.forEach((key, value) {
            final parsedKey = int.tryParse(key.toString());
            if (parsedKey != null) {
              selectedAnswers![parsedKey] = value.toString();
            }
          });
        } else {
          clearSelectedAnswers = true;
        }
      }

      final quizPayloadPresent = payload.containsKey('quiz_passed') ||
          payload.containsKey('quiz_score');
      progress[moduleKey] = existing.copyWith(
        videoWatched: payload['video_watched'] as bool?,
        quizPassed: payload['quiz_passed'] as bool?,
        quizScore: payload['quiz_score'] as num?,
        selectedAnswers: selectedAnswers,
        clearSelectedAnswers: clearSelectedAnswers,
        attemptCount: quizPayloadPresent
            ? existing.attemptCount + 1
            : existing.attemptCount,
      );

      final allComplete = course.publishedModules.isNotEmpty &&
          course.publishedModules.every((module) {
            final moduleProgress = progress[module.moduleNumber.toString()];
            final videoWatched = moduleProgress?.videoWatched == true;
            final quizPassed = module.quiz.isEmpty
                ? videoWatched
                : moduleProgress?.quizPassed == true;
            return videoWatched && quizPassed;
          });

      return course.copyWith(
        assignmentStatus: allComplete
            ? 'completed'
            : course.assignmentStatus == 'pending'
                ? 'started'
                : null,
        moduleProgress: progress,
      );
    }).toList();

    state = EmployeeCourseListState(
      courses: nextCourses,
      isLoading: state.isLoading,
      error: state.error,
    );
  }

  Future<void> updateCourseStatus(String courseId, String status) async {
    final response = await http.put(
      Uri.parse(AppConstants.updateMyCourseStatusEndpoint(courseId)),
      headers: _authHeaders(token),
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
  final token = ref.watch(employeeAuthProvider.select((state) => state.token));
  ref.watch(employeeAuthProvider.select((state) => state.isAuthenticated));
  return EmployeeCourseListNotifier(token: token);
});
