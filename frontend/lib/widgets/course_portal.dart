import 'dart:html' as html;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../theme.dart';
import '../constants.dart';
import '../models/models.dart';
import '../providers/providers.dart';

class CoursesSidebar extends ConsumerWidget {
  final Course? selectedCourse;

  const CoursesSidebar({super.key, required this.selectedCourse});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final courseListState = ref.watch(courseListProvider);

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'My Courses',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                ),
                Text(
                  '${courseListState.courses.length} courses',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          const Divider(height: 1, color: AppTheme.lightGray),
          Expanded(
            child: courseListState.isLoading
                ? const Center(
                    child: CircularProgressIndicator(
                      valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryBlue),
                    ),
                  )
                : courseListState.error != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.error_outline_rounded, color: AppTheme.accentRed, size: 32),
                              const SizedBox(height: 8),
                              Text(
                                'Error loading courses',
                                style: GoogleFonts.barlow(fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                courseListState.error!,
                                textAlign: TextAlign.center,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                      )
                    : courseListState.courses.isEmpty
                        ? Center(
                            child: Padding(
                              padding: const EdgeInsets.all(32.0),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.auto_stories_outlined, color: AppTheme.gray.withOpacity(0.5), size: 48),
                                  const SizedBox(height: 12),
                                  Text(
                                    'No courses created yet',
                                    textAlign: TextAlign.center,
                                    style: GoogleFonts.barlow(
                                      color: AppTheme.gray,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    'Upload a PDF and click "Create Course" to generate one.',
                                    textAlign: TextAlign.center,
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                          )
                        : ListView.separated(
                            itemCount: courseListState.courses.length,
                            separatorBuilder: (context, index) => const Divider(height: 1, color: AppTheme.lightGray),
                            itemBuilder: (context, index) {
                              final course = courseListState.courses[index];
                              final isSelected = selectedCourse?.id == course.id;

                              return ListTile(
                                selected: isSelected,
                                selectedTileColor: AppTheme.primaryBlue.withOpacity(0.05),
                                leading: Icon(
                                  Icons.menu_book,
                                  color: isSelected ? AppTheme.primaryBlue : AppTheme.gray,
                                ),
                                title: Text(
                                  course.courseName,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: GoogleFonts.barlow(
                                    fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                                    color: isSelected ? AppTheme.primaryBlue : AppTheme.textBlack,
                                  ),
                                ),
                                subtitle: Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      course.courseDifficulty,
                                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                            color: _getDifficultyColor(course.courseDifficulty),
                                            fontWeight: FontWeight.bold,
                                          ),
                                    ),
                                    Text(
                                      '${course.modules.length} module${course.modules.length == 1 ? '' : 's'}',
                                      style: Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ],
                                ),
                                onTap: () {
                                  ref.read(selectedCourseProvider.notifier).state = course;
                                },
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }

  Color _getDifficultyColor(String difficulty) {
    switch (difficulty.toLowerCase()) {
      case 'easy':
      case 'beginner':
        return AppTheme.accentGreen;
      case 'medium':
      case 'intermediate':
        return AppTheme.accentOrange;
      case 'hard':
      case 'advanced':
        return AppTheme.accentRed;
      default:
        return AppTheme.gray;
    }
  }
}

class EmptyCourseView extends StatelessWidget {
  const EmptyCourseView();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.collections_bookmark_rounded,
              size: 64,
              color: AppTheme.gray.withOpacity(0.4),
            ),
            const SizedBox(height: 16),
            Text(
              'No Course Selected',
              style: GoogleFonts.inter(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppTheme.primaryBlue,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Select a course from the list on the left to view its syllabus outline.',
              style: GoogleFonts.barlow(
                fontSize: 14,
                color: AppTheme.gray,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class CourseDetailsView extends ConsumerStatefulWidget {
  final Course course;

  const CourseDetailsView({super.key, required this.course});

  @override
  ConsumerState<CourseDetailsView> createState() => _CourseDetailsViewState();
}

class _CourseDetailsViewState extends ConsumerState<CourseDetailsView> {
  final _formKey = GlobalKey<FormState>();
  
  late TextEditingController _nameController;
  late TextEditingController _descController;
  late TextEditingController _objController;
  late TextEditingController _audienceController;
  late TextEditingController _langController;
  late String _selectedDifficulty;

  List<TextEditingController> _moduleTitleControllers = [];
  List<TextEditingController> _moduleTextControllers = [];
  List<TextEditingController> _moduleQuestionsControllers = [];
  List<CourseModule> _moduleData = [];

  @override
  void initState() {
    super.initState();
    _initControllers();
  }

  @override
  void didUpdateWidget(covariant CourseDetailsView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.course.id != widget.course.id) {
      _disposeControllers();
      _initControllers();
    }
  }

  void _initControllers() {
    _nameController = TextEditingController(text: widget.course.courseName);
    _descController = TextEditingController(text: widget.course.courseDescription);
    _objController = TextEditingController(text: widget.course.courseObjective);
    _audienceController = TextEditingController(text: widget.course.targetAudience);
    _langController = TextEditingController(text: widget.course.language);

    final diff = widget.course.courseDifficulty;
    if (['easy', 'medium', 'hard'].contains(diff.toLowerCase())) {
      _selectedDifficulty = diff[0].toUpperCase() + diff.substring(1).toLowerCase();
    } else if (diff.toLowerCase() == 'beginner') {
      _selectedDifficulty = 'Easy';
    } else if (diff.toLowerCase() == 'intermediate') {
      _selectedDifficulty = 'Medium';
    } else if (diff.toLowerCase() == 'advanced') {
      _selectedDifficulty = 'Hard';
    } else {
      _selectedDifficulty = 'Easy';
    }

    _moduleData = List<CourseModule>.from(widget.course.modules);
    _moduleTitleControllers = _moduleData
        .map((m) => TextEditingController(text: m.title))
        .toList();
    _moduleTextControllers = _moduleData
        .map((m) => TextEditingController(text: m.text))
        .toList();
    _moduleQuestionsControllers = _moduleData
        .map((m) => TextEditingController(text: m.numQuestions.toString()))
        .toList();
  }

  void _disposeControllers() {
    _nameController.dispose();
    _descController.dispose();
    _objController.dispose();
    _audienceController.dispose();
    _langController.dispose();
    for (var c in _moduleTitleControllers) c.dispose();
    for (var c in _moduleTextControllers) c.dispose();
    for (var c in _moduleQuestionsControllers) c.dispose();
    _moduleTitleControllers.clear();
    _moduleTextControllers.clear();
    _moduleQuestionsControllers.clear();
    _moduleData.clear();
  }

  @override
  void dispose() {
    _disposeControllers();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      clipBehavior: Clip.antiAlias,
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              color: AppTheme.primaryBlue,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'COURSE BLUEPRINT',
                        style: GoogleFonts.barlow(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: Colors.white.withOpacity(0.7),
                          letterSpacing: 2,
                        ),
                      ),
                      Row(
                        children: [
                          TextButton(
                            style: TextButton.styleFrom(foregroundColor: Colors.white),
                            onPressed: () {
                              setState(() {
                                _disposeControllers();
                                _initControllers();
                              });
                            },
                            child: const Text('Reset'),
                          ),
                          const SizedBox(width: 8),
                          Consumer(
                            builder: (context, ref, _) {
                              final fullGeneration = ref.watch(fullCourseGenerationProvider);
                              final hasModules = widget.course.modules.isNotEmpty;
                              final hasThumbnail = widget.course.thumbnailUrl.isNotEmpty;
                              final checkpoint = widget.course.failedCheckpoint.isNotEmpty
                                  ? widget.course.failedCheckpoint
                                  : widget.course.currentCheckpoint;
                              final hasFailedCheckpoint =
                                  widget.course.generationStatus == 'failed' && checkpoint.isNotEmpty;
                              final isGenerating =
                                  fullGeneration.status == FullCourseGenStatus.generating ||
                                      widget.course.generationStatus == 'running';
                              final isFullyGenerated = hasModules &&
                                  hasThumbnail &&
                                  widget.course.modules.every((m) =>
                                      m.videoPath != null &&
                                      m.videoPath!.isNotEmpty &&
                                      m.quiz != null &&
                                      ((m.quiz!['questions'] as List?)?.isNotEmpty == true ||
                                          m.numQuestions <= 0));
                              final label = isGenerating
                                  ? 'Generating...'
                                  : hasFailedCheckpoint
                                      ? 'Continue from $checkpoint'
                                      : isFullyGenerated
                                          ? 'Already Generated'
                                          : 'Generate Course';
                              final button = ElevatedButton.icon(
                                icon: Icon(
                                  hasFailedCheckpoint ? Icons.play_arrow : Icons.auto_awesome,
                                  size: 14,
                                ),
                                label: Text(label),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: isFullyGenerated && !hasFailedCheckpoint
                                      ? Colors.grey[700]
                                      : AppTheme.accentOrange,
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                ),
                                onPressed: (!isGenerating &&
                                        (hasFailedCheckpoint || (hasModules && !isFullyGenerated)))
                                    ? () {
                                        final notifier =
                                            ref.read(fullCourseGenerationProvider.notifier);
                                        if (hasFailedCheckpoint) {
                                          notifier.continueFromCheckpoint(widget.course.id, ref);
                                        } else {
                                          notifier.generateFullCourse(widget.course.id, ref);
                                        }
                                      }
                                    : null,
                              );
                              if (!hasFailedCheckpoint || widget.course.generationError.isEmpty) {
                                return button;
                              }
                              return Tooltip(
                                message: widget.course.generationError,
                                child: button,
                              );
                            },
                          ),
                          const SizedBox(width: 8),
                          ElevatedButton.icon(
                            icon: const Icon(Icons.save, size: 14),
                            label: const Text('Save Changes'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.accentGreen,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(6),
                              ),
                            ),
                            onPressed: _saveCourseModifications,
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  
                  const Text(
                    'Course Name',
                    style: TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 4),
                  TextFormField(
                    controller: _nameController,
                    style: GoogleFonts.inter(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                    decoration: const InputDecoration(
                      isDense: true,
                      contentPadding: EdgeInsets.symmetric(vertical: 8),
                      enabledBorder: UnderlineInputBorder(
                        borderSide: BorderSide(color: Colors.white38),
                      ),
                      focusedBorder: UnderlineInputBorder(
                        borderSide: BorderSide(color: Colors.white),
                      ),
                    ),
                    validator: (value) => value == null || value.isEmpty ? 'Required' : null,
                  ),
                  const SizedBox(height: 16),
                  
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Difficulty',
                              style: TextStyle(color: Colors.white70, fontSize: 12),
                            ),
                            const SizedBox(height: 4),
                            Theme(
                              data: Theme.of(context).copyWith(canvasColor: AppTheme.primaryBlue),
                              child: DropdownButtonFormField<String>(
                                value: _selectedDifficulty,
                                style: GoogleFonts.barlow(color: Colors.white, fontWeight: FontWeight.bold),
                                decoration: const InputDecoration(
                                  isDense: true,
                                  contentPadding: EdgeInsets.zero,
                                  enabledBorder: UnderlineInputBorder(
                                    borderSide: BorderSide(color: Colors.white38),
                                  ),
                                  focusedBorder: UnderlineInputBorder(
                                    borderSide: BorderSide(color: Colors.white),
                                  ),
                                ),
                                items: ['Easy', 'Medium', 'Hard']
                                    .map((val) => DropdownMenuItem(value: val, child: Text(val)))
                                    .toList(),
                                onChanged: (value) {
                                  if (value != null) {
                                    setState(() {
                                      _selectedDifficulty = value;
                                    });
                                  }
                                },
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 24),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Language',
                              style: TextStyle(color: Colors.white70, fontSize: 12),
                            ),
                            const SizedBox(height: 4),
                            TextFormField(
                              controller: _langController,
                              style: GoogleFonts.barlow(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                              decoration: const InputDecoration(
                                isDense: true,
                                contentPadding: EdgeInsets.symmetric(vertical: 4),
                                enabledBorder: UnderlineInputBorder(
                                  borderSide: BorderSide(color: Colors.white38),
                                ),
                                focusedBorder: UnderlineInputBorder(
                                  borderSide: BorderSide(color: Colors.white),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const _SectionHeaderInput(
                      title: 'Course Description',
                      icon: Icons.description,
                    ),
                    const SizedBox(height: 6),
                    TextFormField(
                      controller: _descController,
                      maxLines: 4,
                      style: GoogleFonts.barlow(fontSize: 15, color: AppTheme.textBlack),
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.all(12),
                        hintText: 'Enter course description...',
                      ),
                    ),
                    const SizedBox(height: 24),

                    const _SectionHeaderInput(
                      title: 'Course Objective',
                      icon: Icons.track_changes,
                    ),
                    const SizedBox(height: 6),
                    TextFormField(
                      controller: _objController,
                      maxLines: 4,
                      style: GoogleFonts.barlow(fontSize: 15, color: AppTheme.textBlack),
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.all(12),
                        hintText: 'Enter course objective...',
                      ),
                    ),
                    const SizedBox(height: 24),

                    const _SectionHeaderInput(
                      title: 'Target Audience',
                      icon: Icons.group,
                    ),
                    const SizedBox(height: 6),
                    TextFormField(
                      controller: _audienceController,
                      maxLines: 2,
                      style: GoogleFonts.barlow(fontSize: 15, color: AppTheme.textBlack),
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.all(12),
                        hintText: 'Enter target audience...',
                      ),
                    ),
                    const SizedBox(height: 24),

                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.format_list_numbered, size: 18, color: AppTheme.primaryBlue),
                            const SizedBox(width: 8),
                            Text(
                              'Modules Curriculum Outline',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.primaryBlue,
                              ),
                            ),
                          ],
                        ),
                        TextButton.icon(
                          icon: const Icon(Icons.add, size: 16),
                          label: const Text('Add Module'),
                          onPressed: () {
                            setState(() {
                              _moduleData.add(CourseModule(
                                moduleNumber: _moduleData.length + 1,
                                title: '',
                                text: '',
                                startLine: '',
                                endLine: '',
                                numQuestions: 3,
                              ));
                              _moduleTitleControllers.add(TextEditingController());
                              _moduleTextControllers.add(TextEditingController());
                              _moduleQuestionsControllers.add(TextEditingController(text: '3'));
                            });
                          },
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    ReorderableListView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: _moduleTitleControllers.length,
                      onReorder: _onReorder,
                      itemBuilder: (context, index) {
                        return Container(
                          key: ValueKey('module_key_${index}_${_moduleData[index].moduleNumber}'),
                          margin: const EdgeInsets.only(bottom: 16),
                          decoration: BoxDecoration(
                            border: Border.all(color: AppTheme.lightGray, width: 1),
                            borderRadius: AppTheme.pShapeRadiusCustom(8),
                          ),
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.center,
                                children: [
                                  const Icon(Icons.drag_indicator, color: AppTheme.gray, size: 20),
                                  const SizedBox(width: 8),
                                  CircleAvatar(
                                    radius: 14,
                                    backgroundColor: AppTheme.primaryBlue,
                                    child: Text(
                                      '${index + 1}',
                                      style: GoogleFonts.barlow(
                                        color: Colors.white,
                                        fontSize: 12,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: TextFormField(
                                      controller: _moduleTitleControllers[index],
                                      style: GoogleFonts.barlow(
                                        fontSize: 15,
                                        fontWeight: FontWeight.w600,
                                      ),
                                      decoration: const InputDecoration(
                                        contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                                        border: OutlineInputBorder(),
                                        hintText: 'Module title...',
                                        isDense: true,
                                      ),
                                    ),
                                  ),
                                  IconButton(
                                    icon: const Icon(Icons.delete, color: AppTheme.accentRed, size: 20),
                                    tooltip: 'Delete module',
                                    onPressed: () {
                                      setState(() {
                                        _moduleTitleControllers[index].dispose();
                                        _moduleTextControllers[index].dispose();
                                        _moduleQuestionsControllers[index].dispose();
                                        _moduleTitleControllers.removeAt(index);
                                        _moduleTextControllers.removeAt(index);
                                        _moduleQuestionsControllers.removeAt(index);
                                        _moduleData.removeAt(index);
                                      });
                                    },
                                  ),
                                ],
                              ),
                              if (_moduleData[index].videoPath != null &&
                                  _moduleData[index].videoPath!.isNotEmpty) ...[
                                const SizedBox(height: 10),
                                Align(
                                  alignment: Alignment.centerRight,
                                  child: ElevatedButton.icon(
                                    icon: const Icon(Icons.download_rounded, size: 16),
                                    label: const Text('Download Video'),
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: AppTheme.primaryBlue,
                                      foregroundColor: Colors.white,
                                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                    ),
                                    onPressed: () {
                                      final module = _moduleData[index];
                                      final videoUrl = '${AppConstants.apiBaseUrl}/${module.videoPath!}';
                                      _downloadVideo(videoUrl, _videoDownloadFilename(module));
                                    },
                                  ),
                                ),
                              ],
                              const SizedBox(height: 10),
                              Row(
                                children: [
                                  const Icon(Icons.quiz_outlined, size: 16, color: AppTheme.primaryBlue),
                                  const SizedBox(width: 6),
                                  Text(
                                    'Quiz questions:',
                                    style: GoogleFonts.barlow(fontSize: 13, color: AppTheme.primaryBlue, fontWeight: FontWeight.w500),
                                  ),
                                  const SizedBox(width: 8),
                                  SizedBox(
                                    width: 70,
                                    child: TextFormField(
                                      controller: _moduleQuestionsControllers[index],
                                      keyboardType: TextInputType.number,
                                      style: GoogleFonts.barlow(fontSize: 13, fontWeight: FontWeight.bold),
                                      decoration: const InputDecoration(
                                        contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                                        border: OutlineInputBorder(),
                                        isDense: true,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    'questions (0 to disable)',
                                    style: GoogleFonts.barlow(fontSize: 12, color: AppTheme.gray),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              TextFormField(
                                controller: _moduleTextControllers[index],
                                maxLines: 6,
                                minLines: 3,
                                style: GoogleFonts.barlow(
                                  fontSize: 13,
                                  color: AppTheme.textBlack,
                                  height: 1.5,
                                ),
                                decoration: InputDecoration(
                                  contentPadding: const EdgeInsets.all(10),
                                  border: const OutlineInputBorder(),
                                  hintText: 'Module content will appear here after generation...',
                                  hintStyle: GoogleFonts.barlow(
                                    fontSize: 13,
                                    color: AppTheme.gray,
                                  ),
                                  filled: true,
                                  fillColor: AppTheme.lightGray.withOpacity(0.5),
                                ),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                    
                    const SizedBox(height: 32),
                    Row(
                      children: [
                        const Icon(Icons.image_search_rounded, size: 18, color: AppTheme.primaryBlue),
                        const SizedBox(width: 8),
                        Text(
                          'Extracted PDF Images & Captions Verification',
                          style: GoogleFonts.inter(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.primaryBlue,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (widget.course.images.isEmpty)
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AppTheme.lightGray.withOpacity(0.5),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AppTheme.lightGray),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.info_outline, color: AppTheme.gray),
                            const SizedBox(width: 8),
                            Text(
                              'No images were extracted from this PDF.',
                              style: GoogleFonts.barlow(color: AppTheme.gray),
                            ),
                          ],
                        ),
                      )
                    else
                      GridView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                          crossAxisSpacing: 16,
                          mainAxisSpacing: 16,
                          childAspectRatio: 1.3,
                        ),
                        itemCount: widget.course.images.length,
                        itemBuilder: (context, idx) {
                          final img = widget.course.images[idx];
                          final mappedModuleNumber = _moduleNumberForImage(img.imageId);
                          return Container(
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: AppTheme.lightGray),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withOpacity(0.02),
                                  blurRadius: 4,
                                  offset: const Offset(0, 2),
                                ),
                              ],
                            ),
                            clipBehavior: Clip.antiAlias,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Expanded(
                                  child: Container(
                                    color: AppTheme.lightGray.withOpacity(0.3),
                                    child: Center(
                                      child: Image.network(
                                        '${AppConstants.apiBaseUrl}/${img.filePath}',
                                        fit: BoxFit.contain,
                                        errorBuilder: (context, error, stackTrace) =>
                                            const Icon(Icons.broken_image, color: AppTheme.gray),
                                      ),
                                    ),
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                                  color: Colors.white,
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Row(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Expanded(
                                            child: Text(
                                              img.caption.isNotEmpty ? img.caption : 'No Caption Found',
                                              maxLines: 2,
                                              overflow: TextOverflow.ellipsis,
                                              style: GoogleFonts.barlow(
                                                fontSize: 12.5,
                                                fontWeight: FontWeight.w600,
                                                color: AppTheme.textBlack,
                                              ),
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                            decoration: BoxDecoration(
                                              color: mappedModuleNumber == null
                                                  ? AppTheme.lightGray
                                                  : AppTheme.primaryBlue.withOpacity(0.08),
                                              borderRadius: BorderRadius.circular(999),
                                              border: Border.all(
                                                color: mappedModuleNumber == null
                                                    ? AppTheme.lightGray
                                                    : AppTheme.primaryBlue.withOpacity(0.25),
                                              ),
                                            ),
                                            child: Text(
                                              mappedModuleNumber == null ? 'Unmapped' : 'Module $mappedModuleNumber',
                                              style: GoogleFonts.barlow(
                                                fontSize: 11,
                                                fontWeight: FontWeight.w700,
                                                color: mappedModuleNumber == null
                                                    ? AppTheme.gray
                                                    : AppTheme.primaryBlue,
                                              ),
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
                        },
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _downloadVideo(String videoUrl, String filename) async {
    try {
      final request = await html.HttpRequest.request(
        videoUrl,
        responseType: 'blob',
      );
      final blob = request.response as html.Blob;
      final objectUrl = html.Url.createObjectUrlFromBlob(blob);
      _clickDownloadLink(objectUrl, filename);
      html.Url.revokeObjectUrl(objectUrl);
    } catch (_) {
      _clickDownloadLink(videoUrl, filename, openInNewTab: true);
    }
  }

  void _clickDownloadLink(
    String href,
    String filename, {
    bool openInNewTab = false,
  }) {
    final anchor = html.AnchorElement(href: href)
      ..download = filename
      ..style.display = 'none';

    if (openInNewTab) {
      anchor.target = '_blank';
    }

    html.document.body?.append(anchor);
    anchor.click();
    anchor.remove();
  }

  String _videoDownloadFilename(CourseModule module) {
    final rawTitle = module.title.trim().isEmpty ? 'module' : module.title.trim();
    final safeTitle = rawTitle
        .toLowerCase()
        .replaceAll(RegExp(r'[^a-z0-9]+'), '-')
        .replaceAll(RegExp(r'^-+|-+$'), '');
    return '${widget.course.id}-module-${module.moduleNumber}-${safeTitle.isEmpty ? 'video' : safeTitle}.mp4';
  }

  void _onReorder(int oldIndex, int newIndex) {
    setState(() {
      if (oldIndex < newIndex) newIndex -= 1;
      
      final TextEditingController titleController = _moduleTitleControllers.removeAt(oldIndex);
      _moduleTitleControllers.insert(newIndex, titleController);

      final TextEditingController textController = _moduleTextControllers.removeAt(oldIndex);
      _moduleTextControllers.insert(newIndex, textController);

      final TextEditingController questionsController = _moduleQuestionsControllers.removeAt(oldIndex);
      _moduleQuestionsControllers.insert(newIndex, questionsController);

      final CourseModule module = _moduleData.removeAt(oldIndex);
      _moduleData.insert(newIndex, module);
    });
  }

  int? _moduleNumberForImage(String imageId) {
    for (final module in _moduleData) {
      final hasImage = module.images.any((img) => img.imageId == imageId);
      if (hasImage) return module.moduleNumber;
    }
    return null;
  }

  void _saveCourseModifications() async {
    if (_formKey.currentState?.validate() ?? false) {
      final updatedModules = _moduleTitleControllers.asMap().entries
          .where((e) => e.value.text.trim().isNotEmpty)
          .map((e) {
            final idx = e.key;
            final original = idx < _moduleData.length ? _moduleData[idx] : null;
            return {
              'title': e.value.text.trim(),
              'text': idx < _moduleTextControllers.length
                  ? _moduleTextControllers[idx].text.trim()
                  : '',
              'num_questions': idx < _moduleQuestionsControllers.length
                  ? int.tryParse(_moduleQuestionsControllers[idx].text.trim()) ?? 0
                  : 0,
              'start_line': original?.startLine ?? '',
              'end_line': original?.endLine ?? '',
              'images': original?.images.map((img) => img.toJson()).toList() ?? [],
            };
          })
          .toList();

      final updatedFields = {
        'course_name': _nameController.text.trim(),
        'course_description': _descController.text.trim(),
        'course_objective': _objController.text.trim(),
        'target_audience': _audienceController.text.trim(),
        'language': _langController.text.trim(),
        'course_difficulty': _selectedDifficulty,
        'modules': updatedModules,
      };

      final success = await ref
          .read(courseUpdateProvider.notifier)
          .updateCourse(widget.course.id, updatedFields, ref);

      if (success && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Course blueprint successfully saved!'),
            backgroundColor: AppTheme.accentGreen,
          ),
        );
      }
    }
  }
}

class _SectionHeaderInput extends StatelessWidget {
  final String title;
  final IconData icon;

  const _SectionHeaderInput({
    required this.title,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: AppTheme.primaryBlue),
        const SizedBox(width: 8),
        Text(
          title,
          style: GoogleFonts.inter(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: AppTheme.primaryBlue,
          ),
        ),
      ],
    );
  }
}


