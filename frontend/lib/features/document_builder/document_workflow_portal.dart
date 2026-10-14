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
import 'package:frontend/features/documents/document_portal.dart';
import 'document_workflow_editor.dart';
import 'document_workflow_models.dart';

class DocumentBuilderEntry extends ConsumerStatefulWidget {
  final VoidCallback onClose;
  final Widget? legacy;
  const DocumentBuilderEntry({super.key, required this.onClose, this.legacy});
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
        return widget.legacy ?? DocumentBuilderPortal(onClose: widget.onClose);
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
  String assistantScope = 'module';
  bool assistantVisible = false;
  bool sourceQuestion = false;
  final question = TextEditingController();
  String? proposedOperation;
  List<Map<String, dynamic>> proposedOutline = [];
  String? retryTask;
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
    editor.load(blocks, moduleTitle: module['title']);
    loadedModule = module['id'];
    if (mounted) setState(() => step = 'editor');
  }

  Future<void> guarded(Future<void> Function() work) => controller.action(work);
  Future<void> start(String mode) => guarded(() async {
        if (controller.draft != null) await controller.flush();
        if (mode != 'existing') await controller.create(mode);
        if (mode == 'existing') controller.operation = null;
        retryTask = null;
        assistantVisible = false;
        assistantScope = 'module';
        sourceQuestion = false;
        proposedOperation = null;
        proposedOutline = [];
        active = 0;
        loadedModule = null;
        if (mounted) {
          setState(() => step = mode == 'existing' ? 'source' : 'setup');
        }
      });
  Future<void> close() => guarded(() async {
        syncEditor();
        await controller.flush();
        await refreshDrafts();
        if (mounted) setState(() => step = 'home');
      });
  Future<void> createCourse() => guarded(() async {
        syncEditor();
        await controller.flush();
        if (controller.draft!['approvedOutline'] == null) {
          setState(() => step = 'outline');
          throw StateError(
              'Review and approve the current outline before creating your course');
        }
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
        retryTask = task;
        await controller.start(task,
            instruction: task == 'answer' ? question.text : instruction.text);
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
    question.dispose();
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
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFE0E6F0))),
      child: child);
  Widget field(String key, String label, {int lines = 1}) => Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Semantics(
          container: true,
          child: TextFormField(
            key: ValueKey('${controller.id}-$step-$key'),
            initialValue: controller.content['metadata'][key] ?? '',
            maxLines: lines,
            enabled: !controller.busy,
            decoration: InputDecoration(
                labelText: label, border: const OutlineInputBorder()),
            onChanged: (value) => controller.change((content) {
              final meta = content['metadata'];
              if (key == 'courseObjective' &&
                  ((meta['courseDescription'] as String? ?? '')
                          .trim()
                          .isEmpty ||
                      meta['courseDescription'] == meta['courseObjective'])) {
                meta['courseDescription'] = value;
              }
              meta[key] = value;
            }),
          )));
  Widget metadata({bool minimal = false}) =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        field('courseName', 'Topic or title'),
        if (!minimal) ...[
          field('targetAudience', 'Who is this for?'),
          field('courseObjective', 'What should employees be able to do?',
              lines: 3),
        ],
      ]);

  Future<void> openReadyDocument(String fileName) async {
    await controller.flush();
    await ref
        .read(courseGenerationProvider.notifier)
        .generateCourse(fileName, ref);
    final result = ref.read(courseGenerationProvider);
    if (result.status == GenerationStatus.error) {
      ref.read(currentTabProvider.notifier).state = 0;
      throw StateError(
          result.error ?? 'Could not prepare the course blueprint. Try again.');
    }
    if (mounted) setState(() => step = 'home');
  }

  Future<void> useReadyDocument(PDFFile file) => guarded(() async {
        syncEditor();
        await openReadyDocument(file.fileName);
      });

  Future<void> importDocument(String id) => guarded(() async {
        if (step == 'editor') syncEditor();
        await controller.flush();
        await controller.create('existing');
        retryTask = null;
        await controller.importSource(documentId: id);
        active = 0;
        loadedModule = null;
        setState(() => step = 'outline');
      });

  Future<void> previewFile(PDFFile file) async {
    await showDialog<void>(
        context: context,
        builder: (context) => Dialog(
            child: SizedBox(
                width: 1000,
                height: 650,
                child: Column(children: [
                  Padding(
                      padding: const EdgeInsets.all(14),
                      child: Row(children: [
                        Expanded(child: Text(file.displayName)),
                        IconButton(
                            tooltip: 'Close preview',
                            onPressed: () => Navigator.pop(context),
                            icon: const Icon(Icons.close)),
                      ])),
                  Expanded(child: PDFViewerCard(selectedFile: file)),
                ]))));
  }

  Widget home() {
    final files = ref.watch(fileListProvider).files;
    return ListView(children: [
      const Text('Create a training document',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
      const SizedBox(height: 16),
      LayoutBuilder(builder: (context, box) {
        final choices = [
          (
            'Use existing content',
            'Upload a document, choose an existing file, or paste notes.',
            'existing',
            Icons.description_outlined
          ),
          (
            'Generate with AI',
            'Describe the topic, audience, and learning goals. Review an AI draft.',
            'ai',
            Icons.auto_awesome_outlined
          ),
          (
            'Start blank',
            'Name your document and start writing.',
            'blank',
            Icons.note_add_outlined
          ),
        ];
        return Wrap(
            spacing: 16,
            runSpacing: 16,
            children: choices
                .map((c) => SizedBox(
                      width: box.maxWidth < 700
                          ? box.maxWidth
                          : (box.maxWidth - 32) / 3,
                      child: Semantics(
                          button: true,
                          label: c.$1,
                          child: InkWell(
                            onTap: controller.busy ? null : () => start(c.$3),
                            borderRadius: BorderRadius.circular(12),
                            child: panel(Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Icon(c.$4,
                                      color: AppTheme.primaryBlue, size: 24),
                                  const SizedBox(height: 20),
                                  Text(c.$1,
                                      style: const TextStyle(
                                          fontSize: 17,
                                          fontWeight: FontWeight.w600)),
                                  const SizedBox(height: 8),
                                  Text(c.$2,
                                      style: const TextStyle(
                                          color: AppTheme.textSecondary)),
                                ])),
                          )),
                    ))
                .toList());
      }),
      const SizedBox(height: 24),
      panel(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Continue your drafts',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        if (drafts.isEmpty)
          const Padding(
              padding: EdgeInsets.only(top: 14),
              child: Text('Your unfinished documents will appear here.')),
        ...drafts.map((d) => ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text((d['title'] as String?)?.isNotEmpty == true
                  ? d['title']
                  : 'Untitled document'),
              subtitle:
                  Text('Last edited: ${d['updated_at'] ?? 'Saved draft'}'),
              trailing: button(
                  'Open draft',
                  () => guarded(() async {
                        await controller.open(d['draft_id']);
                        active = 0;
                        loadedModule = null;
                        proposedOperation = null;
                        assistantVisible = false;
                        if (controller.operation?['request']['task'] ==
                                'outline' &&
                            controller.operation?['status'] == 'proposed') {
                          setState(() => step = 'outline');
                        } else if (controller.modules.isEmpty) {
                          setState(() => step =
                              controller.content['entryMode'] == 'existing'
                                  ? 'source'
                                  : 'setup');
                        } else {
                          await showEditor(sync: false);
                        }
                      })),
            )),
      ])),
      const SizedBox(height: 20),
      panel(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Your documents',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        if (files.isEmpty)
          const Padding(
              padding: EdgeInsets.only(top: 14),
              child: Text(
                  'Uploaded documents will appear here. Start with Use existing content.')),
        ...files.map((f) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Wrap(
                spacing: 12,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  const Icon(Icons.description_outlined,
                      color: AppTheme.primaryBlue),
                  SizedBox(
                      width: 280,
                      child: Text(f.displayName,
                          maxLines: 2, overflow: TextOverflow.ellipsis)),
                  button('Preview', () => previewFile(f)),
                  button(
                      'Create course from document', () => useReadyDocument(f)),
                  TextButton(
                      onPressed: controller.busy
                          ? null
                          : () => importDocument(f.documentId),
                      child: const Text('Edit first')),
                ]))),
      ])),
    ]);
  }

  Widget formPage(Widget child) => ListView(children: [
        Align(
            alignment: Alignment.topCenter,
            child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 780),
                child: panel(child))),
      ]);

  Future<void> uploadSource({bool editFirst = false}) => guarded(() async {
        final selected = await FilePicker.platform.pickFiles(
            type: FileType.custom,
            allowedExtensions: ['pdf', 'docx', 'pptx'],
            withData: true);
        if (selected == null) return;
        final f = selected.files.first;
        if (f.size > 20 * 1024 * 1024 || f.bytes == null) {
          throw StateError('Choose a PDF, DOCX or PPTX file up to 20 MB');
        }
        final request = http.MultipartRequest(
            'POST', Uri.parse(AppConstants.uploadEndpoint));
        request.headers.addAll(ref.read(trainerAuthHeadersProvider));
        request.files.add(http.MultipartFile.fromBytes('file', f.bytes!,
            filename: '${DateTime.now().microsecondsSinceEpoch}-${f.name}'));
        final response = await http.Response.fromStream(await request.send());
        if (response.statusCode >= 400) {
          throw StateError('Upload failed. Try uploading the document again.');
        }
        final uploaded = jsonDecode(response.body);
        await ref.read(fileListProvider.notifier).fetchFiles();
        if (editFirst) {
          await controller.create('existing');
          await controller.importSource(documentId: uploaded['document_id']);
          active = 0;
          setState(() => step = 'outline');
        } else {
          await openReadyDocument(uploaded['file_name']);
        }
      });

  Widget source() => formPage(
          Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Bring in your existing content',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        const Text(
            'Ready-made documents go straight to Blueprint. Review the extracted course, then generate videos and quizzes.'),
        const SizedBox(height: 24),
        button('Upload & open Blueprint', () => uploadSource(), primary: true),
        const SizedBox(height: 8),
        const Text('PDF, DOCX or PPTX · Up to 20 MB',
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
        ExpansionTile(
            title: const Text('Choose an existing document'),
            children: ref
                .watch(fileListProvider)
                .files
                .map((f) => ListTile(
                    title: Text(f.displayName),
                    trailing: TextButton(
                        onPressed:
                            controller.busy ? null : () => useReadyDocument(f),
                        child: const Text('Open Blueprint')),
                    onTap: controller.busy ? null : () => useReadyDocument(f)))
                .toList()),
        ExpansionTile(
            title: const Text('Review or edit a document first · optional'),
            children: [
              const Text(
                  'Create an editable copy only when you need to change the document.'),
              button(
                  'Upload to edit first', () => uploadSource(editFirst: true)),
              ...ref.watch(fileListProvider).files.map((f) => ListTile(
                  title: Text(f.displayName),
                  trailing: const Icon(Icons.edit_outlined),
                  onTap: controller.busy
                      ? null
                      : () => importDocument(f.documentId))),
            ]),
        ExpansionTile(title: const Text('Paste content instead'), children: [
          TextField(
              controller: pasted,
              minLines: 5,
              maxLines: 12,
              decoration: const InputDecoration(
                  labelText: 'Existing notes', border: OutlineInputBorder())),
          const SizedBox(height: 12),
          button(
              'Review outline',
              () => guarded(() async {
                    await controller.create('existing');
                    await controller.importSource(text: pasted.text);
                    active = 0;
                    setState(() => step = 'outline');
                  }),
              primary: true),
        ]),
      ]));

  Widget setup() {
    final ai = controller.content['entryMode'] == 'ai';
    return formPage(
        Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(ai ? 'What would you like to teach?' : 'Name your document',
          style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w600)),
      const SizedBox(height: 8),
      Text(ai
          ? 'Three essentials. Start with four modules or choose a different count.'
          : 'You can add training details later.'),
      const SizedBox(height: 24),
      metadata(minimal: !ai),
      if (ai)
        ExpansionTile(
            title: const Text('Customize generation · optional'),
            children: [
              DropdownButtonFormField<int>(
                  initialValue: controller.content['settings']['moduleCount'],
                  decoration: const InputDecoration(labelText: 'Modules'),
                  items: [
                    for (var i = 2; i <= 8; i++)
                      DropdownMenuItem(
                          value: i,
                          child: Text(
                              i == 4 ? 'Default — 4 modules' : '$i modules'))
                  ],
                  onChanged: controller.busy
                      ? null
                      : (v) => controller
                          .change((c) => c['settings']['moduleCount'] = v)),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                  initialValue: controller.content['settings']['detailLevel'],
                  decoration:
                      const InputDecoration(labelText: 'Document length'),
                  items: const [
                    DropdownMenuItem(value: 'short', child: Text('Concise')),
                    DropdownMenuItem(
                        value: 'standard', child: Text('Standard')),
                    DropdownMenuItem(value: 'detailed', child: Text('Detailed'))
                  ],
                  onChanged: controller.busy
                      ? null
                      : (v) => controller
                          .change((c) => c['settings']['detailLevel'] = v)),
              CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Include illustrative workplace scenarios'),
                  value: controller.content['settings']['includeScenarios'],
                  onChanged: controller.busy
                      ? null
                      : (v) => controller.change(
                          (c) => c['settings']['includeScenarios'] = v)),
              const Text(
                  'Professional tone and key takeaways are included by default.',
                  style:
                      TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              ExpansionTile(
                  title: const Text('Reference documents'),
                  children: [
                    ...ref.watch(fileListProvider).files.map((f) => ListTile(
                        title: Text(f.displayName),
                        trailing: controller.sources
                                .any((s) => s['documentId'] == f.documentId)
                            ? const Icon(Icons.check)
                            : null,
                        onTap: controller.busy
                            ? null
                            : () => guarded(() => controller.importSource(
                                documentId: f.documentId,
                                referenceOnly: true)))),
                    ...controller.sources
                        .map((s) => Text('Attached: ${s['name']}')),
                  ]),
            ]),
      const SizedBox(height: 24),
      button(
          ai ? 'Generate outline' : 'Open editor',
          () => guarded(() async {
                if ((controller.content['metadata']['courseName'] as String)
                    .trim()
                    .isEmpty) {
                  throw StateError('Enter a topic or title');
                }
                if (ai) {
                  retryTask = 'outline';
                  await controller.start('outline');
                  proposedOperation = null;
                  setState(() => step = 'outline');
                } else {
                  await showEditor();
                }
              }),
          primary: true),
    ]));
  }

  bool get hasOutlineProposal =>
      controller.operation?['request']['task'] == 'outline' &&
      controller.operation?['status'] == 'proposed';
  void loadProposedOutline() {
    if (!hasOutlineProposal ||
        proposedOperation == controller.operation!['id']) {
      return;
    }
    proposedOperation = controller.operation!['id'];
    proposedOutline = (controller.operation!['result']['modules'] as List)
        .map((m) => {
              ...Map<String, dynamic>.from(m),
              '_key': uniqueId(),
              'included': true
            })
        .toList();
  }

  Future<void> approveOutline() => guarded(() async {
        if (hasOutlineProposal) {
          final reviewed = proposedOutline
              .where((m) => m['included'] != false)
              .map((m) => <String, dynamic>{
                    'title': m['title'],
                    'objective': m['objective'],
                    'sections': m['sections']
                  })
              .toList();
          await controller.accept(outline: reviewed);
          proposedOperation = null;
        }
        await controller.approve();
        if (controller.content['entryMode'] == 'ai') {
          retryTask = 'draft';
          await controller.start('draft');
          await showEditor(sync: false);
        }
      });

  Widget outline() {
    loadProposedOutline();
    final proposal = hasOutlineProposal;
    final items = proposal ? proposedOutline : controller.modules;
    final ai = controller.content['entryMode'] == 'ai';
    final approved = controller.draft!['approvedOutline'] != null;
    return formPage(
        Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('Review the outline',
          style: TextStyle(fontSize: 24, fontWeight: FontWeight.w600)),
      const SizedBox(height: 8),
      const Text(
          'Adjust the titles, learning goals and order. Approve when the structure is right.'),
      const SizedBox(height: 16),
      if (!proposal)
        ExpansionTile(
            title: const Text('Training details'), children: [metadata()]),
      ...items.asMap().entries.map((e) {
        final m = e.value, index = e.key;
        void update(String key, dynamic value) {
          if (proposal) {
            setState(() => m[key] = value);
          } else {
            controller.change((c) => c['modules'][index][key] = value);
          }
        }

        return Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Column(children: [
              Row(children: [
                Checkbox(
                    value: m['included'] != false,
                    onChanged:
                        controller.busy ? null : (v) => update('included', v)),
                Expanded(
                    child: TextFormField(
                        key: ValueKey('${m['_key'] ?? m['id']}-outline-title'),
                        initialValue: m['title'],
                        enabled: !controller.busy,
                        decoration: InputDecoration(
                            labelText: 'Module ${index + 1} title'),
                        onChanged: (v) => update('title', v))),
                PopupMenuButton<String>(
                    enabled: !controller.busy,
                    tooltip: 'Module actions',
                    onSelected: (action) {
                      if (action == 'up' || action == 'down') {
                        final j = index + (action == 'up' ? -1 : 1);
                        if (j < 0 || j >= items.length) return;
                        if (proposal) {
                          setState(() {
                            final x = proposedOutline.removeAt(index);
                            proposedOutline.insert(j, x);
                          });
                        } else {
                          controller.change((c) {
                            final x = c['modules'].removeAt(index);
                            c['modules'].insert(j, x);
                          });
                        }
                      } else if (action == 'split') {
                        splitModule(index);
                      } else if (action == 'merge') {
                        mergeModule(index);
                      }
                    },
                    itemBuilder: (_) => [
                          PopupMenuItem(
                              value: 'up',
                              enabled: index > 0,
                              child: const Text('Move up')),
                          PopupMenuItem(
                              value: 'down',
                              enabled: index + 1 < items.length,
                              child: const Text('Move down')),
                          if (!proposal)
                            const PopupMenuItem(
                                value: 'split', child: Text('Split module')),
                          if (!proposal && index + 1 < items.length)
                            const PopupMenuItem(
                                value: 'merge', child: Text('Merge with next')),
                        ]),
              ]),
              ExpansionTile(
                  title: const Text('Learning goal & content preview'),
                  children: [
                    TextFormField(
                        key: ValueKey('${m['_key'] ?? m['id']}-goal'),
                        initialValue: m['objective'] ?? '',
                        enabled: !controller.busy,
                        decoration:
                            const InputDecoration(labelText: 'Learning goal'),
                        onChanged: (v) => update('objective', v)),
                    if (!proposal)
                      Padding(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          child: Text(
                              (m['blocks'] as List? ?? [])
                                  .where((b) => b['text'] != null)
                                  .map((b) => b['text'])
                                  .join('\n'),
                              maxLines: 4,
                              overflow: TextOverflow.ellipsis)),
                  ]),
              const Divider(),
            ]));
      }),
      button('Add module', () {
        if (proposal) {
          setState(() => proposedOutline.add({
                '_key': uniqueId(),
                'title': 'New module',
                'objective': 'Apply the learning',
                'sections': ['Explanation', 'Practice'],
                'included': true
              }));
        } else {
          controller.change((c) => c['modules']
              .add({'id': uniqueId(), 'title': 'New module', 'blocks': []}));
        }
      }),
      ...controller.sources.map((s) => ExpansionTile(
              title: Text('Source: ${s['name']}'),
              initiallyExpanded: (s['issues'] as List? ?? []).isNotEmpty,
              children: [
                ...((s['issues'] as List? ?? []).map((i) => Text('• $i'))),
                if ((s['issues'] as List? ?? []).isNotEmpty)
                  CheckboxListTile(
                      value: s['acknowledged'] == true,
                      title: const Text(
                          'I reviewed the extraction against the original'),
                      onChanged: controller.busy
                          ? null
                          : (v) => guarded(() =>
                              controller.acknowledge(s['id'], v ?? false))),
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
                        })),
              ])),
      const SizedBox(height: 24),
      if (approved && !proposal) ...[
        const Text('✓ Outline approved',
            style: TextStyle(color: AppTheme.accentGreen)),
        const SizedBox(height: 12),
        Wrap(spacing: 12, runSpacing: 12, children: [
          button('Create course', openPreflight, primary: true),
          button('Review in editor', () => guarded(() => showEditor())),
          if (ai && hasEmptyIncludedModules)
            button('Resume document generation', () => generate('draft')),
        ]),
      ] else
        Wrap(spacing: 12, runSpacing: 12, children: [
          button(ai ? 'Approve & generate document' : 'Approve outline',
              approveOutline,
              primary: true),
          if (!proposal)
            button('Review in editor first', () => guarded(() => showEditor())),
          if (proposal)
            button(
                'Back to setup',
                () => guarded(() async {
                      await controller.reject();
                      setState(() => step = 'setup');
                    })),
        ]),
    ]));
  }

  bool get hasEmptyIncludedModules => controller.modules.any((m) =>
      m['included'] != false &&
      (m['blocks'] as List? ?? []).every((b) =>
          ['paragraph', 'heading', 'scenario', 'takeaway']
              .contains(b['type']) &&
          (b['text'] as String? ?? '').trim().isEmpty));
  Future<void> openPreflight() => guarded(() async {
        syncEditor();
        await controller.flush();
        setState(() => step = 'course');
      });
  Widget trainingDetails() => formPage(
          Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Training details',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.w600)),
        const SizedBox(height: 20),
        metadata(),
        ExpansionTile(title: const Text('Additional details'), children: [
          field('courseDescription', 'Description', lines: 3),
          field('courseDifficulty', 'Level'),
          field('courseType', 'Training type'),
          const Text('Language: English'),
        ]),
        const SizedBox(height: 16),
        button('Done', () => guarded(() => showEditor(sync: false)),
            primary: true),
      ]));

  Widget preflight() {
    final meta = controller.content['metadata'];
    final missing = <String, String>{
      'courseName': 'Title',
      'targetAudience': 'Audience',
      'courseObjective': 'Learning goals'
    };
    final hasMissing =
        missing.keys.any((k) => (meta[k] as String? ?? '').trim().isEmpty);
    final approved = controller.draft!['approvedOutline'] != null;
    return formPage(
        Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('Create course',
          style: TextStyle(fontSize: 24, fontWeight: FontWeight.w600)),
      const SizedBox(height: 10),
      const Text(
          'Use your reviewed document in the existing video and quiz workflow.'),
      const SizedBox(height: 20),
      Text(meta['courseName'] ?? '',
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
      ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Outline'),
          trailing: Text(approved ? 'Approved' : 'Needs approval')),
      ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Included content'),
          trailing: Text(hasEmptyIncludedModules
              ? 'Empty modules need content'
              : 'Ready')),
      const Text(
          'Course outputs: videos and quizzes through your current course workflow.'),
      ExpansionTile(
          key: ValueKey('details-$hasMissing'),
          initiallyExpanded: hasMissing,
          title: const Text('Review course details'),
          children: [
            metadata(),
            const Text(
                'A description is suggested from your confirmed learning goals. You can edit it in Training details.',
                style: TextStyle(fontSize: 12)),
          ]),
      if (!approved)
        CheckboxListTile(
            value: false,
            title: const Text(
                'I approve the current outline and included module structure'),
            onChanged: hasMissing || controller.busy
                ? null
                : (v) => guarded(controller.approve)),
      if (hasMissing)
        const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text(
                'Complete the title, audience and learning goals above before continuing.')),
      const SizedBox(height: 16),
      button(
          'Create course',
          () => guarded(() async {
                syncEditor();
                await controller.flush();
                if (controller.draft!['approvedOutline'] == null) {
                  throw StateError('Approve the current outline first');
                }
                final value = await controller.api.call(
                    '/drafts/${controller.id}/create-course',
                    method: 'POST',
                    body: {'expectedRevision': controller.revision});
                ref.read(courseListProvider.notifier).upsertCourse(
                    Course.fromJson(Map<String, dynamic>.from(value)),
                    select: true);
                ref.read(currentTabProvider.notifier).state = 1;
                widget.onClose();
              }),
          primary: true,
          enabled: !hasMissing && !hasEmptyIncludedModules && approved),
      const SizedBox(height: 12),
      button('Review in editor', () => guarded(() => showEditor(sync: false))),
    ]));
  }

  Future<void> versionHistory() => guarded(() async {
        syncEditor();
        await controller.flush();
        final versions =
            await controller.api.call('/drafts/${controller.id}/revisions');
        if (!mounted) return;
        final selected = await showDialog<int>(
            context: context,
            builder: (context) =>
                SimpleDialog(title: const Text('Version history'), children: [
                  ...(versions as List).map((v) => SimpleDialogOption(
                      onPressed: () => Navigator.pop(context, v['revision']),
                      child:
                          Text('Revision ${v['revision']} · ${v['reason']}'))),
                ]));
        if (selected != null) {
          await controller.restore(selected);
          await showEditor(sync: false);
        }
      });

  Widget moduleSidebar() =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Padding(
            padding: EdgeInsets.all(12),
            child: Text('MODULES',
                style: TextStyle(
                    fontSize: 11,
                    letterSpacing: 1.2,
                    color: AppTheme.textSecondary))),
        ...controller.modules.asMap().entries.map((e) => Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Material(
              color: e.key == active
                  ? const Color(0xFFEAF1FC)
                  : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
              child: ListTile(
                dense: true,
                contentPadding: const EdgeInsets.symmetric(horizontal: 10),
                leading: Text('${e.key + 1}'.padLeft(2, '0'),
                    style: const TextStyle(
                        fontSize: 11, color: AppTheme.textSecondary)),
                title: Tooltip(
                    message: e.value['title'],
                    child: Text(e.value['title'],
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                            fontSize: 13,
                            color: e.key == active
                                ? AppTheme.primaryBlue
                                : AppTheme.textBlack))),
                subtitle: e.value['included'] == false
                    ? const Text('Excluded')
                    : null,
                onTap: controller.busy
                    ? null
                    : () => guarded(() async {
                          syncEditor();
                          await controller.flush();
                          active = e.key;
                          assistantScope = 'module';
                          await showEditor(sync: false);
                        }),
              ),
            ))),
        const SizedBox(height: 14),
        button(
            'Add module',
            () => guarded(() async {
                  syncEditor();
                  controller.change((c) => c['modules'].add(
                      {'id': uniqueId(), 'title': 'New module', 'blocks': []}));
                  active = controller.modules.length - 1;
                  await showEditor(sync: false);
                })),
      ]);

  Widget assistant() =>
      panel(Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          const Expanded(
              child: Text('AI assistant',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600))),
          IconButton(
              tooltip: 'Close assistant',
              onPressed: () => setState(() => assistantVisible = false),
              icon: const Icon(Icons.close, size: 18))
        ]),
        Wrap(spacing: 4, children: [
          ChoiceChip(
              label: const Text('Improve content'),
              selected: !sourceQuestion,
              onSelected: (_) => setState(() => sourceQuestion = false)),
          if (controller.sources.isNotEmpty)
            ChoiceChip(
                label: const Text('Ask about source'),
                selected: sourceQuestion,
                onSelected: (_) => setState(() => sourceQuestion = true)),
        ]),
        const SizedBox(height: 14),
        if (sourceQuestion) ...[
          TextField(
              controller: question,
              minLines: 3,
              maxLines: 6,
              decoration: const InputDecoration(
                  labelText: 'Your source question',
                  border: OutlineInputBorder())),
          const SizedBox(height: 12),
          button('Ask question', () => generate('answer'), primary: true),
        ] else ...[
          Text(
              'Editing: ${assistantScope == 'selected' ? 'Selected text' : assistantScope == 'document' ? 'Whole document' : 'This module'}',
              style:
                  const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ExpansionTile(title: const Text('Change scope'), children: [
            DropdownButtonFormField<String>(
                initialValue: assistantScope,
                items: const [
                  DropdownMenuItem(value: 'module', child: Text('This module')),
                  DropdownMenuItem(
                      value: 'selected', child: Text('Selected text')),
                  DropdownMenuItem(
                      value: 'document', child: Text('Whole document')),
                ],
                onChanged: controller.busy
                    ? null
                    : (v) => setState(() => assistantScope = v!))
          ]),
          TextField(
              controller: instruction,
              minLines: 3,
              maxLines: 6,
              decoration: const InputDecoration(
                  hintText: 'Describe what you want to improve…',
                  border: OutlineInputBorder())),
          const SizedBox(height: 12),
          button('Suggest changes', suggest, primary: true),
          Wrap(spacing: 8, runSpacing: 8, children: [
            button('Simplify', () {
              instruction.text =
                  'Simplify the wording while preserving factual meaning.';
              suggest();
            }),
            button(
                'Add scenario',
                () => guarded(() async {
                      syncEditor();
                      await controller.start('insert',
                          instruction:
                              'Add one clearly labeled illustrative workplace scenario',
                          scope: 'module',
                          moduleId: controller.modules[active]['id']);
                    })),
            if ((controller.modules[active]['blocks'] as List? ?? []).every(
                (b) =>
                    (b['text'] as String? ?? '').trim().isEmpty &&
                    ['paragraph', 'heading', 'scenario', 'takeaway']
                        .contains(b['type'])))
              button(
                  'Draft this module',
                  () => guarded(() async {
                        syncEditor();
                        await controller.start('draft_module',
                            scope: 'module',
                            moduleId: controller.modules[active]['id']);
                      })),
          ]),
          const SizedBox(height: 14),
          const Text(
              'Review suggestions before accepting. Your content stays unchanged until then.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
        if (controller.operation?['status'] == 'proposed' &&
            ['edit', 'revise', 'insert', 'draft_module']
                .contains(controller.operation?['request']['task'])) ...[
          const Divider(height: 32),
          const Text('Review suggested change',
              style: TextStyle(fontWeight: FontWeight.w600)),
          if (controller.operation!['result']['changes'] != null)
            ...((controller.operation!['result']['changes'] as List).map((c) =>
                Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Original: ${c['originalText']}',
                              style: const TextStyle(
                                  color: AppTheme.textSecondary)),
                          const SizedBox(height: 8),
                          Text('Suggested: ${c['replacementText']}'),
                        ]))))
          else if (controller.operation!['result']['blocks'] != null)
            ...((controller.operation!['result']['blocks'] as List).map((b) =>
                Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Text(b['text']))))
          else
            Text(controller.operation!['result']['replacementText']),
          if (controller.operation!['result']['summary'] != null)
            Text(controller.operation!['result']['summary']),
          const SizedBox(height: 16),
          Wrap(spacing: 8, children: [
            button(
                'Accept changes',
                () => guarded(() async {
                      await controller.accept();
                      await showEditor(sync: false);
                    }),
                primary: true),
            button('Dismiss', () => guarded(controller.reject)),
          ]),
        ],
        if (controller.operation?['status'] == 'completed' &&
            controller.operation?['request']['task'] == 'answer') ...[
          const Divider(height: 32),
          Text(controller.operation!['result']['answer']),
          if (controller.operation!['result']['insufficientEvidence'] == true)
            const Text('The source does not provide enough evidence.',
                style: TextStyle(fontSize: 12)),
          ...((controller.operation!['result']['sourceReferences'] as List? ??
                  [])
              .map((r) {
            final s = controller.sources
                .where((s) => s['id'] == r['sourceId'])
                .firstOrNull;
            final span = (s?['spans'] as List? ?? [])
                .where((p) => p['id'] == r['spanId'])
                .firstOrNull;
            return TextButton(
                onPressed: () => showDialog<void>(
                    context: context,
                    builder: (_) => AlertDialog(
                        title: Text(
                            '${s?['name'] ?? 'Source'} · ${span?['location'] ?? ''}'),
                        content: SingleChildScrollView(
                            child: Text(span?['text'] ??
                                'Source excerpt unavailable')))),
                child: Text(
                    '${s?['name'] ?? 'Source'} · ${span?['location'] ?? ''}'));
          })),
        ],
      ]));

  Widget editorView() => LayoutBuilder(builder: (context, box) {
        final canvas = Container(
            decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFE0E6F0))),
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Padding(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 8),
                      child: Wrap(
                          crossAxisAlignment: WrapCrossAlignment.center,
                          spacing: 4,
                          children: [
                            IconButton(
                                tooltip: 'Bold',
                                onPressed: controller.busy
                                    ? null
                                    : () => editor.format('bold'),
                                icon: const Icon(Icons.format_bold)),
                            IconButton(
                                tooltip: 'Italic',
                                onPressed: controller.busy
                                    ? null
                                    : () => editor.format('italic'),
                                icon: const Icon(Icons.format_italic)),
                            TextButton(
                                onPressed: controller.busy
                                    ? null
                                    : () => addBlock('heading'),
                                child: const Text('Heading')),
                            PopupMenuButton<String>(
                                enabled: !controller.busy,
                                tooltip: 'Insert content',
                                onSelected: (v) {
                                  if (v == 'image') {
                                    addImage();
                                  } else {
                                    addBlock(v);
                                  }
                                },
                                itemBuilder: (_) => const [
                                      PopupMenuItem(
                                          value: 'list',
                                          child: Text('Bullet list')),
                                      PopupMenuItem(
                                          value: 'table', child: Text('Table')),
                                      PopupMenuItem(
                                          value: 'image', child: Text('Image')),
                                    ],
                                child: const Padding(
                                    padding: EdgeInsets.all(12),
                                    child: Text('Insert'))),
                            TextButton.icon(
                                onPressed: () => setState(() {
                                      assistantVisible = !assistantVisible;
                                      if (editor.selection() != null) {
                                        assistantScope = 'selected';
                                      }
                                    }),
                                icon: const Icon(Icons.auto_awesome_outlined,
                                    size: 16),
                                label: const Text('AI assistant')),
                          ])),
                  const Divider(height: 1),
                  Padding(
                      padding: const EdgeInsets.fromLTRB(32, 26, 32, 8),
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text('MODULE ${active + 1}',
                                style: const TextStyle(
                                    fontSize: 11,
                                    letterSpacing: 1,
                                    color: AppTheme.textSecondary)),
                            TextFormField(
                                key: ValueKey(loadedModule),
                                enabled: !controller.busy,
                                initialValue: controller.modules[active]
                                    ['title'],
                                style: const TextStyle(
                                    fontSize: 25, fontWeight: FontWeight.w600),
                                decoration: const InputDecoration(
                                    border: InputBorder.none,
                                    enabledBorder: InputBorder.none,
                                    labelText: 'Module title'),
                                onChanged: (v) => controller.change(
                                    (c) => c['modules'][active]['title'] = v)),
                            if ((controller.modules[active]['objective']
                                        as String? ??
                                    '')
                                .isNotEmpty)
                              Text(controller.modules[active]['objective'],
                                  style: const TextStyle(
                                      fontSize: 13,
                                      color: AppTheme.textSecondary)),
                          ])),
                  Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      child: SizedBox(
                          height: 440,
                          child: HtmlElementView(viewType: viewId))),
                  const Divider(height: 1),
                  const Padding(
                      padding: EdgeInsets.all(14),
                      child: Text('Changes save automatically',
                          style: TextStyle(
                              fontSize: 11, color: AppTheme.textSecondary))),
                ]));
        if (box.maxWidth < 760) {
          return ListView(children: [
            moduleSidebar(),
            const SizedBox(height: 16),
            canvas,
            if (assistantVisible) ...[const SizedBox(height: 16), assistant()]
          ]);
        }
        return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(
              width: 175, child: SingleChildScrollView(child: moduleSidebar())),
          const SizedBox(width: 20),
          Expanded(
              child: SingleChildScrollView(
                  child: Column(children: [
            canvas,
            if (assistantVisible && box.maxWidth < 1100) ...[
              const SizedBox(height: 16),
              assistant()
            ]
          ]))),
          if (assistantVisible && box.maxWidth >= 1100) ...[
            const SizedBox(width: 16),
            SizedBox(
                width: 285, child: SingleChildScrollView(child: assistant()))
          ],
        ]);
      });

  @override
  Widget build(BuildContext context) => ColoredBox(
      color: const Color(0xFFF3F5F9),
      child: Column(children: [
        Padding(
            padding: const EdgeInsets.fromLTRB(24, 22, 24, 18),
            child: SizedBox(
                width: double.infinity,
                child: Wrap(
                    alignment: WrapAlignment.spaceBetween,
                    spacing: 24,
                    runSpacing: 12,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (step != 'home')
                              TextButton(
                                  onPressed: controller.busy ? null : close,
                                  child: const Text('← Documents')),
                            Text(
                                step == 'home'
                                    ? 'Documents'
                                    : step == 'editor'
                                        ? (controller.content['metadata']
                                                ['courseName'] as String? ??
                                            'Untitled document')
                                        : 'Document Builder',
                                style: const TextStyle(
                                    fontSize: 26, fontWeight: FontWeight.w600)),
                            Text(
                                step == 'home'
                                    ? 'Create training content and manage your documents.'
                                    : step == 'editor'
                                        ? 'Training document · Draft'
                                        : 'Create a training document',
                                style: const TextStyle(
                                    fontSize: 12,
                                    color: AppTheme.textSecondary)),
                          ]),
                      if (step == 'editor')
                        Wrap(
                            spacing: 10,
                            runSpacing: 8,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              Text(controller.saveStatus,
                                  style: const TextStyle(
                                      fontSize: 12,
                                      color: AppTheme.accentGreen)),
                              button('Preview', preview),
                              button('Create course', openPreflight,
                                  primary: true),
                              PopupMenuButton<String>(
                                  enabled: !controller.busy,
                                  tooltip: 'More document actions',
                                  onSelected: (v) {
                                    if (v == 'history') {
                                      versionHistory();
                                    } else {
                                      guarded(() async {
                                        syncEditor();
                                        await controller.flush();
                                        setState(() => step = v);
                                      });
                                    }
                                  },
                                  itemBuilder: (_) => const [
                                        PopupMenuItem(
                                            value: 'details',
                                            child: Text('Training details')),
                                        PopupMenuItem(
                                            value: 'outline',
                                            child: Text('Edit outline')),
                                        PopupMenuItem(
                                            value: 'history',
                                            child: Text('Version history'))
                                      ],
                                  child: const Padding(
                                      padding: EdgeInsets.all(12),
                                      child: Text('More'))),
                            ]),
                    ]))),
        if (controller.error != null)
          MaterialBanner(content: Text(controller.error!), actions: [
            if (controller.conflict) ...[
              button(
                  'Keep my edits as a copy',
                  () => guarded(() async {
                        await controller.keepSeparateCopy();
                        await showEditor(sync: false);
                      })),
              button(
                  'Reload saved version',
                  () => guarded(() async {
                        await controller.open(controller.id);
                        await showEditor(sync: false);
                      })),
            ] else if (controller.saveStatus == 'Save failed')
              button('Retry save', () => guarded(controller.flush))
            else ...[
              if (retryTask != null &&
                  controller.operation?['status'] == 'failed')
                button('Retry generation', () => generate(retryTask!)),
              TextButton(
                  onPressed: () {
                    controller.error = null;
                    controller.announce();
                  },
                  child: const Text('Dismiss')),
            ],
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
                        child: const Text('Cancel')),
                ]))
          ]),
        Expanded(
            child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
                child: switch (step) {
                  'source' => source(),
                  'setup' => setup(),
                  'outline' => outline(),
                  'editor' => editorView(),
                  'details' => trainingDetails(),
                  'course' => preflight(),
                  _ => home(),
                })),
      ]));
}
