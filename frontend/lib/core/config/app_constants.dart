import 'package:flutter_dotenv/flutter_dotenv.dart';

import 'lms_runtime_urls.dart';

class AppConstants {
  static String? mediaTicket;
  static String protectedUrl(String url) {
    if (mediaTicket == null || mediaTicket!.isEmpty) return url;
    final uri = Uri.parse(url);
    final api = Uri.base.resolve(apiBaseUrl);
    if (uri.hasAuthority && uri.authority != api.authority) return url;
    if (uri.hasScheme && !{'http', 'https'}.contains(uri.scheme)) return url;
    return uri.replace(queryParameters: {...uri.queryParameters, 'media_ticket': mediaTicket!}).toString();
  }
  static LmsRuntimeUrls get runtimeUrls => LmsRuntimeUrls(
        entrypoint: Uri.base,
        publicMount: '/lms/trainer',
        configuredApiBase: dotenv.env['API_BASE_URL'] ?? '',
      );

  static String get apiBaseUrl => runtimeUrls.apiBaseUrl;

  static String get uploadEndpoint => '$apiBaseUrl/api/upload';
  static String get listFilesEndpoint => '$apiBaseUrl/api/files';
  static String get documentBuilderBuildEndpoint =>
      '$apiBaseUrl/api/document-builder/build-document';
  static String get documentBuilderRenderEndpoint =>
      '$apiBaseUrl/api/document-builder/render-pdf';
  static String get documentBuilderSaveEndpoint =>
      '$apiBaseUrl/api/document-builder/save-pdf';
  static String get generateCourseEndpoint =>
      '$apiBaseUrl/api/courses/generate';
  static String get listCoursesEndpoint => '$apiBaseUrl/api/courses';
  static String get assignableCoursesEndpoint =>
      '$apiBaseUrl/api/assignment/courses';
  static String get assignmentOptionsEndpoint =>
      '$apiBaseUrl/api/assignment/options';
  static String get savedAssignmentGroupsEndpoint =>
      '$apiBaseUrl/api/assignment/saved-groups';
  static String get trainerPerformanceEndpoint =>
      '$apiBaseUrl/api/trainer/performance';
  static String get hubSessionEndpoint => '$apiBaseUrl/api/hub/session/trainer';
  static String get hubLogoutEndpoint => '$apiBaseUrl/api/hub/logout/trainer';
  static String get trainerListEndpoint =>
      '$apiBaseUrl/api/auth/local/trainers';
  static String get trainerLocalLoginEndpoint =>
      '$apiBaseUrl/api/auth/local/trainer-login';

  static String viewFileUrl(String filename) =>
      protectedUrl('$apiBaseUrl/api/files/${Uri.encodeComponent(filename)}');
  static String previewFileUrl(String filename) =>
      protectedUrl('$apiBaseUrl/api/files/${Uri.encodeComponent(filename)}/preview');
  static String assetUrl(String path) => protectedUrl('$apiBaseUrl/${path.replaceFirst(RegExp(r'^/'), '')}');
  static String videoAssetUrl(String videoPath) {
    if (videoPath.startsWith('http')) return protectedUrl(videoPath);
    final path = videoPath.startsWith('/') ? videoPath : '/$videoPath';
    return protectedUrl('$apiBaseUrl$path');
  }

  static String hlsVideoAssetUrl(String videoPath) {
    final hlsPath = videoPath.replaceFirst(
      RegExp(r'\.mp4$', caseSensitive: false),
      '_hls/master.m3u8',
    );
    return videoAssetUrl(hlsPath);
  }

  static String updateCourseEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id';
  static String courseDetailEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id';
  static String deleteCourseEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id';
  static String courseAssignmentEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/assignment';
  static String publishCourseAssignmentEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/publish-assignment';
  static String disableCourseAssignmentEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/disable-assignment';
  static String savedAssignmentGroupEndpoint(String id) =>
      '$apiBaseUrl/api/assignment/saved-groups/$id';
  static String generateSlidesEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/generate-slides';
  static String generateScriptsEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/generate-scripts';
  static String generateFullCourseEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/generate-full-course';
  static String generationJobEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/generation-jobs';
  static String generationJobStatusEndpoint(String id) =>
      '$apiBaseUrl/api/generation-jobs/$id';
  static String continueGenerationEndpoint(String id) =>
      '$apiBaseUrl/api/courses/$id/continue-generation';
  static String moduleQuizEndpoint(String id, int moduleNumber) =>
      '$apiBaseUrl/api/courses/$id/modules/$moduleNumber/quiz';
  static String slideshowHtmlUrl(String courseId, int moduleNum) =>
      protectedUrl('$apiBaseUrl/assets/slides/$courseId/module_$moduleNum.html');
}
