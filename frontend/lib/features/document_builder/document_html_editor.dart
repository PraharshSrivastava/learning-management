import 'dart:async';
import 'dart:html' as html;
import 'dart:ui_web' as ui_web;
import 'package:flutter/material.dart';
import 'document_builder_models.dart';

class DocumentHtmlEditorController {
  final html.DivElement root = html.DivElement();
  html.Element? _selectedFigure;
  html.Range? _savedSelection;
  VoidCallback? onChanged;

  DocumentHtmlEditorController() {
    _installEditorStyles();
    root
      ..contentEditable = 'true'
      ..tabIndex = 0
      ..setAttribute('aria-label', 'Rich document editor');
    root.style
      ..height = '100%'
      ..overflowY = 'auto'
      ..padding = '18px'
      ..outline = 'none'
      ..fontFamily = 'Inter, Arial, sans-serif'
      ..fontSize = '14px'
      ..lineHeight = '1.5'
      ..backgroundColor = 'white';
    root.onInput.listen((_) {
      _changed();
    });
    root.onKeyUp.listen((_) {
      _saveSelection();
    });
    root.onMouseUp.listen((_) {
      _saveSelection();
    });
    root.onFocus.listen((_) {
      _saveSelection();
    });
    root.onClick.listen((event) {
      if ((event.target as html.Node?)?.parent != _selectedFigure) {
        _selectedFigure?.classes.remove('selected');
        _selectedFigure = null;
      }
    });
    root.onPaste.listen(_paste);
    root.onDragOver.listen((event) => event.preventDefault());
    root.onDrop.listen(_drop);
    root.append(html.ParagraphElement()..append(html.BRElement()));
  }

  void _installEditorStyles() {
    const id = 'document-builder-editor-styles';
    if (html.document.getElementById(id) != null) return;
    final style = html.StyleElement()
      ..id = id
      ..text = '''
figure.editor-image.selected img {
  outline: 2px solid #0b2f86;
  outline-offset: 2px;
}
figure.editor-image figcaption {
  border: 1px dashed #9aa8bd;
  border-radius: 6px;
  background: #f8fafc;
  color: #334155;
  margin-top: 8px;
  padding: 8px 10px;
  min-height: 20px;
}
figure.editor-image figcaption:empty::before {
  content: attr(data-placeholder);
  color: #8a96aa;
}
''';
    html.document.head?.append(style);
  }

  void _changed() {
    onChanged?.call();
  }

  void _saveSelection() {
    final selection = html.window.getSelection();
    if (selection != null && (selection.rangeCount ?? 0) > 0) {
      final range = selection.getRangeAt(0);
      if (root.contains(range.commonAncestorContainer)) {
        _savedSelection = range.cloneRange();
      }
    }
  }

  void _restoreSelection() {
    root.focus();
    final selection = html.window.getSelection();
    if (selection == null) return;
    selection.removeAllRanges();
    if (_savedSelection != null) selection.addRange(_savedSelection!);
  }

  String _nodeText(html.Node? node) =>
      (node?.text ?? '').replaceAll('\u00a0', ' ').trim();

  List<DocumentBuilderBlock> get blocks {
    final result = <DocumentBuilderBlock>[];
    for (final node in root.nodes) {
      _collect(node, result);
    }
    return result;
  }

  String get text => blocks
      .where((b) => b.type == 'text')
      .map((b) => b.text)
      .join('\n\n')
      .trim();
  void _collect(html.Node node, List<DocumentBuilderBlock> result) {
    if (node.nodeType == html.Node.TEXT_NODE) {
      final clean = _nodeText(node);
      if (clean.isNotEmpty) result.add(DocumentBuilderBlock.text(clean));
      return;
    }
    if (node is! html.Element) return;
    if (node.classes.contains('image-popover')) return;
    if (node.localName == 'figure' && node.classes.contains('editor-image')) {
      final image = node.querySelector('img') as html.ImageElement?;
      final src = image?.src ?? '';
      if (src.isNotEmpty) {
        result.add(DocumentBuilderBlock.image(
            src: src,
            width: int.tryParse(node.dataset['width'] ?? '60') ?? 60,
            align: node.dataset['align'] ?? 'left',
            caption: _nodeText(node.querySelector('figcaption'))));
      }
      return;
    }
    if (node.querySelector('figure.editor-image') != null) {
      for (final child in node.nodes) {
        _collect(child, result);
      }
      return;
    }
    final clean = _nodeText(node);
    if (clean.isNotEmpty) result.add(DocumentBuilderBlock.text(clean));
  }

  String _moduleOnly(String value) {
    final trimmed = value.trim();
    if (trimmed.isEmpty) return '';
    final match =
        RegExp(r'^Module\s+\d+\s*:', caseSensitive: false, multiLine: true)
            .firstMatch(trimmed);
    if (match == null || match.start <= 0) return trimmed;
    return trimmed.substring(match.start).trim();
  }

  void setText(String value, {bool preserveImages = false}) {
    final images = preserveImages
        ? blocks.where((b) => b.type == 'image').toList()
        : <DocumentBuilderBlock>[];
    root.children.clear();
    for (final part in _moduleOnly(value)
        .split(RegExp(r'\n{2,}'))
        .map((v) => v.trim())
        .where((v) => v.isNotEmpty)) {
      root.append(html.ParagraphElement()..text = part);
    }
    for (final image in images) {
      root.append(_figure(image.src,
          width: image.width, align: image.align, caption: image.caption));
    }
    _changed();
  }

  html.Element _figure(String src,
      {int width = 60, String align = 'left', String caption = ''}) {
    final figure = html.Element.tag('figure')
      ..classes.addAll(['editor-image', 'align-$align'])
      ..contentEditable = 'false'
      ..draggable = false;
    figure.dataset['width'] = '$width';
    figure.dataset['align'] = align;
    figure.style
      ..position = 'relative'
      ..margin = '12px 0'
      ..paddingTop = '36px';
    final controls = html.DivElement()..classes.add('image-popover');
    controls.style
      ..display = 'none'
      ..position = 'absolute'
      ..top = '0'
      ..left = '0'
      ..zIndex = '2'
      ..backgroundColor = 'white'
      ..border = '1px solid #dbe3ef'
      ..padding = '5px';
    final slider = html.InputElement(type: 'range')
      ..min = '25'
      ..max = '100'
      ..value = '$width'
      ..title = 'Resize image'
      ..draggable = false;
    slider.style.width = '110px';
    final select = html.SelectElement()
      ..title = 'Align image'
      ..draggable = false;
    for (final value in ['left', 'center', 'right']) {
      select.append(html.OptionElement(data: value, value: value));
    }
    select.value = align;
    final remove = html.ButtonElement()
      ..type = 'button'
      ..text = 'Delete'
      ..draggable = false;
    remove.style
      ..marginLeft = '6px'
      ..color = '#9b1c1c';
    final image = html.ImageElement(src: src)
      ..alt = ''
      ..draggable = true;
    image.style
      ..width = '$width%'
      ..maxWidth = '100%'
      ..display = 'block';
    final cap = html.Element.tag('figcaption')
      ..contentEditable = 'true'
      ..text = caption;
    cap.setAttribute('data-placeholder', 'Caption');
    cap.style
      ..fontSize = '12px'
      ..color = '#64748b'
      ..minHeight = '20px'
      ..boxSizing = 'border-box';
    void stop(html.Event event) => event.stopPropagation();
    for (final element in [controls, slider, select, remove]) {
      element.onMouseDown.listen(stop);
      element.onClick.listen(stop);
      element.onDragStart.listen((e) => e.preventDefault());
    }
    slider.onInput.listen((_) {
      final nextWidth = slider.value ?? '60';
      figure.dataset['width'] = nextWidth;
      image.style.width = '$nextWidth%';
      _changed();
    });
    select.onChange.listen((_) {
      final next = select.value ?? 'left';
      figure.classes.removeAll(['align-left', 'align-center', 'align-right']);
      figure.classes.add('align-$next');
      figure.dataset['align'] = next;
      _applyAlignment(figure, next);
      _changed();
    });
    remove.onClick.listen((_) {
      if (_selectedFigure == figure) _selectedFigure = null;
      figure.remove();
      _changed();
    });
    cap.onInput.listen((_) {
      _changed();
    });
    cap.onFocus.listen((_) {
      _select(figure);
    });
    controls
      ..append(slider)
      ..append(select)
      ..append(remove);
    figure
      ..append(controls)
      ..append(image)
      ..append(cap);
    _applyAlignment(figure, align);
    figure.onClick.listen((event) {
      event.stopPropagation();
      _select(figure);
    });
    image.onDragStart.listen((event) {
      event.stopPropagation();
      event.dataTransfer.setData('application/x-editor-image', 'move');
      event.dataTransfer.effectAllowed = 'move';
      _selectedFigure = figure;
    });
    return figure;
  }

  void _applyAlignment(html.Element figure, String align) {
    final margin = align == 'center'
        ? 'auto'
        : align == 'right'
            ? 'auto'
            : '0';
    for (final item in figure.querySelectorAll('img,figcaption')) {
      item.style.marginLeft = margin;
      item.style.marginRight = align == 'center'
          ? 'auto'
          : align == 'left'
              ? 'auto'
              : '0';
    }
  }

  void _select(html.Element figure) {
    _selectedFigure?.classes.remove('selected');
    _selectedFigure = figure;
    figure.classes.add('selected');
    final controls = figure.querySelector('.image-popover');
    if (controls != null) controls.style.display = 'block';
    for (final other in root.querySelectorAll('figure.editor-image')) {
      if (other != figure) {
        other.classes.remove('selected');
        other.querySelector('.image-popover')?.style.display = 'none';
      }
    }
  }

  html.Element? _topLevel(html.Node node) {
    html.Element? current = node is html.Element
        ? node
        : (node.parent is html.Element ? node.parent as html.Element : null);
    while (current != null && current.parent != root) {
      final parent = current.parent;
      current = parent is html.Element ? parent : null;
    }
    return current?.parent == root ? current : null;
  }

  void _placeCaret(html.Node node) {
    final range = html.document.createRange()
      ..setStart(node, 0)
      ..collapse(true);
    final selection = html.window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    _savedSelection = range.cloneRange();
  }

  void _insertFigure(html.Element figure) {
    _restoreSelection();
    final selection = html.window.getSelection();
    final range = selection != null && (selection.rangeCount ?? 0) > 0
        ? selection.getRangeAt(0)
        : null;
    if (range == null || !root.contains(range.commonAncestorContainer)) {
      root.append(figure);
    } else if (range.commonAncestorContainer == root) {
      final reference = range.startOffset < root.nodes.length
          ? root.nodes[range.startOffset]
          : null;
      root.insertBefore(figure, reference);
    } else {
      final anchor = _topLevel(range.startContainer);
      if (anchor != null && anchor != figure) {
        anchor.insertAdjacentElement('afterend', figure);
      } else {
        root.append(figure);
      }
    }
    final spacer = html.ParagraphElement()..append(html.BRElement());
    figure.insertAdjacentElement('afterend', spacer);
    _placeCaret(spacer);
    _changed();
  }

  Future<String> _dataUrl(html.File file) {
    final completer = Completer<String>();
    final reader = html.FileReader();
    reader.onLoad.listen((_) {
      completer.complete(reader.result?.toString() ?? '');
    });
    reader.onError.listen((_) {
      completer
          .completeError(reader.error ?? StateError('Could not read image'));
    });
    reader.readAsDataUrl(file);
    return completer.future;
  }

  Future<void> _files(Iterable<html.File> files) async {
    for (final file in files.where((file) => file.type.startsWith('image/'))) {
      _insertFigure(_figure(await _dataUrl(file)));
    }
  }

  Future<void> _paste(html.ClipboardEvent event) async {
    final files = event.clipboardData?.files ?? [];
    final images =
        files.where((file) => file.type.startsWith('image/')).toList();
    if (images.isEmpty) return;
    event.preventDefault();
    await _files(images);
  }

  void _moveCaret(num x, num y) {
    final range = html.document.caretRangeFromPoint(x.round(), y.round());
    if (!root.contains(range.commonAncestorContainer)) return;
    final selection = html.window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    _savedSelection = range.cloneRange();
  }

  Future<void> _drop(html.MouseEvent event) async {
    final moving = _selectedFigure;
    final transfer = event.dataTransfer;
    final files = transfer.files ?? <html.File>[];
    event.preventDefault();
    _moveCaret(event.client.x, event.client.y);
    if (moving != null &&
        transfer.getData('application/x-editor-image') == 'move') {
      _insertFigure(moving);
      return;
    }
    await _files(files);
  }

  void dispose() {
    root.remove();
  }
}

class DocumentHtmlEditor extends StatefulWidget {
  final DocumentHtmlEditorController controller;
  const DocumentHtmlEditor({super.key, required this.controller});
  @override
  State<DocumentHtmlEditor> createState() => _DocumentHtmlEditorState();
}

class _DocumentHtmlEditorState extends State<DocumentHtmlEditor> {
  late final String viewId;
  @override
  void initState() {
    super.initState();
    viewId = 'document-builder-editor-${identityHashCode(this)}';
    ui_web.platformViewRegistry
        .registerViewFactory(viewId, (_) => widget.controller.root);
  }

  @override
  Widget build(BuildContext context) => HtmlElementView(viewType: viewId);
}
