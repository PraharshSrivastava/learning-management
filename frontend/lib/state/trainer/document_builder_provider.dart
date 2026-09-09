import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:frontend/core/config/app_constants.dart';
import 'package:frontend/data/models/models.dart';
import 'package:frontend/features/document_builder/document_builder_models.dart';
import 'package:frontend/state/trainer_providers.dart';

class DocumentBuilderApi {
  final Ref ref;
  const DocumentBuilderApi(this.ref);
  Map<String, String> get _headers => {
        ...ref.read(trainerAuthHeadersProvider),
        'Content-Type': 'application/json'
      };
  Future<Map<String, dynamic>> build(
      {required String message,
      required List<String> instructions,
      required String currentDraft,
      required DocumentBuilderSettings settings}) async {
    final response =
        await http.post(Uri.parse(AppConstants.documentBuilderBuildEndpoint),
            headers: _headers,
            body: jsonEncode({
              'message': message,
              'instructions': instructions,
              'currentDraft': currentDraft,
              'builderSettings': settings.toJson()
            }));
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    if (response.statusCode != 200) {
      throw Exception(body['detail'] ?? body['error'] ?? 'LLM request failed');
    }
    return body;
  }

  Map<String, dynamic> _pdfPayload(DocumentBuilderMetadata metadata,
          String document, List<DocumentBuilderBlock> blocks) =>
      {
        'metadata': metadata.toJson(),
        'document': document,
        'documentBlocks': blocks.map((block) => block.toJson()).toList()
      };
  Future<Uint8List> render(DocumentBuilderMetadata metadata, String document,
      List<DocumentBuilderBlock> blocks) async {
    final response = await http.post(
        Uri.parse(AppConstants.documentBuilderRenderEndpoint),
        headers: _headers,
        body: jsonEncode(_pdfPayload(metadata, document, blocks)));
    if (response.statusCode != 200) {
      final body = jsonDecode(response.body);
      throw Exception(body['detail'] ?? 'PDF render failed');
    }
    return response.bodyBytes;
  }

  Future<PDFFile> save(DocumentBuilderMetadata metadata, String document,
      List<DocumentBuilderBlock> blocks) async {
    final response = await http.post(
        Uri.parse(AppConstants.documentBuilderSaveEndpoint),
        headers: _headers,
        body: jsonEncode(_pdfPayload(metadata, document, blocks)));
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    if (response.statusCode != 200) {
      throw Exception(body['detail'] ?? 'PDF save failed');
    }
    final file = PDFFile.fromJson(body['file'] as Map<String, dynamic>);
    await ref.read(fileListProvider.notifier).fetchFiles();
    ref.read(selectedFileProvider.notifier).state = file;
    return file;
  }
}

final documentBuilderApiProvider =
    Provider<DocumentBuilderApi>((ref) => DocumentBuilderApi(ref));
final documentBuilderVisibleProvider = StateProvider<bool>((ref) => false);
