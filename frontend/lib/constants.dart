import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConstants {
  static String get apiBaseUrl => dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000';

  static String get uploadEndpoint => '$apiBaseUrl/api/upload';
  static String get listFilesEndpoint => '$apiBaseUrl/api/files';
  static String get generateCourseEndpoint => '$apiBaseUrl/api/courses/generate';
  static String get listCoursesEndpoint => '$apiBaseUrl/api/courses';
  static String get assignableCoursesEndpoint => '$apiBaseUrl/api/assignment/courses';
  static String get assignmentOptionsEndpoint => '$apiBaseUrl/api/assignment/options';
  static String get trainerPerformanceEndpoint => '$apiBaseUrl/api/trainer/performance';

  
  static String viewFileUrl(String filename) => '$apiBaseUrl/api/files/$filename';
  static String updateCourseEndpoint(String id) => '$apiBaseUrl/api/courses/$id';
  static String courseAssignmentEndpoint(String id) => '$apiBaseUrl/api/courses/$id/assignment';
  static String publishCourseAssignmentEndpoint(String id) => '$apiBaseUrl/api/courses/$id/publish-assignment';
  static String generateLessonsEndpoint(String id) => '$apiBaseUrl/api/courses/$id/generate-lessons';
  static String refineBulletsEndpoint(String id) => '$apiBaseUrl/api/courses/$id/refine-bullets';
  static String generateSlidesEndpoint(String id) => '$apiBaseUrl/api/courses/$id/generate-slides';
  static String generateScriptsEndpoint(String id) => '$apiBaseUrl/api/courses/$id/generate-scripts';
  static String generateFullCourseEndpoint(String id) => '$apiBaseUrl/api/courses/$id/generate-full-course';
  static String moduleQuizEndpoint(String id, int moduleNumber) =>
      '$apiBaseUrl/api/courses/$id/modules/$moduleNumber/quiz';
  static String slideshowHtmlUrl(String courseId, int moduleNum) => '$apiBaseUrl/assets/slides/$courseId/module_$moduleNum.html';
}
