part of '../trainer_providers.dart';

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
  final Ref ref;

  FileListNotifier(this.ref) : super(FileListState()) {
    if (ref.read(trainerAuthProvider).isAuthenticated) {
      fetchFiles();
    }
  }

  Future<void> fetchFiles() async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await http.get(
        Uri.parse(AppConstants.listFilesEndpoint),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode == 200) {
        final List<dynamic> decoded = jsonDecode(response.body);
        final List<PDFFile> fileList =
            decoded.map((item) => PDFFile.fromJson(item)).toList();
        state = FileListState(files: fileList, isLoading: false);
      } else {
        state = FileListState(
            files: [],
            isLoading: false,
            error: 'Server returned ${response.statusCode}');
      }
    } catch (e) {
      state = FileListState(files: [], isLoading: false, error: e.toString());
    }
  }
}

final fileListProvider =
    StateNotifierProvider<FileListNotifier, FileListState>((ref) {
  return FileListNotifier(ref);
});
