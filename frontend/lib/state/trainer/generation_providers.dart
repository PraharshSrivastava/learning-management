part of '../trainer_providers.dart';

enum QuizGenStatus { idle, generating, success, error }

class QuizGenerationState {
  final QuizGenStatus status;
  final String? error;

  QuizGenerationState({required this.status, this.error});
}

class QuizGenerationNotifier extends StateNotifier<QuizGenerationState> {
  QuizGenerationNotifier()
      : super(QuizGenerationState(status: QuizGenStatus.idle));

  Future<void> generateQuiz(String courseId, WidgetRef ref) async {
    state = QuizGenerationState(status: QuizGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse(
            '${AppConstants.apiBaseUrl}/api/courses/$courseId/generate-quiz'),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        ref.read(courseListProvider.notifier).upsertCourse(updatedCourse, select: true);
        ref
            .read(assignableCourseListProvider.notifier)
            .syncFromCourseList(ref.read(courseListProvider).courses);
        state = QuizGenerationState(status: QuizGenStatus.success);
      } else {
        final errorMsg =
            jsonDecode(response.body)['detail'] ?? 'Quiz generation failed.';
        state = QuizGenerationState(
            status: QuizGenStatus.error, error: errorMsg.toString());
      }
    } catch (e) {
      state =
          QuizGenerationState(status: QuizGenStatus.error, error: e.toString());
    }
  }

  void reset() {
    state = QuizGenerationState(status: QuizGenStatus.idle);
  }
}

final quizGenerationProvider =
    StateNotifierProvider<QuizGenerationNotifier, QuizGenerationState>((ref) {
  return QuizGenerationNotifier();
});

// Slide generation state
enum SlideGenStatus { idle, generating, success, error }

class SlideGenerationState {
  final SlideGenStatus status;
  final String? error;

  SlideGenerationState({required this.status, this.error});
}

class SlideGenerationNotifier extends StateNotifier<SlideGenerationState> {
  SlideGenerationNotifier()
      : super(SlideGenerationState(status: SlideGenStatus.idle));

  Future<bool> generateSlides(String courseId, WidgetRef ref) async {
    state = SlideGenerationState(status: SlideGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.generateSlidesEndpoint(courseId)),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        ref.read(courseListProvider.notifier).upsertCourse(updatedCourse, select: true);
        ref
            .read(assignableCourseListProvider.notifier)
            .syncFromCourseList(ref.read(courseListProvider).courses);
        state = SlideGenerationState(status: SlideGenStatus.success);
        return true;
      } else {
        final errorMsg =
            jsonDecode(response.body)['detail'] ?? 'Slide generation failed.';
        state = SlideGenerationState(
            status: SlideGenStatus.error, error: errorMsg.toString());
        return false;
      }
    } catch (e) {
      state = SlideGenerationState(
          status: SlideGenStatus.error, error: e.toString());
      return false;
    }
  }

  void reset() {
    state = SlideGenerationState(status: SlideGenStatus.idle);
  }
}

final slideGenerationProvider =
    StateNotifierProvider<SlideGenerationNotifier, SlideGenerationState>((ref) {
  return SlideGenerationNotifier();
});

// Script generation state
enum ScriptGenStatus { idle, generating, success, error }

class ScriptGenerationState {
  final ScriptGenStatus status;
  final String? error;

  ScriptGenerationState({required this.status, this.error});
}

class ScriptGenerationNotifier extends StateNotifier<ScriptGenerationState> {
  ScriptGenerationNotifier()
      : super(ScriptGenerationState(status: ScriptGenStatus.idle));

  Future<bool> generateScripts(String courseId, WidgetRef ref) async {
    state = ScriptGenerationState(status: ScriptGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.generateScriptsEndpoint(courseId)),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        ref.read(courseListProvider.notifier).upsertCourse(updatedCourse, select: true);
        ref
            .read(assignableCourseListProvider.notifier)
            .syncFromCourseList(ref.read(courseListProvider).courses);
        state = ScriptGenerationState(status: ScriptGenStatus.success);
        return true;
      } else {
        final errorMsg =
            jsonDecode(response.body)['detail'] ?? 'Script generation failed.';
        state = ScriptGenerationState(
            status: ScriptGenStatus.error, error: errorMsg.toString());
        return false;
      }
    } catch (e) {
      state = ScriptGenerationState(
          status: ScriptGenStatus.error, error: e.toString());
      return false;
    }
  }

  void reset() {
    state = ScriptGenerationState(status: ScriptGenStatus.idle);
  }
}

final scriptGenerationProvider =
    StateNotifierProvider<ScriptGenerationNotifier, ScriptGenerationState>(
        (ref) {
  return ScriptGenerationNotifier();
});

final activeSlideIndexProvider = StateProvider<int>((ref) => 0);

Future<Course?> _refreshSelectedCourse(String courseId, WidgetRef ref) async {
  final updatedCourse =
      await ref.read(courseListProvider.notifier).refreshCourseDetail(courseId);
  ref
      .read(assignableCourseListProvider.notifier)
      .syncFromCourseList(ref.read(courseListProvider).courses);
  return updatedCourse;
}

// Video generation state
enum VideoGenStatus { idle, generating, success, error }

class VideoGenerationState {
  final VideoGenStatus status;
  final String? error;
  final String? videoUrl;

  VideoGenerationState({required this.status, this.error, this.videoUrl});
}

class VideoGenerationNotifier extends StateNotifier<VideoGenerationState> {
  VideoGenerationNotifier()
      : super(VideoGenerationState(status: VideoGenStatus.idle));

  Future<bool> generateVideo(
      String courseId, int moduleNumber, WidgetRef ref) async {
    state = VideoGenerationState(status: VideoGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse(
            '${AppConstants.apiBaseUrl}/api/courses/$courseId/modules/$moduleNumber/generate-video'),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);

        final relativeUrl =
            updatedCourse.modules[moduleNumber - 1].videoPath ?? '';
        final absoluteUrl = relativeUrl.isNotEmpty
            ? '${AppConstants.apiBaseUrl}/$relativeUrl'
            : null;

        state = VideoGenerationState(
            status: VideoGenStatus.success, videoUrl: absoluteUrl);
        ref.read(courseListProvider.notifier).upsertCourse(updatedCourse, select: true);
        ref
            .read(assignableCourseListProvider.notifier)
            .syncFromCourseList(ref.read(courseListProvider).courses);
        return true;
      } else {
        final errorMsg =
            jsonDecode(response.body)['detail'] ?? 'Video generation failed.';
        state = VideoGenerationState(
            status: VideoGenStatus.error, error: errorMsg.toString());
        return false;
      }
    } catch (e) {
      state = VideoGenerationState(
          status: VideoGenStatus.error, error: e.toString());
      return false;
    }
  }

  void reset() {
    state = VideoGenerationState(status: VideoGenStatus.idle);
  }
}

final videoGenerationProvider =
    StateNotifierProvider<VideoGenerationNotifier, VideoGenerationState>((ref) {
  return VideoGenerationNotifier();
});

// Full Course Generation State
enum FullCourseGenStatus { idle, generating, success, error }

class FullCourseGenerationState {
  final FullCourseGenStatus status;
  final String? error;

  FullCourseGenerationState({required this.status, this.error});
}

class FullCourseGenerationNotifier
    extends StateNotifier<FullCourseGenerationState> {
  FullCourseGenerationNotifier()
      : super(FullCourseGenerationState(status: FullCourseGenStatus.idle));

  Future<void> generateFullCourse(String courseId, WidgetRef ref) async {
    state = FullCourseGenerationState(status: FullCourseGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.generationJobEndpoint(courseId)),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
      );
      if (response.statusCode == 202 || response.statusCode == 200) {
        final job = GenerationJob.fromJson(jsonDecode(response.body));
        await _pollFullCourseJob(job.id, courseId, ref);
      } else {
        final errorMsg = _generationErrorDetail(
          response,
          fallback: 'Full course generation failed.',
        );
        state = FullCourseGenerationState(
            status: FullCourseGenStatus.error, error: errorMsg.toString());
        final failedCourse = await _refreshSelectedCourse(courseId, ref);
        if (failedCourse != null) {
          ref.read(currentTabProvider.notifier).state = 1;
        }
      }
    } catch (e) {
      state = FullCourseGenerationState(
          status: FullCourseGenStatus.error, error: e.toString());
      final failedCourse = await _refreshSelectedCourse(courseId, ref);
      if (failedCourse != null) {
        ref.read(currentTabProvider.notifier).state = 1;
      }
    }
  }

  Future<void> continueFromCheckpoint(String courseId, WidgetRef ref) async {
    state = FullCourseGenerationState(status: FullCourseGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.continueGenerationEndpoint(courseId)),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
      );
      if (response.statusCode == 200) {
        final updatedCourse = Course.fromJson(jsonDecode(response.body));
        final isFullyGenerated = updatedCourse.modules.isNotEmpty &&
            updatedCourse.thumbnailPath.isNotEmpty &&
            updatedCourse.modules.every((module) =>
                module.videoPath != null &&
                module.videoPath!.isNotEmpty &&
                module.quiz != null &&
                (((module.quiz!['questions'] as List?)?.isNotEmpty == true) ||
                    module.numQuestions <= 0));
        ref.read(courseListProvider.notifier).upsertCourse(updatedCourse, select: true);
        ref
            .read(assignableCourseListProvider.notifier)
            .syncFromCourseList(ref.read(courseListProvider).courses);
        ref.read(currentTabProvider.notifier).state = isFullyGenerated ? 2 : 1;
        state = FullCourseGenerationState(status: FullCourseGenStatus.success);
      } else {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        state = FullCourseGenerationState(
          status: FullCourseGenStatus.error,
          error: body['detail']?.toString() ?? 'Could not continue generation.',
        );
        final failedCourse = await _refreshSelectedCourse(courseId, ref);
        if (failedCourse != null) {
          ref.read(currentTabProvider.notifier).state = 1;
        }
      }
    } catch (e) {
      state = FullCourseGenerationState(
          status: FullCourseGenStatus.error, error: e.toString());
      final failedCourse = await _refreshSelectedCourse(courseId, ref);
      if (failedCourse != null) {
        ref.read(currentTabProvider.notifier).state = 1;
      }
    }
  }

  void reset() {
    state = FullCourseGenerationState(status: FullCourseGenStatus.idle);
  }

  Future<void> _pollFullCourseJob(
    String jobId,
    String courseId,
    WidgetRef ref,
  ) async {
    while (true) {
      await Future.delayed(const Duration(seconds: 4));
      final response = await http.get(
        Uri.parse(AppConstants.generationJobStatusEndpoint(jobId)),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode != 200) {
        final errorMsg = _generationErrorDetail(
          response,
          fallback: 'Could not check generation progress.',
        );
        state = FullCourseGenerationState(
          status: FullCourseGenStatus.error,
          error: errorMsg,
        );
        await _refreshSelectedCourse(courseId, ref);
        return;
      }
      final job = GenerationJob.fromJson(jsonDecode(response.body));
      await _refreshSelectedCourse(courseId, ref);
      if (!job.isComplete) continue;
      if (job.status == 'completed') {
        state = FullCourseGenerationState(status: FullCourseGenStatus.success);
        ref.read(currentTabProvider.notifier).state = 2;
        return;
      }
      state = FullCourseGenerationState(
        status: FullCourseGenStatus.error,
        error: job.error ?? 'Full course generation failed.',
      );
      ref.read(currentTabProvider.notifier).state = 1;
      return;
    }
  }
}

final fullCourseGenerationProvider = StateNotifierProvider<
    FullCourseGenerationNotifier, FullCourseGenerationState>((ref) {
  return FullCourseGenerationNotifier();
});

String _generationErrorDetail(http.Response response, {required String fallback}) {
  try {
    final decoded = jsonDecode(response.body);
    if (decoded is Map<String, dynamic>) {
      final detail = decoded['detail'];
      if (detail is Map<String, dynamic>) {
        final message = detail['message'];
        if (message != null && message.toString().trim().isNotEmpty) {
          return message.toString();
        }
      }
      if (detail != null && detail.toString().trim().isNotEmpty) {
        return detail.toString();
      }
    }
  } catch (_) {
    // Plain-text framework errors are possible here.
  }
  return '$fallback Server returned ${response.statusCode}.';
}
