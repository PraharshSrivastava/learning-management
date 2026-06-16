import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:file_picker/file_picker.dart';
import 'package:http/http.dart' as http;

// Conditional imports for Web
import 'dart:html' as html;
import 'dart:ui_web' as ui_web;

import 'theme.dart';
import 'constants.dart';

void main() {
  runApp(
    const ProviderScope(
      child: LMSApp(),
    ),
  );
}

class LMSApp extends StatelessWidget {
  const LMSApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PhillipCapital LMS',
      theme: AppTheme.lightTheme,
      debugShowCheckedModeBanner: false,
      home: const DashboardPage(),
    );
  }
}

// --- RIVERPOD STATE MANAGEMENT ---

// Model for PDF File Metadata
class PDFFile {
  final String filename;
  final int size;
  final double created;

  PDFFile({
    required this.filename,
    required this.size,
    required this.created,
  });

  factory PDFFile.fromJson(Map<String, dynamic> json) {
    return PDFFile(
      filename: json['filename'] as String,
      size: json['size'] as int,
      created: (json['created'] as num).toDouble(),
    );
  }

  String get formattedSize {
    if (size < 1024) return '$size B';
    if (size < 1024 * 1024) return '${(size / 1024).toStringAsFixed(1)} KB';
    return '${(size / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  String get formattedDate {
    final dateTime = DateTime.fromMillisecondsSinceEpoch((created * 1000).toInt());
    return '${dateTime.day}/${dateTime.month}/${dateTime.year} ${dateTime.hour.toString().padLeft(2, '0')}:${dateTime.minute.toString().padLeft(2, '0')}';
  }
}

// ---------- Lessons Data Models ----------

class BulletPoint {
  final String text;
  BulletPoint({required this.text});

  factory BulletPoint.fromJson(Map<String, dynamic> json) =>
      BulletPoint(text: json['text']?.toString() ?? '');

  Map<String, dynamic> toJson() => {'text': text};
}

class SlideImage {
  final String imageId;
  final String caption;
  final String filePath;

  SlideImage({
    required this.imageId,
    required this.caption,
    required this.filePath,
  });

  factory SlideImage.fromJson(Map<String, dynamic> json) {
    return SlideImage(
      imageId: json['image_id']?.toString() ?? '',
      caption: json['caption']?.toString() ?? '',
      filePath: json['file_path']?.toString() ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'image_id': imageId,
    'caption': caption,
    'file_path': filePath,
  };
}

class CourseSlide {
  final int slideNumber;
  final String slideTitle;
  final List<BulletPoint> bullets;
  final String script;
  final List<SlideImage> images;

  CourseSlide({
    required this.slideNumber,
    required this.slideTitle,
    required this.bullets,
    required this.script,
    required this.images,
  });

  factory CourseSlide.fromJson(Map<String, dynamic> json) {
    return CourseSlide(
      slideNumber: (json['slide_number'] as num?)?.toInt() ?? 0,
      slideTitle: json['slide_title']?.toString() ?? '',
      bullets: (json['bullets'] as List? ?? [])
          .map((b) => BulletPoint.fromJson(b as Map<String, dynamic>))
          .toList(),
      script: json['script']?.toString() ?? '',
      images: (json['images'] as List? ?? [])
          .map((img) => SlideImage.fromJson(img as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
    'slide_number': slideNumber,
    'slide_title': slideTitle,
    'bullets': bullets.map((b) => b.toJson()).toList(),
    'script': script,
    'images': images.map((img) => img.toJson()).toList(),
  };
}

class CourseLesson {
  final int lessonNumber;
  final String lessonTitle;
  final List<CourseSlide> slides;

  CourseLesson({
    required this.lessonNumber,
    required this.lessonTitle,
    required this.slides,
  });

  factory CourseLesson.fromJson(Map<String, dynamic> json) {
    return CourseLesson(
      lessonNumber: (json['lesson_number'] as num?)?.toInt() ?? 0,
      lessonTitle: json['lesson_title']?.toString() ?? '',
      slides: (json['slides'] as List? ?? [])
          .map((s) => CourseSlide.fromJson(s as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
    'lesson_number': lessonNumber,
    'lesson_title': lessonTitle,
    'slides': slides.map((s) => s.toJson()).toList(),
  };
}

// ---------- Module Model ----------

// Model for a single Course Module
class CourseModule {
  final int moduleNumber;
  final String title;
  final String text;
  final String startLine;
  final String endLine;
  final List<CourseLesson> lessons;
  final int numQuestions;
  final Map<String, dynamic>? quiz;

  CourseModule({
    required this.moduleNumber,
    required this.title,
    required this.text,
    required this.startLine,
    required this.endLine,
    this.lessons = const [],
    this.numQuestions = 0,
    this.quiz,
  });

  factory CourseModule.fromJson(Map<String, dynamic> json) {
    return CourseModule(
      moduleNumber: (json['module_number'] as num?)?.toInt() ?? 0,
      title: json['title']?.toString() ?? '',
      text: json['text']?.toString() ?? '',
      startLine: json['start_line']?.toString() ?? '',
      endLine: json['end_line']?.toString() ?? '',
      lessons: (json['lessons'] as List? ?? [])
          .map((l) => CourseLesson.fromJson(l as Map<String, dynamic>))
          .toList(),
      numQuestions: (json['num_questions'] as num?)?.toInt() ?? 0,
      quiz: json['quiz'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() => {
    'module_number': moduleNumber,
    'title': title,
    'text': text,
    'start_line': startLine,
    'end_line': endLine,
    'lessons': lessons.map((l) => l.toJson()).toList(),
    'num_questions': numQuestions,
    'quiz': quiz,
  };
}

// Model for Generated Course Outline
class Course {
  final String id;
  final String courseName;
  final String courseDescription;
  final String courseObjective;
  final String courseDifficulty;
  final String language;
  final String targetAudience;
  final List<CourseModule> modules;
  final List<SlideImage> images; // Course-level extracted images
  final String sourceFile;
  final double createdAt;

  Course({
    required this.id,
    required this.courseName,
    required this.courseDescription,
    required this.courseObjective,
    required this.courseDifficulty,
    required this.language,
    required this.targetAudience,
    required this.modules,
    required this.images,
    required this.sourceFile,
    required this.createdAt,
  });

  factory Course.fromJson(Map<String, dynamic> json) {
    return Course(
      id: json['id'] as String,
      courseName: json['course_name'] as String,
      courseDescription: json['course_description'] as String,
      courseObjective: json['course_objective'] as String,
      courseDifficulty: json['course_difficulty'] as String,
      language: json['language'] as String,
      targetAudience: json['target_audience'] as String,
      modules: (json['modules'] as List).map((item) {
        if (item is Map<String, dynamic>) {
          return CourseModule.fromJson(item);
        }
        // Legacy string-only format fallback
        return CourseModule(
          moduleNumber: 0,
          title: item.toString(),
          text: '',
          startLine: '',
          endLine: '',
        );
      }).toList(),
      images: (json['images'] as List? ?? [])
          .map((img) => SlideImage.fromJson(img as Map<String, dynamic>))
          .toList(),
      sourceFile: json['source_file'] as String,
      createdAt: (json['created_at'] as num).toDouble(),
    );
  }
}

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

final lessonGenerationProvider =
    StateNotifierProvider<LessonGenerationNotifier, LessonGenerationState>((ref) {
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

final bulletRefinementProvider =
    StateNotifierProvider<BulletRefinementNotifier, BulletRefinementState>((ref) {
  return BulletRefinementNotifier();
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

  Future<void> generateSlides(String courseId, WidgetRef ref) async {
    state = SlideGenerationState(status: SlideGenStatus.generating);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.generateSlidesEndpoint(courseId)),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        state = SlideGenerationState(status: SlideGenStatus.success);
      } else {
        final errorMsg = jsonDecode(response.body)['detail'] ?? 'Slide generation failed.';
        state = SlideGenerationState(status: SlideGenStatus.error, error: errorMsg.toString());
      }
    } catch (e) {
      state = SlideGenerationState(status: SlideGenStatus.error, error: e.toString());
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

  Future<void> generateScripts(String courseId, WidgetRef ref) async {
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
      } else {
        final errorMsg = jsonDecode(response.body)['detail'] ?? 'Script generation failed.';
        state = ScriptGenerationState(status: ScriptGenStatus.error, error: errorMsg.toString());
      }
    } catch (e) {
      state = ScriptGenerationState(status: ScriptGenStatus.error, error: e.toString());
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

final quizGenerationProvider =
    StateNotifierProvider<QuizGenerationNotifier, QuizGenerationState>((ref) {
  return QuizGenerationNotifier();
});

// --- DASHBOARD UI ---

class DashboardPage extends ConsumerWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final activeTab = ref.watch(currentTabProvider);
    final selectedFile = ref.watch(selectedFileProvider);
    final selectedCourse = ref.watch(selectedCourseProvider);
    final isMobile = MediaQuery.of(context).size.width < 900;

    final generationState = ref.watch(courseGenerationProvider);
    final updateState = ref.watch(courseUpdateProvider);
    final lessonGenState = ref.watch(lessonGenerationProvider);

    return Stack(
      children: [
        Scaffold(
          backgroundColor: Colors.white,
          appBar: AppBar(
            title: Row(
              children: [
                Image.asset(
                  'assets/logos/Type=Primary.png',
                  height: 28,
                  errorBuilder: (context, error, stackTrace) {
                    return Text(
                      'PHILLIPCAPITAL',
                      style: GoogleFonts.inter(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                        letterSpacing: 1.5,
                      ),
                    );
                  },
                ),
                const SizedBox(width: 8),
                Container(
                  height: 20,
                  width: 1,
                  color: AppTheme.gray.withOpacity(0.5),
                ),
                const SizedBox(width: 12),
                _TabHeaderButton(
                  title: 'Documents',
                  isActive: activeTab == 0,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 0,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Courses',
                  isActive: activeTab == 1,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 1,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Lessons',
                  isActive: activeTab == 2,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 2,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Slides',
                  isActive: activeTab == 3,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 3,
                ),
                const SizedBox(width: 8),
                _TabHeaderButton(
                  title: 'Quiz',
                  isActive: activeTab == 4,
                  onTap: () => ref.read(currentTabProvider.notifier).state = 4,
                ),
              ],
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh, color: AppTheme.primaryBlue),
                onPressed: () {
                  ref.read(fileListProvider.notifier).fetchFiles();
                  ref.read(courseListProvider.notifier).fetchCourses();
                },
                tooltip: 'Refresh All Data',
              ),
              const SizedBox(width: 16),
            ],
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(1),
              child: Container(
                color: AppTheme.lightGray,
                height: 1,
              ),
            ),
          ),
          body: activeTab == 0
              ? _buildDocumentsPortal(context, ref, selectedFile, isMobile)
              : activeTab == 1
                  ? _buildCoursesPortal(context, ref, selectedCourse, isMobile)
                  : activeTab == 2
                      ? _buildLessonsPortal(context, ref, selectedCourse, isMobile)
                      : activeTab == 3
                          ? _buildSlidesPortal(context, ref, selectedCourse, isMobile)
                          : _buildQuizPortal(context, ref, selectedCourse, isMobile),
        ),
        
        if (generationState.status == GenerationStatus.generating)
          const _LoadingOverlay(message: 'Running modular extraction pipeline...\nAnalyzing document metadata & curriculum outline using Qwen3-8B...'),

        if (updateState.isUpdating)
          const _LoadingOverlay(message: 'Saving course blueprint modifications...'),

        if (lessonGenState.status == LessonGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating lessons for all modules...\n'
                'Step 1: LLM extracts lessons & slides per module.\n'
                'Step 2: Holistic bullet refinement across full course.\n'
                'This may take 4–6 minutes — please wait.',
          ),

        if (ref.watch(slideGenerationProvider).status == SlideGenStatus.generating)
          const _LoadingOverlay(message: 'Generating PowerPoint slides for all lessons...\nThis usually takes a few seconds.'),

        if (ref.watch(scriptGenerationProvider).status == ScriptGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating narration scripts for all modules sequentially...\n'
                'Calling LLM to write speaker notes for each slide.\n'
                'This may take 1–3 minutes — please wait.',
          ),

        if (ref.watch(quizGenerationProvider).status == QuizGenStatus.generating)
          const _LoadingOverlay(
            message: 'Generating module quizzes...\n'
                'Applying difficulty scaling and creating multiple choice questions...\n'
                'This may take 1–2 minutes — please wait.',
          ),
      ],
    );
  }

  Widget _buildLessonsPortal(BuildContext context, WidgetRef ref, Course? selectedCourse, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 300,
                child: CoursesSidebar(selectedCourse: selectedCourse),
              ),
            ),
            if (selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: LessonsView(course: selectedCourse),
              ),
          ],
        ),
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 380,
          child: Container(
            decoration: const BoxDecoration(
              border: Border(
                right: BorderSide(color: AppTheme.lightGray, width: 1),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: CoursesSidebar(selectedCourse: selectedCourse),
            ),
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: selectedCourse == null
                ? const _EmptyCourseView()
                : LessonsView(course: selectedCourse),
          ),
        ),
      ],
    );
  }

  Widget _buildQuizPortal(BuildContext context, WidgetRef ref, Course? selectedCourse, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 300,
                child: CoursesSidebar(selectedCourse: selectedCourse),
              ),
            ),
            if (selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: QuizView(course: selectedCourse),
              ),
          ],
        ),
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 380,
          child: Container(
            decoration: const BoxDecoration(
              border: Border(
                right: BorderSide(color: AppTheme.lightGray, width: 1),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: CoursesSidebar(selectedCourse: selectedCourse),
            ),
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: selectedCourse == null
                ? const _EmptyCourseView()
                : QuizView(course: selectedCourse),
          ),
        ),
      ],
    );
  }

  Widget _buildDocumentsPortal(BuildContext context, WidgetRef ref, PDFFile? selectedFile, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.all(16.0),
              child: UploadCard(),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              child: DocumentListCard(selectedFile: selectedFile),
            ),
            if (selectedFile != null)
              Padding(
                padding: const EdgeInsets.all(16.0),
                child: SizedBox(
                  height: 600,
                  child: PDFViewerCard(selectedFile: selectedFile),
                ),
              ),
          ],
        ),
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 380,
          child: Container(
            decoration: const BoxDecoration(
              border: Border(
                right: BorderSide(color: AppTheme.lightGray, width: 1),
              ),
            ),
            child: Column(
              children: [
                const Padding(
                  padding: EdgeInsets.all(20.0),
                  child: UploadCard(),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20.0),
                    child: DocumentListCard(selectedFile: selectedFile),
                  ),
                ),
                const SizedBox(height: 20),
              ],
            ),
          ),
        ),
        Expanded(
          child: Container(
            color: AppTheme.lightGray.withOpacity(0.3),
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: PDFViewerCard(selectedFile: selectedFile),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildCoursesPortal(BuildContext context, WidgetRef ref, Course? selectedCourse, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 350,
                child: CoursesSidebar(selectedCourse: selectedCourse),
              ),
            ),
            if (selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: CourseDetailsView(course: selectedCourse),
              ),
          ],
        ),
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 380,
          child: Container(
            decoration: const BoxDecoration(
              border: Border(
                right: BorderSide(color: AppTheme.lightGray, width: 1),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: CoursesSidebar(selectedCourse: selectedCourse),
            ),
          ),
        ),
        Expanded(
          child: Container(
            color: AppTheme.lightGray.withOpacity(0.3),
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: selectedCourse == null
                  ? const _EmptyCourseView()
                  : CourseDetailsView(course: selectedCourse),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSlidesPortal(BuildContext context, WidgetRef ref, Course? selectedCourse, bool isMobile) {
    if (isMobile) {
      return SingleChildScrollView(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: SizedBox(
                height: 300,
                child: CoursesSidebar(selectedCourse: selectedCourse),
              ),
            ),
            if (selectedCourse != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: SlidesViewerPage(course: selectedCourse),
              ),
          ],
        ),
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 380,
          child: Container(
            decoration: const BoxDecoration(
              border: Border(
                right: BorderSide(color: AppTheme.lightGray, width: 1),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: CoursesSidebar(selectedCourse: selectedCourse),
            ),
          ),
        ),
        Expanded(
          child: Container(
            color: AppTheme.lightGray.withOpacity(0.3),
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: selectedCourse == null
                  ? const _EmptyCourseView()
                  : SlidesViewerPage(course: selectedCourse),
            ),
          ),
        ),
      ],
    );
  }
}

class _TabHeaderButton extends StatelessWidget {
  final String title;
  final bool isActive;
  final VoidCallback onTap;

  const _TabHeaderButton({
    required this.title,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isActive ? AppTheme.primaryBlue.withOpacity(0.08) : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          title,
          style: GoogleFonts.barlow(
            fontSize: 15,
            fontWeight: isActive ? FontWeight.bold : FontWeight.w600,
            color: isActive ? AppTheme.primaryBlue : AppTheme.gray,
          ),
        ),
      ),
    );
  }
}

class _LoadingOverlay extends StatelessWidget {
  final String message;

  const _LoadingOverlay({required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.black.withOpacity(0.65),
      child: Center(
        child: Container(
          width: 380,
          padding: const EdgeInsets.all(32),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: AppTheme.pShapeRadius,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.2),
                blurRadius: 15,
                offset: const Offset(0, 5),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(
                width: 48,
                height: 48,
                child: CircularProgressIndicator(
                  valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryBlue),
                  strokeWidth: 4.5,
                ),
              ),
              const SizedBox(height: 24),
              Text(
                message,
                textAlign: TextAlign.center,
                style: GoogleFonts.barlow(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textBlack,
                  height: 1.4,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class UploadCard extends ConsumerWidget {
  const UploadCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final uploadState = ref.watch(uploadProgressProvider);

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.lightGray,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.gray.withOpacity(0.3), width: 1),
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Upload Document',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            'Support PDF format files',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
          InkWell(
            onTap: uploadState.status == UploadStatus.uploading
                ? null
                : () async {
                    final result = await FilePicker.platform.pickFiles(
                      type: FileType.custom,
                      allowedExtensions: ['pdf'],
                      withData: true,
                    );
                    if (result != null && result.files.isNotEmpty) {
                      final file = result.files.first;
                      ref.read(uploadProgressProvider.notifier).uploadFile(file, ref);
                    }
                  },
            borderRadius: AppTheme.pShapeRadiusCustom(8),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: AppTheme.pShapeRadiusCustom(8),
                border: Border.all(
                  color: AppTheme.primaryBlue.withOpacity(0.3),
                  width: 1.5,
                  style: BorderStyle.solid,
                ),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(
                    Icons.cloud_upload_rounded,
                    size: 40,
                    color: AppTheme.primaryBlue,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Click to select PDF document',
                    style: GoogleFonts.barlow(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.primaryBlue,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'PDF file up to 20MB',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
          if (uploadState.status == UploadStatus.uploading) ...[
            const SizedBox(height: 12),
            const LinearProgressIndicator(
              backgroundColor: Colors.white,
              valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryBlue),
            ),
            const SizedBox(height: 8),
            Center(
              child: Text(
                'Uploading document...',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.primaryBlue,
                    ),
              ),
            ),
          ],
          if (uploadState.status == UploadStatus.success) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppTheme.accentGreen.withOpacity(0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Row(
                children: [
                  const Icon(Icons.check_circle_rounded, color: AppTheme.accentGreen, size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      uploadState.message ?? 'Uploaded successfully!',
                      style: GoogleFonts.barlow(
                        fontSize: 13,
                        color: AppTheme.accentGreen,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (uploadState.status == UploadStatus.error) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppTheme.accentRed.withOpacity(0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_rounded, color: AppTheme.accentRed, size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      uploadState.message ?? 'Upload failed.',
                      style: GoogleFonts.barlow(
                        fontSize: 13,
                        color: AppTheme.accentRed,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class DocumentListCard extends ConsumerWidget {
  final PDFFile? selectedFile;

  const DocumentListCard({super.key, required this.selectedFile});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fileListState = ref.watch(fileListProvider);

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Uploaded PDFs',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                ),
                Text(
                  '${fileListState.files.length} items',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          const Divider(height: 1, color: AppTheme.lightGray),
          Expanded(
            child: fileListState.isLoading
                ? const Center(
                    child: CircularProgressIndicator(
                      valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryBlue),
                    ),
                  )
                : fileListState.error != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.error_outline_rounded, color: AppTheme.accentRed, size: 32),
                              const SizedBox(height: 8),
                              Text(
                                'Error loading files',
                                style: GoogleFonts.barlow(fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                fileListState.error!,
                                textAlign: TextAlign.center,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                      )
                    : fileListState.files.isEmpty
                        ? Center(
                            child: Padding(
                              padding: const EdgeInsets.all(32.0),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.picture_as_pdf_outlined, color: AppTheme.gray.withOpacity(0.5), size: 48),
                                  const SizedBox(height: 12),
                                  Text(
                                    'No documents uploaded yet',
                                    textAlign: TextAlign.center,
                                    style: GoogleFonts.barlow(
                                      color: AppTheme.gray,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          )
                        : ListView.separated(
                            itemCount: fileListState.files.length,
                            separatorBuilder: (context, index) => const Divider(height: 1, color: AppTheme.lightGray),
                            itemBuilder: (context, index) {
                              final file = fileListState.files[index];
                              final isSelected = selectedFile?.filename == file.filename;

                              return ListTile(
                                selected: isSelected,
                                selectedTileColor: AppTheme.primaryBlue.withOpacity(0.05),
                                leading: Icon(
                                  Icons.picture_as_pdf,
                                  color: isSelected ? AppTheme.primaryBlue : AppTheme.gray,
                                ),
                                title: Text(
                                  file.filename,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: GoogleFonts.barlow(
                                    fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                                    color: isSelected ? AppTheme.primaryBlue : AppTheme.textBlack,
                                  ),
                                ),
                                subtitle: Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      file.formattedSize,
                                      style: Theme.of(context).textTheme.bodySmall,
                                    ),
                                    Text(
                                      file.formattedDate,
                                      style: Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ],
                                ),
                                onTap: () {
                                  ref.read(selectedFileProvider.notifier).state = file;
                                },
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }
}

class PDFViewerCard extends ConsumerWidget {
  final PDFFile? selectedFile;

  const PDFViewerCard({super.key, required this.selectedFile});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (selectedFile == null) {
      return Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: AppTheme.pShapeRadius,
          border: Border.all(color: AppTheme.lightGray, width: 1),
        ),
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.folder_open_rounded,
                size: 64,
                color: AppTheme.gray.withOpacity(0.4),
              ),
              const SizedBox(height: 16),
              Text(
                'No Document Selected',
                style: GoogleFonts.inter(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryBlue,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Upload a PDF document or select one from the list to view it.',
                style: GoogleFonts.barlow(
                  fontSize: 14,
                  color: AppTheme.gray,
                ),
              ),
            ],
          ),
        ),
      );
    }

    final fileUrl = AppConstants.viewFileUrl(selectedFile!.filename);

    if (kIsWeb) {
      final String viewId = 'pdf-viewer-${selectedFile!.filename.hashCode}';
      ui_web.platformViewRegistry.registerViewFactory(
        viewId,
        (int id) => html.IFrameElement()
          ..src = fileUrl
          ..style.border = 'none'
          ..style.width = '100%'
          ..style.height = '100%',
      );

      return Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: AppTheme.pShapeRadius,
          border: Border.all(color: AppTheme.lightGray, width: 1),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: AppTheme.lightGray,
              child: Row(
                children: [
                  const Icon(Icons.picture_as_pdf, color: AppTheme.primaryBlue),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      selectedFile!.filename,
                      style: GoogleFonts.barlow(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.auto_stories, size: 16),
                    label: const Text('Create Course'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      backgroundColor: AppTheme.primaryBlue,
                      shape: RoundedRectangleBorder(
                        borderRadius: AppTheme.pShapeRadiusCustom(6.0),
                      ),
                    ),
                    onPressed: () {
                      ref.read(courseGenerationProvider.notifier).generateCourse(selectedFile!.filename, ref);
                    },
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: const Icon(Icons.open_in_new, color: AppTheme.primaryBlue, size: 20),
                    onPressed: () {
                      html.window.open(fileUrl, '_blank');
                    },
                    tooltip: 'Open in new tab',
                  ),
                ],
              ),
            ),
            Expanded(
              child: HtmlElementView(
                viewType: viewId,
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.picture_as_pdf, size: 64, color: AppTheme.primaryBlue),
            const SizedBox(height: 16),
            Text(
              'PDF viewer is running in Web mode.',
              style: GoogleFonts.barlow(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            TextButton.icon(
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open Document Link'),
              onPressed: () {
                debugPrint('Open URL: $fileUrl');
              },
            ),
          ],
        ),
      ),
    );
  }
}

class CoursesSidebar extends ConsumerWidget {
  final Course? selectedCourse;

  const CoursesSidebar({super.key, required this.selectedCourse});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final courseListState = ref.watch(courseListProvider);

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'My Courses',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                ),
                Text(
                  '${courseListState.courses.length} courses',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          const Divider(height: 1, color: AppTheme.lightGray),
          Expanded(
            child: courseListState.isLoading
                ? const Center(
                    child: CircularProgressIndicator(
                      valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryBlue),
                    ),
                  )
                : courseListState.error != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.error_outline_rounded, color: AppTheme.accentRed, size: 32),
                              const SizedBox(height: 8),
                              Text(
                                'Error loading courses',
                                style: GoogleFonts.barlow(fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                courseListState.error!,
                                textAlign: TextAlign.center,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                      )
                    : courseListState.courses.isEmpty
                        ? Center(
                            child: Padding(
                              padding: const EdgeInsets.all(32.0),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.auto_stories_outlined, color: AppTheme.gray.withOpacity(0.5), size: 48),
                                  const SizedBox(height: 12),
                                  Text(
                                    'No courses created yet',
                                    textAlign: TextAlign.center,
                                    style: GoogleFonts.barlow(
                                      color: AppTheme.gray,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    'Upload a PDF and click "Create Course" to generate one.',
                                    textAlign: TextAlign.center,
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                          )
                        : ListView.separated(
                            itemCount: courseListState.courses.length,
                            separatorBuilder: (context, index) => const Divider(height: 1, color: AppTheme.lightGray),
                            itemBuilder: (context, index) {
                              final course = courseListState.courses[index];
                              final isSelected = selectedCourse?.id == course.id;

                              return ListTile(
                                selected: isSelected,
                                selectedTileColor: AppTheme.primaryBlue.withOpacity(0.05),
                                leading: Icon(
                                  Icons.menu_book,
                                  color: isSelected ? AppTheme.primaryBlue : AppTheme.gray,
                                ),
                                title: Text(
                                  course.courseName,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: GoogleFonts.barlow(
                                    fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                                    color: isSelected ? AppTheme.primaryBlue : AppTheme.textBlack,
                                  ),
                                ),
                                subtitle: Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      course.courseDifficulty,
                                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                            color: _getDifficultyColor(course.courseDifficulty),
                                            fontWeight: FontWeight.bold,
                                          ),
                                    ),
                                    Text(
                                      '${course.modules.length} module${course.modules.length == 1 ? '' : 's'}',
                                      style: Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ],
                                ),
                                onTap: () {
                                  ref.read(selectedCourseProvider.notifier).state = course;
                                },
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }

  Color _getDifficultyColor(String difficulty) {
    switch (difficulty.toLowerCase()) {
      case 'easy':
      case 'beginner':
        return AppTheme.accentGreen;
      case 'medium':
      case 'intermediate':
        return AppTheme.accentOrange;
      case 'hard':
      case 'advanced':
        return AppTheme.accentRed;
      default:
        return AppTheme.gray;
    }
  }
}

class _EmptyCourseView extends StatelessWidget {
  const _EmptyCourseView();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.collections_bookmark_rounded,
              size: 64,
              color: AppTheme.gray.withOpacity(0.4),
            ),
            const SizedBox(height: 16),
            Text(
              'No Course Selected',
              style: GoogleFonts.inter(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppTheme.primaryBlue,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Select a course from the list on the left to view its syllabus outline.',
              style: GoogleFonts.barlow(
                fontSize: 14,
                color: AppTheme.gray,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// --- COURSE DETAILS VIEW COMPONENT (ALWAYS EDITABLE BY DEFAULT & INDIVIDUAL INFERRED BADGES) ---

class CourseDetailsView extends ConsumerStatefulWidget {
  final Course course;

  const CourseDetailsView({super.key, required this.course});

  @override
  ConsumerState<CourseDetailsView> createState() => _CourseDetailsViewState();
}

class _CourseDetailsViewState extends ConsumerState<CourseDetailsView> {
  final _formKey = GlobalKey<FormState>();
  
  late TextEditingController _nameController;
  late TextEditingController _descController;
  late TextEditingController _objController;
  late TextEditingController _audienceController;
  late TextEditingController _langController;
  late String _selectedDifficulty;

  List<TextEditingController> _moduleTitleControllers = [];
  List<TextEditingController> _moduleTextControllers = [];
  List<TextEditingController> _moduleQuestionsControllers = [];
  // Keep track of original module data (for preserving start_line/end_line anchors)
  List<CourseModule> _moduleData = [];

  @override
  void initState() {
    super.initState();
    _initControllers();
  }

  @override
  void didUpdateWidget(covariant CourseDetailsView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.course.id != widget.course.id) {
      _disposeControllers();
      _initControllers();
    }
  }

  void _initControllers() {
    _nameController = TextEditingController(text: widget.course.courseName);
    _descController = TextEditingController(text: widget.course.courseDescription);
    _objController = TextEditingController(text: widget.course.courseObjective);
    _audienceController = TextEditingController(text: widget.course.targetAudience);
    _langController = TextEditingController(text: widget.course.language);

    final diff = widget.course.courseDifficulty;
    if (['easy', 'medium', 'hard'].contains(diff.toLowerCase())) {
      _selectedDifficulty = diff[0].toUpperCase() + diff.substring(1).toLowerCase();
    } else if (diff.toLowerCase() == 'beginner') {
      _selectedDifficulty = 'Easy';
    } else if (diff.toLowerCase() == 'intermediate') {
      _selectedDifficulty = 'Medium';
    } else if (diff.toLowerCase() == 'advanced') {
      _selectedDifficulty = 'Hard';
    } else {
      _selectedDifficulty = 'Easy';
    }

    _moduleData = List<CourseModule>.from(widget.course.modules);
    _moduleTitleControllers = _moduleData
        .map((m) => TextEditingController(text: m.title))
        .toList();
    _moduleTextControllers = _moduleData
        .map((m) => TextEditingController(text: m.text))
        .toList();
    _moduleQuestionsControllers = _moduleData
        .map((m) => TextEditingController(text: m.numQuestions.toString()))
        .toList();
  }

  void _disposeControllers() {
    _nameController.dispose();
    _descController.dispose();
    _objController.dispose();
    _audienceController.dispose();
    _langController.dispose();
    for (var c in _moduleTitleControllers) c.dispose();
    for (var c in _moduleTextControllers) c.dispose();
    for (var c in _moduleQuestionsControllers) c.dispose();
    _moduleTitleControllers.clear();
    _moduleTextControllers.clear();
    _moduleQuestionsControllers.clear();
    _moduleData.clear();
  }

  @override
  void dispose() {
    _disposeControllers();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      clipBehavior: Clip.antiAlias,
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header Bar
            Container(
              padding: const EdgeInsets.all(24),
              color: AppTheme.primaryBlue,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'COURSE BLUEPRINT',
                        style: GoogleFonts.barlow(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: Colors.white.withOpacity(0.7),
                          letterSpacing: 2,
                        ),
                      ),
                      Row(
                        children: [
                          TextButton(
                            style: TextButton.styleFrom(foregroundColor: Colors.white),
                            onPressed: () {
                              setState(() {
                                _disposeControllers();
                                _initControllers();
                              });
                            },
                            child: const Text('Reset'),
                          ),
                          const SizedBox(width: 8),
                          // Generate Lessons button
                          Consumer(
                            builder: (context, ref, _) {
                              final hasModules = widget.course.modules.isNotEmpty;
                              return ElevatedButton.icon(
                                icon: const Icon(Icons.auto_awesome, size: 14),
                                label: const Text('Generate Lessons'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppTheme.accentOrange,
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                ),
                                onPressed: hasModules
                                    ? () => ref
                                        .read(lessonGenerationProvider.notifier)
                                        .generateLessons(widget.course.id, ref)
                                    : null,
                              );
                            },
                          ),
                          const SizedBox(width: 8),
                          ElevatedButton.icon(
                            icon: const Icon(Icons.save, size: 14),
                            label: const Text('Save Changes'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.accentGreen,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(6),
                              ),
                            ),
                            onPressed: _saveCourseModifications,
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  
                  // Course Name field
                  const Text(
                    'Course Name',
                    style: TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 4),
                  TextFormField(
                    controller: _nameController,
                    style: GoogleFonts.inter(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                    decoration: const InputDecoration(
                      isDense: true,
                      contentPadding: EdgeInsets.symmetric(vertical: 8),
                      enabledBorder: UnderlineInputBorder(
                        borderSide: BorderSide(color: Colors.white38),
                      ),
                      focusedBorder: UnderlineInputBorder(
                        borderSide: BorderSide(color: Colors.white),
                      ),
                    ),
                    validator: (value) => value == null || value.isEmpty ? 'Required' : null,
                  ),
                  const SizedBox(height: 16),
                  
                  // Difficulty & Language side by side
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Difficulty',
                              style: TextStyle(color: Colors.white70, fontSize: 12),
                            ),
                            const SizedBox(height: 4),
                            Theme(
                              data: Theme.of(context).copyWith(canvasColor: AppTheme.primaryBlue),
                              child: DropdownButtonFormField<String>(
                                value: _selectedDifficulty,
                                style: GoogleFonts.barlow(color: Colors.white, fontWeight: FontWeight.bold),
                                decoration: const InputDecoration(
                                  isDense: true,
                                  contentPadding: EdgeInsets.zero,
                                  enabledBorder: UnderlineInputBorder(
                                    borderSide: BorderSide(color: Colors.white38),
                                  ),
                                  focusedBorder: UnderlineInputBorder(
                                    borderSide: BorderSide(color: Colors.white),
                                  ),
                                ),
                                items: ['Easy', 'Medium', 'Hard']
                                    .map((val) => DropdownMenuItem(value: val, child: Text(val)))
                                    .toList(),
                                onChanged: (value) {
                                  if (value != null) {
                                    setState(() {
                                      _selectedDifficulty = value;
                                    });
                                  }
                                },
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 24),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Language',
                              style: TextStyle(color: Colors.white70, fontSize: 12),
                            ),
                            const SizedBox(height: 4),
                            TextFormField(
                              controller: _langController,
                              style: GoogleFonts.barlow(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                              decoration: const InputDecoration(
                                isDense: true,
                                contentPadding: EdgeInsets.symmetric(vertical: 4),
                                enabledBorder: UnderlineInputBorder(
                                  borderSide: BorderSide(color: Colors.white38),
                                ),
                                focusedBorder: UnderlineInputBorder(
                                  borderSide: BorderSide(color: Colors.white),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            
            // Body Scroll View
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Description Input
                    const _SectionHeaderInput(
                      title: 'Course Description',
                      icon: Icons.description,
                    ),
                    const SizedBox(height: 6),
                    TextFormField(
                      controller: _descController,
                      maxLines: 4,
                      style: GoogleFonts.barlow(fontSize: 15, color: AppTheme.textBlack),
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.all(12),
                        hintText: 'Enter course description...',
                      ),
                    ),
                    const SizedBox(height: 24),

                    // Objective Input
                    const _SectionHeaderInput(
                      title: 'Course Objective',
                      icon: Icons.track_changes,
                    ),
                    const SizedBox(height: 6),
                    TextFormField(
                      controller: _objController,
                      maxLines: 4,
                      style: GoogleFonts.barlow(fontSize: 15, color: AppTheme.textBlack),
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.all(12),
                        hintText: 'Enter course objective...',
                      ),
                    ),
                    const SizedBox(height: 24),

                    // Target Audience Input
                    const _SectionHeaderInput(
                      title: 'Target Audience',
                      icon: Icons.group,
                    ),
                    const SizedBox(height: 6),
                    TextFormField(
                      controller: _audienceController,
                      maxLines: 2,
                      style: GoogleFonts.barlow(fontSize: 15, color: AppTheme.textBlack),
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.all(12),
                        hintText: 'Enter target audience...',
                      ),
                    ),
                    const SizedBox(height: 24),

                    // Modules dynamic list input
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.format_list_numbered, size: 18, color: AppTheme.primaryBlue),
                            const SizedBox(width: 8),
                            Text(
                              'Modules Curriculum Outline',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.primaryBlue,
                              ),
                            ),
                          ],
                        ),
                        TextButton.icon(
                          icon: const Icon(Icons.add, size: 16),
                          label: const Text('Add Module'),
                          onPressed: () {
                            setState(() {
                              _moduleData.add(CourseModule(
                                moduleNumber: _moduleData.length + 1,
                                title: '',
                                text: '',
                                startLine: '',
                                endLine: '',
                                numQuestions: 0,
                              ));
                              _moduleTitleControllers.add(TextEditingController());
                              _moduleTextControllers.add(TextEditingController());
                              _moduleQuestionsControllers.add(TextEditingController(text: '0'));
                            });
                          },
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    ReorderableListView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: _moduleTitleControllers.length,
                      onReorder: _onReorder,
                      itemBuilder: (context, index) {
                        return Container(
                          key: ValueKey('module_key_${index}_${_moduleData[index].moduleNumber}'),
                          margin: const EdgeInsets.only(bottom: 16),
                          decoration: BoxDecoration(
                            border: Border.all(color: AppTheme.lightGray, width: 1),
                            borderRadius: AppTheme.pShapeRadiusCustom(8),
                          ),
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // Module number + title row
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.center,
                                children: [
                                  // Drag handle indicator
                                  const Icon(Icons.drag_indicator, color: AppTheme.gray, size: 20),
                                  const SizedBox(width: 8),
                                  CircleAvatar(
                                    radius: 14,
                                    backgroundColor: AppTheme.primaryBlue,
                                    child: Text(
                                      '${index + 1}',
                                      style: GoogleFonts.barlow(
                                        color: Colors.white,
                                        fontSize: 12,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: TextFormField(
                                      controller: _moduleTitleControllers[index],
                                      style: GoogleFonts.barlow(
                                        fontSize: 15,
                                        fontWeight: FontWeight.w600,
                                      ),
                                      decoration: const InputDecoration(
                                        contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                                        border: OutlineInputBorder(),
                                        hintText: 'Module title...',
                                        isDense: true,
                                      ),
                                    ),
                                  ),
                                  IconButton(
                                    icon: const Icon(Icons.delete, color: AppTheme.accentRed, size: 20),
                                    tooltip: 'Delete module',
                                    onPressed: () {
                                      setState(() {
                                        _moduleTitleControllers[index].dispose();
                                        _moduleTextControllers[index].dispose();
                                        _moduleQuestionsControllers[index].dispose();
                                        _moduleTitleControllers.removeAt(index);
                                        _moduleTextControllers.removeAt(index);
                                        _moduleQuestionsControllers.removeAt(index);
                                        _moduleData.removeAt(index);
                                      });
                                    },
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              // Question Count Input
                              Row(
                                children: [
                                  const Icon(Icons.quiz_outlined, size: 16, color: AppTheme.primaryBlue),
                                  const SizedBox(width: 6),
                                  Text(
                                    'Quiz questions:',
                                    style: GoogleFonts.barlow(fontSize: 13, color: AppTheme.primaryBlue, fontWeight: FontWeight.w500),
                                  ),
                                  const SizedBox(width: 8),
                                  SizedBox(
                                    width: 70,
                                    child: TextFormField(
                                      controller: _moduleQuestionsControllers[index],
                                      keyboardType: TextInputType.number,
                                      style: GoogleFonts.barlow(fontSize: 13, fontWeight: FontWeight.bold),
                                      decoration: const InputDecoration(
                                        contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                                        border: OutlineInputBorder(),
                                        isDense: true,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    'questions (0 to disable)',
                                    style: GoogleFonts.barlow(fontSize: 12, color: AppTheme.gray),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              // Module text body
                              TextFormField(
                                controller: _moduleTextControllers[index],
                                maxLines: 6,
                                minLines: 3,
                                style: GoogleFonts.barlow(
                                  fontSize: 13,
                                  color: AppTheme.textBlack,
                                  height: 1.5,
                                ),
                                decoration: InputDecoration(
                                  contentPadding: const EdgeInsets.all(10),
                                  border: const OutlineInputBorder(),
                                  hintText: 'Module content will appear here after generation...',
                                  hintStyle: GoogleFonts.barlow(
                                    fontSize: 13,
                                    color: AppTheme.gray,
                                  ),
                                  filled: true,
                                  fillColor: AppTheme.lightGray.withOpacity(0.5),
                                ),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                    
                    // Extracted images section
                    const SizedBox(height: 32),
                    Row(
                      children: [
                        const Icon(Icons.image_search_rounded, size: 18, color: AppTheme.primaryBlue),
                        const SizedBox(width: 8),
                        Text(
                          'Extracted PDF Images & Captions Verification',
                          style: GoogleFonts.inter(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.primaryBlue,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (widget.course.images.isEmpty)
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AppTheme.lightGray.withOpacity(0.5),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AppTheme.lightGray),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.info_outline, color: AppTheme.gray),
                            const SizedBox(width: 8),
                            Text(
                              'No images were extracted from this PDF.',
                              style: GoogleFonts.barlow(color: AppTheme.gray),
                            ),
                          ],
                        ),
                      )
                    else
                      GridView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                          crossAxisSpacing: 16,
                          mainAxisSpacing: 16,
                          childAspectRatio: 1.3,
                        ),
                        itemCount: widget.course.images.length,
                        itemBuilder: (context, idx) {
                          final img = widget.course.images[idx];
                          return Container(
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: AppTheme.lightGray),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withOpacity(0.02),
                                  blurRadius: 4,
                                  offset: const Offset(0, 2),
                                ),
                              ],
                            ),
                            clipBehavior: Clip.antiAlias,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Expanded(
                                  child: Container(
                                    color: AppTheme.lightGray.withOpacity(0.3),
                                    child: Center(
                                      child: Image.network(
                                        '${AppConstants.apiBaseUrl}/${img.filePath}',
                                        fit: BoxFit.contain,
                                        errorBuilder: (context, error, stackTrace) =>
                                            const Icon(Icons.broken_image, color: AppTheme.gray),
                                      ),
                                    ),
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                                  color: Colors.white,
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Text(
                                        img.caption.isNotEmpty ? img.caption : 'No Caption Found',
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                        style: GoogleFonts.barlow(
                                          fontSize: 12.5,
                                          fontWeight: FontWeight.w600,
                                          color: AppTheme.textBlack,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _onReorder(int oldIndex, int newIndex) {
    setState(() {
      if (oldIndex < newIndex) {
        newIndex -= 1;
      }
      final CourseModule item = _moduleData.removeAt(oldIndex);
      _moduleData.insert(newIndex, item);

      final TextEditingController titleController = _moduleTitleControllers.removeAt(oldIndex);
      _moduleTitleControllers.insert(newIndex, titleController);

      final TextEditingController textController = _moduleTextControllers.removeAt(oldIndex);
      _moduleTextControllers.insert(newIndex, textController);

      final TextEditingController questionsController = _moduleQuestionsControllers.removeAt(oldIndex);
      _moduleQuestionsControllers.insert(newIndex, questionsController);
    });
  }

  void _saveCourseModifications() async {
    if (_formKey.currentState?.validate() ?? false) {
      // Build full module objects — include title, text, and LLM anchors (pass-through)
      final updatedModules = _moduleTitleControllers.asMap().entries
          .where((e) => e.value.text.trim().isNotEmpty)
          .map((e) {
            final idx = e.key;
            final original = idx < _moduleData.length ? _moduleData[idx] : null;
            return {
              'title': e.value.text.trim(),
              'text': idx < _moduleTextControllers.length
                  ? _moduleTextControllers[idx].text.trim()
                  : '',
              'num_questions': idx < _moduleQuestionsControllers.length
                  ? int.tryParse(_moduleQuestionsControllers[idx].text.trim()) ?? 0
                  : 0,
              // Preserve LLM-generated anchors unchanged
              'start_line': original?.startLine ?? '',
              'end_line': original?.endLine ?? '',
            };
          })
          .toList();

      final updatedFields = {
        'course_name': _nameController.text.trim(),
        'course_description': _descController.text.trim(),
        'course_objective': _objController.text.trim(),
        'target_audience': _audienceController.text.trim(),
        'language': _langController.text.trim(),
        'course_difficulty': _selectedDifficulty,
        'modules': updatedModules,
      };

      final success = await ref
          .read(courseUpdateProvider.notifier)
          .updateCourse(widget.course.id, updatedFields, ref);

      if (success && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Course blueprint successfully saved!'),
            backgroundColor: AppTheme.accentGreen,
          ),
        );
      }
    }
  }
}

class _SectionHeaderInput extends StatelessWidget {
  final String title;
  final IconData icon;

  const _SectionHeaderInput({
    required this.title,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: AppTheme.primaryBlue),
        const SizedBox(width: 8),
        Text(
          title,
          style: GoogleFonts.inter(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: AppTheme.primaryBlue,
          ),
        ),
      ],
    );
  }
}

// ============================================================
// LESSONS VIEW — Editable accordion: Module → Lesson → Slide → Bullets
// ============================================================

class LessonsView extends ConsumerStatefulWidget {
  final Course course;

  const LessonsView({super.key, required this.course});

  @override
  ConsumerState<LessonsView> createState() => _LessonsViewState();
}

class _LessonsViewState extends ConsumerState<LessonsView> {
  // Nested mutable state mirrors:
  // _moduleData[m].lessons[l].slides[s].bullets[b]
  //
  // We hold controllers only for text fields that need them.
  // Lesson titles, slide titles, bullet texts are all TextEditingControllers
  // stored in parallel nested lists.

  late List<_ModuleLessonData> _data;

  @override
  void initState() {
    super.initState();
    _initData();
  }

  @override
  void didUpdateWidget(covariant LessonsView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.course.id != widget.course.id) {
      _disposeData();
      _initData();
    }
  }

  void _initData() {
    _data = widget.course.modules.map((module) {
      return _ModuleLessonData(
        moduleTitle: module.title,
        moduleNumber: module.moduleNumber,
        lessons: module.lessons.map((lesson) {
          return _LessonData(
            lessonTitleCtrl: TextEditingController(text: lesson.lessonTitle),
            slides: lesson.slides.map((slide) {
              return _SlideData(
                slideTitleCtrl: TextEditingController(text: slide.slideTitle),
                bulletCtrls: slide.bullets
                    .map((b) => TextEditingController(text: b.text))
                    .toList(),
                images: List<SlideImage>.from(slide.images),
              );
            }).toList(),
          );
        }).toList(),
      );
    }).toList();
  }

  void _disposeData() {
    for (final m in _data) {
      for (final l in m.lessons) {
        l.lessonTitleCtrl.dispose();
        for (final s in l.slides) {
          s.slideTitleCtrl.dispose();
          for (final b in s.bulletCtrls) b.dispose();
        }
      }
    }
    _data.clear();
  }

  @override
  void dispose() {
    _disposeData();
    super.dispose();
  }

  // ---- helpers ----

  void _addLesson(int mIdx) {
    setState(() {
      _data[mIdx].lessons.add(_LessonData(
        lessonTitleCtrl: TextEditingController(),
        slides: [
          _SlideData(
            slideTitleCtrl: TextEditingController(),
            bulletCtrls: [TextEditingController()],
            images: [],
          ),
        ],
      ));
    });
  }

  void _deleteLesson(int mIdx, int lIdx) {
    setState(() {
      final lesson = _data[mIdx].lessons.removeAt(lIdx);
      lesson.lessonTitleCtrl.dispose();
      for (final s in lesson.slides) {
        s.slideTitleCtrl.dispose();
        for (final b in s.bulletCtrls) b.dispose();
      }
    });
  }

  void _addSlide(int mIdx, int lIdx) {
    setState(() {
      _data[mIdx].lessons[lIdx].slides.add(_SlideData(
        slideTitleCtrl: TextEditingController(),
        bulletCtrls: [TextEditingController()],
        images: [],
      ));
    });
  }

  void _deleteSlide(int mIdx, int lIdx, int sIdx) {
    setState(() {
      final slide = _data[mIdx].lessons[lIdx].slides.removeAt(sIdx);
      slide.slideTitleCtrl.dispose();
      for (final b in slide.bulletCtrls) b.dispose();
    });
  }

  void _addBullet(int mIdx, int lIdx, int sIdx) {
    setState(() {
      _data[mIdx].lessons[lIdx].slides[sIdx].bulletCtrls.add(TextEditingController());
    });
  }

  void _deleteBullet(int mIdx, int lIdx, int sIdx, int bIdx) {
    setState(() {
      final ctrl = _data[mIdx].lessons[lIdx].slides[sIdx].bulletCtrls.removeAt(bIdx);
      ctrl.dispose();
    });
  }

  Future<void> _saveChanges() async {
    // Rebuild the full modules list preserving blueprint fields
    final updatedModules = widget.course.modules.asMap().entries.map((mEntry) {
      final mIdx = mEntry.key;
      final originalModule = mEntry.value;
      final mData = mIdx < _data.length ? _data[mIdx] : null;

      final lessons = mData?.lessons.asMap().entries.map((lEntry) {
        final lIdx = lEntry.key;
        final lData = lEntry.value;
        final slides = lData.slides.asMap().entries.map((sEntry) {
          final sIdx = sEntry.key;
          final sData = sEntry.value;
          final bullets = sData.bulletCtrls
              .where((c) => c.text.trim().isNotEmpty)
              .map((c) => {'text': c.text.trim()})
              .toList();
          return {
            'slide_number': sIdx + 1,
            'slide_title': sData.slideTitleCtrl.text.trim(),
            'bullets': bullets,
            'images': sData.images.map((img) => img.toJson()).toList(),
          };
        }).toList();
        return {
          'lesson_number': lIdx + 1,
          'lesson_title': lData.lessonTitleCtrl.text.trim(),
          'slides': slides,
        };
      }).toList() ?? [];

      return {
        'title': originalModule.title,
        'text': originalModule.text,
        'start_line': originalModule.startLine,
        'end_line': originalModule.endLine,
        'lessons': lessons,
      };
    }).toList();

    final success = await ref.read(courseUpdateProvider.notifier).updateCourse(
      widget.course.id,
      {'modules': updatedModules},
      ref,
    );

    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Lessons saved successfully!'),
          backgroundColor: AppTheme.accentGreen,
        ),
      );
    }
  }

  // ---- build ----

  @override
  Widget build(BuildContext context) {
    final hasLessons = _data.any((m) => m.lessons.isNotEmpty);

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            color: AppTheme.primaryBlue,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'LESSONS OUTLINE',
                      style: GoogleFonts.barlow(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: Colors.white.withOpacity(0.7),
                        letterSpacing: 2,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      widget.course.courseName,
                      style: GoogleFonts.inter(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
                if (hasLessons)
                  Row(
                    children: [
                      ElevatedButton.icon(
                        icon: const Icon(Icons.save, size: 14),
                        label: const Text('Save Changes'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.accentGreen,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                        ),
                        onPressed: _saveChanges,
                      ),
                      const SizedBox(width: 10),
                      ElevatedButton.icon(
                        icon: const Icon(Icons.record_voice_over_rounded, size: 14),
                        label: const Text('Generate Script'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.accentBlue,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                        ),
                        onPressed: () async {
                          await ref.read(scriptGenerationProvider.notifier).generateScripts(
                            widget.course.id, ref,
                          );
                          if (mounted) {
                            final state = ref.read(scriptGenerationProvider);
                            if (state.status == ScriptGenStatus.success) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Narration scripts generated successfully!'),
                                  backgroundColor: AppTheme.accentGreen,
                                ),
                              );
                            } else if (state.status == ScriptGenStatus.error) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('Script generation failed: ${state.error}'),
                                  backgroundColor: AppTheme.accentRed,
                                ),
                              );
                            }
                          }
                        },
                      ),
                      const SizedBox(width: 10),
                      ElevatedButton.icon(
                        icon: const Icon(Icons.slideshow_rounded, size: 14),
                        label: const Text('Generate Slides'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.accentOrange,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                        ),
                        onPressed: () async {
                          await ref.read(slideGenerationProvider.notifier).generateSlides(
                            widget.course.id, ref,
                          );
                          if (mounted) {
                            final state = ref.read(slideGenerationProvider);
                            if (state.status == SlideGenStatus.success) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Slides generated! Switching to Slides tab.'),
                                  backgroundColor: AppTheme.accentGreen,
                                ),
                              );
                              ref.read(currentTabProvider.notifier).state = 3;
                            } else if (state.status == SlideGenStatus.error) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('Slide generation failed: ${state.error}'),
                                  backgroundColor: AppTheme.accentRed,
                                ),
                              );
                            }
                          }
                        },
                      ),
                      const SizedBox(width: 10),
                      ElevatedButton.icon(
                        icon: const Icon(Icons.quiz_rounded, size: 14),
                        label: const Text('Generate Quiz'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.primaryBlue,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                        ),
                        onPressed: () async {
                          await ref.read(quizGenerationProvider.notifier).generateQuiz(
                            widget.course.id, ref,
                          );
                          if (mounted) {
                            final state = ref.read(quizGenerationProvider);
                            if (state.status == QuizGenStatus.success) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Quiz generated successfully! Switching to Quiz tab.'),
                                  backgroundColor: AppTheme.accentGreen,
                                ),
                              );
                              ref.read(currentTabProvider.notifier).state = 4;
                            } else if (state.status == QuizGenStatus.error) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('Quiz generation failed: ${state.error}'),
                                  backgroundColor: AppTheme.accentRed,
                                ),
                              );
                            }
                          }
                        },
                      ),
                    ],
                  ),
              ],
            ),
          ),

          // Body
          Expanded(
            child: !hasLessons
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.auto_awesome_outlined,
                            size: 56, color: AppTheme.gray.withOpacity(0.4)),
                        const SizedBox(height: 16),
                        Text(
                          'No Lessons Generated Yet',
                          style: GoogleFonts.inter(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.primaryBlue,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Go to the Courses tab, open a course blueprint,\nand press "Generate Lessons".',
                          textAlign: TextAlign.center,
                          style: GoogleFonts.barlow(fontSize: 14, color: AppTheme.gray),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(24),
                    itemCount: _data.length,
                    itemBuilder: (context, mIdx) => _buildModuleBlock(mIdx),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildModuleBlock(int mIdx) {
    final mData = _data[mIdx];
    return Container(
      margin: const EdgeInsets.only(bottom: 24),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.primaryBlue.withOpacity(0.2), width: 1.5),
        borderRadius: AppTheme.pShapeRadiusCustom(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Module header bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: AppTheme.primaryBlue.withOpacity(0.06),
              borderRadius: const BorderRadius.only(
                topRight: Radius.circular(8),
                topLeft: Radius.zero,
              ),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryBlue,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    'MODULE ${mData.moduleNumber}',
                    style: GoogleFonts.barlow(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                      letterSpacing: 1,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    mData.moduleTitle,
                    style: GoogleFonts.barlow(
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primaryBlue,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                TextButton.icon(
                  icon: const Icon(Icons.add, size: 14),
                  label: const Text('Add Lesson'),
                  style: TextButton.styleFrom(foregroundColor: AppTheme.primaryBlue),
                  onPressed: () => _addLesson(mIdx),
                ),
              ],
            ),
          ),

          // Lessons
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              children: mData.lessons.asMap().entries.map((lEntry) {
                return _buildLessonBlock(mIdx, lEntry.key);
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLessonBlock(int mIdx, int lIdx) {
    final lData = _data[mIdx].lessons[lIdx];
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.lightGray, width: 1),
        borderRadius: AppTheme.pShapeRadiusCustom(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Lesson title row
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            color: AppTheme.accentOrange.withOpacity(0.08),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppTheme.accentOrange,
                    borderRadius: BorderRadius.circular(3),
                  ),
                  child: Text(
                    'L${lIdx + 1}',
                    style: GoogleFonts.barlow(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: TextFormField(
                    controller: lData.lessonTitleCtrl,
                    style: GoogleFonts.barlow(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textBlack,
                    ),
                    decoration: const InputDecoration(
                      isDense: true,
                      contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                      border: OutlineInputBorder(),
                      hintText: 'Lesson title...',
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                TextButton.icon(
                  icon: const Icon(Icons.add, size: 13),
                  label: const Text('Add Slide'),
                  style: TextButton.styleFrom(
                    foregroundColor: AppTheme.accentOrange,
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  ),
                  onPressed: () => _addSlide(mIdx, lIdx),
                ),
                IconButton(
                  icon: const Icon(Icons.delete_outline, color: AppTheme.accentRed, size: 18),
                  tooltip: 'Delete lesson',
                  onPressed: () => _deleteLesson(mIdx, lIdx),
                ),
              ],
            ),
          ),

          // Slides
          Padding(
            padding: const EdgeInsets.all(10),
            child: Column(
              children: lData.slides.asMap().entries.map((sEntry) {
                return _buildSlideBlock(mIdx, lIdx, sEntry.key);
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSlideBlock(int mIdx, int lIdx, int sIdx) {
    final sData = _data[mIdx].lessons[lIdx].slides[sIdx];
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: AppTheme.lightGray.withOpacity(0.4),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppTheme.gray.withOpacity(0.2)),
      ),
      padding: const EdgeInsets.all(10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Slide title row
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: AppTheme.accentCyan.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(3),
                  border: Border.all(color: AppTheme.accentCyan.withOpacity(0.4)),
                ),
                child: Text(
                  'Slide ${sIdx + 1}',
                  style: GoogleFonts.barlow(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.accentCyan,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextFormField(
                  controller: sData.slideTitleCtrl,
                  style: GoogleFonts.barlow(fontSize: 13, fontWeight: FontWeight.w600),
                  decoration: const InputDecoration(
                    isDense: true,
                    contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                    border: OutlineInputBorder(),
                    hintText: 'Slide title...',
                    filled: true,
                    fillColor: Colors.white,
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline, color: AppTheme.accentRed, size: 16),
                tooltip: 'Delete slide',
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                onPressed: () => _deleteSlide(mIdx, lIdx, sIdx),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Bullets
          ...sData.bulletCtrls.asMap().entries.map((bEntry) {
            final bIdx = bEntry.key;
            final ctrl = bEntry.value;
            return Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(right: 8, top: 2),
                    child: Icon(Icons.circle, size: 6, color: AppTheme.primaryBlue),
                  ),
                  Expanded(
                    child: TextFormField(
                      controller: ctrl,
                      style: GoogleFonts.barlow(fontSize: 13, color: AppTheme.textBlack),
                      decoration: const InputDecoration(
                        isDense: true,
                        contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                        border: OutlineInputBorder(),
                        hintText: 'Bullet point (~7 words)...',
                        filled: true,
                        fillColor: Colors.white,
                      ),
                    ),
                  ),
                  const SizedBox(width: 4),
                  IconButton(
                    icon: const Icon(Icons.remove_circle_outline,
                        color: AppTheme.accentRed, size: 16),
                    tooltip: 'Delete bullet',
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    onPressed: () => _deleteBullet(mIdx, lIdx, sIdx, bIdx),
                  ),
                ],
              ),
            );
          }),

          // Add bullet
          TextButton.icon(
            icon: const Icon(Icons.add, size: 13),
            label: const Text('Add Bullet'),
            style: TextButton.styleFrom(
              foregroundColor: AppTheme.primaryBlue,
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            onPressed: () => _addBullet(mIdx, lIdx, sIdx),
          ),
        ],
      ),
    );
  }
}

// ---- Mutable data holders (no const, holds controllers) ----

class _ModuleLessonData {
  final int moduleNumber;
  final String moduleTitle;
  final List<_LessonData> lessons;

  _ModuleLessonData({
    required this.moduleNumber,
    required this.moduleTitle,
    required this.lessons,
  });
}

class _LessonData {
  final TextEditingController lessonTitleCtrl;
  final List<_SlideData> slides;

  _LessonData({required this.lessonTitleCtrl, required this.slides});
}

class _SlideData {
  final TextEditingController slideTitleCtrl;
  final List<TextEditingController> bulletCtrls;
  final List<SlideImage> images;

  _SlideData({
    required this.slideTitleCtrl,
    required this.bulletCtrls,
    required this.images,
  });
}

// ============================================================
// SLIDES VIEWER PAGE — Module → Lesson selector + slide viewer
// ============================================================

class SlidesViewerPage extends ConsumerStatefulWidget {
  final Course course;

  const SlidesViewerPage({super.key, required this.course});

  @override
  ConsumerState<SlidesViewerPage> createState() => _SlidesViewerPageState();
}

class _SlidesViewerPageState extends ConsumerState<SlidesViewerPage> {
  int _selectedModuleIdx = 0;
  int _selectedLessonIdx = 0;
  late PageController _pageController;
  int _currentSlideIdx = 0;
  final FocusNode _focusNode = FocusNode();

  bool _loading = true;
  bool _slidesExist = false;

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
    _checkSlidesExist();
  }

  @override
  void didUpdateWidget(covariant SlidesViewerPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.course.id != widget.course.id) {
      setState(() {
        _selectedModuleIdx = 0;
        _selectedLessonIdx = 0;
        _currentSlideIdx = 0;
        _loading = true;
        _slidesExist = false;
      });
      _pageController.jumpToPage(0);
      _checkSlidesExist();
    }
  }

  Future<void> _checkSlidesExist() async {
    try {
      final response = await http.get(
        Uri.parse(AppConstants.listSlidesEndpoint(widget.course.id)),
      );
      if (response.statusCode == 200 && mounted) {
        final list = jsonDecode(response.body) as List;
        setState(() {
          _slidesExist = list.isNotEmpty;
          _loading = false;
        });
      } else if (mounted) {
        setState(() { _loading = false; });
      }
    } catch (_) {
      if (mounted) setState(() { _loading = false; });
    }
  }

  @override
  void dispose() {
    _pageController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  List<CourseModule> get _modulesWithLessons =>
      widget.course.modules.where((m) => m.lessons.isNotEmpty).toList();

  CourseModule? get _currentModule {
    final mods = _modulesWithLessons;
    if (_selectedModuleIdx >= mods.length) return null;
    return mods[_selectedModuleIdx];
  }

  CourseLesson? get _currentLesson {
    final mod = _currentModule;
    if (mod == null || _selectedLessonIdx >= mod.lessons.length) return null;
    return mod.lessons[_selectedLessonIdx];
  }

  void _goToSlide(int idx) {
    if (idx < 0 || _currentLesson == null || idx >= _currentLesson!.slides.length) return;
    _pageController.animateToPage(
      idx,
      duration: const Duration(milliseconds: 350),
      curve: Curves.easeInOut,
    );
  }

  void _handleKeyEvent(KeyEvent event) {
    if (event is! KeyDownEvent) return;
    if (event.logicalKey == LogicalKeyboardKey.arrowRight) {
      _goToSlide(_currentSlideIdx + 1);
    } else if (event.logicalKey == LogicalKeyboardKey.arrowLeft) {
      _goToSlide(_currentSlideIdx - 1);
    }
  }

  void _downloadPptx() {
    final mod = _currentModule;
    if (mod == null) return;

    // Find the actual module index in the original list
    final actualModuleIdx = widget.course.modules.indexOf(mod);
    if (actualModuleIdx < 0) return;

    final url = AppConstants.downloadSlideEndpoint(
      widget.course.id, actualModuleIdx, _selectedLessonIdx,
    );
    html.window.open(url, '_blank');
  }

  @override
  Widget build(BuildContext context) {
    // Re-check when slide generation completes (from Lessons tab)
    ref.listen<SlideGenerationState>(slideGenerationProvider, (prev, next) {
      if (next.status == SlideGenStatus.success) {
        _checkSlidesExist();
      }
    });

    // If still checking the backend, show spinner
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    // If no PPTX files have been generated, show empty state
    if (!_slidesExist) {
      return Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: AppTheme.pShapeRadius,
          border: Border.all(color: AppTheme.lightGray, width: 1),
        ),
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.slideshow_outlined,
                  size: 56, color: AppTheme.gray.withOpacity(0.4)),
              const SizedBox(height: 16),
              Text(
                'No Slides Generated Yet',
                style: GoogleFonts.inter(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryBlue,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Go to the Lessons tab, open a course,\nand press "Generate Slides" to create slide decks.',
                textAlign: TextAlign.center,
                style: GoogleFonts.barlow(fontSize: 14, color: AppTheme.gray),
              ),
            ],
          ),
        ),
      );
    }

    final modulesWithLessons = _modulesWithLessons;
    final hasLessons = modulesWithLessons.isNotEmpty;

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            color: AppTheme.primaryBlue,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'SLIDE VIEWER',
                      style: GoogleFonts.barlow(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: Colors.white.withOpacity(0.7),
                        letterSpacing: 2,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      widget.course.courseName,
                      style: GoogleFonts.inter(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
                if (hasLessons)
                  Row(
                    children: [
                      ElevatedButton.icon(
                        icon: const Icon(Icons.download, size: 14),
                        label: const Text('Download PPTX'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.accentGreen,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                        ),
                        onPressed: _downloadPptx,
                      ),
                    ],
                  ),
              ],
            ),
          ),

          if (!hasLessons)
            Expanded(
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.slideshow_outlined,
                        size: 56, color: AppTheme.gray.withOpacity(0.4)),
                    const SizedBox(height: 16),
                    Text(
                      'No Slides Available',
                      style: GoogleFonts.inter(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Generate lessons first from the Courses tab,\nthen come back to view slides.',
                      textAlign: TextAlign.center,
                      style: GoogleFonts.barlow(fontSize: 14, color: AppTheme.gray),
                    ),
                  ],
                ),
              ),
            )
          else ...[
            // Module and Lesson selectors
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              decoration: BoxDecoration(
                color: AppTheme.primaryBlue.withOpacity(0.04),
                border: const Border(
                  bottom: BorderSide(color: AppTheme.lightGray, width: 1),
                ),
              ),
              child: Row(
                children: [
                  // Module selector
                  Expanded(
                    child: _SelectorDropdown(
                      label: 'Module',
                      icon: Icons.view_module_rounded,
                      accentColor: AppTheme.primaryBlue,
                      items: modulesWithLessons.asMap().entries.map((e) {
                        return DropdownMenuItem<int>(
                          value: e.key,
                          child: Text(
                            'M${e.key + 1}: ${e.value.title}',
                            overflow: TextOverflow.ellipsis,
                          ),
                        );
                      }).toList(),
                      value: _selectedModuleIdx < modulesWithLessons.length
                          ? _selectedModuleIdx
                          : 0,
                      onChanged: (val) {
                        if (val != null) {
                          setState(() {
                            _selectedModuleIdx = val;
                            _selectedLessonIdx = 0;
                            _currentSlideIdx = 0;
                          });
                          _pageController.jumpToPage(0);
                        }
                      },
                    ),
                  ),
                  const SizedBox(width: 16),
                  // Lesson selector
                  if (_currentModule != null)
                    Expanded(
                      child: _SelectorDropdown(
                        label: 'Lesson',
                        icon: Icons.auto_stories_rounded,
                        accentColor: AppTheme.accentOrange,
                        items: _currentModule!.lessons.asMap().entries.map((e) {
                          return DropdownMenuItem<int>(
                            value: e.key,
                            child: Text(
                              'L${e.key + 1}: ${e.value.lessonTitle}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          );
                        }).toList(),
                        value: _selectedLessonIdx < _currentModule!.lessons.length
                            ? _selectedLessonIdx
                            : 0,
                        onChanged: (val) {
                          if (val != null) {
                            setState(() {
                              _selectedLessonIdx = val;
                              _currentSlideIdx = 0;
                            });
                            _pageController.jumpToPage(0);
                          }
                        },
                      ),
                    ),
                ],
              ),
            ),

            // Slide viewer
            Expanded(
              child: _currentLesson == null || _currentLesson!.slides.isEmpty
                  ? Center(
                      child: Text(
                        'This lesson has no slides.',
                        style: GoogleFonts.barlow(fontSize: 14, color: AppTheme.gray),
                      ),
                    )
                  : KeyboardListener(
                      focusNode: _focusNode,
                      autofocus: true,
                      onKeyEvent: _handleKeyEvent,
                      child: Column(
                        children: [
                          Expanded(
                            child: Padding(
                              padding: const EdgeInsets.fromLTRB(32, 20, 32, 8),
                              child: PageView.builder(
                                controller: _pageController,
                                itemCount: _currentLesson!.slides.length,
                                onPageChanged: (idx) {
                                  setState(() => _currentSlideIdx = idx);
                                },
                                itemBuilder: (context, idx) {
                                  return SlideRenderer(
                                    slide: _currentLesson!.slides[idx],
                                    slideIndex: idx,
                                    totalSlides: _currentLesson!.slides.length,
                                    courseName: widget.course.courseName,
                                    moduleName: _currentModule!.title,
                                    lessonName: _currentLesson!.lessonTitle,
                                    moduleNumber: _currentModule!.moduleNumber,
                                    lessonNumber: _currentLesson!.lessonNumber,
                                  );
                                },
                              ),
                            ),
                          ),

                          // Navigation bar
                          Padding(
                            padding: const EdgeInsets.only(bottom: 16, top: 4),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                // Prev button
                                IconButton(
                                  icon: const Icon(Icons.chevron_left_rounded),
                                  iconSize: 32,
                                  color: _currentSlideIdx > 0
                                      ? AppTheme.primaryBlue
                                      : AppTheme.gray.withOpacity(0.3),
                                  onPressed: _currentSlideIdx > 0
                                      ? () => _goToSlide(_currentSlideIdx - 1)
                                      : null,
                                ),

                                const SizedBox(width: 8),

                                // Dot indicators
                                ...List.generate(
                                  _currentLesson!.slides.length,
                                  (i) => GestureDetector(
                                    onTap: () => _goToSlide(i),
                                    child: AnimatedContainer(
                                      duration: const Duration(milliseconds: 250),
                                      margin: const EdgeInsets.symmetric(horizontal: 4),
                                      width: i == _currentSlideIdx ? 24 : 10,
                                      height: 10,
                                      decoration: BoxDecoration(
                                        borderRadius: BorderRadius.circular(5),
                                        color: i == _currentSlideIdx
                                            ? AppTheme.primaryBlue
                                            : AppTheme.gray.withOpacity(0.3),
                                      ),
                                    ),
                                  ),
                                ),

                                const SizedBox(width: 8),

                                // Next button
                                IconButton(
                                  icon: const Icon(Icons.chevron_right_rounded),
                                  iconSize: 32,
                                  color: _currentSlideIdx < _currentLesson!.slides.length - 1
                                      ? AppTheme.primaryBlue
                                      : AppTheme.gray.withOpacity(0.3),
                                  onPressed: _currentSlideIdx < _currentLesson!.slides.length - 1
                                      ? () => _goToSlide(_currentSlideIdx + 1)
                                      : null,
                                ),

                                const SizedBox(width: 24),

                                // Slide counter
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: AppTheme.primaryBlue.withOpacity(0.08),
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: Text(
                                    'Slide ${_currentSlideIdx + 1} of ${_currentLesson!.slides.length}',
                                    style: GoogleFonts.barlow(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w600,
                                      color: AppTheme.primaryBlue,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),

                          // Speaker Notes / Narration Script Block
                          if (_currentSlideIdx < _currentLesson!.slides.length &&
                              _currentLesson!.slides[_currentSlideIdx].script.isNotEmpty)
                            Container(
                              margin: const EdgeInsets.fromLTRB(32, 0, 32, 20),
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: AppTheme.primaryBlue.withOpacity(0.04),
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: AppTheme.primaryBlue.withOpacity(0.1)),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Row(
                                        children: [
                                          const Icon(Icons.record_voice_over_outlined,
                                              size: 18, color: AppTheme.primaryBlue),
                                          const SizedBox(width: 8),
                                          Text(
                                            'SPEAKER NOTES / NARRATION SCRIPT',
                                            style: GoogleFonts.barlow(
                                              fontSize: 11,
                                              fontWeight: FontWeight.bold,
                                              color: AppTheme.primaryBlue,
                                              letterSpacing: 1.2,
                                            ),
                                          ),
                                        ],
                                      ),
                                      IconButton(
                                        icon: const Icon(Icons.copy, size: 16, color: AppTheme.primaryBlue),
                                        tooltip: 'Copy script to clipboard',
                                        padding: EdgeInsets.zero,
                                        constraints: const BoxConstraints(),
                                        onPressed: () {
                                          Clipboard.setData(ClipboardData(
                                            text: _currentLesson!.slides[_currentSlideIdx].script
                                          ));
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            const SnackBar(content: Text('Script copied to clipboard!')),
                                          );
                                        },
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    _currentLesson!.slides[_currentSlideIdx].script,
                                    style: GoogleFonts.barlow(
                                      fontSize: 13.5,
                                      height: 1.45,
                                      color: AppTheme.textBlack.withOpacity(0.85),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ),
                    ),
            ),
          ],
        ],
      ),
    );
  }
}

// ---- Selector Dropdown ----

class _SelectorDropdown extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color accentColor;
  final List<DropdownMenuItem<int>> items;
  final int value;
  final ValueChanged<int?> onChanged;

  const _SelectorDropdown({
    required this.label,
    required this.icon,
    required this.accentColor,
    required this.items,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            color: accentColor.withOpacity(0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Icon(icon, size: 18, color: accentColor),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: DropdownButtonFormField<int>(
            value: value,
            items: items,
            onChanged: onChanged,
            isExpanded: true,
            style: GoogleFonts.barlow(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.textBlack,
            ),
            decoration: InputDecoration(
              isDense: true,
              contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(6),
                borderSide: BorderSide(color: AppTheme.gray.withOpacity(0.3)),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(6),
                borderSide: BorderSide(color: AppTheme.gray.withOpacity(0.3)),
              ),
              filled: true,
              fillColor: Colors.white,
            ),
          ),
        ),
      ],
    );
  }
}

// ============================================================
// SLIDE RENDERER — renders one slide as a branded 16:9 card
// ============================================================

class SlideRenderer extends StatelessWidget {
  final CourseSlide slide;
  final int slideIndex;
  final int totalSlides;
  final String courseName;
  final String moduleName;
  final String lessonName;
  final int moduleNumber;
  final int lessonNumber;

  const SlideRenderer({
    super.key,
    required this.slide,
    required this.slideIndex,
    required this.totalSlides,
    required this.courseName,
    required this.moduleName,
    required this.lessonName,
    required this.moduleNumber,
    required this.lessonNumber,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: AspectRatio(
        aspectRatio: 16 / 9,
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(8),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.15),
                blurRadius: 20,
                offset: const Offset(0, 6),
              ),
              BoxShadow(
                color: Colors.black.withOpacity(0.05),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Top accent line (cyan)
              Container(height: 4, color: AppTheme.accentCyan),

              // Navy header bar
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 16),
                color: AppTheme.primaryBlue,
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        slide.slideTitle,
                        style: GoogleFonts.inter(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 16),
                    // Module/Lesson badge
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        'M$moduleNumber · L$lessonNumber',
                        style: GoogleFonts.barlow(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: Colors.white.withOpacity(0.8),
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // Content area
              Expanded(
                child: Container(
                  color: const Color(0xFFF8F9FB),
                  padding: const EdgeInsets.fromLTRB(32, 20, 32, 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Slide Body: Bullets on left, Image on right split layout
                      Expanded(
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              flex: slide.images.isNotEmpty ? 60 : 100,
                              child: SingleChildScrollView(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: slide.bullets.map((entry) {
                                    return Padding(
                                      padding: const EdgeInsets.only(bottom: 12),
                                      child: Row(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Padding(
                                            padding: const EdgeInsets.only(top: 7, right: 14),
                                            child: Container(
                                              width: 8,
                                              height: 8,
                                              decoration: BoxDecoration(
                                                color: AppTheme.primaryBlue,
                                                borderRadius: BorderRadius.circular(4),
                                              ),
                                            ),
                                          ),
                                          Expanded(
                                            child: Text(
                                              entry.text,
                                              style: GoogleFonts.barlow(
                                                fontSize: 16,
                                                height: 1.5,
                                                color: const Color(0xFF333333),
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                    );
                                  }).toList(),
                                ),
                              ),
                            ),
                            if (slide.images.isNotEmpty) ...[
                              const SizedBox(width: 24),
                              Expanded(
                                flex: 40,
                                child: Center(
                                  child: ClipRRect(
                                    borderRadius: BorderRadius.circular(4),
                                    child: Image.network(
                                      '${AppConstants.apiBaseUrl}/${slide.images.first.filePath}',
                                      fit: BoxFit.contain,
                                      errorBuilder: (context, error, stackTrace) {
                                        return Container(
                                          decoration: BoxDecoration(
                                            color: AppTheme.lightGray,
                                            borderRadius: BorderRadius.circular(4),
                                            border: Border.all(color: AppTheme.gray.withOpacity(0.3)),
                                          ),
                                          padding: const EdgeInsets.all(16),
                                          child: Column(
                                            mainAxisAlignment: MainAxisAlignment.center,
                                            children: [
                                              const Icon(Icons.broken_image_rounded, color: AppTheme.accentRed, size: 32),
                                              const SizedBox(height: 8),
                                              Text(
                                                'Image failed to load',
                                                textAlign: TextAlign.center,
                                                style: GoogleFonts.barlow(
                                                  fontSize: 12,
                                                  fontWeight: FontWeight.bold,
                                                  color: AppTheme.gray,
                                                ),
                                              ),
                                            ],
                                          ),
                                        );
                                      },
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),

                      const SizedBox(height: 12),

                      // Bottom bar: slide number + course name
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            courseName,
                            style: GoogleFonts.barlow(
                              fontSize: 11,
                              color: AppTheme.gray,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: AppTheme.primaryBlue.withOpacity(0.08),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              '${slideIndex + 1} / $totalSlides',
                              style: GoogleFonts.barlow(
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.primaryBlue,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),

              // Bottom accent bar (navy)
              Container(height: 4, color: AppTheme.primaryBlue),
            ],
          ),
        ),
      ),
    );
  }
}

// ============================================================================
// COURSE QUIZ WIDGET & DATA MODELS
// ============================================================================

class QuizView extends ConsumerStatefulWidget {
  final Course course;

  const QuizView({super.key, required this.course});

  @override
  ConsumerState<QuizView> createState() => _QuizViewState();
}

class _QuizViewState extends ConsumerState<QuizView> {
  int? _selectedModuleIndex;
  
  // Selection and Submission States
  // Keys: "$moduleIndex-$questionIndex"
  final Map<String, String> _selectedOptions = {};
  final Map<String, bool> _submittedQuestions = {};

  @override
  void initState() {
    super.initState();
    _initSelection();
  }

  @override
  void didUpdateWidget(covariant QuizView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.course.id != widget.course.id) {
      _initSelection();
      _selectedOptions.clear();
      _submittedQuestions.clear();
    }
  }

  void _initSelection() {
    _selectedModuleIndex = null;
    for (int i = 0; i < widget.course.modules.length; i++) {
      final m = widget.course.modules[i];
      if (m.quiz != null && m.quiz!['questions'] != null && (m.quiz!['questions'] as List).isNotEmpty) {
        _selectedModuleIndex = i;
        break;
      }
    }
  }

  bool get _hasAnyQuiz => widget.course.modules.any((m) =>
      m.quiz != null && m.quiz!['questions'] != null && (m.quiz!['questions'] as List).isNotEmpty);

  List<int> get _quizModuleIndices {
    final indices = <int>[];
    for (int i = 0; i < widget.course.modules.length; i++) {
      final m = widget.course.modules[i];
      if (m.quiz != null && m.quiz!['questions'] != null && (m.quiz!['questions'] as List).isNotEmpty) {
        indices.add(i);
      }
    }
    return indices;
  }

  @override
  Widget build(BuildContext context) {
    if (!_hasAnyQuiz) {
      return _buildEmptyState(context);
    }

    final isMobile = MediaQuery.of(context).size.width < 900;
    if (isMobile) {
      return _buildMobileLayout(context);
    } else {
      return _buildDesktopLayout(context);
    }
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Container(
        constraints: const BoxConstraints(maxWidth: 550),
        padding: const EdgeInsets.all(40),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: AppTheme.pShapeRadius,
          border: Border.all(color: AppTheme.lightGray, width: 1),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.02),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.primaryBlue.withOpacity(0.08),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.quiz_rounded,
                size: 64,
                color: AppTheme.primaryBlue,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'No Quizzes Generated Yet',
              style: GoogleFonts.inter(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: AppTheme.primaryBlue,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(
              'Test learning outcomes with multiple-choice questions customized to your course difficulty level.\n\nTo generate quizzes:\n1. Go to the Courses tab\n2. Set "Quiz questions" count for each module\n3. Click Save Blueprint\n4. Generate Lessons (if not done already)\n5. Click "Generate Quiz" in the Lessons or Quiz tab',
              style: GoogleFonts.barlow(
                fontSize: 14,
                color: AppTheme.gray,
                height: 1.5,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: () {
                ref.read(currentTabProvider.notifier).state = 1;
              },
              icon: const Icon(Icons.arrow_forward_rounded, size: 16),
              label: const Text('Go to Course Outline'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryBlue,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                elevation: 0,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDesktopLayout(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Left Sidebar for Modules
        SizedBox(
          width: 320,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Quiz Modules',
                style: GoogleFonts.inter(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryBlue,
                ),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: _buildModuleList(context, isMobile: false),
              ),
            ],
          ),
        ),
        const SizedBox(width: 24),
        // Right main quiz pane
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: AppTheme.pShapeRadius,
              border: Border.all(color: AppTheme.lightGray, width: 1),
            ),
            child: _buildQuizDetailPane(context),
          ),
        ),
      ],
    );
  }

  Widget _buildMobileLayout(BuildContext context) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Select Module Quiz',
            style: GoogleFonts.inter(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: AppTheme.primaryBlue,
            ),
          ),
          const SizedBox(height: 8),
          _buildModuleList(context, isMobile: true),
          const SizedBox(height: 16),
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: AppTheme.pShapeRadius,
              border: Border.all(color: AppTheme.lightGray, width: 1),
            ),
            child: _buildQuizDetailPane(context),
          ),
        ],
      ),
    );
  }

  Widget _buildModuleList(BuildContext context, {required bool isMobile}) {
    final indices = _quizModuleIndices;
    return ListView.builder(
      shrinkWrap: isMobile,
      physics: isMobile ? const NeverScrollableScrollPhysics() : const ClampingScrollPhysics(),
      itemCount: indices.length,
      itemBuilder: (context, index) {
        final modIndex = indices[index];
        final m = widget.course.modules[modIndex];
        final isSelected = _selectedModuleIndex == modIndex;
        final qList = m.quiz!['questions'] as List;

        // Calculate completed/correct stats
        int completedCount = 0;
        int correctCount = 0;
        for (int qIdx = 0; qIdx < qList.length; qIdx++) {
          final key = "$modIndex-$qIdx";
          if (_submittedQuestions[key] == true) {
            completedCount++;
            final qJson = qList[qIdx] as Map<String, dynamic>;
            final correctOpt = qJson['correct_option']?.toString() ?? '';
            if (_selectedOptions[key] == correctOpt) {
              correctCount++;
            }
          }
        }

        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          decoration: BoxDecoration(
            color: isSelected ? AppTheme.primaryBlue.withOpacity(0.06) : Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: isSelected ? AppTheme.primaryBlue : AppTheme.lightGray,
              width: isSelected ? 1.5 : 1,
            ),
          ),
          child: ListTile(
            dense: true,
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            title: Text(
              'Module ${m.moduleNumber}',
              style: GoogleFonts.inter(
                fontWeight: FontWeight.bold,
                fontSize: 12,
                color: isSelected ? AppTheme.primaryBlue : AppTheme.gray,
              ),
            ),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 4),
                Text(
                  m.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                    color: AppTheme.textBlack,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '${qList.length} MCQ questions',
                      style: GoogleFonts.barlow(
                        fontSize: 12,
                        color: AppTheme.gray,
                      ),
                    ),
                    if (completedCount > 0)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: completedCount == qList.length
                              ? AppTheme.accentGreen.withOpacity(0.12)
                              : AppTheme.accentOrange.withOpacity(0.12),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          completedCount == qList.length
                              ? 'Score: $correctCount/${qList.length}'
                              : '$completedCount/${qList.length} Done',
                          style: GoogleFonts.barlow(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: completedCount == qList.length
                                ? AppTheme.accentGreen
                                : AppTheme.accentOrange,
                          ),
                        ),
                      ),
                  ],
                ),
              ],
            ),
            onTap: () {
              setState(() {
                _selectedModuleIndex = modIndex;
              });
            },
          ),
        );
      },
    );
  }

  Widget _buildQuizDetailPane(BuildContext context) {
    if (_selectedModuleIndex == null) {
      return const Center(child: Padding(
        padding: EdgeInsets.all(24.0),
        child: Text('Select a module quiz to begin.'),
      ));
    }

    final moduleIndex = _selectedModuleIndex!;
    final module = widget.course.modules[moduleIndex];

    if (module.quiz == null || module.quiz!['questions'] == null) {
      return const Center(child: Padding(
        padding: EdgeInsets.all(24.0),
        child: Text('No quiz questions for this module.'),
      ));
    }

    final questionsList = module.quiz!['questions'] as List;

    // Calculate module quiz stats
    int submittedCount = 0;
    int correctCount = 0;
    for (int i = 0; i < questionsList.length; i++) {
      final key = "$moduleIndex-$i";
      if (_submittedQuestions[key] == true) {
        submittedCount++;
        final qJson = questionsList[i] as Map<String, dynamic>;
        final correctOpt = qJson['correct_option']?.toString() ?? '';
        if (_selectedOptions[key] == correctOpt) {
          correctCount++;
        }
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Module Quiz Header
        Container(
          padding: const EdgeInsets.all(20),
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: AppTheme.lightGray, width: 1)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Module ${module.moduleNumber} Quiz',
                      style: GoogleFonts.inter(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      module.title,
                      style: GoogleFonts.barlow(
                        fontSize: 14,
                        color: AppTheme.gray,
                      ),
                    ),
                  ],
                ),
              ),
              // Difficulty level chip
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: _getDifficultyColor(widget.course.courseDifficulty).withOpacity(0.12),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  widget.course.courseDifficulty.toUpperCase(),
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: _getDifficultyColor(widget.course.courseDifficulty),
                  ),
                ),
              ),
            ],
          ),
        ),

        // Question List
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(20),
            itemCount: questionsList.length + 1, // +1 for summary card
            itemBuilder: (context, index) {
              if (index == questionsList.length) {
                return _buildSummaryCard(moduleIndex, questionsList.length, submittedCount, correctCount);
              }

              final qJson = questionsList[index] as Map<String, dynamic>;
              final question = QuizQuestion.fromJson(qJson);

              return _buildQuestionCard(moduleIndex, index, question);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildQuestionCard(int moduleIndex, int questionIndex, QuizQuestion question) {
    final key = "$moduleIndex-$questionIndex";
    final selectedOption = _selectedOptions[key];
    final isSubmitted = _submittedQuestions[key] == true;

    return Container(
      margin: const EdgeInsets.only(bottom: 24),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.lightGray, width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.01),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Question number
          Text(
            'QUESTION ${questionIndex + 1}',
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: AppTheme.primaryBlue.withOpacity(0.7),
              letterSpacing: 1.0,
          ),
          ),
          const SizedBox(height: 8),
          // Question text
          Text(
            question.questionText,
            style: GoogleFonts.inter(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: AppTheme.textBlack,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 16),

          // MCQ Options
          ...question.options.map((opt) {
            final optKey = opt.key; // "A", "B", "C", "D"
            final isOptSelected = selectedOption == optKey;
            final isCorrectOpt = question.correctOption == optKey;

            Color cardBorderColor = AppTheme.lightGray;
            Color cardBgColor = Colors.white;
            Widget? suffixIcon;

            if (isSubmitted) {
              if (isCorrectOpt) {
                cardBorderColor = AppTheme.accentGreen;
                cardBgColor = AppTheme.accentGreen.withOpacity(0.08);
                suffixIcon = const Icon(Icons.check_circle_rounded, color: AppTheme.accentGreen, size: 18);
              } else if (isOptSelected) {
                cardBorderColor = AppTheme.accentRed;
                cardBgColor = AppTheme.accentRed.withOpacity(0.08);
                suffixIcon = const Icon(Icons.cancel_rounded, color: AppTheme.accentRed, size: 18);
              } else {
                cardBgColor = Colors.grey.shade50;
              }
            } else if (isOptSelected) {
              cardBorderColor = AppTheme.primaryBlue;
              cardBgColor = AppTheme.primaryBlue.withOpacity(0.05);
            }

            return Container(
              margin: const EdgeInsets.only(bottom: 10),
              child: InkWell(
                onTap: isSubmitted
                    ? null
                    : () {
                        setState(() {
                          _selectedOptions[key] = optKey;
                        });
                      },
                borderRadius: BorderRadius.circular(8),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: cardBgColor,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: cardBorderColor,
                      width: isOptSelected || (isSubmitted && isCorrectOpt) ? 1.5 : 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      // Key indicator: A, B, C, D
                      Container(
                        width: 24,
                        height: 24,
                        decoration: BoxDecoration(
                          color: isOptSelected
                              ? (isSubmitted
                                  ? (isCorrectOpt ? AppTheme.accentGreen : AppTheme.accentRed)
                                  : AppTheme.primaryBlue)
                              : (isSubmitted && isCorrectOpt
                                  ? AppTheme.accentGreen
                                  : Colors.grey.shade100),
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: isOptSelected || (isSubmitted && isCorrectOpt)
                                ? Colors.transparent
                                : Colors.grey.shade300,
                          ),
                        ),
                        child: Center(
                          child: Text(
                            optKey,
                            style: GoogleFonts.inter(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: isOptSelected || (isSubmitted && isCorrectOpt)
                                  ? Colors.white
                                  : AppTheme.textBlack,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      // Option text
                      Expanded(
                        child: Text(
                          opt.text,
                          style: GoogleFonts.inter(
                            fontSize: 14,
                            fontWeight: isOptSelected ? FontWeight.w600 : FontWeight.w500,
                            color: isSubmitted && !isCorrectOpt && !isOptSelected
                                ? AppTheme.gray
                                : AppTheme.textBlack,
                          ),
                        ),
                      ),
                      if (suffixIcon != null) ...[
                        const SizedBox(width: 10),
                        suffixIcon,
                      ],
                    ],
                  ),
                ),
              ),
            );
          }).toList(),

          const SizedBox(height: 12),
          // Action Button or Explanation Panel
          if (!isSubmitted)
            Align(
              alignment: Alignment.centerRight,
              child: ElevatedButton(
                onPressed: selectedOption == null
                    ? null
                    : () {
                        setState(() {
                          _submittedQuestions[key] = true;
                        });
                      },
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryBlue,
                  foregroundColor: Colors.white,
                  disabledBackgroundColor: Colors.grey.shade200,
                  disabledForegroundColor: Colors.grey.shade400,
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                  elevation: 0,
                ),
                child: const Text('Check Answer'),
              ),
            )
          else ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.grey.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.grey.shade200),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.info_outline_rounded,
                    color: AppTheme.primaryBlue.withOpacity(0.8),
                    size: 20,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Explanation',
                          style: GoogleFonts.inter(
                            fontWeight: FontWeight.bold,
                            fontSize: 13,
                            color: AppTheme.textBlack,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          question.explanation,
                          style: GoogleFonts.inter(
                            fontSize: 13,
                            color: AppTheme.gray,
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSummaryCard(int moduleIndex, int totalQuestions, int submittedCount, int correctCount) {
    final isFinished = submittedCount == totalQuestions;

    return Container(
      margin: const EdgeInsets.only(top: 8, bottom: 40),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [AppTheme.primaryBlue, AppTheme.primaryBlue.withOpacity(0.85)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primaryBlue.withOpacity(0.2),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Quiz Progress',
                    style: GoogleFonts.inter(
                      color: Colors.white70,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    isFinished ? 'Completed!' : 'In Progress',
                    style: GoogleFonts.inter(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.15),
                  shape: BoxShape.circle,
                ),
                child: Text(
                  '$correctCount / $totalQuestions',
                  style: GoogleFonts.inter(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: LinearProgressIndicator(
              value: totalQuestions > 0 ? (submittedCount / totalQuestions) : 0,
              backgroundColor: Colors.white24,
              valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
              minHeight: 8,
            ),
          ),
          const SizedBox(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              OutlinedButton.icon(
                onPressed: () {
                  setState(() {
                    for (int i = 0; i < totalQuestions; i++) {
                      final key = "$moduleIndex-$i";
                      _selectedOptions.remove(key);
                      _submittedQuestions.remove(key);
                    }
                  });
                },
                icon: const Icon(Icons.refresh_rounded, size: 16),
                label: const Text('Reset Quiz'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Colors.white60),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Color _getDifficultyColor(String difficulty) {
    switch (difficulty.toLowerCase()) {
      case 'easy':
        return AppTheme.accentGreen;
      case 'medium':
        return AppTheme.accentOrange;
      case 'hard':
        return AppTheme.accentRed;
      default:
        return AppTheme.gray;
    }
  }
}

// ============================================================================
// DATA MODELS FOR QUIZ
// ============================================================================

class QuizQuestion {
  final String questionText;
  final List<QuizOption> options;
  final String correctOption;
  final String explanation;

  QuizQuestion({
    required this.questionText,
    required this.options,
    required this.correctOption,
    required this.explanation,
  });

  factory QuizQuestion.fromJson(Map<String, dynamic> json) {
    return QuizQuestion(
      questionText: json['question_text']?.toString() ?? '',
      options: (json['options'] as List? ?? [])
          .map((o) => QuizOption.fromJson(o as Map<String, dynamic>))
          .toList(),
      correctOption: json['correct_option']?.toString() ?? '',
      explanation: json['explanation']?.toString() ?? '',
    );
  }
}

class QuizOption {
  final String key;
  final String text;

  QuizOption({required this.key, required this.text});

  factory QuizOption.fromJson(Map<String, dynamic> json) {
    return QuizOption(
      key: json['key']?.toString() ?? '',
      text: json['text']?.toString() ?? '',
    );
  }
}

