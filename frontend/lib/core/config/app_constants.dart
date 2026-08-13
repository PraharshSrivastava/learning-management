import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConstants {
  static String get apiBaseUrl {
    if (dotenv.env['USE_SAME_ORIGIN_API']?.toLowerCase() == 'true') {
      return '';
    }
    final configured = dotenv.env['API_BASE_URL'];
    if (configured != null && configured.trim().isNotEmpty) {
      return configured.trim();
    }
    return '';
  }

  static String get uploadEndpoint => '$apiBaseUrl/api/upload';
  static String get listFilesEndpoint => '$apiBaseUrl/api/files';
  static String get generateCourseEndpoint =>
      '$apiBaseUrl/api/courses/generate';
  static String get listCoursesEndpoint => '$apiBaseUrl/api/courses';
  static String get assignableCoursesEndpoint =>
      '$apiBaseUrl/api/assignment/courses';
  static String get assignmentOptionsEndpoint =>
      '$apiBaseUrl/api/assignment/options';
  static String get trainerPerformanceEndpoint =>
      '$apiBaseUrl/api/trainer/performance';
  static String get hubSessionEndpoint => '$apiBaseUrl/api/hub/session/trainer';
  static String get hubLogoutEndpoint => '$apiBaseUrl/api/hub/logout/trainer';
  static String get trainerListEndpoint => '$apiBaseUrl/api/auth/trainers';
  static String get trainerDemoLoginEndpoint =>
      '$apiBaseUrl/api/auth/trainer-demo-login';

  static String viewFileUrl(String filename) =>
      '$apiBaseUrl/api/files/$filename';
  static String previewFileUrl(String filename) =>
      '$apiBaseUrl/api/files/$filename/preview';
  static String updateCourseEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id';
  static String courseAssignmentEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/assignment';
  static String publishCourseAssignmentEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/publish-assignment';
  static String disableCourseAssignmentEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/disable-assignment';
  static String generateSlidesEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/generate-slides';
  static String generateScriptsEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/generate-scripts';
  static String generateFullCourseEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/generate-full-course';
  static String continueGenerationEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/continue-generation';
  static String moduleQuizEndpoint(String id, int moduleNumber) =>
      '$apiBaseUrl/api/courses/$id/modules/$moduleNumber/quiz';
  static String slideshowHtmlUrl(String courseId, int moduleNum) =>
      '$apiBaseUrl/assets/slides/$courseId/module_$moduleNum.html';
}
