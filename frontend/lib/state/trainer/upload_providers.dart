part of '../trainer_providers.dart';

enum UploadStatus { idle, uploading, success, error }

class UploadProgressState {
  final UploadStatus status;
  final String? message;

  UploadProgressState({required this.status, this.message});
}

class UploadProgressNotifier extends StateNotifier<UploadProgressState> {
  UploadProgressNotifier()
      : super(UploadProgressState(status: UploadStatus.idle));

  Future<void> uploadFile(PlatformFile file, WidgetRef ref) async {
    state = UploadProgressState(status: UploadStatus.uploading);
    try {
      final bytes = file.bytes;
      if (bytes == null) {
        state = UploadProgressState(
            status: UploadStatus.error, message: 'Could not read file data.');
        return;
      }

      final request =
          http.MultipartRequest('POST', Uri.parse(AppConstants.uploadEndpoint));
      request.headers.addAll(ref.read(trainerAuthHeadersProvider));
      final multipartFile =
          http.MultipartFile.fromBytes('file', bytes, filename: file.name);
      request.files.add(multipartFile);

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        state = UploadProgressState(
            status: UploadStatus.success, message: 'Uploaded successfully!');
        ref.read(fileListProvider.notifier).fetchFiles();
      } else {
        final errorMsg =
            jsonDecode(response.body)['detail'] ?? 'Upload failed.';
        state = UploadProgressState(
            status: UploadStatus.error, message: errorMsg.toString());
      }
    } catch (e) {
      state = UploadProgressState(
          status: UploadStatus.error, message: 'Upload error: ${e.toString()}');
    }
  }
}

final uploadProgressProvider =
    StateNotifierProvider<UploadProgressNotifier, UploadProgressState>((ref) {
  return UploadProgressNotifier();
});
