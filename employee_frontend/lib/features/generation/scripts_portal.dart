import 'dart:html' as html;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:employee_frontend/core/theme/app_theme.dart';
import 'package:employee_frontend/core/config/app_constants.dart';
import 'package:employee_frontend/data/models/models.dart';
import 'package:employee_frontend/state/trainer_preview_providers.dart';

class ScriptsView extends ConsumerStatefulWidget {
  final Course course;

  const ScriptsView({super.key, required this.course});

  @override
  ConsumerState<ScriptsView> createState() => _ScriptsViewState();
}

class _ScriptsViewState extends ConsumerState<ScriptsView> {
  int _activeModuleIndex = 0;
  int? _playingSlideIndex;
  bool _isAudioPlaying = false;
  html.AudioElement? _audioElement;

  @override
  void dispose() {
    _audioElement?.pause();
    super.dispose();
  }

  void _togglePlayAudio(int index, String audioPathRel) {
    final audioUrl = '${AppConstants.apiBaseUrl}/$audioPathRel';

    if (_playingSlideIndex == index && _audioElement != null) {
      if (_isAudioPlaying) {
        _audioElement!.pause();
        setState(() {
          _isAudioPlaying = false;
        });
      } else {
        _audioElement!.play();
        setState(() {
          _isAudioPlaying = true;
        });
      }
      return;
    }

    _audioElement?.pause();

    setState(() {
      _playingSlideIndex = index;
      _isAudioPlaying = true;
    });

    _audioElement = html.AudioElement(audioUrl)
      ..onEnded.listen((_) {
        setState(() {
          _isAudioPlaying = false;
        });
      })
      ..onPlay.listen((_) {
        setState(() {
          _isAudioPlaying = true;
        });
      })
      ..onPause.listen((_) {
        setState(() {
          _isAudioPlaying = false;
        });
      })
      ..onError.listen((_) {
        setState(() {
          _isAudioPlaying = false;
        });
      });

    _audioElement!.play();
  }

  bool _hasAnyScripts(CourseModule module) {
    if (module.slides.isEmpty) return false;
    return module.slides.any((s) =>
        s is Map<String, dynamic> &&
        s['script'] != null &&
        s['script'].toString().trim().isNotEmpty);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.course.modules.isEmpty) {
      return const Center(
          child: Text('No modules available. Please blueprint outline first.'));
    }

    final module = widget.course.modules[_activeModuleIndex];
    final hasSlides = module.slides.isNotEmpty;
    final hasScripts = _hasAnyScripts(module);

    if (!hasSlides) {
      return _buildNoSlidesState(context);
    }

    if (!hasScripts) {
      return _buildNoScriptsState(context, module);
    }

    return _buildScriptsContent(context, module);
  }

  Widget _buildNoSlidesState(BuildContext context) {
    return Center(
      child: Container(
        constraints: const BoxConstraints(maxWidth: 550),
        padding: const EdgeInsets.all(40),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: AppTheme.pShapeRadius,
          border: Border.all(color: AppTheme.lightGray, width: 1),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.primaryBlue.withOpacity(0.08),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.slideshow_rounded,
                size: 64,
                color: AppTheme.primaryBlue,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Slides Not Yet Planned',
              style: GoogleFonts.inter(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: AppTheme.primaryBlue,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(
              'Narration scripts correspond to slide outlines. Please go to the Slides tab and click "Generate Module Slide Deck" first.',
              style: GoogleFonts.barlow(
                fontSize: 14,
                color: AppTheme.gray,
                height: 1.4,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 28),
            ElevatedButton.icon(
              onPressed: () {
                ref.read(currentTabProvider.notifier).state =
                    3; // Navigate to Slides tab
              },
              icon: const Icon(Icons.arrow_forward_rounded, size: 16),
              label: const Text('Go to Slides tab'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryBlue,
                foregroundColor: Colors.white,
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(6)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNoScriptsState(BuildContext context, CourseModule module) {
    return Center(
      child: Container(
        constraints: const BoxConstraints(maxWidth: 550),
        padding: const EdgeInsets.all(40),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: AppTheme.pShapeRadius,
          border: Border.all(color: AppTheme.lightGray, width: 1),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.primaryBlue.withOpacity(0.08),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.record_voice_over_rounded,
                size: 64,
                color: AppTheme.primaryBlue,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'No Narration Scripts Generated',
              style: GoogleFonts.inter(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: AppTheme.primaryBlue,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(
              'Generate slide-by-slide conversational narration scripts (speaker notes) and high-quality spoken audio synthesis for your course module presentation.',
              style: GoogleFonts.barlow(
                fontSize: 14,
                color: AppTheme.gray,
                height: 1.4,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 28),
            ElevatedButton.icon(
              onPressed: () async {
                await ref
                    .read(scriptGenerationProvider.notifier)
                    .generateScripts(widget.course.courseId, ref);
              },
              icon: const Icon(Icons.auto_awesome, size: 16),
              label: const Text('Generate Narration & TTS Audio'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.accentOrange,
                foregroundColor: Colors.white,
                padding:
                    const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(6)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildScriptsContent(BuildContext context, CourseModule module) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Header Controls Row
        Container(
          padding: const EdgeInsets.only(bottom: 16),
          decoration: const BoxDecoration(
            border:
                Border(bottom: BorderSide(color: AppTheme.lightGray, width: 1)),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'MODULE NARRATION SCRIPTS',
                      style: GoogleFonts.barlow(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.gray,
                        letterSpacing: 1.5,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Text(
                          'Select Module: ',
                          style: GoogleFonts.barlow(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.textBlack,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                          decoration: BoxDecoration(
                            color: AppTheme.lightGray.withOpacity(0.4),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: AppTheme.lightGray),
                          ),
                          child: DropdownButtonHideUnderline(
                            child: DropdownButton<int>(
                              value: _activeModuleIndex,
                              icon: const Icon(Icons.keyboard_arrow_down,
                                  color: AppTheme.primaryBlue),
                              items: List.generate(widget.course.modules.length,
                                  (idx) {
                                final mod = widget.course.modules[idx];
                                return DropdownMenuItem<int>(
                                  value: idx,
                                  child: Text(
                                    'Module ${mod.moduleNumber}: ${mod.title}',
                                    style: GoogleFonts.barlow(
                                      fontWeight: FontWeight.w600,
                                      fontSize: 14,
                                      color: AppTheme.primaryBlue,
                                    ),
                                  ),
                                );
                              }),
                              onChanged: (val) {
                                if (val != null) {
                                  _audioElement?.pause();
                                  setState(() {
                                    _activeModuleIndex = val;
                                    _playingSlideIndex = null;
                                    _isAudioPlaying = false;
                                  });
                                }
                              },
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              Row(
                children: [
                  ElevatedButton.icon(
                    icon: const Icon(Icons.refresh_rounded, size: 14),
                    label: const Text('Regenerate scripts'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: AppTheme.primaryBlue,
                      side: const BorderSide(color: AppTheme.primaryBlue),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 8),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(6)),
                    ),
                    onPressed: () async {
                      await ref
                          .read(scriptGenerationProvider.notifier)
                          .generateScripts(widget.course.courseId, ref);
                    },
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.quiz_rounded, size: 14),
                    label: const Text('Generate Quiz'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.accentOrange,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 12),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(6)),
                    ),
                    onPressed: () async {
                      await ref
                          .read(quizGenerationProvider.notifier)
                          .generateQuiz(
                            widget.course.courseId,
                            ref,
                          );
                      if (context.mounted) {
                        final state = ref.read(quizGenerationProvider);
                        if (state.status == QuizGenStatus.success) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text(
                                  'Quiz generated successfully! Switching to Quiz tab.'),
                              backgroundColor: AppTheme.accentGreen,
                            ),
                          );
                        } else if (state.status == QuizGenStatus.error) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                  'Quiz generation failed: ${state.error}'),
                              backgroundColor: AppTheme.accentRed,
                            ),
                          );
                        }
                      }
                    },
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // Scrollable slide scripts list
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.only(bottom: 24),
            itemCount: module.slides.length,
            separatorBuilder: (context, idx) => const SizedBox(height: 16),
            itemBuilder: (context, idx) {
              final slide = module.slides[idx] as Map<String, dynamic>;
              final scriptText = slide['script']?.toString() ?? '';
              final audioPath = slide['audio_path']?.toString() ?? '';
              final hasAudio = audioPath.isNotEmpty;
              final isPlayingThis =
                  _playingSlideIndex == idx && _isAudioPlaying;

              return Container(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: AppTheme.pShapeRadius,
                  border: Border.all(color: AppTheme.lightGray, width: 1),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.01),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                clipBehavior: Clip.antiAlias,
                child: IntrinsicHeight(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Slide Outline Description Pane (Left side)
                      Expanded(
                        flex: 4,
                        child: Container(
                          color: AppTheme.lightGray.withOpacity(0.15),
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  CircleAvatar(
                                    radius: 12,
                                    backgroundColor: AppTheme.primaryBlue,
                                    child: Text(
                                      '${idx + 1}',
                                      style: GoogleFonts.barlow(
                                        color: Colors.white,
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      slide['slide_title'] ?? 'Untitled Slide',
                                      style: GoogleFonts.inter(
                                        fontSize: 15,
                                        fontWeight: FontWeight.bold,
                                        color: AppTheme.textBlack,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const Divider(height: 20),
                              _buildSlideOutlineDetails(slide),
                            ],
                          ),
                        ),
                      ),
                      // Divider line
                      Container(width: 1, color: AppTheme.lightGray),
                      // Narration Script / Speaker Notes Card (Right side)
                      Expanded(
                        flex: 6,
                        child: Container(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Row(
                                    children: [
                                      const Icon(Icons.description_outlined,
                                          color: AppTheme.primaryBlue,
                                          size: 18),
                                      const SizedBox(width: 6),
                                      Text(
                                        'SPEAKER NOTES / NARRATION',
                                        style: GoogleFonts.barlow(
                                          fontSize: 11,
                                          fontWeight: FontWeight.bold,
                                          color: AppTheme.primaryBlue,
                                          letterSpacing: 1.0,
                                        ),
                                      ),
                                    ],
                                  ),
                                  if (hasAudio)
                                    IconButton(
                                      iconSize: 32,
                                      color: isPlayingThis
                                          ? AppTheme.accentGreen
                                          : AppTheme.primaryBlue,
                                      icon: Icon(
                                        isPlayingThis
                                            ? Icons.pause_circle_filled_rounded
                                            : Icons.play_circle_filled_rounded,
                                      ),
                                      onPressed: () =>
                                          _togglePlayAudio(idx, audioPath),
                                      tooltip: isPlayingThis
                                          ? 'Pause Narration'
                                          : 'Listen to Narration',
                                    ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              Expanded(
                                child: Container(
                                  padding: const EdgeInsets.all(14),
                                  decoration: BoxDecoration(
                                    color: AppTheme.lightGray.withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(8),
                                    border:
                                        Border.all(color: AppTheme.lightGray),
                                  ),
                                  child: SingleChildScrollView(
                                    child: Text(
                                      scriptText.isNotEmpty
                                          ? scriptText
                                          : 'No narration script generated for this slide.',
                                      style: GoogleFonts.barlow(
                                        fontSize: 14,
                                        color: AppTheme.textBlack,
                                        height: 1.5,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildSlideOutlineDetails(Map<String, dynamic> slide) {
    final layout = slide['layout_type'] ?? 'bullets';
    final layoutStr = layout.toString().toLowerCase().split('.').last;

    if (layoutStr == 'concept' && slide['concept_data'] != null) {
      final data = slide['concept_data'];
      final coreTerm = data['core_term'] ?? '';
      final definition = data['definition'] ?? '';

      List<dynamic> takeaways = [];
      if (data['key_takeaways'] != null) {
        takeaways = data['key_takeaways'];
      } else if (data['key_takeaway'] != null) {
        takeaways = [data['key_takeaway']];
      }

      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Concept layout',
              style: GoogleFonts.barlow(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.gray)),
          const SizedBox(height: 4),
          Text(coreTerm,
              style: GoogleFonts.inter(
                  fontSize: 15,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryBlue)),
          const SizedBox(height: 4),
          Text(definition,
              style:
                  GoogleFonts.barlow(fontSize: 13, color: AppTheme.textBlack)),
          if (takeaways.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('Takeaways:',
                style: GoogleFonts.barlow(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.gray)),
            ...takeaways.map((t) => Padding(
                  padding: const EdgeInsets.only(left: 6.0, top: 2.0),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('• ',
                          style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: AppTheme.primaryBlue)),
                      Expanded(
                          child: Text(t.toString(),
                              style: GoogleFonts.barlow(fontSize: 12.5))),
                    ],
                  ),
                )),
          ],
        ],
      );
    } else if (layoutStr == 'steps' && slide['steps_data'] != null) {
      final List<dynamic> steps = slide['steps_data']['steps'] ?? [];
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Timeline layout',
              style: GoogleFonts.barlow(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.gray)),
          const SizedBox(height: 6),
          ...steps.map((step) => Padding(
                padding: const EdgeInsets.only(bottom: 6.0),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    CircleAvatar(
                      radius: 8,
                      backgroundColor: AppTheme.primaryBlue,
                      child: Text(
                        '${step['step_number'] ?? ''}',
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 9,
                            fontWeight: FontWeight.bold),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(step['title'] ?? '',
                              style: GoogleFonts.inter(
                                  fontSize: 13, fontWeight: FontWeight.bold)),
                          Text(step['description'] ?? '',
                              style: GoogleFonts.barlow(
                                  fontSize: 12, color: AppTheme.gray)),
                        ],
                      ),
                    ),
                  ],
                ),
              )),
        ],
      );
    } else if (layoutStr == 'comparison' && slide['comparison_data'] != null) {
      final data = slide['comparison_data'];
      final leftTitle = data['left_column_title'] ?? '';
      final List<dynamic> leftPoints = data['left_column_points'] ?? [];
      final rightTitle = data['right_column_title'] ?? '';
      final List<dynamic> rightPoints = data['right_column_points'] ?? [];

      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Comparison layout',
              style: GoogleFonts.barlow(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.gray)),
          const SizedBox(height: 6),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(leftTitle,
                        style: GoogleFonts.inter(
                            fontSize: 12.5,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.primaryBlue)),
                    const Divider(height: 8),
                    ...leftPoints.map((p) => Text('• ${p.toString()}',
                        style: GoogleFonts.barlow(fontSize: 12))),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(rightTitle,
                        style: GoogleFonts.inter(
                            fontSize: 12.5,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.accentOrange)),
                    const Divider(height: 8),
                    ...rightPoints.map((p) => Text('• ${p.toString()}',
                        style: GoogleFonts.barlow(fontSize: 12))),
                  ],
                ),
              ),
            ],
          ),
        ],
      );
    } else if (layoutStr == 'grid' && slide['grid_data'] != null) {
      final List<dynamic> columns = slide['grid_data']['columns'] ?? [];
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Grid layout',
              style: GoogleFonts.barlow(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.gray)),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: columns
                .map((col) => Container(
                      width: 120,
                      padding: const EdgeInsets.all(5),
                      decoration: BoxDecoration(
                        border: Border.all(color: AppTheme.lightGray),
                        borderRadius: BorderRadius.circular(4),
                        color: AppTheme.lightGray.withOpacity(0.2),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(col['header'] ?? '',
                              style: GoogleFonts.inter(
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.primaryBlue)),
                          const SizedBox(height: 2),
                          Text(col['content'] ?? '',
                              style: GoogleFonts.barlow(
                                  fontSize: 10.5, color: AppTheme.textBlack)),
                        ],
                      ),
                    ))
                .toList(),
          ),
        ],
      );
    } else {
      final List<dynamic> bullets =
          slide['bullets_data'] ?? slide['bullets'] ?? [];
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Bullets list layout',
              style: GoogleFonts.barlow(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.gray)),
          const SizedBox(height: 6),
          ...bullets.map((b) {
            final bText = b is String ? b : (b['text'] ?? '');
            return Padding(
              padding: const EdgeInsets.only(bottom: 4.0),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('• ',
                      style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: AppTheme.primaryBlue)),
                  Expanded(
                      child: Text(bText.toString(),
                          style: GoogleFonts.barlow(fontSize: 12.5))),
                ],
              ),
            );
          }),
        ],
      );
    }
  }
}
