import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConstants {
  static String get apiBaseUrl {
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
  static String get employeesEndpoint => '$apiBaseUrl/api/employees';
  static String get hubSessionEndpoint => '$apiBaseUrl/api/hub/session/employee';
  static String get hubLogoutEndpoint => '$apiBaseUrl/api/hub/logout/employee';
  static String get demoLoginEndpoint => '$apiBaseUrl/api/auth/demo-login';
  static String get meEndpoint => '$apiBaseUrl/api/me';
  static String get myCoursesEndpoint => '$apiBaseUrl/api/me/courses';

  static String myCoursesWsEndpoint(String token) {
    final wsBase = apiBaseUrl.isEmpty
        ? '${Uri.base.scheme == 'https' ? 'wss' : 'ws'}://${Uri.base.authority}'
        : apiBaseUrl
            .replaceFirst('http://', 'ws://')
            .replaceFirst('https://', 'wss://');
    return '$wsBase/api/me/courses/ws?token=$token';
  }

  static String viewFileUrl(String filename) =>
      '$apiBaseUrl/api/files/$filename';
  static String previewFileUrl(String filename) =>
      '$apiBaseUrl/api/files/$filename/preview';
  static String videoAssetUrl(String videoPath) {
    if (videoPath.startsWith('http')) return videoPath;
    final path = videoPath.startsWith('/') ? videoPath : '/$videoPath';
    return '$apiBaseUrl$path';
  }

  static String assetUrl(String assetPath) {
    if (assetPath.startsWith('http')) return assetPath;
    final path = assetPath.startsWith('/') ? assetPath : '/$assetPath';
    return '$apiBaseUrl$path';
  }

  static String updateCourseEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id';
  static String updateMyCourseStatusEndpoint(String id) =>
      '$apiBaseUrl/api/me/courses/$id/status';
  static String updateMyModuleProgressEndpoint(
          String courseId, int moduleNumber) =>
      '$apiBaseUrl/api/me/courses/$courseId/modules/$moduleNumber';
  static String generateLessonsEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/generate-lessons';
  static String refineBulletsEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/refine-bullets';
  static String generateSlidesEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/generate-slides';
  static String generateScriptsEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/generate-scripts';
  static String generateFullCourseEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/generate-full-course';
  static String slideshowHtmlUrl(String courseId, int moduleNum) =>
      '$apiBaseUrl/assets/slides/$courseId/module_$moduleNum.html';
}
