@TestOn('browser')
library;

// Browser-only spike against the legacy editor DOM API.
// ignore: deprecated_member_use, avoid_web_libraries_in_flutter
import 'dart:html' as html;
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/features/document_builder/document_workflow_models.dart';
import 'package:frontend/features/document_builder/document_workflow_editor.dart';

void main() {
  test('Scoped edit preserves image position, caption, IDs and outside marks',
      () {
    final editor = WorkflowEditorAdapter(
        resolveOwnedAsset: (_) => 'data:image/png;base64,');
    html.document.body!.append(editor.root);
    editor.load([
      WorkflowBlock.fromJson({
        'id': 'text_1',
        'type': 'paragraph',
        'text': 'Ask 😀 and listen.',
        'marks': [
          {'start': 0, 'end': 3, 'type': 'bold'},
          {'start': 10, 'end': 16, 'type': 'italic'}
        ]
      }),
      WorkflowBlock.fromJson({
        'id': 'image_1',
        'type': 'image',
        'assetId': 'owned_asset',
        'caption': 'Customer conversation',
        'width': 60,
        'align': 'center'
      }),
      WorkflowBlock.paragraph('text_2', 'Other paragraph remains unchanged.'),
    ]);
    final text = editor.root.children.first.nodes[1];
    final range = html.document.createRange()
      ..setStart(text, 1)
      ..setEnd(text, 3);
    html.window.getSelection()!
      ..removeAllRanges()
      ..addRange(range);
    final selected = editor.selection()!;
    expect(selected.text, '😀');
    expect(selected.start, 4);
    expect(selected.end, 5);
    editor.replaceSelection(selected, 'carefully');
    final result = editor.snapshot();
    expect(result[0].text, 'Ask carefully and listen.');
    expect(result[1].toJson()['assetId'], 'owned_asset');
    expect(result[1].toJson()['caption'], 'Customer conversation');
    expect(result[2].text, 'Other paragraph remains unchanged.');
    expect(result.map((b) => b.id), ['text_1', 'image_1', 'text_2']);
    expect(result[0].toJson()['marks'],
        contains({'start': 0, 'end': 3, 'type': 'bold'}));
    editor.dispose();
  });

  test('Changed text refuses a stale proposal', () {
    final editor = WorkflowEditorAdapter(resolveOwnedAsset: (_) => '');
    editor.load([WorkflowBlock.paragraph('text_1', 'Changed text')]);
    expect(
        () => editor.replaceSelection(
            const WorkflowSelection('text_1', 0, 3, 'Old'), 'New'),
        throwsStateError);
    expect(editor.snapshot().first.text, 'Changed text');
    editor.dispose();
  });

  test('UTF-16 offsets preserve emoji and reject surrogate splits', () {
    expect(utf16ToCodePoint('Ask 😀 and listen.', 6), 5);
    expect(codePointToUtf16('Ask 😀 and listen.', 5), 6);
    expect(
        () => utf16ToCodePoint('Ask 😀 and listen.', 5), throwsFormatException);
  });
}
