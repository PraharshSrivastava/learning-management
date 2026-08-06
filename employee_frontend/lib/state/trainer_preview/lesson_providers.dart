part of '../trainer_preview_providers.dart';

enum LessonGenStatus { idle, generating, success, error }

class LessonGenerationState {
  final LessonGenStatus status;
  final String? error;

  LessonGenerationState({required this.status, this.error});
}

class LessonGenerationNotifier extends StateNotifier<LessonGenerationState> {
  LessonGenerationNotifier()
      : super(LessonGenerationState(status: LessonGenStatus.idle));

  Future<void> generateLessons(String courseId, WidgetRef ref) async {
    state = LessonGenerationState(status: LessonGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.generateLessonsEndpoint(courseId)),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        state = LessonGenerationState(status: LessonGenStatus.success);
        await ref.read(courseListProvider.notifier).fetchCourses();
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        ref.read(selectedCourseProvider.notifier).state = updatedCourse;
        ref.read(currentTabProvider.notifier).state =
            2; // Navigate to Lessons tab
      } else {
        final errorMsg =
            jsonDecode(response.body)['detail'] ?? 'Lesson generation failed.';
        state = LessonGenerationState(
            status: LessonGenStatus.error, error: errorMsg.toString());
      }
    } catch (e) {
      state = LessonGenerationState(
          status: LessonGenStatus.error, error: e.toString());
    }
  }

  void reset() {
    state = LessonGenerationState(status: LessonGenStatus.idle);
  }
}

final lessonGenerationProvider =
    StateNotifierProvider<LessonGenerationNotifier, LessonGenerationState>(
        (ref) {
  return LessonGenerationNotifier();
});

// Bullet refinement state
enum BulletRefineStatus { idle, refining, success, error }

class BulletRefinementState {
  final BulletRefineStatus status;
  final String? error;

  BulletRefinementState({required this.status, this.error});
}

class BulletRefinementNotifier extends StateNotifier<BulletRefinementState> {
  BulletRefinementNotifier()
      : super(BulletRefinementState(status: BulletRefineStatus.idle));

  Future<void> refineBullets(String courseId, WidgetRef ref) async {
    state = BulletRefinementState(status: BulletRefineStatus.refining);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.refineBulletsEndpoint(courseId)),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        state = BulletRefinementState(status: BulletRefineStatus.success);
        await ref.read(courseListProvider.notifier).fetchCourses();
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        ref.read(selectedCourseProvider.notifier).state = updatedCourse;
      } else {
        final errorMsg =
            jsonDecode(response.body)['detail'] ?? 'Bullet refinement failed.';
        state = BulletRefinementState(
            status: BulletRefineStatus.error, error: errorMsg.toString());
      }
    } catch (e) {
      state = BulletRefinementState(
          status: BulletRefineStatus.error, error: e.toString());
    }
  }

  void reset() {
    state = BulletRefinementState(status: BulletRefineStatus.idle);
  }
}

final bulletRefinementProvider =
    StateNotifierProvider<BulletRefinementNotifier, BulletRefinementState>(
        (ref) {
  return BulletRefinementNotifier();
});
