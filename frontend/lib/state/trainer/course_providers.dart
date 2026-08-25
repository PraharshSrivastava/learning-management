part of '../trainer_providers.dart';

class CourseListState {
  final List<Course> courses;
  final bool isLoading;
  final bool hasLoaded;
  final String? error;

  CourseListState({
    this.courses = const [],
    this.isLoading = false,
    this.hasLoaded = false,
    this.error,
  });
}

class CourseListNotifier extends StateNotifier<CourseListState> {
  final Ref ref;

  Future<void>? _fetchInFlight;
  final Map<String, Future<Course?>> _detailInFlight = {};

  CourseListNotifier(this.ref) : super(CourseListState());

  Future<void> ensureLoaded() {
    if (state.hasLoaded || state.isLoading) {
      return _fetchInFlight ?? Future.value();
    }
    return fetchCourses();
  }

  Future<void> fetchCourses() {
    if (_fetchInFlight != null) return _fetchInFlight!;
    final request = _fetchCourses();
    _fetchInFlight = request;
    request.whenComplete(() => _fetchInFlight = null);
    return request;
  }

  Future<void> _fetchCourses() async {
    state = CourseListState(
      courses: state.courses,
      isLoading: true,
      hasLoaded: state.hasLoaded,
    );
    try {
      final response = await http.get(
        Uri.parse(AppConstants.listCoursesEndpoint),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode == 200) {
        final List<dynamic> decoded = jsonDecode(response.body);
        final summaries = decoded.map((item) => Course.fromJson(item)).toList();
        final courseList = summaries.map(_preserveLoadedDetail).toList();
        state = CourseListState(
          courses: courseList,
          isLoading: false,
          hasLoaded: true,
        );
        _syncSelectedAfterListRefresh();
      } else {
        state = CourseListState(
            courses: state.courses,
            isLoading: false,
            hasLoaded: state.hasLoaded,
            error: 'Server returned ${response.statusCode}');
      }
    } catch (e) {
      state = CourseListState(
          courses: state.courses,
          isLoading: false,
          hasLoaded: state.hasLoaded,
          error: e.toString());
    }
  }

  Course _preserveLoadedDetail(Course summary) {
    final existing = state.courses.where((course) {
      return course.courseId == summary.courseId && course.modules.isNotEmpty;
    }).toList();
    if (existing.isEmpty) return summary;
    final detail = existing.first;
    return detail.copyWith(
      courseName: summary.courseName,
      courseDescription: summary.courseDescription,
      courseObjective: summary.courseObjective,
      courseDifficulty: summary.courseDifficulty,
      language: summary.language,
      targetAudience: summary.targetAudience,
      thumbnailPath: summary.thumbnailPath,
      status: summary.status,
      generationStatus: summary.generationStatus,
      failedCheckpoint: summary.failedCheckpoint,
      currentCheckpoint: summary.currentCheckpoint,
      generationError: summary.generationError,
      moduleCount: summary.moduleCount,
      isAssignable: summary.isAssignable,
    );
  }

  Future<Course?> fetchCourseDetail(String courseId) {
    if (_detailInFlight.containsKey(courseId)) {
      return _detailInFlight[courseId]!;
    }
    final existing = state.courses.where((course) {
      return course.courseId == courseId && course.modules.isNotEmpty;
    }).toList();
    if (existing.isNotEmpty) return Future.value(existing.first);

    final request = _fetchCourseDetail(courseId);
    _detailInFlight[courseId] = request;
    request.whenComplete(() => _detailInFlight.remove(courseId));
    return request;
  }

  Future<Course?> refreshCourseDetail(String courseId) {
    final request = _fetchCourseDetail(courseId);
    _detailInFlight[courseId] = request;
    request.whenComplete(() => _detailInFlight.remove(courseId));
    return request;
  }

  Future<Course?> _fetchCourseDetail(String courseId) async {
    try {
      final response = await http.get(
        Uri.parse(AppConstants.courseDetailEndpoint(courseId)),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode != 200) {
        state = CourseListState(
          courses: state.courses,
          isLoading: false,
          hasLoaded: state.hasLoaded,
          error: 'Server returned ${response.statusCode}',
        );
        return null;
      }
      final course = Course.fromJson(jsonDecode(response.body));
      upsertCourse(course, select: true);
      return course;
    } catch (e) {
      state = CourseListState(
        courses: state.courses,
        isLoading: false,
        hasLoaded: state.hasLoaded,
        error: e.toString(),
      );
      return null;
    }
  }

  void upsertCourse(Course course, {bool select = false}) {
    final index =
        state.courses.indexWhere((item) => item.courseId == course.courseId);
    final next = [...state.courses];
    if (index >= 0) {
      next[index] = course;
    } else {
      next.insert(0, course);
    }
    state = CourseListState(
      courses: next,
      isLoading: false,
      hasLoaded: true,
    );
    if (select) {
      ref.read(selectedCourseProvider.notifier).state = course;
    } else {
      _syncSelectedAfterListRefresh();
    }
  }

  void removeCourse(String courseId) {
    state = CourseListState(
      courses:
          state.courses.where((course) => course.courseId != courseId).toList(),
      isLoading: false,
      hasLoaded: state.hasLoaded,
    );
    final selected = ref.read(selectedCourseProvider);
    if (selected?.courseId == courseId) {
      ref.read(selectedCourseProvider.notifier).state = null;
    }
  }

  void _syncSelectedAfterListRefresh() {
    final selected = ref.read(selectedCourseProvider);
    if (selected == null) return;
    final matches = state.courses
        .where((course) => course.courseId == selected.courseId)
        .toList();
    if (matches.isNotEmpty) {
      ref.read(selectedCourseProvider.notifier).state = matches.first;
    }
  }
}

final courseListProvider =
    StateNotifierProvider<CourseListNotifier, CourseListState>((ref) {
  return CourseListNotifier(ref);
});

class AssignableCourseListNotifier extends StateNotifier<CourseListState> {
  final Ref ref;

  Future<void>? _fetchInFlight;

  AssignableCourseListNotifier(this.ref) : super(CourseListState());

  Future<void> ensureLoaded() {
    if (state.hasLoaded || state.isLoading) {
      return _fetchInFlight ?? Future.value();
    }
    return fetchCourses();
  }

  Future<void> fetchCourses() {
    if (_fetchInFlight != null) return _fetchInFlight!;
    final request = _fetchCourses();
    _fetchInFlight = request;
    request.whenComplete(() => _fetchInFlight = null);
    return request;
  }

  Future<void> _fetchCourses() async {
    state = CourseListState(
      courses: state.courses,
      isLoading: true,
      hasLoaded: state.hasLoaded,
    );
    try {
      final response = await http.get(
        Uri.parse(AppConstants.assignableCoursesEndpoint),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode == 200) {
        final List<dynamic> decoded = jsonDecode(response.body);
        final courseList =
            decoded.map((item) => Course.fromJson(item)).toList();
        state = CourseListState(
          courses: courseList,
          isLoading: false,
          hasLoaded: true,
        );
      } else {
        state = CourseListState(
          courses: state.courses,
          isLoading: false,
          hasLoaded: state.hasLoaded,
          error: 'Server returned ${response.statusCode}',
        );
      }
    } catch (e) {
      state = CourseListState(
          courses: state.courses,
          isLoading: false,
          hasLoaded: state.hasLoaded,
          error: e.toString());
    }
  }

  void syncFromCourseList(List<Course> courses) {
    state = CourseListState(
      courses: courses.where((course) => course.isAssignable).toList(),
      isLoading: false,
      hasLoaded: true,
    );
  }
}

final assignableCourseListProvider =
    StateNotifierProvider<AssignableCourseListNotifier, CourseListState>((ref) {
  return AssignableCourseListNotifier(ref);
});

// Active selections & current tab
final selectedFileProvider = StateProvider<PDFFile?>((ref) => null);
final selectedCourseProvider = StateProvider<Course?>((ref) => null);
final currentTabProvider =
    StateProvider<int>((ref) => 0); // 0 = Documents, 1 = Courses
