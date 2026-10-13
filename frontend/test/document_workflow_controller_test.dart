import 'dart:async';
import 'dart:convert';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/state/trainer/document_workflow_controller.dart';

Map<String, dynamic> record(int revision, String title) => {
      'id': 'draft_1',
      'revision': revision,
      'content': {
        'entryMode': 'blank',
        'metadata': {'courseName': title},
        'settings': {},
        'modules': []
      }
    };

void main() {
  setUp(
      () => dotenv.loadFromString(envString: 'API_BASE_URL=http://localhost'));
  test('Autosave preserves edits made while an earlier save is in flight',
      () async {
    final first = Completer<http.Response>();
    final saved = <Map<String, dynamic>>[];
    final client = MockClient((request) async {
      if (request.method == 'POST')
        return http.Response(jsonEncode(record(1, 'Original')), 201);
      saved.add(jsonDecode(request.body));
      if (saved.length == 1) return first.future;
      return http.Response(jsonEncode(record(3, 'Latest')), 200);
    });
    final controller =
        DocumentWorkflowController(WorkflowApi(() => {}, client: client));
    await controller.create('blank');
    controller.change((c) => c['metadata']['courseName'] = 'Earlier');
    final flush = controller.flush();
    await Future<void>.delayed(Duration.zero);
    controller.change((c) => c['metadata']['courseName'] = 'Latest');
    first.complete(http.Response(jsonEncode(record(2, 'Earlier')), 200));
    await flush;
    expect(controller.content['metadata']['courseName'], 'Latest');
    expect(saved.map((s) => s['expectedRevision']), [1, 2]);
    expect(controller.saveStatus, 'Saved');
    controller.dispose();
  });
  test('Revision conflicts retain unsaved content and stop silent retries',
      () async {
    final client = MockClient((request) async => request.method == 'POST'
        ? http.Response(jsonEncode(record(1, 'Original')), 201)
        : http.Response('{"detail":"Draft changed"}', 409));
    final controller =
        DocumentWorkflowController(WorkflowApi(() => {}, client: client));
    await controller.create('blank');
    controller
        .change((c) => c['metadata']['courseName'] = 'Keep my local changes');
    await expectLater(controller.flush(), throwsA(isA<WorkflowError>()));
    expect(controller.conflict, isTrue);
    expect(
        controller.content['metadata']['courseName'], 'Keep my local changes');
    expect(controller.saveStatus, 'Save failed');
    controller.dispose();
  });
  test('Non-JSON gateway errors are reported without discarding draft',
      () async {
    final api = WorkflowApi(() => {},
        client: MockClient(
            (_) async => http.Response('<html>Bad gateway</html>', 502)));
    await expectLater(api.call('/drafts'),
        throwsA(isA<WorkflowError>().having((e) => e.status, 'status', 502)));
    api.dispose();
  });
  test('Selection fingerprint matches backend Unicode JSON hashing', () async {
    expect(await DocumentWorkflowController.textHash('Ask 😀'),
        '850c305551ad58442630fc812987a621f851619bf5642aaa742021d97a951c16');
  });
  test('Reopen reloads imported sources after a durable job completes',
      () async {
    var finished = false;
    final client = MockClient((request) async {
      final path = request.url.path;
      if (path.endsWith('/operations/job_1')) {
        finished = true;
        return http.Response(
            jsonEncode({'id': 'job_1', 'status': 'completed'}), 200);
      }
      if (path.endsWith('/operations')) {
        return http.Response(
            jsonEncode([
              {
                'id': 'job_1',
                'status': 'running',
                'request': {'task': 'import'}
              }
            ]),
            200);
      }
      if (path.endsWith('/sources')) {
        return http.Response(
            jsonEncode(finished
                ? [
                    {'id': 'source_1', 'name': 'Imported source'}
                  ]
                : []),
            200);
      }
      return http.Response(jsonEncode(record(finished ? 2 : 1, 'Import')), 200);
    });
    final controller =
        DocumentWorkflowController(WorkflowApi(() => {}, client: client));
    await controller.open('draft_1');
    expect(controller.revision, 2);
    expect(controller.sources.single['id'], 'source_1');
    controller.dispose();
  });
}
