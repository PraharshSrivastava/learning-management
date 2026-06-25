import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../constants.dart';
import '../models/models.dart';

// State for files list
class FileListState {
  final List<PDFFile> files;
  final bool isLoading;
  final String? error;

  FileListState({
    this.files = const [],
    this.isLoading = false,
    this.error,
  });

  FileListState copyWith({
    List<PDFFile>? files,
    bool? isLoading,
    String? error,
  }) {
    return FileListState(
      files: files ?? this.files,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

class FileListNotifier extends StateNotifier<FileListState> {
  FileListNotifier() : super(FileListState()) {
    fetchFiles();
  }

  Future<void> fetchFiles() async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await http.get(Uri.parse(AppConstants.listFilesEndpoint));
      if (response.statusCode == 200) {
        final List<dynamic> decoded = jsonDecode(response.body);
        final List<PDFFile> fileList = decoded.map((item) => PDFFile.fromJson(item)).toList();
        state = FileListState(files: fileList, isLoading: false);
      } else {
        state = FileListState(files: [], isLoading: false, error: 'Server returned ${response.statusCode}');
      }
    } catch (e) {
      state = FileListState(files: [], isLoading: false, error: e.toString());
    }
  }
}

final fileListProvider = StateNotifierProvider<FileListNotifier, FileListState>((ref) {
  return FileListNotifier();
});

// State for generated courses list
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
  CourseListNotifier() : super(CourseListState()) {
    fetchCourses();
  }

  Future<void> fetchCourses() async {
    state = CourseListState(courses: state.courses, isLoading: true);
    try {
      final response = await http.get(Uri.parse(AppConstants.listCoursesEndpoint));
      if (response.statusCode == 200) {
        final List<dynamic> decoded = jsonDecode(response.body);
        final List<Course> courseList = decoded.map((item) => Course.fromJson(item)).toList();
        state = CourseListState(courses: courseList, isLoading: false);
      } else {
        state = CourseListState(courses: state.courses, isLoading: false, error: 'Server returned ${response.statusCode}');
      }
    } catch (e) {
      state = CourseListState(courses: state.courses, isLoading: false, error: e.toString());
    }
  }
}

final courseListProvider = StateNotifierProvider<CourseListNotifier, CourseListState>((ref) {
  return CourseListNotifier();
});

// Active selections & current tab
final selectedFileProvider = StateProvider<PDFFile?>((ref) => null);
final selectedCourseProvider = StateProvider<Course?>((ref) => null);
final currentTabProvider = StateProvider<int>((ref) => 0); // 0 = Documents, 1 = Courses

// Upload progress state
enum UploadStatus { idle, uploading, success, error }

class UploadProgressState {
  final UploadStatus status;
  final String? message;

  UploadProgressState({required this.status, this.message});
}

class UploadProgressNotifier extends StateNotifier<UploadProgressState> {
  UploadProgressNotifier() : super(UploadProgressState(status: UploadStatus.idle));

  Future<void> uploadFile(PlatformFile file, WidgetRef ref) async {
    state = UploadProgressState(status: UploadStatus.uploading);
    try {
      final bytes = file.bytes;
      if (bytes == null) {
        state = UploadProgressState(status: UploadStatus.error, message: 'Could not read file data.');
        return;
      }

      final request = http.MultipartRequest('POST', Uri.parse(AppConstants.uploadEndpoint));
      final multipartFile = http.MultipartFile.fromBytes('file', bytes, filename: file.name);
      request.files.add(multipartFile);

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        state = UploadProgressState(status: UploadStatus.success, message: 'Uploaded successfully!');
        ref.read(fileListProvider.notifier).fetchFiles();
      } else {
        final errorMsg = jsonDecode(response.body)['detail'] ?? 'Upload failed.';
        state = UploadProgressState(status: UploadStatus.error, message: errorMsg.toString());
      }
    } catch (e) {
      state = UploadProgressState(status: UploadStatus.error, message: 'Upload error: ${e.toString()}');
    }
  }
}

final uploadProgressProvider = StateNotifierProvider<UploadProgressNotifier, UploadProgressState>((ref) {
  return UploadProgressNotifier();
});

// Course generation state
enum GenerationStatus { idle, generating, success, error }

class CourseGenerationState {
  final GenerationStatus status;
  final String? error;

  CourseGenerationState({required this.status, this.error});
}

class CourseGenerationNotifier extends StateNotifier<CourseGenerationState> {
  CourseGenerationNotifier() : super(CourseGenerationState(status: GenerationStatus.idle));

  Future<void> generateCourse(String filename, WidgetRef ref) async {
    state = CourseGenerationState(status: GenerationStatus.generating);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.generateCourseEndpoint),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'filename': filename}),
      );
      if (response.statusCode == 200) {
        state = CourseGenerationState(status: GenerationStatus.success);
        await ref.read(courseListProvider.notifier).fetchCourses();
        final decoded = jsonDecode(response.body);
        final newCourse = Course.fromJson(decoded);
        ref.read(selectedCourseProvider.notifier).state = newCourse;
        ref.read(currentTabProvider.notifier).state = 1;
      } else {
        final errorMsg = jsonDecode(response.body)['detail'] ?? 'Course outline extraction failed.';
        state = CourseGenerationState(status: GenerationStatus.error, error: errorMsg.toString());
      }
    } catch (e) {
      state = CourseGenerationState(status: GenerationStatus.error, error: e.toString());
    }
  }

  void reset() {
    state = CourseGenerationState(status: GenerationStatus.idle);
  }
}

final courseGenerationProvider = StateNotifierProvider<CourseGenerationNotifier, CourseGenerationState>((ref) {
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

  Future<bool> updateCourse(String id, Map<String, dynamic> updatedFields, WidgetRef ref) async {
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
        final errorMsg = jsonDecode(response.body)['detail'] ?? 'Failed to update course blueprint.';
        state = CourseUpdateState(isUpdating: false, error: errorMsg.toString());
        return false;
      }
    } catch (e) {
      state = CourseUpdateState(isUpdating: false, error: e.toString());
      return false;
    }
  }
}

final courseUpdateProvider = StateNotifierProvider<CourseUpdateNotifier, CourseUpdateState>((ref) {
  return CourseUpdateNotifier();
});

// Lesson generation state
enum LessonGenStatus { idle, generating, success, error }

class LessonGenerationState {
  final LessonGenStatus status;
  final String? error;

  LessonGenerationState({required this.status, this.error});
}

class LessonGenerationNotifier extends StateNotifier<LessonGenerationState> {
  LessonGenerationNotifier() : super(LessonGenerationState(status: LessonGenStatus.idle));

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
        ref.read(currentTabProvider.notifier).state = 2; // Navigate to Lessons tab
      } else {
        final errorMsg = jsonDecode(response.body)['detail'] ?? 'Lesson generation failed.';
        state = LessonGenerationState(status: LessonGenStatus.error, error: errorMsg.toString());
      }
    } catch (e) {
      state = LessonGenerationState(status: LessonGenStatus.error, error: e.toString());
    }
  }

  void reset() {
    state = LessonGenerationState(status: LessonGenStatus.idle);
  }
}

final lessonGenerationProvider = StateNotifierProvider<LessonGenerationNotifier, LessonGenerationState>((ref) {
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
  BulletRefinementNotifier() : super(BulletRefinementState(status: BulletRefineStatus.idle));

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
        final errorMsg = jsonDecode(response.body)['detail'] ?? 'Bullet refinement failed.';
        state = BulletRefinementState(status: BulletRefineStatus.error, error: errorMsg.toString());
      }
    } catch (e) {
      state = BulletRefinementState(status: BulletRefineStatus.error, error: e.toString());
    }
  }

  void reset() {
    state = BulletRefinementState(status: BulletRefineStatus.idle);
  }
}

final bulletRefinementProvider = StateNotifierProvider<BulletRefinementNotifier, BulletRefinementState>((ref) {
  return BulletRefinementNotifier();
});



// Quiz generation state
enum QuizGenStatus { idle, generating, success, error }

class QuizGenerationState {
  final QuizGenStatus status;
  final String? error;

  QuizGenerationState({required this.status, this.error});
}

class QuizGenerationNotifier extends StateNotifier<QuizGenerationState> {
  QuizGenerationNotifier() : super(QuizGenerationState(status: QuizGenStatus.idle));

  Future<void> generateQuiz(String courseId, WidgetRef ref) async {
    state = QuizGenerationState(status: QuizGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse('${AppConstants.apiBaseUrl}/api/courses/$courseId/generate-quiz'),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        state = QuizGenerationState(status: QuizGenStatus.success);
        await ref.read(courseListProvider.notifier).fetchCourses();
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        ref.read(selectedCourseProvider.notifier).state = updatedCourse;
        ref.read(currentTabProvider.notifier).state = 5; // Navigate to Quiz tab
      } else {
        final errorMsg = jsonDecode(response.body)['detail'] ?? 'Quiz generation failed.';
        state = QuizGenerationState(status: QuizGenStatus.error, error: errorMsg.toString());
      }
    } catch (e) {
      state = QuizGenerationState(status: QuizGenStatus.error, error: e.toString());
    }
  }

  void reset() {
    state = QuizGenerationState(status: QuizGenStatus.idle);
  }
}

final quizGenerationProvider = StateNotifierProvider<QuizGenerationNotifier, QuizGenerationState>((ref) {
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
  SlideGenerationNotifier() : super(SlideGenerationState(status: SlideGenStatus.idle));

  Future<bool> generateSlides(String courseId, WidgetRef ref) async {
    state = SlideGenerationState(status: SlideGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.generateSlidesEndpoint(courseId)),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        state = SlideGenerationState(status: SlideGenStatus.success);
        await ref.read(courseListProvider.notifier).fetchCourses();
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        ref.read(selectedCourseProvider.notifier).state = updatedCourse;
        return true;
      } else {
        final errorMsg = jsonDecode(response.body)['detail'] ?? 'Slide generation failed.';
        state = SlideGenerationState(status: SlideGenStatus.error, error: errorMsg.toString());
        return false;
      }
    } catch (e) {
      state = SlideGenerationState(status: SlideGenStatus.error, error: e.toString());
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
  ScriptGenerationNotifier() : super(ScriptGenerationState(status: ScriptGenStatus.idle));

  Future<bool> generateScripts(String courseId, WidgetRef ref) async {
    state = ScriptGenerationState(status: ScriptGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.generateScriptsEndpoint(courseId)),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        state = ScriptGenerationState(status: ScriptGenStatus.success);
        await ref.read(courseListProvider.notifier).fetchCourses();
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        ref.read(selectedCourseProvider.notifier).state = updatedCourse;
        return true;
      } else {
        final errorMsg = jsonDecode(response.body)['detail'] ?? 'Script generation failed.';
        state = ScriptGenerationState(status: ScriptGenStatus.error, error: errorMsg.toString());
        return false;
      }
    } catch (e) {
      state = ScriptGenerationState(status: ScriptGenStatus.error, error: e.toString());
      return false;
    }
  }

  void reset() {
    state = ScriptGenerationState(status: ScriptGenStatus.idle);
  }
}

final scriptGenerationProvider =
    StateNotifierProvider<ScriptGenerationNotifier, ScriptGenerationState>((ref) {
  return ScriptGenerationNotifier();
});

final activeSlideIndexProvider = StateProvider<int>((ref) => 0);

// Video generation state
enum VideoGenStatus { idle, generating, success, error }

class VideoGenerationState {
  final VideoGenStatus status;
  final String? error;
  final String? videoUrl;

  VideoGenerationState({required this.status, this.error, this.videoUrl});
}

class VideoGenerationNotifier extends StateNotifier<VideoGenerationState> {
  VideoGenerationNotifier() : super(VideoGenerationState(status: VideoGenStatus.idle));

  Future<bool> generateVideo(String courseId, int moduleNumber, WidgetRef ref) async {
    state = VideoGenerationState(status: VideoGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse('${AppConstants.apiBaseUrl}/api/courses/$courseId/modules/$moduleNumber/generate-video'),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final updatedCourse = Course.fromJson(decoded);
        
        final relativeUrl = updatedCourse.modules[moduleNumber - 1].videoPath ?? '';
        final absoluteUrl = relativeUrl.isNotEmpty ? '${AppConstants.apiBaseUrl}/$relativeUrl' : null;
        
        state = VideoGenerationState(status: VideoGenStatus.success, videoUrl: absoluteUrl);
        await ref.read(courseListProvider.notifier).fetchCourses();
        ref.read(selectedCourseProvider.notifier).state = updatedCourse;
        return true;
      } else {
        final errorMsg = jsonDecode(response.body)['detail'] ?? 'Video generation failed.';
        state = VideoGenerationState(status: VideoGenStatus.error, error: errorMsg.toString());
        return false;
      }
    } catch (e) {
      state = VideoGenerationState(status: VideoGenStatus.error, error: e.toString());
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
