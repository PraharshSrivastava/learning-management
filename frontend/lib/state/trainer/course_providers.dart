part of '../trainer_providers.dart';

class CourseListState {
  final List<Course> courses;
  final bool isLoading;
  final bool hasLoaded;
  final String? ownerTrainerId;
  final String? error;

  CourseListState({
    this.courses = const [],
    this.isLoading = false,
    this.hasLoaded = false,
    this.ownerTrainerId,
    this.error,
  });
}

class CourseListNotifier extends StateNotifier<CourseListState> {
  final Ref ref;

  Future<void>? _fetchInFlight;
  String? _fetchTrainerId;
  String? _currentTrainerId;
  final Map<String, Future<Course?>> _detailInFlight = {};

  CourseListNotifier(this.ref) : super(CourseListState());

  Future<void> ensureLoaded() {
    final trainerId = _currentTrainerId;
    if (trainerId == null) return Future.value();
    if (state.hasLoaded &&
        state.ownerTrainerId == trainerId &&
        state.error == null) {
      return Future.value();
    }
    if (state.isLoading && _fetchTrainerId == trainerId) {
      return _fetchInFlight ?? Future.value();
    }
    return fetchCourses();
  }

  Future<void> fetchCourses() {
    final trainerId = _currentTrainerId;
    if (trainerId == null) return Future.value();
    if (_fetchInFlight != null && _fetchTrainerId == trainerId) {
      return _fetchInFlight!;
    }
    final request = _fetchCourses();
    _fetchInFlight = request;
    _fetchTrainerId = trainerId;
    request.whenComplete(() {
      if (_fetchInFlight == request) {
        _fetchInFlight = null;
        _fetchTrainerId = null;
      }
    });
    return request;
  }

  Future<void> _fetchCourses() async {
    final trainerId = _currentTrainerId;
    if (trainerId == null) return;
    state = CourseListState(
      courses: state.courses,
      isLoading: true,
      hasLoaded: state.hasLoaded,
      ownerTrainerId: trainerId,
    );
    try {
      final response = await http.get(
        Uri.parse(AppConstants.listCoursesEndpoint),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (_currentTrainerId != trainerId) return;
      if (response.statusCode == 200) {
        final List<dynamic> decoded = jsonDecode(response.body);
        final summaries = decoded.map((item) => Course.fromJson(item)).toList();
        final courseList = summaries.map(_preserveLoadedDetail).toList();
        state = CourseListState(
          courses: courseList,
          isLoading: false,
          hasLoaded: true,
          ownerTrainerId: trainerId,
        );
        _syncSelectedAfterListRefresh();
      } else {
        state = CourseListState(
            courses: state.courses,
            isLoading: false,
            hasLoaded: state.hasLoaded,
            ownerTrainerId: trainerId,
            error: 'Server returned ${response.statusCode}');
      }
    } catch (e) {
      if (_currentTrainerId != trainerId) return;
      state = CourseListState(
          courses: state.courses,
          isLoading: false,
          hasLoaded: state.hasLoaded,
          ownerTrainerId: trainerId,
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
    final trainerId = _currentTrainerId;
    if (trainerId == null) return null;
    try {
      final response = await http.get(
        Uri.parse(AppConstants.courseDetailEndpoint(courseId)),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (_currentTrainerId != trainerId) return null;
      if (response.statusCode != 200) {
        state = CourseListState(
          courses: state.courses,
          isLoading: false,
          hasLoaded: state.hasLoaded,
          ownerTrainerId: trainerId,
          error: 'Server returned ${response.statusCode}',
        );
        return null;
      }
      final course = Course.fromJson(jsonDecode(response.body));
      upsertCourse(course, select: true);
      return course;
    } catch (e) {
      if (_currentTrainerId != trainerId) return null;
      state = CourseListState(
        courses: state.courses,
        isLoading: false,
        hasLoaded: state.hasLoaded,
        ownerTrainerId: trainerId,
        error: e.toString(),
      );
      return null;
    }
  }

  void upsertCourse(Course course, {bool select = false}) {
    final trainerId = _currentTrainerId;
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
      hasLoaded: state.hasLoaded && state.ownerTrainerId == trainerId,
      ownerTrainerId: trainerId ?? state.ownerTrainerId,
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
      ownerTrainerId: state.ownerTrainerId,
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

  void handleAuthChanged(String? trainerId) {
    if (_currentTrainerId == trainerId) return;
    _currentTrainerId = trainerId;
    _detailInFlight.clear();
    if (trainerId == null) {
      state = CourseListState();
      ref.read(selectedCourseProvider.notifier).state = null;
      return;
    }
    state = CourseListState(ownerTrainerId: trainerId);
    Future.microtask(ensureLoaded);
  }
}

final courseListProvider =
    StateNotifierProvider<CourseListNotifier, CourseListState>((ref) {
  final notifier = CourseListNotifier(ref);
  notifier.handleAuthChanged(ref.read(trainerAuthProvider).trainer?.trainerId);
  ref.listen<TrainerAuthState>(trainerAuthProvider, (previous, next) {
    notifier.handleAuthChanged(next.trainer?.trainerId);
  });
  return notifier;
});

class AssignableCourseListNotifier extends StateNotifier<CourseListState> {
  final Ref ref;

  Future<void>? _fetchInFlight;
  String? _fetchTrainerId;
  String? _currentTrainerId;

  AssignableCourseListNotifier(this.ref) : super(CourseListState());

  Future<void> ensureLoaded() {
    final trainerId = _currentTrainerId;
    if (trainerId == null) return Future.value();
    if (state.hasLoaded &&
        state.ownerTrainerId == trainerId &&
        state.error == null) {
      return Future.value();
    }
    if (state.isLoading && _fetchTrainerId == trainerId) {
      return _fetchInFlight ?? Future.value();
    }
    return fetchCourses();
  }

  Future<void> fetchCourses() {
    final trainerId = _currentTrainerId;
    if (trainerId == null) return Future.value();
    if (_fetchInFlight != null && _fetchTrainerId == trainerId) {
      return _fetchInFlight!;
    }
    final request = _fetchCourses();
    _fetchInFlight = request;
    _fetchTrainerId = trainerId;
    request.whenComplete(() {
      if (_fetchInFlight == request) {
        _fetchInFlight = null;
        _fetchTrainerId = null;
      }
    });
    return request;
  }

  Future<void> _fetchCourses() async {
    final trainerId = _currentTrainerId;
    if (trainerId == null) return;
    state = CourseListState(
      courses: state.courses,
      isLoading: true,
      hasLoaded: state.hasLoaded,
      ownerTrainerId: trainerId,
    );
    try {
      final response = await http.get(
        Uri.parse(AppConstants.assignableCoursesEndpoint),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (_currentTrainerId != trainerId) return;
      if (response.statusCode == 200) {
        final List<dynamic> decoded = jsonDecode(response.body);
        final courseList =
            decoded.map((item) => Course.fromJson(item)).toList();
        state = CourseListState(
          courses: courseList,
          isLoading: false,
          hasLoaded: true,
          ownerTrainerId: trainerId,
        );
      } else {
        state = CourseListState(
          courses: state.courses,
          isLoading: false,
          hasLoaded: state.hasLoaded,
          ownerTrainerId: trainerId,
          error: 'Server returned ${response.statusCode}',
        );
      }
    } catch (e) {
      if (_currentTrainerId != trainerId) return;
      state = CourseListState(
          courses: state.courses,
          isLoading: false,
          hasLoaded: state.hasLoaded,
          ownerTrainerId: trainerId,
          error: e.toString());
    }
  }

  void syncFromCourseList(List<Course> courses) {
    final source = ref.read(courseListProvider);
    final trainerId = _currentTrainerId;
    state = CourseListState(
      courses: courses.where((course) => course.isAssignable).toList(),
      isLoading: false,
      hasLoaded: source.hasLoaded && source.ownerTrainerId == trainerId,
      ownerTrainerId: trainerId,
    );
  }

  void handleAuthChanged(String? trainerId) {
    if (_currentTrainerId == trainerId) return;
    _currentTrainerId = trainerId;
    if (trainerId == null) {
      state = CourseListState();
      return;
    }
    state = CourseListState(ownerTrainerId: trainerId);
    Future.microtask(ensureLoaded);
  }
}

final assignableCourseListProvider =
    StateNotifierProvider<AssignableCourseListNotifier, CourseListState>((ref) {
  final notifier = AssignableCourseListNotifier(ref);
  notifier.handleAuthChanged(ref.read(trainerAuthProvider).trainer?.trainerId);
  ref.listen<TrainerAuthState>(trainerAuthProvider, (previous, next) {
    notifier.handleAuthChanged(next.trainer?.trainerId);
  });
  return notifier;
});

// Active selections & current tab
final selectedFileProvider = StateProvider<PDFFile?>((ref) => null);
final selectedCourseProvider = StateProvider<Course?>((ref) => null);
final currentTabProvider =
    StateProvider<int>((ref) => 0); // 0 = Documents, 1 = Courses
