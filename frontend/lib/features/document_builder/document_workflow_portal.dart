// Trainer web editor shares the existing DOM rendering platform.
// ignore: deprecated_member_use, avoid_web_libraries_in_flutter
import 'dart:html' as html;
import 'dart:convert';
import 'dart:ui_web' as ui_web;
import 'package:http/http.dart' as http;
import 'package:frontend/core/config/app_constants.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import 'package:frontend/core/theme/app_theme.dart';
import 'package:frontend/data/models/models.dart';
import 'package:frontend/state/trainer_providers.dart';
import 'package:frontend/state/trainer/document_workflow_controller.dart';
import 'document_builder_portal.dart';
import 'document_workflow_editor.dart';
import 'document_workflow_models.dart';

class DocumentBuilderEntry extends ConsumerStatefulWidget {
  final VoidCallback onClose;
  const DocumentBuilderEntry({super.key, required this.onClose});
  @override
  ConsumerState<DocumentBuilderEntry> createState() =>
      _DocumentBuilderEntryState();
}

class _DocumentBuilderEntryState extends ConsumerState<DocumentBuilderEntry> {
  late WorkflowApi api;
  late Future<dynamic> capability;
  @override
  void initState() {
    super.initState();
    api = WorkflowApi(() => ref.read(trainerAuthHeadersProvider));
    capability = api.call('/capabilities');
  }

  @override
  void dispose() {
    api.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
      future: capability,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.data is Map && snapshot.data['workflowEnabled'] == true) {
          return DocumentWorkflowPortal(onClose: widget.onClose);
        }
        return DocumentBuilderPortal(onClose: widget.onClose);
      });
}

class DocumentWorkflowPortal extends ConsumerStatefulWidget {
  final VoidCallback onClose;
  const DocumentWorkflowPortal({super.key, required this.onClose});
  @override
  ConsumerState<DocumentWorkflowPortal> createState() =>
      _DocumentWorkflowPortalState();
}

class _DocumentWorkflowPortalState
    extends ConsumerState<DocumentWorkflowPortal> {
  late DocumentWorkflowController controller;
  late WorkflowEditorAdapter editor;
  late String viewId;
  String step = 'home';
  int active = 0;
  String assistantScope = 'selected';
  String? loadedModule;
  final instruction = TextEditingController();
  final pasted = TextEditingController();
  final assetUrls = <String, String>{};
  final objectUrls = <String>[];
  List<dynamic> drafts = [];
  bool disposed = false;
  @override
  void initState() {
    super.initState();
    controller = DocumentWorkflowController(
        WorkflowApi(() => ref.read(trainerAuthHeadersProvider)))
      ..addListener(changed);
    editor =
        WorkflowEditorAdapter(resolveOwnedAsset: (id) => assetUrls[id] ?? '')
          ..onChanged = syncEditor
          ..onProperties = editProperties;
    viewId = 'workflow-editor-${identityHashCode(this)}';
    ui_web.platformViewRegistry.registerViewFactory(viewId, (_) => editor.root);
    refreshDrafts();
  }

  void changed() {
    editor.root.contentEditable = controller.busy ? 'false' : 'true';
    if (mounted) setState(() {});
  }

  Future<void> refreshDrafts() async {
    try {
      final result = await controller.api.call('/drafts');
      if (mounted) setState(() => drafts = result);
    } catch (error) {
      controller.error = '$error';
      controller.announce();
    }
  }

  String uniqueId() => 'b_${DateTime.now().microsecondsSinceEpoch}';
  void syncEditor() {
    if (step != 'editor' || controller.modules.isEmpty) return;
    if (editor.isComposing) {
      throw StateError(
          'Finish entering the current character before continuing');
    }
    final blocks = editor.snapshot().map((b) => b.toJson()).toList();
    controller.change((content) {
      content['modules'][active]['blocks'] = blocks;
    });
  }

  Future<void> showEditor({bool sync = true}) async {
    if (sync && step == 'editor') syncEditor();
    await controller.flush();
    if (controller.modules.isEmpty) {
      controller.change((content) => content['modules'].add({
            'id': uniqueId(),
            'title': 'New module',
            'blocks': [
              {'id': '${uniqueId()}_text', 'type': 'paragraph', 'text': ''}
            ]
          }));
      await controller.flush();
    }
    active = active.clamp(0, controller.modules.length - 1);
    final module = controller.modules[active];
    for (final block in module['blocks'] ?? []) {
      if (block['type'] == 'image' &&
          !assetUrls.containsKey(block['assetId'])) {
        final bytes = await controller.api
            .bytes('/drafts/${controller.id}/assets/${block['assetId']}');
        final url =
            html.Url.createObjectUrlFromBlob(html.Blob([bytes], 'image/png'));
        assetUrls[block['assetId']] = url;
        objectUrls.add(url);
      }
    }
    final blocks = (module['blocks'] as List? ?? [])
        .map((b) => WorkflowBlock.fromJson(Map<String, dynamic>.from(b)))
        .toList();
    if (blocks.isEmpty) blocks.add(WorkflowBlock.paragraph(uniqueId(), ''));
    editor.load(blocks);
    loadedModule = module['id'];
    if (mounted) setState(() => step = 'editor');
  }

  Future<void> guarded(Future<void> Function() work) => controller.action(work);
  Future<void> start(String mode) => guarded(() async {
        if (controller.draft != null) await controller.flush();
        await controller.create(mode);
        active = 0;
        loadedModule = null;
        if (mounted) {
          setState(() => step = mode == 'existing' ? 'source' : 'setup');
        }
      });
  Future<void> close() => guarded(() async {
        syncEditor();
        await controller.flush();
        widget.onClose();
      });
  Future<void> createCourse() => guarded(() async {
        syncEditor();
        await controller.flush();
        await controller.approve();
        final value = await controller.api.call(
            '/drafts/${controller.id}/create-course',
            method: 'POST',
            body: {'expectedRevision': controller.revision});
        ref.read(courseListProvider.notifier).upsertCourse(
            Course.fromJson(Map<String, dynamic>.from(value)),
            select: true);
        ref.read(currentTabProvider.notifier).state = 1;
        widget.onClose();
      });
  Future<void> preview() => guarded(() async {
        syncEditor();
        await controller.flush();
        final bytes = await controller.api.bytes(
            '/drafts/${controller.id}/render-pdf',
            body: {'expectedRevision': controller.revision});
        final url = html.Url.createObjectUrlFromBlob(
            html.Blob([bytes], 'application/pdf'));
        objectUrls.add(url);
        html.window.open(url, '_blank');
      });
  Future<void> generate(String task) => guarded(() async {
        syncEditor();
        await controller.start(task, instruction: instruction.text);
        if (task == 'outline') {
          if (mounted) setState(() => step = 'outline');
        }
        if (task == 'draft') await showEditor(sync: false);
      });
  Future<void> suggest() => guarded(() async {
        if (assistantScope != 'selected') {
          if (assistantScope == 'document') {
            final confirmed = await showDialog<bool>(
                context: context,
                builder: (context) => AlertDialog(
                        title:
                            const Text('Suggest changes across the document?'),
                        content: const Text(
                            'AI will prepare replacements for all text modules. You will review them before anything is applied.'),
                        actions: [
                          TextButton(
                              onPressed: () => Navigator.pop(context, false),
                              child: const Text('Cancel')),
                          FilledButton(
                              onPressed: () => Navigator.pop(context, true),
                              child: const Text('Prepare suggestions'))
                        ]));
            if (confirmed != true) return;
          }
          syncEditor();
          await controller.start('revise',
              instruction: instruction.text,
              scope: assistantScope,
              moduleId: controller.modules[active]['id']);
          return;
        }
        final selected = editor.selection();
        if (selected == null) {
          throw StateError('Select text in one paragraph first');
        }
        syncEditor();
        await controller.flush();
        await controller.start('edit', instruction: instruction.text, target: {
          'moduleId': controller.modules[active]['id'],
          'blockId': selected.blockId,
          'start': selected.start,
          'end': selected.end,
          'textHash': await DocumentWorkflowController.textHash(selected.text),
        });
      });
  @override
  void dispose() {
    disposed = true;
    controller.removeListener(changed);
    controller.dispose();
    editor.dispose();
    instruction.dispose();
    pasted.dispose();
    for (final url in objectUrls) {
      html.Url.revokeObjectUrl(url);
    }
    super.dispose();
  }

  Future<void> addImage() => guarded(() async {
        syncEditor();
        await controller.flush();
        final selected = await FilePicker.platform.pickFiles(
            type: FileType.custom,
            allowedExtensions: ['png', 'jpg', 'jpeg'],
            withData: true);
        if (selected == null) return;
        final file = selected.files.first;
        if (file.bytes == null || file.size > 10 * 1024 * 1024) {
          throw StateError('Choose an image up to 10 MB');
        }
        final request = http.MultipartRequest('POST',
            Uri.parse('${controller.api.base}/drafts/${controller.id}/assets'));
        request.headers.addAll(ref.read(trainerAuthHeadersProvider));
        request.files.add(http.MultipartFile.fromBytes('file', file.bytes!,
            filename: file.name));
        final response = await http.Response.fromStream(await request.send());
        if (response.statusCode >= 400) {
          throw StateError('Image upload failed; choose a supported image');
        }
        final assetId = jsonDecode(response.body)['assetId'];
        controller
            .change((content) => content['modules'][active]['blocks'].add({
                  'id': uniqueId(),
                  'type': 'image',
                  'assetId': assetId,
                  'caption': file.name,
                  'width': 60,
                  'align': 'left'
                }));
        await showEditor(sync: false);
      });

  Future<void> editProperties(String id) => guarded(() async {
        syncEditor();
        await controller.flush();
        final block = controller.modules[active]['blocks']
            .firstWhere((block) => block['id'] == id);
        final value = jsonDecode(jsonEncode(block)) as Map<String, dynamic>;
        if (!mounted) return;
        final decision = await showDialog<String>(
            context: context,
            builder: (context) => AlertDialog(
                  title: Text('Edit ${value['type']}'),
                  content: SizedBox(
                      width: 440,
                      child: SingleChildScrollView(
                          child:
                              Column(mainAxisSize: MainAxisSize.min, children: [
                        if (value['type'] == 'image') ...[
                          TextFormField(
                              initialValue: value['caption'] ?? '',
                              decoration:
                                  const InputDecoration(labelText: 'Caption'),
                              onChanged: (text) => value['caption'] = text),
                          DropdownButtonFormField<int>(
                              initialValue: value['width'] ?? 60,
                              decoration: const InputDecoration(
                                  labelText: 'Image width'),
                              items: [25, 40, 60, 80, 100]
                                  .map((size) => DropdownMenuItem(
                                      value: size, child: Text('$size%')))
                                  .toList(),
                              onChanged: (size) => value['width'] = size),
                          DropdownButtonFormField<String>(
                              initialValue: value['align'] ?? 'left',
                              decoration:
                                  const InputDecoration(labelText: 'Alignment'),
                              items: ['left', 'center', 'right']
                                  .map((align) => DropdownMenuItem(
                                      value: align, child: Text(align)))
                                  .toList(),
                              onChanged: (align) => value['align'] = align),
                        ],
                        if (value['type'] == 'list')
                          TextFormField(
                              initialValue: (value['items'] as List).join('\n'),
                              minLines: 3,
                              maxLines: 12,
                              decoration: const InputDecoration(
                                  labelText: 'One item per line'),
                              onChanged: (text) => value['items'] = text
                                  .split('\n')
                                  .where((line) => line.trim().isNotEmpty)
                                  .toList()),
                        if (value['type'] == 'table')
                          ...((value['rows'] as List).asMap().entries.map(
                              (row) => Wrap(
                                  children: (row.value as List)
                                      .asMap()
                                      .entries
                                      .map((cell) => SizedBox(
                                          width: 180,
                                          child: Padding(
                                              padding: const EdgeInsets.all(4),
                                              child: TextFormField(
                                                  initialValue: cell.value,
                                                  decoration: InputDecoration(
                                                      labelText:
                                                          'Row ${row.key + 1}, column ${cell.key + 1}'),
                                                  onChanged: (text) =>
                                                      value['rows'][row.key]
                                                          [cell.key] = text))))
                                      .toList()))),
                      ]))),
                  actions: [
                    TextButton(
                        onPressed: () => Navigator.pop(context, 'up'),
                        child: const Text('Move up')),
                    TextButton(
                        onPressed: () => Navigator.pop(context, 'delete'),
                        child: const Text('Remove block')),
                    TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Cancel')),
                    FilledButton(
                        onPressed: () => Navigator.pop(context, 'save'),
                        child: const Text('Save changes'))
                  ],
                ));
        if (decision == null) return;
        controller.change((content) {
          final blocks = content['modules'][active]['blocks'] as List;
          final index = blocks.indexWhere((block) => block['id'] == id);
          if (decision == 'delete') {
            blocks.removeAt(index);
          } else if (decision == 'up' && index > 0) {
            final moved = blocks.removeAt(index);
            blocks.insert(index - 1, moved);
          } else if (decision == 'save') {
            blocks[index] = value;
          }
        });
        await showEditor(sync: false);
      });
  void addBlock(String type) {
    final blocks = editor.snapshot();
    blocks.add(WorkflowBlock.fromJson({
      'id': uniqueId(),
      'type': type,
      if (type == 'list') ...{
        'ordered': false,
        'items': ['First item', 'Second item']
      } else if (type == 'table')
        'rows': [
          ['Heading', 'Heading'],
          ['Content', 'Content']
        ]
      else
        'text': type == 'heading' ? 'Section heading' : ''
    }));
    editor.load(blocks);
    syncEditor();
  }

  Future<void> splitModule(int index) => guarded(() async {
        await controller.flush();
        final module = controller.modules[index];
        final blocks = module['blocks'] as List;
        if (blocks.length < 2) {
          throw StateError('Add at least two content blocks before splitting');
        }
        if (!mounted) return;
        final boundary = await showDialog<int>(
            context: context,
            builder: (context) => SimpleDialog(
                    title: const Text('Split after which block?'),
                    children: [
                      for (var i = 1; i < blocks.length; i++)
                        SimpleDialogOption(
                            onPressed: () => Navigator.pop(context, i),
                            child: Text(
                                'After block $i: ${blocks[i - 1]['text'] ?? blocks[i - 1]['type']}'))
                    ]));
        if (boundary == null) return;
        controller.change((content) {
          final modules = content['modules'] as List;
          final original = modules[index];
          final next = jsonDecode(jsonEncode(original)) as Map<String, dynamic>;
          next['id'] = uniqueId();
          next['title'] = 'Continued: ${original['title']}'.substring(
              0, ('Continued: ${original['title']}').length.clamp(0, 240));
          next['blocks'] = original['blocks'].sublist(boundary);
          next['sourceReferences'] = (next['blocks'] as List)
              .expand((block) => block['sourceReferences'] as List? ?? [])
              .toList();
          original['blocks'] = original['blocks'].sublist(0, boundary);
          final rightReferences = (next['sourceReferences'] as List)
              .map((ref) => '${ref['sourceId']}:${ref['spanId']}')
              .toSet();
          original['sourceReferences'] =
              (original['sourceReferences'] as List? ?? [])
                  .where((ref) => !rightReferences
                      .contains('${ref['sourceId']}:${ref['spanId']}'))
                  .toList();
          modules.insert(index + 1, next);
        });
        await controller.flush();
      });
  void mergeModule(int index) => controller.change((content) {
        final modules = content['modules'] as List;
        final next = modules.removeAt(index + 1);
        modules[index]['blocks'].addAll(next['blocks']);
        modules[index]['sourceReferences'] = [
          ...(modules[index]['sourceReferences'] as List? ?? []),
          ...(next['sourceReferences'] as List? ?? [])
        ];
        modules[index]['sections'] = [
          ...(modules[index]['sections'] as List? ?? []),
          ...(next['sections'] as List? ?? [])
        ].take(20).toList();
      });
  Widget button(String label, VoidCallback onPressed,
          {bool primary = false, bool enabled = true}) =>
      primary
          ? FilledButton(
              onPressed: enabled && !controller.busy ? onPressed : null,
              child: Text(label))
          : OutlinedButton(
              style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.primaryBlue,
                  backgroundColor: Colors.white),
              onPressed: enabled && !controller.busy ? onPressed : null,
              child: Text(label));
  Widget panel(Widget child) => Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.cardDecoration(),
      child: child);
  Widget field(String key, String label, {int lines = 1}) => Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: TextFormField(
        key: ValueKey('${controller.id}-$step-$key'),
        initialValue: controller.content['metadata'][key] ?? '',
        maxLines: lines,
        enabled: !controller.busy,
        decoration: InputDecoration(
            labelText: label, border: const OutlineInputBorder()),
        onChanged: (value) =>
            controller.change((content) => content['metadata'][key] = value),
      ));
  Widget metadata() =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        field('courseName', 'Course name'),
        field('courseDescription', 'Description', lines: 2),
        field('courseObjective', 'Learning objective', lines: 2),
        field('targetAudience', 'Audience'),
        field('courseDifficulty', 'Difficulty'),
        field('courseType', 'Course type'),
        const Text('Language: English'),
      ]);
  Widget home() => ListView(children: [
        const Text('What would you like to create?',
            style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        const Text('Turn your knowledge into a training document.'),
        const SizedBox(height: 24),
        LayoutBuilder(builder: (context, box) {
          final choices = [
            (
              'Use Existing Content',
              'Upload a document or paste existing notes.',
              'existing',
              Icons.description_outlined
            ),
            (
              'Generate with AI',
              'Describe a topic and review an AI-generated outline.',
              'ai',
              Icons.auto_awesome
            ),
            (
              'Start blank',
              'Write your own modules with optional AI assistance.',
              'blank',
              Icons.edit_note
            ),
          ]
              .map((choice) => SizedBox(
                  width: box.maxWidth < 700
                      ? box.maxWidth
                      : (box.maxWidth - 32) / 3,
                  child: InkWell(
                      onTap: controller.busy ? null : () => start(choice.$3),
                      child: panel(Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(choice.$4,
                                color: AppTheme.primaryBlue, size: 30),
                            const SizedBox(height: 18),
                            Text(choice.$1,
                                style: const TextStyle(
                                    fontWeight: FontWeight.bold)),
                            const SizedBox(height: 8),
                            Text(choice.$2),
                          ])))))
              .toList();
          return Wrap(spacing: 16, runSpacing: 16, children: choices);
        }),
        const SizedBox(height: 28),
        const Text('Saved drafts',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        if (drafts.isEmpty)
          const Padding(
              padding: EdgeInsets.all(16),
              child: Text('Your unfinished documents will appear here.')),
        ...drafts.map((draft) => ListTile(
            title: Text((draft['title'] as String?)?.isNotEmpty == true
                ? draft['title']
                : 'Untitled document'),
            subtitle: Text('Revision ${draft['revision']}'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => guarded(() async {
                  await controller.open(draft['draft_id']);
                  active = 0;
                  if (controller.operation?['status'] == 'proposed' &&
                      controller.operation?['request']['task'] == 'outline') {
                    setState(() => step = 'outline');
                  } else if (controller.modules.isEmpty) {
                    setState(() => step =
                        controller.content['entryMode'] == 'existing'
                            ? 'source'
                            : 'setup');
                  } else {
                    await showEditor(sync: false);
                  }
                }))),
      ]);
  Widget source() {
    final files = ref.watch(fileListProvider).files;
    return ListView(children: [
      const Text('Use your existing content',
          style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
      const SizedBox(height: 16),
      button(
          'Upload a new document',
          () => guarded(() async {
                final selected = await FilePicker.platform.pickFiles(
                    type: FileType.custom,
                    allowedExtensions: ['pdf', 'docx', 'pptx'],
                    withData: true);
                if (selected == null) return;
                final file = selected.files.first;
                if (file.size > 20 * 1024 * 1024 || file.bytes == null) {
                  throw StateError('Choose a file up to 20 MB');
                }
                // Unique filename prevents overwriting an existing original upload.
                final request = http.MultipartRequest(
                    'POST', Uri.parse(AppConstants.uploadEndpoint));
                request.headers.addAll(ref.read(trainerAuthHeadersProvider));
                request.files.add(http.MultipartFile.fromBytes(
                    'file', file.bytes!,
                    filename:
                        '${DateTime.now().microsecondsSinceEpoch}-${file.name}'));
                final response =
                    await http.Response.fromStream(await request.send());
                if (response.statusCode >= 400) {
                  throw StateError('Upload failed; try again');
                }
                final uploaded = jsonDecode(response.body);
                await controller.importSource(
                    documentId: uploaded['document_id']);
                await ref.read(fileListProvider.notifier).fetchFiles();
                setState(() => step = 'outline');
              })),
      const SizedBox(height: 18),
      const Text('Or choose an existing upload'),
      ...files.map((file) => ListTile(
          title: Text(file.displayName),
          trailing: const Icon(Icons.arrow_forward),
          onTap: controller.busy
              ? null
              : () => guarded(() async {
                    await controller.importSource(documentId: file.documentId);
                    setState(() => step = 'outline');
                  }))),
      const SizedBox(height: 18),
      TextField(
          controller: pasted,
          minLines: 5,
          maxLines: 10,
          decoration: const InputDecoration(
              labelText: 'Or paste existing content',
              border: OutlineInputBorder())),
      const SizedBox(height: 12),
      button(
          'Review pasted content',
          () => guarded(() async {
                await controller.importSource(text: pasted.text);
                setState(() => step = 'outline');
              }),
          primary: true),
    ]);
  }

  Widget setup() => ListView(children: [
        Text(
            controller.content['entryMode'] == 'ai'
                ? 'Describe your training'
                : 'Set up your document',
            style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
        const SizedBox(height: 18),
        metadata(),
        if (controller.content['entryMode'] == 'ai') ...[
          ExpansionTile(
              title: const Text('Optional reference documents'),
              children: [
                ...ref.watch(fileListProvider).files.map((file) => ListTile(
                    title: Text(file.displayName),
                    onTap: controller.busy
                        ? null
                        : () => guarded(() => controller.importSource(
                            documentId: file.documentId,
                            referenceOnly: true)))),
                ...controller.sources
                    .map((source) => Text('Attached: ${source['name']}')),
              ]),
          DropdownButtonFormField<int>(
              initialValue: controller.content['settings']['moduleCount'],
              decoration: const InputDecoration(labelText: 'Number of modules'),
              items: [
                for (var i = 2; i <= 8; i++)
                  DropdownMenuItem(
                      value: i,
                      child: Text(i == 4 ? 'Default — 4 modules' : '$i modules'))
              ],
              onChanged: controller.busy
                  ? null
                  : (value) => controller.change(
                      (content) => content['settings']['moduleCount'] = value)),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
              initialValue: controller.content['settings']['detailLevel'],
              decoration: const InputDecoration(labelText: 'Detail level'),
              items: ['short', 'standard', 'detailed']
                  .map((v) => DropdownMenuItem(value: v, child: Text(v)))
                  .toList(),
              onChanged: controller.busy
                  ? null
                  : (value) => controller.change(
                      (content) => content['settings']['detailLevel'] = value)),
          const SizedBox(height: 16),
          ExpansionTile(title: const Text('Writing preferences'), children: [
            TextFormField(
                initialValue: controller.content['settings']['tone'],
                decoration: const InputDecoration(labelText: 'Tone'),
                onChanged: (value) =>
                    controller.change((c) => c['settings']['tone'] = value)),
            DropdownButtonFormField<String>(
                initialValue: controller.content['settings']['writingFocus'],
                decoration: const InputDecoration(labelText: 'Writing focus'),
                items: const [
                  DropdownMenuItem(value: 'balanced', child: Text('Balanced')),
                  DropdownMenuItem(
                      value: 'practical', child: Text('Practical')),
                  DropdownMenuItem(
                      value: 'conceptual', child: Text('Conceptual'))
                ],
                onChanged: (value) => controller
                    .change((c) => c['settings']['writingFocus'] = value)),
            for (final preference in const {
              'includeScenarios': 'Practical scenarios',
              'includeBadGood': 'Weak and better examples',
              'includeTakeaways': 'Key takeaways',
              'includeMistakes': 'Common mistakes'
            }.entries)
              CheckboxListTile(
                  title: Text(preference.value),
                  value: controller.content['settings'][preference.key],
                  onChanged: controller.busy
                      ? null
                      : (value) => controller.change(
                          (c) => c['settings'][preference.key] = value)),
          ]),
          button('Generate outline', () => generate('outline'), primary: true),
        ] else
          button('Open blank editor', () => guarded(() => showEditor()),
              primary: true),
      ]);
  Widget outline() => ListView(children: [
        const Text('Review the outline',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
        const SizedBox(height: 16),
        if (controller.operation?['request']['task'] == 'outline' &&
            controller.operation?['status'] == 'proposed') ...[
          ...((controller.operation!['result']['modules'] as List).map((m) =>
              ListTile(
                  title: Text(m['title']), subtitle: Text(m['objective'])))),
          Wrap(spacing: 12, children: [
            button(
                'Use this outline',
                () => guarded(() async {
                      await controller.accept();
                    }),
                primary: true),
            button(
                'Reject & return to setup',
                () => guarded(() async {
                      await controller.reject();
                      setState(() => step = 'setup');
                    }))
          ]),
        ] else ...[
          ...controller.modules.asMap().entries.map((entry) {
            final m = entry.value, index = entry.key;
            return Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: panel(Column(children: [
                  Row(children: [
                    Checkbox(
                        value: m['included'] ?? true,
                        onChanged: controller.busy
                            ? null
                            : (value) => controller.change((c) =>
                                c['modules'][index]['included'] = value)),
                    Expanded(
                        child: TextFormField(
                            key: ValueKey('${m['id']}-title'),
                            initialValue: m['title'],
                            decoration: const InputDecoration(
                                labelText: 'Module title'),
                            onChanged: (value) => controller.change(
                                (c) => c['modules'][index]['title'] = value))),
                    IconButton(
                        onPressed: index == 0 || controller.busy
                            ? null
                            : () => controller.change((c) {
                                  final item = c['modules'].removeAt(index);
                                  c['modules'].insert(index - 1, item);
                                }),
                        icon: const Icon(Icons.arrow_upward),
                        tooltip: 'Move module up'),
                    IconButton(
                        onPressed:
                            controller.busy ? null : () => splitModule(index),
                        icon: const Icon(Icons.call_split),
                        tooltip: 'Split module'),
                    IconButton(
                        onPressed: controller.busy ||
                                index + 1 >= controller.modules.length
                            ? null
                            : () => mergeModule(index),
                        icon: const Icon(Icons.merge),
                        tooltip: 'Merge with next module')
                  ]),
                  TextFormField(
                      key: ValueKey('${m['id']}-objective'),
                      initialValue: m['objective'] ?? '',
                      decoration:
                          const InputDecoration(labelText: 'Module objective'),
                      onChanged: (value) => controller.change(
                          (c) => c['modules'][index]['objective'] = value)),
                  if ((m['blocks'] as List? ?? []).isNotEmpty)
                    Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Text(
                            (m['blocks'] as List)
                                .where((b) => b['text'] != null)
                                .map((b) => b['text'])
                                .join('\n'),
                            maxLines: 4,
                            overflow: TextOverflow.ellipsis)),
                ])));
          }),
          ...controller.sources.map((s) => panel(Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s['name'],
                        style: const TextStyle(fontWeight: FontWeight.bold)),
                    ...((s['issues'] as List).map((issue) => Text('• $issue'))),
                    if ((s['issues'] as List).isNotEmpty)
                      CheckboxListTile(
                          value: s['acknowledged'],
                          title: const Text(
                              'I reviewed the extraction against the original'),
                          onChanged: (value) => guarded(() =>
                              controller.acknowledge(s['id'], value ?? false))),
                    button(
                        'Download original',
                        () => guarded(() async {
                              final bytes = await controller.api.bytes(
                                  '/drafts/${controller.id}/sources/${s['id']}/original');
                              final url = html.Url.createObjectUrlFromBlob(
                                  html.Blob([bytes]));
                              objectUrls.add(url);
                              html.AnchorElement(href: url)
                                ..download = s['name']
                                ..click();
                            }))
                  ]))),
          const SizedBox(height: 20),
          ExpansionTile(
              title: const Text('Course details'), children: [metadata()]),
          Wrap(spacing: 12, runSpacing: 12, children: [
            button('Approve outline', () => guarded(controller.approve),
                primary: controller.draft!['approvedOutline'] == null),
            if (controller.draft!['approvedOutline'] != null &&
                controller.content['entryMode'] == 'ai')
              button('Write modules & open editor', () => generate('draft'),
                  primary: true),
            if (controller.draft!['approvedOutline'] != null &&
                controller.content['entryMode'] != 'ai')
              button('Create Course', createCourse, primary: true),
            button('Review in editor first', () => guarded(() => showEditor())),
          ]),
        ],
      ]);
  Widget moduleSidebar() =>
      panel(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('MODULES', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        ...controller.modules.asMap().entries.map((entry) => ListTile(
            selected: entry.key == active,
            title: Text(entry.value['title']),
            onTap: controller.busy
                ? null
                : () => guarded(() async {
                      syncEditor();
                      await controller.flush();
                      active = entry.key;
                      await showEditor(sync: false);
                    }))),
        button(
            'Add module',
            () => guarded(() async {
                  syncEditor();
                  controller.change((c) => c['modules'].add(
                      {'id': uniqueId(), 'title': 'New module', 'blocks': []}));
                  await controller.flush();
                  active = controller.modules.length - 1;
                  await showEditor(sync: false);
                })),
        const SizedBox(height: 12),
        button(
            'Version history',
            () => guarded(() async {
                  await controller.flush();
                  final versions = await controller.api
                      .call('/drafts/${controller.id}/revisions');
                  if (!mounted) return;
                  final selected = await showDialog<int>(
                      context: context,
                      builder: (context) => SimpleDialog(
                              title: const Text('Restore a previous version'),
                              children: [
                                ...(versions as List).map((v) => SimpleDialogOption(
                                    onPressed: () =>
                                        Navigator.pop(context, v['revision']),
                                    child: Text(
                                        'Revision ${v['revision']} · ${v['reason']}')))
                              ]));
                  if (selected != null) {
                    await controller.restore(selected);
                    await showEditor(sync: false);
                  }
                })),
      ]));
  Widget assistant() =>
      panel(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('AI Assistant',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
            initialValue: assistantScope,
            decoration: const InputDecoration(labelText: 'Scope'),
            items: const [
              DropdownMenuItem(value: 'selected', child: Text('Selected text')),
              DropdownMenuItem(value: 'module', child: Text('Current module')),
              DropdownMenuItem(value: 'document', child: Text('Whole document'))
            ],
            onChanged: controller.busy
                ? null
                : (value) => setState(() => assistantScope = value!)),
        const SizedBox(height: 12),
        TextField(
            controller: instruction,
            minLines: 3,
            maxLines: 6,
            decoration: const InputDecoration(
                hintText: 'Make this more practical for new employees…',
                border: OutlineInputBorder())),
        const SizedBox(height: 12),
        button('Suggest edit', suggest, primary: true),
        button(
            'Add a practical scenario',
            () => guarded(() async {
                  syncEditor();
                  await controller.start('insert',
                      instruction: instruction.text.isEmpty
                          ? 'Add a practical illustrative scenario'
                          : instruction.text,
                      scope: 'module',
                      moduleId: controller.modules[active]['id']);
                })),
        const SizedBox(height: 8),
        button('Ask about source', () => generate('answer')),
        const SizedBox(height: 8),
        button(
            'Draft empty modules',
            () => guarded(() async {
                  syncEditor();
                  await controller.approve();
                  await controller.start('draft');
                  await showEditor(sync: false);
                })),
        if (controller.operation?['status'] == 'proposed' &&
            ['edit', 'revise', 'insert']
                .contains(controller.operation?['request']['task'])) ...[
          const Divider(height: 32),
          const Text('Suggested change',
              style: TextStyle(fontWeight: FontWeight.bold)),
          if (controller.operation!['result']['changes'] != null)
            ...((controller.operation!['result']['changes'] as List).map(
                (change) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Original: ${change['originalText']}'),
                          const SizedBox(height: 6),
                          Text('Proposed: ${change['replacementText']}')
                        ]))))
          else
            Text(controller.operation!['result']['replacementText']),
          Text(controller.operation!['result']['summary']),
          const SizedBox(height: 12),
          Wrap(spacing: 8, children: [
            button(
                'Accept',
                () => guarded(() async {
                      await controller.accept();
                      await showEditor(sync: false);
                    }),
                primary: true),
            button('Reject', () => guarded(controller.reject))
          ]),
        ],
        if (controller.operation?['status'] == 'completed' &&
            controller.operation?['request']['task'] == 'answer') ...[
          const Divider(height: 32),
          Text(controller.operation!['result']['answer']),
          if (controller.operation!['result']['insufficientEvidence'] == true)
            const Text(
                'The available source evidence is incomplete for this question.',
                style: TextStyle(fontSize: 12, fontStyle: FontStyle.italic)),
          ...((controller.operation!['result']['sourceReferences'] as List? ??
                  [])
              .map((reference) {
            final source = controller.sources
                .where((s) => s['id'] == reference['sourceId'])
                .firstOrNull;
            final span = (source?['spans'] as List? ?? [])
                .where((s) => s['id'] == reference['spanId'])
                .firstOrNull;
            return Text(
                '${source?['name'] ?? 'Source'} · ${span?['location'] ?? ''}',
                style: const TextStyle(fontSize: 12));
          })),
        ],
      ]));
  Widget editorView() => LayoutBuilder(builder: (context, box) {
        final canvas = panel(Column(children: [
          TextFormField(
              key: ValueKey(loadedModule),
              enabled: !controller.busy,
              initialValue: controller.modules[active]['title'],
              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              decoration: const InputDecoration(
                  border: InputBorder.none,
                  enabledBorder: InputBorder.none,
                  focusedBorder: UnderlineInputBorder()),
              onChanged: (value) => controller
                  .change((c) => c['modules'][active]['title'] = value)),
          Wrap(children: [
            IconButton(
                onPressed: controller.busy ? null : () => editor.format('bold'),
                icon: const Icon(Icons.format_bold),
                tooltip: 'Bold'),
            IconButton(
                onPressed:
                    controller.busy ? null : () => editor.format('italic'),
                icon: const Icon(Icons.format_italic),
                tooltip: 'Italic'),
            button('Add image', addImage),
            button('Heading', () => addBlock('heading')),
            button('List', () => addBlock('list')),
            button('Table', () => addBlock('table')),
            button('Add paragraph', () {
              final blocks = editor.snapshot();
              blocks.add(WorkflowBlock.paragraph(uniqueId(), ''));
              editor.load(blocks);
              syncEditor();
            })
          ]),
          const Divider(),
          SizedBox(height: 460, child: HtmlElementView(viewType: viewId)),
        ]));
        if (box.maxWidth < 950) {
          return ListView(children: [
            moduleSidebar(),
            const SizedBox(height: 12),
            canvas,
            const SizedBox(height: 12),
            assistant()
          ]);
        }
        return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(
              width: 220, child: SingleChildScrollView(child: moduleSidebar())),
          const SizedBox(width: 16),
          Expanded(child: SingleChildScrollView(child: canvas)),
          const SizedBox(width: 16),
          SizedBox(width: 280, child: SingleChildScrollView(child: assistant()))
        ]);
      });
  @override
  Widget build(BuildContext context) => Column(children: [
        Container(
            width: double.infinity,
            color: AppTheme.primaryBlue,
            padding: const EdgeInsets.all(16),
            child: Wrap(
                spacing: 12,
                runSpacing: 10,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  TextButton(
                      onPressed: controller.busy ? null : close,
                      child: const Text('← Documents',
                          style: TextStyle(color: Colors.white))),
                  Text(
                      controller.draft == null
                          ? 'Create Document'
                          : controller.content['metadata']['courseName'],
                      style: const TextStyle(
                          color: Colors.white, fontWeight: FontWeight.bold)),
                  if (controller.draft != null)
                    Text(controller.saveStatus,
                        style: const TextStyle(color: Colors.white)),
                  if (step == 'editor') ...[
                    button(
                        'Course details',
                        () => guarded(() async {
                              syncEditor();
                              await controller.flush();
                              setState(() => step = 'outline');
                            })),
                    button('Preview PDF', preview),
                    button('Create Course', createCourse, primary: true)
                  ],
                  if (step != 'home')
                    button(
                        'Saved drafts',
                        () => guarded(() async {
                              syncEditor();
                              await controller.flush();
                              await refreshDrafts();
                              setState(() => step = 'home');
                            })),
                ])),
        if (step != 'home')
          Padding(
              padding: const EdgeInsets.all(12),
              child: Text(
                  'Setup  →  Outline  →  Editor${controller.content['entryMode'] == 'existing' ? ' (optional)' : ''}  →  Courses')),
        if (controller.error != null)
          MaterialBanner(content: Text(controller.error!), actions: [
            if (controller.conflict)
              button(
                  'Keep my edits as a copy',
                  () => guarded(() async {
                        await controller.keepSeparateCopy();
                        await showEditor(sync: false);
                      })),
            if (controller.conflict)
              button(
                  'Reload saved version',
                  () => guarded(() async {
                        await controller.open(controller.id);
                        await showEditor(sync: false);
                      }))
            else
              button('Retry save', () => guarded(controller.flush))
          ]),
        if (controller.busy)
          Column(children: [
            const LinearProgressIndicator(),
            Padding(
                padding: const EdgeInsets.all(8),
                child: Row(children: [
                  Expanded(
                      child: Text(
                          controller.operation?['progress'] ?? 'Working…')),
                  if (controller.operation != null)
                    TextButton(
                        onPressed: controller.cancel,
                        child: const Text('Cancel'))
                ]))
          ]),
        Expanded(
            child: Padding(
                padding: const EdgeInsets.all(16),
                child: switch (step) {
                  'source' => source(),
                  'setup' => setup(),
                  'outline' => outline(),
                  'editor' => editorView(),
                  _ => home()
                })),
      ]);
}
