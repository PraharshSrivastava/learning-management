part of '../trainer_preview_providers.dart';

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
    try {
      final response = await http.post(
        Uri.parse(AppConstants.generateCourseEndpoint),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'file_name': fileName}),
      );
      if (response.statusCode == 200) {
        state = CourseGenerationState(status: GenerationStatus.success);
        await ref.read(courseListProvider.notifier).fetchCourses();
        final decoded = jsonDecode(response.body);
        final newCourse = Course.fromJson(decoded);
        ref.read(selectedCourseProvider.notifier).state = newCourse;
        ref.read(currentTabProvider.notifier).state = 1;
      } else {
        final errorMsg = jsonDecode(response.body)['detail'] ??
            'Course outline extraction failed.';
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
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(updatedFields),
      );
      if (response.statusCode == 200) {
        state = CourseUpdateState(isUpdating: false);
        await ref.read(courseListProvider.notifier).fetchCourses();
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        ref.read(selectedCourseProvider.notifier).state = updatedCourse;
        return true;
      } else {
        final errorMsg = jsonDecode(response.body)['detail'] ??
            'Failed to update course blueprint.';
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
