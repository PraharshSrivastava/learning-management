import 'dart:async';
import 'dart:convert';
import 'package:crypto/crypto.dart' as crypto;
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:frontend/core/config/app_constants.dart';

class WorkflowApi {
  final Map<String, String> Function() headers;
  final http.Client client;
  WorkflowApi(this.headers, {http.Client? client})
      : client = client ?? http.Client();
  String get base => '${AppConstants.apiBaseUrl}/api/document-builder';
  Future<dynamic> call(String path,
      {String method = 'GET', Object? body}) async {
    final request = http.Request(method, Uri.parse('$base$path'));
    request.headers.addAll({...headers(), 'Content-Type': 'application/json'});
    if (body != null) request.body = jsonEncode(body);
    final response = await http.Response.fromStream(await client.send(request))
        .timeout(const Duration(seconds: 120));
    dynamic decoded;
    try {
      decoded = jsonDecode(response.body);
    } catch (_) {
      decoded = null;
    }
    if (response.statusCode >= 400) {
      final detail = decoded is Map ? decoded['detail'] : null;
      throw WorkflowError(
          response.statusCode,
          detail is String
              ? detail
              : 'Request failed (${response.statusCode}). Your draft is retained.');
    }
    return decoded;
  }

  Future<Uint8List> bytes(String path, {Object? body}) async {
    final request =
        http.Request(body == null ? 'GET' : 'POST', Uri.parse('$base$path'));
    request.headers.addAll({...headers(), 'Content-Type': 'application/json'});
    if (body != null) request.body = jsonEncode(body);
    final response = await http.Response.fromStream(await client.send(request))
        .timeout(const Duration(seconds: 120));
    if (response.statusCode >= 400) {
      dynamic decoded;
      try {
        decoded = jsonDecode(response.body);
      } catch (_) {}
      throw WorkflowError(
          response.statusCode,
          decoded is Map && decoded['detail'] is String
              ? decoded['detail']
              : 'Document request failed');
    }
    return response.bodyBytes;
  }

  void dispose() => client.close();
}

class WorkflowError implements Exception {
  final int status;
  final String message;
  WorkflowError(this.status, this.message);
  @override
  String toString() => message;
}

class DocumentWorkflowController extends ChangeNotifier {
  final WorkflowApi api;
  Map<String, dynamic>? draft;
  Map<String, dynamic>? operation;
  List<dynamic> sources = [];
  String saveStatus = 'Saved';
  String? error;
  bool busy = false, conflict = false, _disposed = false;
  int _epoch = 0, _savedEpoch = 0;
  Timer? _debounce;
  Future<void>? _saving;
  DocumentWorkflowController(this.api);
  String get id => draft!['id'];
  int get revision => draft!['revision'];
  Map<String, dynamic> get content => draft!['content'];
  List<dynamic> get modules => content['modules'];
  void announce() {
    if (!_disposed) notifyListeners();
  }

  Future<void> create(String mode) async {
    draft = Map<String, dynamic>.from(
        await api.call('/drafts', method: 'POST', body: {
      'entryMode': mode,
      'settings': {
        'writingFocus': 'practical',
        'includeBadGood': false,
        'includeMistakes': false
      }
    }));
    sources = [];
    operation = null;
    _epoch = 0;
    _savedEpoch = 0;
    error = null;
    conflict = false;
    announce();
  }

  Future<void> open(String draftId) async {
    draft = Map<String, dynamic>.from(await api.call('/drafts/$draftId'));
    sources = await api.call('/drafts/$draftId/sources');
    final operations = await api.call('/drafts/$draftId/operations') as List;
    operation = operations
        .where((item) =>
            ['proposed', 'queued', 'running'].contains(item['status']))
        .firstOrNull;
    _epoch = 0;
    _savedEpoch = 0;
    error = null;
    conflict = false;
    saveStatus = 'Saved';
    announce();
    if (operation != null &&
        ['queued', 'running'].contains(operation!['status'])) {
      final operationId = operation!['id'];
      while (
          !_disposed && ['queued', 'running'].contains(operation!['status'])) {
        await Future<void>.delayed(const Duration(seconds: 1));
        if (_disposed) return;
        operation = Map<String, dynamic>.from(
            await api.call('/drafts/$draftId/operations/$operationId'));
        announce();
      }
      draft = Map<String, dynamic>.from(await api.call('/drafts/$draftId'));
      sources = await api.call('/drafts/$draftId/sources');
      if (operation!['status'] == 'failed') error = operation!['error'];
      announce();
    }
  }

  void change(void Function(Map<String, dynamic>) edit) {
    edit(content);
    _epoch++;
    saveStatus = 'Unsaved changes';
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 800), () {
      flush().catchError((_) {});
    });
    announce();
  }

  Future<void> flush() async {
    _debounce?.cancel();
    if (_saving != null) await _saving;
    if (draft == null || _savedEpoch == _epoch) return;
    if (conflict) {
      throw WorkflowError(
          409, 'Reload or keep a separate copy before continuing');
    }
    final completer = Completer<void>();
    _saving = completer.future;
    final epoch = _epoch;
    final snapshot = jsonDecode(jsonEncode(content));
    saveStatus = 'Saving';
    announce();
    try {
      final saved = Map<String, dynamic>.from(await api.call('/drafts/$id',
          method: 'PATCH',
          body: {'expectedRevision': revision, 'content': snapshot}));
      if (_epoch == epoch) {
        draft = saved;
      } else {
        draft!['revision'] = saved['revision'];
        draft!['approvedOutline'] = saved['approvedOutline'];
      }
      _savedEpoch = epoch;
      error = null;
      saveStatus = _epoch == epoch ? 'Saved' : 'Unsaved changes';
      completer.complete();
    } catch (exc) {
      if (exc is WorkflowError && exc.status == 409) conflict = true;
      error = '$exc';
      saveStatus = 'Save failed';
      completer.completeError(exc);
    } finally {
      _saving = null;
      announce();
    }
    await completer.future;
    if (_epoch != _savedEpoch) await flush();
  }

  Future<void> action(Future<void> Function() work) async {
    if (busy) return;
    busy = true;
    error = null;
    announce();
    try {
      await work();
    } catch (exc) {
      error = '$exc';
    } finally {
      busy = false;
      announce();
    }
  }

  Future<void> importSource(
      {String? documentId, String? text, bool referenceOnly = false}) async {
    await flush();
    await start('import', sourceImport: {
      'expectedRevision': revision,
      'referenceOnly': referenceOnly,
      if (documentId != null) 'documentId': documentId,
      if (text != null) 'text': text
    });
    sources = await api.call('/drafts/$id/sources');
    announce();
  }

  Future<void> approve() async {
    await flush();
    draft = Map<String, dynamic>.from(await api.call(
        '/drafts/$id/approve-outline',
        method: 'POST',
        body: {'expectedRevision': revision}));
    announce();
  }

  Future<void> acknowledge(String sourceId, bool value) async {
    await flush();
    draft = Map<String, dynamic>.from(await api.call(
        '/drafts/$id/sources/$sourceId/acknowledge',
        method: 'POST',
        body: {'expectedRevision': revision, 'acknowledged': value}));
    sources = await api.call('/drafts/$id/sources');
    announce();
  }

  Future<void> start(String task,
      {String instruction = '',
      Map<String, dynamic>? target,
      String scope = 'selected',
      Map<String, dynamic>? sourceImport,
      String? moduleId}) async {
    await flush();
    operation = Map<String, dynamic>.from(
        await api.call('/drafts/$id/operations', method: 'POST', body: {
      'task': task,
      'instruction': instruction,
      'scope': scope,
      if (sourceImport != null) 'sourceImport': sourceImport,
      if (moduleId != null) 'moduleId': moduleId,
      'expectedRevision': revision,
      'key': 'r_${DateTime.now().microsecondsSinceEpoch}',
      if (target != null) 'target': target
    }));
    announce();
    final operationId = operation!['id'];
    while (!_disposed && ['queued', 'running'].contains(operation!['status'])) {
      await Future<void>.delayed(const Duration(seconds: 1));
      if (_disposed) return;
      operation = Map<String, dynamic>.from(
          await api.call('/drafts/$id/operations/$operationId'));
      announce();
    }
    if (task == 'draft' || task == 'import') {
      draft = Map<String, dynamic>.from(await api.call('/drafts/$id'));
      announce();
    }
    if (operation!['status'] == 'failed') {
      throw WorkflowError(502, operation!['error'] ?? 'Generation failed');
    }
  }

  Future<void> cancel() async {
    if (operation != null) {
      await api.call('/drafts/$id/operations/${operation!['id']}/cancel',
          method: 'POST');
    }
  }

  Future<void> accept({List<Map<String, dynamic>>? outline}) async {
    await flush();
    draft = Map<String, dynamic>.from(await api.call(
        '/drafts/$id/proposals/${operation!['id']}/accept',
        method: 'POST',
        body: {
          'expectedRevision': revision,
          if (outline != null) 'outline': {'modules': outline}
        }));
    operation = null;
    announce();
  }

  Future<void> reject() async {
    await api.call('/drafts/$id/proposals/${operation!['id']}/reject',
        method: 'POST');
    operation = null;
    announce();
  }

  Future<void> restore(int selected) async {
    await flush();
    draft = Map<String, dynamic>.from(await api.call('/drafts/$id/restore',
        method: 'POST',
        body: {'expectedRevision': revision, 'restoreRevision': selected}));
    operation = null;
    announce();
  }

  Future<void> keepSeparateCopy() async {
    final snapshot = jsonDecode(jsonEncode(content));
    draft = Map<String, dynamic>.from(await api
        .call('/drafts/$id/copy', method: 'POST', body: {'content': snapshot}));
    sources = await api.call('/drafts/$id/sources');
    _epoch = 0;
    _savedEpoch = 0;
    conflict = false;
    error = null;
    saveStatus = 'Saved';
    announce();
  }

  static Future<String> textHash(String selected) async {
    return crypto.sha256.convert(utf8.encode(jsonEncode(selected))).toString();
  }

  @override
  void dispose() {
    _disposed = true;
    _debounce?.cancel();
    api.dispose();
    super.dispose();
  }
}
