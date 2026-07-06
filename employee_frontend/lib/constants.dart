class AppConstants {
  // Base API URL. Can be overridden using environment variables in flutter run / build.
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const String uploadEndpoint = '$apiBaseUrl/api/upload';
  static const String listFilesEndpoint = '$apiBaseUrl/api/files';
  static const String generateCourseEndpoint = '$apiBaseUrl/api/courses/generate';
  static const String listCoursesEndpoint = '$apiBaseUrl/api/courses';
  static const String employeeCoursesEndpoint = '$apiBaseUrl/api/employee/courses';
  static const String employeeCoursesWsEndpoint = 'ws://localhost:8000/api/employee/courses/ws';
  
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
