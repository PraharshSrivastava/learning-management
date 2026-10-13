// Standalone browser acceptance harness, independent of the Flutter test server.
// ignore: deprecated_member_use, avoid_web_libraries_in_flutter
import 'dart:html' as html;
import '../lib/features/document_builder/document_workflow_editor.dart';
import '../lib/features/document_builder/document_workflow_models.dart';

void check(bool condition, String message) {
  if (!condition) throw StateError(message);
}

void main() {
  try {
    final editor = WorkflowEditorAdapter(
        resolveOwnedAsset: (_) =>
            'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7');
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
    final node = editor.root.children.first.nodes[1];
    final range = html.document.createRange()
      ..setStart(node, 1)
      ..setEnd(node, 3);
    html.window.getSelection()!
      ..removeAllRanges()
      ..addRange(range);
    final selected = editor.selection()!;
    check(selected.text == '😀' && selected.start == 4 && selected.end == 5,
        'Browser selection must map emoji to one code point');
    editor.replaceSelection(selected, 'carefully');
    final blocks = editor.snapshot();
    check(blocks[0].text == 'Ask carefully and listen.',
        'Scoped replacement failed');
    check(
        blocks[1].id == 'image_1' &&
            blocks[1].toJson()['caption'] == 'Customer conversation',
        'Image identity or position changed');
    check(blocks[2].text == 'Other paragraph remains unchanged.',
        'Neighboring paragraph changed');
    final marks = blocks[0].toJson()['marks'] as List;
    check(
        marks.any(
            (m) => m['type'] == 'bold' && m['start'] == 0 && m['end'] == 3),
        'Outside bold formatting changed');
    var staleRejected = false;
    try {
      editor.replaceSelection(selected, 'stale replacement');
    } on StateError {
      staleRejected = true;
    }
    check(staleRejected, 'Stale proposal must be rejected');
    var splitRejected = false;
    try {
      utf16ToCodePoint('Ask 😀 and listen.', 5);
    } on FormatException {
      splitRejected = true;
    }
    check(splitRejected, 'Surrogate split must be rejected');
    var changes = 0;
    editor.onChanged = () => changes++;
    editor.root.dispatchEvent(html.Event('compositionstart'));
    editor.root.dispatchEvent(html.Event('input'));
    check(editor.isComposing && changes == 0,
        'IME input must not save an incomplete character');
    editor.root.dispatchEvent(html.Event('compositionend'));
    check(!editor.isComposing && changes == 1,
        'IME completion must notify autosave');
    final inserted = html.DivElement()..text = 'New paragraph after Enter';
    editor.root.append(inserted);
    final normalized = editor.snapshot();
    check(
        normalized.last.id.isNotEmpty && normalized.last.text == inserted.text,
        'New DOM paragraphs must receive stable canonical identity');
    final normalizedAgain = editor.snapshot();
    check(normalizedAgain.last.id == normalized.last.id,
        'Paragraph identity must survive repeated snapshots');
    editor.load([WorkflowBlock.paragraph('line_break', 'First\nSecond')]);
    final multiline = editor.root.children.first;
    multiline.nodes.clear();
    final secondLine = html.Text('Second');
    multiline
      ..append(html.Text('First'))
      ..append(html.BRElement())
      ..append(secondLine);
    final multilineRange = html.document.createRange()
      ..setStart(secondLine, 0)
      ..setEnd(secondLine, 6);
    html.window.getSelection()!
      ..removeAllRanges()
      ..addRange(multilineRange);
    final multilineSelection = editor.selection()!;
    check(multilineSelection.start == 6 && multilineSelection.end == 12,
        'Line-break offsets must match the canonical snapshot');
    editor.replaceSelection(multilineSelection, 'Revised');
    check(editor.snapshot().single.text == 'First\nRevised',
        'Line-break selection edit must preserve the previous line');
    editor.dispose();
    html.document.documentElement!.setAttribute('data-spike-result', 'passed');
  } catch (error) {
    html.document.documentElement!
        .setAttribute('data-spike-result', 'failed: $error');
  }
}
