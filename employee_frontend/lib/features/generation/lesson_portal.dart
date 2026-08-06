import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:employee_frontend/core/theme/app_theme.dart';
import 'package:employee_frontend/data/models/models.dart';
import 'package:employee_frontend/state/trainer_preview_providers.dart';

class LessonsView extends ConsumerStatefulWidget {
  final Course course;

  const LessonsView({super.key, required this.course});

  @override
  ConsumerState<LessonsView> createState() => _LessonsViewState();
}

class _LessonsViewState extends ConsumerState<LessonsView> {
  late List<_ModuleLessonData> _data;

  @override
  void initState() {
    super.initState();
    _initData();
  }

  @override
  void didUpdateWidget(covariant LessonsView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.course.courseId != widget.course.courseId) {
      _disposeData();
      _initData();
    }
  }

  void _initData() {
    _data = widget.course.modules.map((module) {
      final sourceList = module.lessons;
      return _ModuleLessonData(
        moduleTitle: module.title,
        moduleNumber: module.moduleNumber,
        lessons: sourceList.map((lesson) {
          return _LessonData(
            lessonTitleCtrl: TextEditingController(text: lesson.lessonTitle),
            bulletCtrls: lesson.bullets
                .map((b) => TextEditingController(text: b.text))
                .toList(),
            images: List<LessonImage>.from(lesson.images),
          );
        }).toList(),
      );
    }).toList();
  }

  void _disposeData() {
    for (final m in _data) {
      for (final s in m.lessons) {
        s.lessonTitleCtrl.dispose();
        for (final b in s.bulletCtrls) b.dispose();
      }
    }
    _data.clear();
  }

  @override
  void dispose() {
    _disposeData();
    super.dispose();
  }

  void _addLesson(int mIdx) {
    setState(() {
      _data[mIdx].lessons.add(_LessonData(
            lessonTitleCtrl: TextEditingController(),
            bulletCtrls: [TextEditingController()],
            images: [],
          ));
    });
  }

  void _deleteLesson(int mIdx, int sIdx) {
    setState(() {
      final lesson = _data[mIdx].lessons.removeAt(sIdx);
      lesson.lessonTitleCtrl.dispose();
      for (final b in lesson.bulletCtrls) b.dispose();
    });
  }

  void _addBullet(int mIdx, int sIdx) {
    setState(() {
      _data[mIdx].lessons[sIdx].bulletCtrls.add(TextEditingController());
    });
  }

  void _deleteBullet(int mIdx, int sIdx, int bIdx) {
    setState(() {
      final ctrl = _data[mIdx].lessons[sIdx].bulletCtrls.removeAt(bIdx);
      ctrl.dispose();
    });
  }

  Future<void> _saveChanges() async {
    final updatedModules = widget.course.modules.asMap().entries.map((mEntry) {
      final mIdx = mEntry.key;
      final originalModule = mEntry.value;
      final mData = mIdx < _data.length ? _data[mIdx] : null;

      final lessonsList = mData?.lessons.asMap().entries.map((sEntry) {
            final sIdx = sEntry.key;
            final sData = sEntry.value;
            final bullets = sData.bulletCtrls
                .where((c) => c.text.trim().isNotEmpty)
                .map((c) => {'text': c.text.trim()})
                .toList();
            return {
              'lesson_number': sIdx + 1,
              'lesson_title': sData.lessonTitleCtrl.text.trim(),
              'bullets': bullets,
              'images': sData.images.map((img) => img.toJson()).toList(),
            };
          }).toList() ??
          [];

      return {
        'title': originalModule.title,
        'source_text': originalModule.sourceText,
        'start_line': originalModule.startLine,
        'end_line': originalModule.endLine,
        'lessons': lessonsList,
      };
    }).toList();

    final success = await ref.read(courseUpdateProvider.notifier).updateCourse(
          widget.course.courseId,
          {'modules': updatedModules},
          ref,
        );

    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Lessons saved successfully!'),
          backgroundColor: AppTheme.accentGreen,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final hasLessons = _data.any((m) => m.lessons.isNotEmpty);

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: AppTheme.pShapeRadius,
        border: Border.all(color: AppTheme.lightGray, width: 1),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            color: AppTheme.primaryBlue,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'CURRICULUM OUTLINE',
                      style: GoogleFonts.barlow(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: Colors.white.withOpacity(0.7),
                        letterSpacing: 2,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      widget.course.courseName,
                      style: GoogleFonts.inter(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
                if (hasLessons)
                  Row(
                    children: [
                      ElevatedButton.icon(
                        icon: const Icon(Icons.save, size: 14),
                        label: const Text('Save Changes'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.accentGreen,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(
                              horizontal: 16, vertical: 8),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(6)),
                        ),
                        onPressed: _saveChanges,
                      ),
                      const SizedBox(width: 10),
                      ElevatedButton.icon(
                        icon: const Icon(Icons.slideshow_rounded, size: 14),
                        label: const Text('Generate Slides'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.primaryBlue,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(
                              horizontal: 16, vertical: 8),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(6)),
                        ),
                        onPressed: () async {
                          final success = await ref
                              .read(slideGenerationProvider.notifier)
                              .generateSlides(
                                widget.course.courseId,
                                ref,
                              );
                          if (success && mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text(
                                    'Slides generated successfully! Switching to Slides tab.'),
                                backgroundColor: AppTheme.accentGreen,
                              ),
                            );
                            ref.read(currentTabProvider.notifier).state = 3;
                          }
                        },
                      ),
                    ],
                  ),
              ],
            ),
          ),
          Expanded(
            child: !hasLessons
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.auto_awesome_outlined,
                            size: 56, color: AppTheme.gray.withOpacity(0.4)),
                        const SizedBox(height: 16),
                        Text(
                          'No Lessons Generated Yet',
                          style: GoogleFonts.inter(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.primaryBlue,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Go to the Courses tab, select a course,\nand click "Generate Lessons".',
                          textAlign: TextAlign.center,
                          style: GoogleFonts.barlow(
                              fontSize: 14, color: AppTheme.gray),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(24),
                    itemCount: _data.length,
                    itemBuilder: (context, mIdx) => _buildModuleBlock(mIdx),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildModuleBlock(int mIdx) {
    final mData = _data[mIdx];
    return Container(
      margin: const EdgeInsets.only(bottom: 24),
      decoration: BoxDecoration(
        border: Border.all(
            color: AppTheme.primaryBlue.withOpacity(0.2), width: 1.5),
        borderRadius: AppTheme.pShapeRadiusCustom(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: AppTheme.primaryBlue.withOpacity(0.06),
              borderRadius: const BorderRadius.only(
                topRight: Radius.circular(8),
                topLeft: Radius.zero,
              ),
            ),
            child: Row(
              children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryBlue,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    'MODULE ${mData.moduleNumber}',
                    style: GoogleFonts.barlow(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                      letterSpacing: 1,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    mData.moduleTitle,
                    style: GoogleFonts.barlow(
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primaryBlue,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                TextButton.icon(
                  icon: const Icon(Icons.add, size: 14),
                  label: const Text('Add Lesson'),
                  style: TextButton.styleFrom(
                      foregroundColor: AppTheme.primaryBlue),
                  onPressed: () => _addLesson(mIdx),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              children: mData.lessons.asMap().entries.map((sEntry) {
                return _buildLessonBlock(mIdx, sEntry.key);
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLessonBlock(int mIdx, int sIdx) {
    final sData = _data[mIdx].lessons[sIdx];
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: AppTheme.lightGray.withOpacity(0.4),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppTheme.gray.withOpacity(0.2)),
      ),
      padding: const EdgeInsets.all(10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: AppTheme.accentCyan.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(3),
                  border:
                      Border.all(color: AppTheme.accentCyan.withOpacity(0.4)),
                ),
                child: Text(
                  'Lesson ${sIdx + 1}',
                  style: GoogleFonts.barlow(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.accentCyan,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextFormField(
                  controller: sData.lessonTitleCtrl,
                  style: GoogleFonts.barlow(
                      fontSize: 13, fontWeight: FontWeight.w600),
                  decoration: const InputDecoration(
                    isDense: true,
                    contentPadding:
                        EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                    border: OutlineInputBorder(),
                    hintText: 'Lesson title...',
                    filled: true,
                    fillColor: Colors.white,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.delete_outline,
                    color: AppTheme.accentRed, size: 16),
                tooltip: 'Delete lesson',
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                onPressed: () => _deleteLesson(mIdx, sIdx),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...sData.bulletCtrls.asMap().entries.map((bEntry) {
            final bIdx = bEntry.key;
            final ctrl = bEntry.value;
            return Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(right: 8, top: 2),
                    child: Icon(Icons.circle,
                        size: 6, color: AppTheme.primaryBlue),
                  ),
                  Expanded(
                    child: TextFormField(
                      controller: ctrl,
                      style: GoogleFonts.barlow(
                          fontSize: 13, color: AppTheme.textBlack),
                      decoration: const InputDecoration(
                        isDense: true,
                        contentPadding:
                            EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                        border: OutlineInputBorder(),
                        hintText: 'Bullet point (~7 words)...',
                        filled: true,
                        fillColor: Colors.white,
                      ),
                    ),
                  ),
                  const SizedBox(width: 4),
                  IconButton(
                    icon: const Icon(Icons.remove_circle_outline,
                        color: AppTheme.accentRed, size: 16),
                    tooltip: 'Delete bullet',
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    onPressed: () => _deleteBullet(mIdx, sIdx, bIdx),
                  ),
                ],
              ),
            );
          }),
          TextButton.icon(
            icon: const Icon(Icons.add, size: 13),
            label: const Text('Add Bullet'),
            style: TextButton.styleFrom(
              foregroundColor: AppTheme.primaryBlue,
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            onPressed: () => _addBullet(mIdx, sIdx),
          ),
        ],
      ),
    );
  }
}

class _ModuleLessonData {
  final int moduleNumber;
  final String moduleTitle;
  final List<_LessonData> lessons;

  _ModuleLessonData({
    required this.moduleNumber,
    required this.moduleTitle,
    required this.lessons,
  });
}

class _LessonData {
  final TextEditingController lessonTitleCtrl;
  final List<TextEditingController> bulletCtrls;
  final List<LessonImage> images;

  _LessonData({
    required this.lessonTitleCtrl,
    required this.bulletCtrls,
    required this.images,
  });
}
