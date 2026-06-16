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
  
  static String viewFileUrl(String filename) => '$apiBaseUrl/api/files/$filename';
  static String updateCourseEndpoint(String id) => '$apiBaseUrl/api/courses/$id';
  static String generateLessonsEndpoint(String id) => '$apiBaseUrl/api/courses/$id/generate-lessons';
  static String refineBulletsEndpoint(String id) => '$apiBaseUrl/api/courses/$id/refine-bullets';
  static String generateScriptsEndpoint(String id) => '$apiBaseUrl/api/courses/$id/generate-scripts';
  static String generateSlidesEndpoint(String id) => '$apiBaseUrl/api/courses/$id/generate-slides';
  static String downloadSlideEndpoint(String id, int moduleIdx, int lessonIdx) =>
      '$apiBaseUrl/api/courses/$id/slides/$moduleIdx/$lessonIdx';
  static String listSlidesEndpoint(String id) => '$apiBaseUrl/api/courses/$id/slides';
}
