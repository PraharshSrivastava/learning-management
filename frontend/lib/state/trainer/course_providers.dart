part of '../trainer_providers.dart';

class CourseListState {
  final List<Course> courses;
  final bool isLoading;
  final String? error;

  CourseListState({
    this.courses = const [],
    this.isLoading = false,
    this.error,
  });
}

class CourseListNotifier extends StateNotifier<CourseListState> {
  final Ref ref;

  CourseListNotifier(this.ref) : super(CourseListState()) {
    if (ref.read(trainerAuthProvider).isAuthenticated) {
      fetchCourses();
    }
  }

  Future<void> fetchCourses() async {
    state = CourseListState(courses: state.courses, isLoading: true);
    try {
      final response = await http.get(
        Uri.parse(AppConstants.listCoursesEndpoint),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode == 200) {
        final List<dynamic> decoded = jsonDecode(response.body);
        final List<Course> courseList =
            decoded.map((item) => Course.fromJson(item)).toList();
        state = CourseListState(courses: courseList, isLoading: false);
      } else {
        state = CourseListState(
            courses: state.courses,
            isLoading: false,
            error: 'Server returned ${response.statusCode}');
      }
    } catch (e) {
      state = CourseListState(
          courses: state.courses, isLoading: false, error: e.toString());
    }
  }
}

final courseListProvider =
    StateNotifierProvider<CourseListNotifier, CourseListState>((ref) {
  return CourseListNotifier(ref);
});

class AssignableCourseListNotifier extends StateNotifier<CourseListState> {
  final Ref ref;

  AssignableCourseListNotifier(this.ref) : super(CourseListState()) {
    if (ref.read(trainerAuthProvider).isAuthenticated) {
      fetchCourses();
    }
  }

  Future<void> fetchCourses() async {
    state = CourseListState(courses: state.courses, isLoading: true);
    try {
      final response = await http.get(
        Uri.parse(AppConstants.assignableCoursesEndpoint),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode == 200) {
        final List<dynamic> decoded = jsonDecode(response.body);
        final courseList =
            decoded.map((item) => Course.fromJson(item)).toList();
        state = CourseListState(courses: courseList, isLoading: false);
      } else {
        state = CourseListState(
          courses: state.courses,
          isLoading: false,
          error: 'Server returned ${response.statusCode}',
        );
      }
    } catch (e) {
      state = CourseListState(
          courses: state.courses, isLoading: false, error: e.toString());
    }
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
