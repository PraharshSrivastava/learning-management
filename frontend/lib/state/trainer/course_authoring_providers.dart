part of '../trainer_providers.dart';

enum GenerationStatus { idle, generating, success, error }

class CourseGenerationState {
  final GenerationStatus status;
  final String? error;

  CourseGenerationState({required this.status, this.error});
}

class CourseGenerationNotifier extends StateNotifier<CourseGenerationState> {
  CourseGenerationNotifier()
      : super(CourseGenerationState(status: GenerationStatus.idle));

  Future<void> generateCourse(String fileName, WidgetRef ref) async {
    state = CourseGenerationState(status: GenerationStatus.generating);
    ref.read(selectedCourseProvider.notifier).state = null;
    ref.read(currentTabProvider.notifier).state = 1;
    try {
      final response = await http.post(
        Uri.parse(AppConstants.generateCourseEndpoint),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
        body: jsonEncode({'file_name': fileName}),
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final newCourse = Course.fromJson(decoded);
        ref.read(courseListProvider.notifier).upsertCourse(newCourse, select: true);
        state = CourseGenerationState(status: GenerationStatus.success);
      } else {
        final errorMsg = _responseErrorDetail(
          response,
          fallback: 'Course outline extraction failed.',
        );
        state = CourseGenerationState(
            status: GenerationStatus.error, error: errorMsg.toString());
      }
    } catch (e) {
      state = CourseGenerationState(
          status: GenerationStatus.error, error: e.toString());
    }
  }

  void reset() {
    state = CourseGenerationState(status: GenerationStatus.idle);
  }
}

final courseGenerationProvider =
    StateNotifierProvider<CourseGenerationNotifier, CourseGenerationState>(
        (ref) {
  return CourseGenerationNotifier();
});

// Course manual update state
class CourseUpdateState {
  final bool isUpdating;
  final String? error;

  CourseUpdateState({this.isUpdating = false, this.error});
}

class CourseUpdateNotifier extends StateNotifier<CourseUpdateState> {
  CourseUpdateNotifier() : super(CourseUpdateState());

  Future<bool> updateCourse(
      String id, Map<String, dynamic> updatedFields, WidgetRef ref) async {
    state = CourseUpdateState(isUpdating: true);
    try {
      final response = await http.put(
        Uri.parse(AppConstants.updateCourseEndpoint(id)),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
        body: jsonEncode(updatedFields),
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        ref.read(courseListProvider.notifier).upsertCourse(updatedCourse, select: true);
        ref
            .read(assignableCourseListProvider.notifier)
            .syncFromCourseList(ref.read(courseListProvider).courses);
        state = CourseUpdateState(isUpdating: false);
        return true;
      } else {
        final errorMsg = _responseErrorDetail(
          response,
          fallback: 'Failed to update course blueprint.',
        );
        state =
            CourseUpdateState(isUpdating: false, error: errorMsg.toString());
        return false;
      }
    } catch (e) {
      state = CourseUpdateState(isUpdating: false, error: e.toString());
      return false;
    }
  }

  Future<bool> saveModuleQuiz(
    String courseId,
    int moduleNumber,
    List<Map<String, dynamic>> questions,
    WidgetRef ref,
  ) async {
    state = CourseUpdateState(isUpdating: true);
    try {
      final response = await http.put(
        Uri.parse(AppConstants.moduleQuizEndpoint(courseId, moduleNumber)),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
        body: jsonEncode({'questions': questions}),
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        ref.read(courseListProvider.notifier).upsertCourse(updatedCourse, select: true);
        ref
            .read(assignableCourseListProvider.notifier)
            .syncFromCourseList(ref.read(courseListProvider).courses);
        state = CourseUpdateState(isUpdating: false);
        return true;
      } else {
        final errorMsg = _responseErrorDetail(
          response,
          fallback: 'Failed to save module quiz.',
        );
        state =
            CourseUpdateState(isUpdating: false, error: errorMsg.toString());
        return false;
      }
    } catch (e) {
      state = CourseUpdateState(isUpdating: false, error: e.toString());
      return false;
    }
  }
}

final courseUpdateProvider =
    StateNotifierProvider<CourseUpdateNotifier, CourseUpdateState>((ref) {
  return CourseUpdateNotifier();
});

String _responseErrorDetail(http.Response response, {required String fallback}) {
  try {
    final decoded = jsonDecode(response.body);
    if (decoded is Map<String, dynamic>) {
      final detail = decoded['detail'];
      if (detail != null && detail.toString().trim().isNotEmpty) {
        return detail.toString();
      }
    }
  } catch (_) {
    // Some framework errors are plain text, not JSON.
  }
  return '$fallback Server returned ${response.statusCode}.';
}
