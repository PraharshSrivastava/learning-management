import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConstants {
  static String get apiBaseUrl => dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000';

  static String get uploadEndpoint => '$apiBaseUrl/api/upload';
  static String get listFilesEndpoint => '$apiBaseUrl/api/files';
  static String get generateCourseEndpoint => '$apiBaseUrl/api/courses/generate';
  static String get listCoursesEndpoint => '$apiBaseUrl/api/courses';
  static String get employeeCoursesEndpoint => '$apiBaseUrl/api/employee/courses';

  static String get employeeCoursesWsEndpoint {
    final wsBase = apiBaseUrl.replaceFirst('http://', 'ws://').replaceFirst('https://', 'wss://');
    return '$wsBase/api/employee/courses/ws';
  }
  
  static String viewFileUrl(String filename) => '$apiBaseUrl/api/files/$filename';
  static String videoAssetUrl(String videoPath) {
    if (videoPath.startsWith('http')) return videoPath;
    final path = videoPath.startsWith('/') ? videoPath : '/$videoPath';
    return '$apiBaseUrl$path';
  }
  static String updateCourseEndpoint(String id) => '$apiBaseUrl/api/courses/$id';
  static String updateEmployeeCourseStatusEndpoint(String id) => '$apiBaseUrl/api/employee/courses/$id/status';
  static String generateLessonsEndpoint(String id) => '$apiBaseUrl/api/courses/$id/generate-lessons';
  static String refineBulletsEndpoint(String id) => '$apiBaseUrl/api/courses/$id/refine-bullets';
  static String generateSlidesEndpoint(String id) => '$apiBaseUrl/api/courses/$id/generate-slides';
  static String generateScriptsEndpoint(String id) => '$apiBaseUrl/api/courses/$id/generate-scripts';
  static String generateFullCourseEndpoint(String id) => '$apiBaseUrl/api/courses/$id/generate-full-course';
  static String slideshowHtmlUrl(String courseId, int moduleNum) => '$apiBaseUrl/assets/slides/$courseId/module_$moduleNum.html';
}
