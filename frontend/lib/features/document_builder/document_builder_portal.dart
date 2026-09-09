import 'dart:html' as html;
import 'dart:typed_data';
import 'dart:ui_web' as ui_web;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:frontend/core/theme/app_theme.dart';
import 'package:frontend/features/document_builder/document_builder_models.dart';
import 'package:frontend/features/document_builder/document_html_editor.dart';
import 'package:frontend/state/trainer/document_builder_provider.dart';

final documentBuilderVisibleProvider = StateProvider<bool>((ref) => false);

class DocumentBuilderPortal extends ConsumerStatefulWidget {
  final VoidCallback onClose;
  const DocumentBuilderPortal({super.key, required this.onClose});
  @override
  ConsumerState<DocumentBuilderPortal> createState() =>
      _DocumentBuilderPortalState();
}

class _DocumentBuilderPortalState extends ConsumerState<DocumentBuilderPortal> {
  final _courseName = TextEditingController(),
      _description = TextEditingController(),
      _objective = TextEditingController(),
      _language = TextEditingController(text: 'English'),
      _audience = TextEditingController(),
      _courseType = TextEditingController(),
      _prompt = TextEditingController();
  late final DocumentHtmlEditorController _editor;
  late final html.IFrameElement _previewFrame;
  late final String _previewViewId;
  final _instructions = <String>[],
      _messages = <BuilderChatMessage>[
        const BuilderChatMessage(false,
            'Save metadata separately if you need it for the LMS. Apply builder settings when you want them to affect future AI edits. Type normally in the draft and paste or drag images where you want them.')
      ];
  String _difficulty = '',
      _detailLevel = 'standard',
      _tone = 'Clear and professional',
      _writingFocus = 'balanced',
      _llmStatus = 'LLM idle';
  int _moduleCount = 4;
  bool _scenarios = true,
      _badGood = true,
      _takeaways = true,
      _mistakes = true,
      _metadataDirty = false,
      _metadataSaved = false,
      _settingsDirty = false,
      _settingsApplied = false,
      _preview = false,
      _busy = false,
      _saving = false;
  String? _pdfUrl;
  DocumentBuilderSettings _applied = const DocumentBuilderSettings();

  @override
  void initState() {
    super.initState();
    _editor = DocumentHtmlEditorController()..onChanged = _invalidatePdf;
    _previewFrame = html.IFrameElement()
      ..style.border = 'none'
      ..style.width = '100%'
      ..style.height = '100%';
    _previewViewId = 'document-builder-preview-${identityHashCode(this)}';
    ui_web.platformViewRegistry
        .registerViewFactory(_previewViewId, (_) => _previewFrame);
    for (final c in [
      _courseName,
      _description,
      _objective,
      _language,
      _audience,
      _courseType
    ]) {
      c.addListener(_metadataChanged);
    }
  }

  @override
  void dispose() {
    for (final c in [
      _courseName,
      _description,
      _objective,
      _language,
      _audience,
      _courseType,
      _prompt
    ]) {
      c.dispose();
    }
    _editor.dispose();
    if (_pdfUrl != null) html.Url.revokeObjectUrl(_pdfUrl!);
    super.dispose();
  }

  void _metadataChanged() {
    if (mounted) {
      setState(() {
        _metadataDirty = true;
        _clearPdf();
      });
    }
  }

  void _invalidatePdf() {
    if (mounted) setState(_clearPdf);
  }

  void _clearPdf() {
    if (_pdfUrl != null) {
      html.Url.revokeObjectUrl(_pdfUrl!);
      _pdfUrl = null;
    }
    _previewFrame.src = 'about:blank';
  }

  void _bot(String text) {
    setState(() => _messages.add(BuilderChatMessage(false, text)));
  }

  DocumentBuilderMetadata get _metadata => DocumentBuilderMetadata(
      courseName: _courseName.text,
      courseDescription: _description.text,
      courseObjective: _objective.text,
      courseDifficulty: _difficulty,
      language: _language.text,
      targetAudience: _audience.text,
      courseType: _courseType.text);
  DocumentBuilderSettings get _settingsForm => DocumentBuilderSettings(
      moduleCount: _moduleCount,
      detailLevel: _detailLevel,
      tone: _tone,
      writingFocus: _writingFocus,
      includeScenarios: _scenarios,
      includeBadGood: _badGood,
      includeTakeaways: _takeaways,
      includeMistakes: _mistakes);
  bool _validate() {
    final missing = _metadata.missingFields;
    if (missing.isNotEmpty) {
      _bot(
          'Fill these metadata fields before PDF preview/download:\n\n${missing.join('\n')}');
      return false;
    }
    if (_editor.text.isEmpty) {
      _bot('Add or generate module content before PDF preview/download.');
      return false;
    }
    return true;
  }

  Future<Uint8List?> _render() async {
    if (!_validate()) return null;
    try {
      final bytes = await ref
          .read(documentBuilderApiProvider)
          .render(_metadata, _editor.text, _editor.blocks);
      _clearPdf();
      final blob = html.Blob([bytes], 'application/pdf');
      _pdfUrl = html.Url.createObjectUrlFromBlob(blob);
      _previewFrame.src = _pdfUrl!;
      return bytes;
    } catch (error) {
      _bot('Could not render PDF preview.\n\nError: $error');
      return null;
    }
  }

  Future<void> _send() async {
    final message = _prompt.text.trim();
    if (message.isEmpty || _busy) return;
    setState(() {
      _busy = true;
      _llmStatus = 'Gemma writing';
      _instructions.add(message);
      _messages.add(BuilderChatMessage(true, message));
      _prompt.clear();
    });
    try {
      final body = await ref.read(documentBuilderApiProvider).build(
          message: message,
          instructions: _instructions,
          currentDraft: _editor.text,
          settings: _applied);
      _editor.setText(body['document']?.toString() ?? '', preserveImages: true);
      setState(() => _llmStatus = '${body['model'] ?? 'Gemma'} done');
      _bot(body['reply']?.toString() ??
          'I updated the module-only draft on the right.');
    } catch (error) {
      setState(() => _llmStatus = 'LLM failed');
      _bot('No LLM document was generated.\n\nError: $error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _showPreview() async {
    setState(() => _preview = true);
    await _render();
  }

  Future<void> _download() async {
    final bytes = _pdfUrl == null ? await _render() : Uint8List(0);
    if (bytes == null) return;
    final name = _safeName(_metadata.courseName);
    final anchor = html.AnchorElement(href: _pdfUrl)
      ..download = '${name.isEmpty ? 'document' : name}-source.pdf'
      ..style.display = 'none';
    html.document.body?.append(anchor);
    anchor.click();
    anchor.remove();
  }

  Future<void> _save() async {
    if (!_validate() || _saving) return;
    setState(() => _saving = true);
    try {
      await ref
          .read(documentBuilderApiProvider)
          .save(_metadata, _editor.text, _editor.blocks);
      _bot('Document saved successfully. It is now available in Documents.');
      widget.onClose();
    } catch (error) {
      _bot('Could not save PDF.\n\nError: $error');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String _safeName(String value) {
    final safe = value
        .toLowerCase()
        .replaceAll(RegExp(r'[^a-z0-9]+'), '-')
        .replaceAll(RegExp(r'^-|-$'), '');
    return safe.substring(0, safe.length.clamp(0, 60));
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Container(
          height: 52,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: AppTheme.cardDecoration(),
          child: Row(children: [
            const Icon(Icons.edit_document, color: AppTheme.primaryBlue),
            const SizedBox(width: 10),
            Text('Document Builder',
                style: GoogleFonts.inter(
                    fontWeight: FontWeight.w700,
                    fontSize: 17,
                    color: AppTheme.primaryBlue)),
            const Spacer(),
            IconButton(
                onPressed: widget.onClose,
                tooltip: 'Close builder',
                icon: const Icon(Icons.close))
          ])),
      const SizedBox(height: 12),
      Expanded(child: LayoutBuilder(builder: (context, constraints) {
        final panels = [
          _metadataPanel(),
          _settingsPanel(),
          _chatPanel(),
          _documentPanel()
        ];
        if (constraints.maxWidth < 900) {
          return ListView.separated(
              itemCount: 4,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (_, i) =>
                  SizedBox(height: i == 3 ? 650 : 520, child: panels[i]));
        }
        final rowWidth =
            constraints.maxWidth < 1520 ? 1520.0 : constraints.maxWidth;
        return Scrollbar(
            thumbVisibility: constraints.maxWidth < 1520,
            child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: ConstrainedBox(
                    constraints: BoxConstraints.tightFor(width: rowWidth),
                    child: Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          SizedBox(width: 288, child: panels[0]),
                          const SizedBox(width: 12),
                          SizedBox(width: 292, child: panels[1]),
                          const SizedBox(width: 12),
                          SizedBox(width: 384, child: panels[2]),
                          const SizedBox(width: 12),
                          Expanded(child: panels[3])
                        ]))));
      }))
    ]);
  }

  Widget _panel({required Widget child}) => Container(
      decoration: AppTheme.cardDecoration(),
      clipBehavior: Clip.antiAlias,
      child: child);
  Widget _header(String title, String status,
          {bool active = false, bool error = false}) =>
      Container(
          padding: const EdgeInsets.all(14),
          decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: AppTheme.lightGray))),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
                child: Text(title,
                    style: GoogleFonts.inter(
                        fontSize: 17, fontWeight: FontWeight.w700))),
            _pill(status, active: error ? false : active, error: error)
          ]));
  Widget _pill(String text, {bool active = false, bool error = false}) =>
      Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
              color: error
                  ? AppTheme.accentRed.withOpacity(.1)
                  : active
                      ? AppTheme.brandBlue100
                      : AppTheme.lightGray,
              borderRadius: BorderRadius.circular(999)),
          child: Text(text,
              style: GoogleFonts.barlow(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: error
                      ? AppTheme.accentRed
                      : active
                          ? AppTheme.primaryBlue
                          : AppTheme.gray)));
  InputDecoration _dec(String hint) => InputDecoration(
      hintText: hint,
      isDense: true,
      isCollapsed: false,
      contentPadding: const EdgeInsets.all(10),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)));
  Widget _label(String name, Widget field) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(name,
            style: GoogleFonts.barlow(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.gray)),
        const SizedBox(height: 7),
        field,
        const SizedBox(height: 12)
      ]);
  Widget _metadataPanel() => _panel(
          child: Column(children: [
        _header(
            'Metadata',
            _metadataDirty
                ? 'Unsaved changes'
                : (_metadataSaved ? 'Saved' : 'Not saved'),
            active: !_metadataDirty && _metadata.courseName.isNotEmpty),
        Expanded(
            child: SingleChildScrollView(
                padding: const EdgeInsets.all(14),
                child: Column(children: [
                  _label(
                      'Course name',
                      TextField(
                          controller: _courseName,
                          decoration: _dec('Workplace Training'))),
                  _label(
                      'Course description',
                      TextField(
                          controller: _description,
                          maxLines: 3,
                          decoration:
                              _dec('Short LMS-facing course description'))),
                  _label(
                      'Course objective',
                      TextField(
                          controller: _objective,
                          maxLines: 3,
                          decoration:
                              _dec('What the learner should be able to do'))),
                  _label(
                      'Course difficulty',
                      DropdownButtonFormField<String>(
                          value: _difficulty,
                          decoration: _dec(''),
                          isExpanded: true,
                          items: [
                            '',
                            'Easy',
                            'Beginner to Intermediate',
                            'Intermediate',
                            'Advanced'
                          ]
                              .map((v) => DropdownMenuItem(
                                  value: v,
                                  child: Text(
                                    v.isEmpty ? 'Select difficulty' : v,
                                    overflow: TextOverflow.ellipsis,
                                  )))
                              .toList(),
                          onChanged: (v) => setState(() {
                                _difficulty = v ?? '';
                                _metadataDirty = true;
                                _clearPdf();
                              }))),
                  _label('Language',
                      TextField(controller: _language, decoration: _dec(''))),
                  _label(
                      'Target audience',
                      TextField(
                          controller: _audience,
                          decoration: _dec('New employees'))),
                  _label(
                      'Course type',
                      TextField(
                          controller: _courseType,
                          decoration: _dec('Functional Training'))),
                  SizedBox(
                      width: double.infinity,
                      child: FilledButton(
                          onPressed: () {
                            setState(() {
                              _metadataDirty = false;
                              _metadataSaved = true;
                            });
                            _bot(
                                'Metadata saved separately. It will not be sent to the AI document writer.');
                          },
                          child: const Text('Save metadata')))
                ])))
      ]));
  Widget _settingsPanel() => _panel(
          child: Column(children: [
        _header(
            'Builder Settings',
            _settingsDirty
                ? 'Unsaved changes'
                : (_settingsApplied ? 'Applied' : 'Defaults applied'),
            active: !_settingsDirty),
        Expanded(
            child: SingleChildScrollView(
                padding: const EdgeInsets.all(14),
                child: Column(children: [
                  _label(
                      'Module count',
                      TextFormField(
                          initialValue: '4',
                          keyboardType: TextInputType.number,
                          decoration: _dec(''),
                          onChanged: (v) => setState(() {
                                _moduleCount =
                                    (int.tryParse(v) ?? 4).clamp(2, 8);
                                _settingsDirty = true;
                              }))),
                  _label(
                      'Detail level',
                      _select(
                          _detailLevel,
                          const {
                            'standard': 'Standard',
                            'short': 'Short',
                            'detailed': 'Detailed'
                          },
                          (v) => setState(() {
                                _detailLevel = v;
                                _settingsDirty = true;
                              }))),
                  _label(
                      'Tone',
                      _select(
                          _tone,
                          const {
                            'Clear and professional': 'Clear and professional',
                            'Warm and conversational':
                                'Warm and conversational',
                            'Compliance-safe': 'Compliance-safe',
                            'Step-by-step operational':
                                'Step-by-step operational'
                          },
                          (v) => setState(() {
                                _tone = v;
                                _settingsDirty = true;
                              }))),
                  _label(
                      'Writing focus',
                      _select(
                          _writingFocus,
                          const {
                            'balanced': 'Balanced explanation and application',
                            'conceptual': 'Concept explanation',
                            'practical': 'Practical application',
                            'process': 'Step-by-step process'
                          },
                          (v) => setState(() {
                                _writingFocus = v;
                                _settingsDirty = true;
                              }))),
                  const Divider(),
                  _check('Include scenarios inside modules', _scenarios,
                      (v) => _scenarios = v),
                  _check('Include weak vs better examples', _badGood,
                      (v) => _badGood = v),
                  _check('Include short takeaways', _takeaways,
                      (v) => _takeaways = v),
                  _check('Include common mistakes', _mistakes,
                      (v) => _mistakes = v),
                  const SizedBox(height: 8),
                  SizedBox(
                      width: double.infinity,
                      child: OutlinedButton(
                          onPressed: () {
                            setState(() {
                              _applied = _settingsForm;
                              _settingsDirty = false;
                              _settingsApplied = true;
                            });
                            _bot(
                                'Builder settings applied for future AI drafts and edits.');
                          },
                          child: const Text('Apply builder settings')))
                ])))
      ]));
  Widget _select(String value, Map<String, String> values,
          ValueChanged<String> onChanged) =>
      DropdownButtonFormField<String>(
          value: value,
          decoration: _dec(''),
          isExpanded: true,
          items: values.entries
              .map((e) => DropdownMenuItem(
                  value: e.key,
                  child: Text(e.value, overflow: TextOverflow.ellipsis)))
              .toList(),
          onChanged: (v) {
            if (v != null) onChanged(v);
          });
  Widget _check(String label, bool value, ValueChanged<bool> change) =>
      CheckboxListTile(
          value: value,
          dense: true,
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          title: Text(label,
              style: GoogleFonts.barlow(
                  fontSize: 13, fontWeight: FontWeight.w500)),
          onChanged: (v) => setState(() {
                change(v ?? false);
                _settingsDirty = true;
              }));
  Widget _chatPanel() => _panel(
        child: Column(
          children: [
            _header(
              'AI Editor Chat',
              _llmStatus,
              active: _llmStatus.contains('done'),
              error: _llmStatus.contains('failed'),
            ),
            Expanded(
              child: ListView.builder(
                padding: const EdgeInsets.all(14),
                itemCount: _messages.length,
                itemBuilder: (_, i) {
                  final message = _messages[i];
                  return Align(
                    alignment: message.user
                        ? Alignment.centerRight
                        : Alignment.centerLeft,
                    child: Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(12),
                      constraints: const BoxConstraints(maxWidth: 340),
                      decoration: BoxDecoration(
                        color: message.user
                            ? AppTheme.brandBlue100
                            : AppTheme.brandBlue50,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(message.text),
                    ),
                  );
                },
              ),
            ),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: AppTheme.lightGray)),
              ),
              child: Column(
                children: [
                  TextField(
                    controller: _prompt,
                    maxLines: 5,
                    decoration: _dec(
                      'Example: Create a 5-module document about clear communication. Or: rewrite Module 2 with a stronger scenario.',
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: FilledButton(
                          onPressed: _busy ? null : _send,
                          child: Text(_busy ? 'Writing...' : 'Send to AI'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () => _bot(
                            'Before finalizing, I would ask:\n\nShould the draft be short, standard, or detailed?\nShould examples be practical, policy-focused, process-focused, or avoided?\nWhich module should get the most depth?\nShould the writing focus more on concepts, application, or step-by-step process?',
                          ),
                          child: const Text('Ask missing questions'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      );
  Widget _documentPanel() => _panel(
          child: Column(children: [
        LayoutBuilder(builder: (context, constraints) {
          final controls = Wrap(spacing: 6, runSpacing: 6, children: [
            _small('Draft', () => setState(() => _preview = false),
                active: !_preview),
            _small('Preview Doc', _showPreview, active: _preview),
            _small('Copy', () async {
              await html.window.navigator.clipboard?.writeText(_editor.text);
              _bot('Copied the current document text.');
            }),
            _small(_saving ? 'Saving...' : 'Save PDF', _saving ? null : _save),
            _small('Download PDF', _download, filled: true)
          ]);
          return Container(
              padding: const EdgeInsets.all(14),
              decoration: const BoxDecoration(
                  border:
                      Border(bottom: BorderSide(color: AppTheme.lightGray))),
              child: constraints.maxWidth < 620
                  ? Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                          Text('Document Draft',
                              style: GoogleFonts.inter(
                                  fontSize: 17, fontWeight: FontWeight.w700)),
                          const SizedBox(height: 10),
                          controls
                        ])
                  : Row(children: [
                      Expanded(
                          child: Text('Document Draft',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: GoogleFonts.inter(
                                  fontSize: 17, fontWeight: FontWeight.w700))),
                      const SizedBox(width: 10),
                      controls
                    ]));
        }),
        Expanded(
            child: _preview
                ? HtmlElementView(viewType: _previewViewId)
                : Stack(children: [
                    DocumentHtmlEditor(controller: _editor),
                    if (_editor.blocks.isEmpty)
                      const Center(
                          child: IgnorePointer(
                              child: Text(
                                  'Type here, paste images, or drag images into the document.')))
                  ]))
      ]));
  Widget _small(String text, VoidCallback? onTap,
          {bool active = false, bool filled = false}) =>
      filled
          ? FilledButton(
              onPressed: onTap,
              style: FilledButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 8)),
              child: Text(text))
          : OutlinedButton(
              onPressed: onTap,
              style: OutlinedButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  backgroundColor: active ? AppTheme.brandBlue100 : null),
              child: Text(text));
}
