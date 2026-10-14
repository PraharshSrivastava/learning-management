// Isolated browser spike using the current editor's DOM API. Production adapter
// selection (including package:web migration) is still a Phase 0 acceptance gate.
// ignore: deprecated_member_use, avoid_web_libraries_in_flutter
import 'dart:html' as html;
import 'document_workflow_models.dart';

class WorkflowEditorAdapter {
  final html.DivElement root = html.DivElement();
  List<WorkflowBlock> _blocks = [];
  html.Range? _savedRange;
  void Function()? onChanged;
  void Function(String id)? onProperties;
  bool _composing = false;
  bool get isComposing => _composing;
  final String Function(String assetId) resolveOwnedAsset;

  WorkflowEditorAdapter({required this.resolveOwnedAsset}) {
    root
      ..contentEditable = 'true'
      ..setAttribute('aria-label', 'Training document editor');
    root.style
      ..padding = '22px'
      ..fontFamily = 'Segoe UI, Arial, sans-serif'
      ..fontSize = '16px'
      ..lineHeight = '1.65'
      ..height = '100%'
      ..overflowY = 'auto';
    root.onInput.listen((_) {
      if (!_composing) onChanged?.call();
    });
    root.addEventListener('compositionstart', (_) {
      _composing = true;
    });
    root.addEventListener('compositionend', (_) {
      _composing = false;
      onChanged?.call();
    });
    void remember(html.Event _) {
      final selection = html.window.getSelection();
      if (selection != null && (selection.rangeCount ?? 0) > 0) {
        final range = selection.getRangeAt(0);
        if (root.contains(range.commonAncestorContainer)) {
          _savedRange = range.cloneRange();
        }
      }
    }

    root.onMouseUp.listen(remember);
    root.onKeyUp.listen(remember);
    root.onPaste.listen((event) {
      event.preventDefault();
      html.document.execCommand('insertText', false,
          event.clipboardData?.getData('text/plain') ?? '');
      onChanged?.call();
    });
    root.onDrop.listen((event) => event.preventDefault());
  }

  void format(String command) {
    if (!['bold', 'italic', 'insertUnorderedList', 'insertOrderedList']
        .contains(command)) {
      return;
    }
    root.focus();
    if (_savedRange != null) {
      html.window.getSelection()!
        ..removeAllRanges()
        ..addRange(_savedRange!);
    }
    html.document.execCommand(command);
    onChanged?.call();
  }

  void load(List<WorkflowBlock> blocks, {String? moduleTitle}) {
    _blocks = List.of(blocks);
    _savedRange = null;
    root.children.clear();
    for (final block in blocks) {
      final value = block.toJson();
      final element = html.DivElement()
        ..dataset['blockId'] = block.id
        ..dataset['blockType'] = block.type;
      if (block.type == 'image') {
        final image = html.ImageElement(
            src: resolveOwnedAsset(value['assetId'] as String))
          ..alt = value['caption'] as String? ?? 'Document image';
        image.style
          ..width = '${value['width'] ?? 60}%'
          ..maxWidth = '100%'
          ..display = 'block';
        image.style.marginLeft = value['align'] == 'left' ? '0' : 'auto';
        image.style.marginRight = value['align'] == 'right' ? '0' : 'auto';
        element
          ..contentEditable = 'false'
          ..append(image)
          ..append(
              html.SpanElement()..text = value['caption'] as String? ?? '');
      } else if (const ['list', 'table'].contains(block.type)) {
        // The spike preserves these canonical blocks without pretending they
        // are already editable. Full structured editing is a later phase gate.
        element
          ..contentEditable = 'false'
          ..text = block.type == 'list'
              ? (value['items'] as List).join('\n')
              : (value['rows'] as List)
                  .map((r) => (r as List).join(' | '))
                  .join('\n');
      } else {
        _renderText(element, block.text, value['marks'] as List? ?? []);
        if (block.type == 'heading') {
          element.style
            ..fontSize = '22px'
            ..fontWeight = 'bold';
        }
        if (block.type == 'scenario' || block.type == 'takeaway') {
          element.style
            ..backgroundColor = '#edf3ff'
            ..padding = '14px';
        }
      }
      if (['image', 'list', 'table'].contains(block.type)) {
        final control = html.ButtonElement()
          ..type = 'button'
          ..text = 'Edit ${block.type}'
          ..onClick.listen((_) => onProperties?.call(block.id));
        element.append(control);
      }
      element.style.marginBottom = '14px';
      if (block.type == 'heading' &&
          moduleTitle != null &&
          block.text.trim().toLowerCase() == moduleTitle.trim().toLowerCase()) {
        element.style.display = 'none';
      }
      root.append(element);
    }
  }

  void _renderText(html.Element element, String text, List marks) {
    // Split at mark boundaries so overlapping bold/italic/link ranges survive.
    final points = <int>{0, text.runes.length};
    for (final mark in marks.cast<Map>()) {
      points.add(mark['start'] as int);
      points.add(mark['end'] as int);
    }
    final boundaries = points.toList()..sort();
    for (var i = 0; i < boundaries.length - 1; i++) {
      final start = boundaries[i], end = boundaries[i + 1];
      html.Node node = html.Text(text.substring(
          codePointToUtf16(text, start), codePointToUtf16(text, end)));
      for (final mark in marks.cast<Map>().where(
          (m) => (m['start'] as int) <= start && (m['end'] as int) >= end)) {
        final type = mark['type'];
        final wrapper = html.Element.tag(type == 'bold'
            ? 'strong'
            : type == 'italic'
                ? 'em'
                : 'a');
        if (type == 'link') {
          final href = mark['href'] as String;
          if (!href.startsWith('https://') &&
              !href.startsWith('http://') &&
              !href.startsWith('mailto:')) {
            throw const FormatException('Unsafe link');
          }
          wrapper.setAttribute('href', href);
        }
        wrapper.append(node);
        node = wrapper;
      }
      element.append(node);
    }
    if (text.isEmpty) element.append(html.BRElement());
  }

  html.Element? _blockFor(html.Node node) {
    html.Node? current = node;
    while (current != null && current.parent != root) {
      current = current.parent;
    }
    return current is html.Element && current.parent == root ? current : null;
  }

  WorkflowSelection? selection() {
    final selected = html.window.getSelection();
    final range = selected != null &&
            (selected.rangeCount ?? 0) > 0 &&
            root.contains(selected.getRangeAt(0).commonAncestorContainer)
        ? selected.getRangeAt(0)
        : _savedRange;
    if (range == null || range.collapsed == true) return null;
    final block = _blockFor(range.startContainer);
    if (block == null ||
        block != _blockFor(range.endContainer) ||
        !const ['paragraph', 'heading', 'scenario', 'takeaway']
            .contains(block.dataset['blockType'])) {
      return null;
    }
    final prefix = html.document.createRange()
      ..selectNodeContents(block)
      ..setEnd(range.startContainer, range.startOffset);
    String rangeText(html.Node node) {
      if (node is html.Text) return node.text ?? '';
      if (node is html.Element && node.localName == 'br') return '\n';
      return node.nodes.map(rangeText).join();
    }

    final text = rangeText(block);
    final selectedText = rangeText(range.cloneContents());
    final start = rangeText(prefix.cloneContents()).length;
    final end = start + selectedText.length;
    return WorkflowSelection(
        block.dataset['blockId']!,
        utf16ToCodePoint(text, start),
        utf16ToCodePoint(text, end),
        selectedText);
  }

  List<WorkflowBlock> snapshot() {
    final existing = {for (final block in _blocks) block.id: block};
    final seen = <String>{};
    final live = <WorkflowBlock>[];
    for (final node in root.nodes.toList()) {
      if (node is html.Text) {
        final element = html.DivElement()..text = node.text;
        root.insertBefore(element, node);
        node.remove();
      }
    }
    for (final element in root.children) {
      var id = element.dataset['blockId'];
      if (id == null || seen.contains(id)) {
        id = 'b_${DateTime.now().microsecondsSinceEpoch}_${seen.length}';
        element.dataset['blockId'] = id;
      }
      seen.add(id);
      element.dataset['blockType'] = existing[id]?.type ?? 'paragraph';
      live.add(existing[id] ?? WorkflowBlock.paragraph(id, element.text ?? ''));
    }
    _blocks = live;
    return live.map((block) {
      if (!const ['paragraph', 'heading', 'scenario', 'takeaway']
          .contains(block.type)) {
        return block;
      }
      final element =
          root.children.firstWhere((e) => e.dataset['blockId'] == block.id);
      final marks = <Map<String, dynamic>>[];
      var points = 0;
      String visit(html.Node node) {
        if (node is html.Text) {
          final value = node.text ?? '';
          points += value.runes.length;
          return value;
        }
        if (node is! html.Element) return '';
        final start = points;
        if (node.localName == 'br') {
          points++;
          return '\n';
        }
        final value = node.nodes.map(visit).join();
        final tag = node.localName;
        final type = ['b', 'strong'].contains(tag)
            ? 'bold'
            : ['i', 'em'].contains(tag)
                ? 'italic'
                : tag == 'a'
                    ? 'link'
                    : null;
        if (type != null && points > start) {
          marks.add({
            'start': start,
            'end': points,
            'type': type,
            if (type == 'link') 'href': node.getAttribute('href')
          });
        }
        return value;
      }

      final text = visit(element);
      return WorkflowBlock.fromJson(
          {...block.toJson(), 'text': text, 'marks': marks});
    }).toList();
  }

  void replaceSelection(WorkflowSelection target, String replacement) {
    final blocks = snapshot();
    final index = blocks.indexWhere((b) => b.id == target.blockId);
    if (index < 0) throw StateError('Selected block no longer exists');
    final value = blocks[index].toJson();
    final text = blocks[index].text;
    final start = codePointToUtf16(text, target.start),
        end = codePointToUtf16(text, target.end);
    if (text.substring(start, end) != target.text) {
      throw StateError('Selected text changed');
    }
    final delta = replacement.runes.length - (target.end - target.start);
    final marks = <Map<String, dynamic>>[];
    for (final raw in (value['marks'] as List? ?? []).cast<Map>()) {
      final mark = Map<String, dynamic>.from(raw);
      final a = mark['start'] as int, b = mark['end'] as int;
      if (b <= target.start) {
        marks.add(mark);
      } else if (a >= target.end) {
        marks.add({...mark, 'start': a + delta, 'end': b + delta});
      } else {
        // Keep formatting outside the replacement, show replacement formatting
        // as part of the proposal rather than implicitly extending old marks.
        if (a < target.start) marks.add({...mark, 'end': target.start});
        if (b > target.end) {
          marks.add({
            ...mark,
            'start': target.start + replacement.runes.length,
            'end': b + delta
          });
        }
      }
    }
    blocks[index] = WorkflowBlock.fromJson({
      ...value,
      'text': text.replaceRange(start, end, replacement),
      'marks': marks
    });
    load(blocks);
  }

  void dispose() => root.remove();
}
