import 'dart:async';
import 'dart:html' as html;
import 'dart:ui_web' as ui_web;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:frontend/core/theme/app_theme.dart';
import 'package:frontend/core/config/app_constants.dart';
import 'package:frontend/data/models/models.dart';
import 'package:frontend/state/trainer_providers.dart';

class SlidesView extends ConsumerStatefulWidget {
  final Course course;

  const SlidesView({super.key, required this.course});

  @override
  ConsumerState<SlidesView> createState() => _SlidesViewState();
}

class _SlidesViewState extends ConsumerState<SlidesView> {
  int _activeModuleIndex = 0;
  StreamSubscription? _messageSub;

  @override
  void initState() {
    super.initState();
    // Listen to messages from the slide HTML document
    _messageSub = html.window.onMessage.listen((event) {
      if (event.data is Map && event.data['type'] == 'slide_changed') {
        final idx = event.data['index'] as int;
        ref.read(activeSlideIndexProvider.notifier).state = idx;
      }
    });
  }

  @override
  void dispose() {
    _messageSub?.cancel();
    super.dispose();
  }

  void _navigateToSlide(int index, String viewId) {
    ref.read(activeSlideIndexProvider.notifier).state = index;
    // Send postMessage to iframe
    final iframe = html.document.getElementById(viewId) as html.IFrameElement?;
    if (iframe != null && iframe.contentWindow != null) {
      iframe.contentWindow!.postMessage({
        'type': 'go_to_slide',
        'index': index,
      }, '*');
    }
  }

  void _enterFullscreen(String viewId, String slideUrl, CourseModule module) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => Scaffold(
          backgroundColor: Colors.black,
          appBar: AppBar(
            backgroundColor: Colors.black,
            elevation: 0,
            title: Text(
              'Slideshow Mode - ${widget.course.courseName}',
              style: GoogleFonts.inter(color: Colors.white, fontSize: 16),
            ),
            leading: IconButton(
              icon: const Icon(Icons.close, color: Colors.white),
              onPressed: () => Navigator.of(context).pop(),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.arrow_back_ios_new_rounded,
                    color: Colors.white, size: 16),
                onPressed: () {
                  final activeIdx = ref.read(activeSlideIndexProvider);
                  if (activeIdx > 0) {
                    _navigateToSlide(activeIdx - 1, viewId);
                  }
                },
              ),
              Center(
                child: Consumer(
                  builder: (context, ref, child) {
                    final activeIdx = ref.watch(activeSlideIndexProvider);
                    return Text(
                      'Slide ${activeIdx + 1} of ${module.slides.length}',
                      style: GoogleFonts.barlow(
                          color: Colors.white70,
                          fontSize: 14,
                          fontWeight: FontWeight.w600),
                    );
                  },
                ),
              ),
              IconButton(
                icon: const Icon(Icons.arrow_forward_ios_rounded,
                    color: Colors.white, size: 16),
                onPressed: () {
                  final activeIdx = ref.read(activeSlideIndexProvider);
                  if (activeIdx < module.slides.length - 1) {
                    _navigateToSlide(activeIdx + 1, viewId);
                  }
                },
              ),
              const SizedBox(width: 24),
            ],
          ),
          body: Center(
            child: AspectRatio(
              aspectRatio: 16 / 9,
              child: Container(
                color: Colors.white,
                child: kIsWeb
                    ? HtmlElementView(
                        viewType: viewId,
                        key: ValueKey(slideUrl),
                      )
                    : const Center(
                        child: Text(
                          'Visual presentations are supported in Web View Mode.',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                      ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.course.modules.isEmpty) {
      return const Center(child: Text('No modules available in this course.'));
    }

    final module = widget.course.modules[_activeModuleIndex];
    final hasSlides = module.slides.isNotEmpty;
    final slideGenState = ref.watch(slideGenerationProvider);
    final activeSlideIndex = ref.watch(activeSlideIndexProvider);

    if (!hasSlides) {
      return Center(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 600),
          padding: const EdgeInsets.all(32),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: AppTheme.pShapeRadiusCustom(16),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.05),
                blurRadius: 20,
                offset: const Offset(0, 4),
              ),
            ],
            border: Border.all(color: AppTheme.lightGray),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.primaryBlue.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.slideshow_rounded,
                  size: 48,
                  color: AppTheme.primaryBlue,
                ),
              ),
              const SizedBox(height: 24),
              Text(
                'Slide Deck Not Generated',
                style: GoogleFonts.inter(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryBlue,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                'This module does not have a visual presentation planned or generated yet. Generate slides to access dynamic layout templates.',
                style: GoogleFonts.barlow(
                  fontSize: 14,
                  color: AppTheme.gray,
                  height: 1.4,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 28),
              if (slideGenState.status == SlideGenStatus.generating) ...[
                const CircularProgressIndicator(
                  valueColor:
                      AlwaysStoppedAnimation<Color>(AppTheme.primaryBlue),
                ),
                const SizedBox(height: 12),
                Text(
                  'Slicing module content and planning slide layouts...',
                  style: GoogleFonts.barlow(
                    fontSize: 13,
                    color: AppTheme.primaryBlue,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ] else ...[
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryBlue,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 24, vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: AppTheme.pShapeRadiusCustom(8),
                    ),
                  ),
                  icon: const Icon(Icons.auto_awesome, size: 18),
                  label: const Text('Generate Module Slide Deck'),
                  onPressed: () async {
                    final success = await ref
                        .read(slideGenerationProvider.notifier)
                        .generateSlides(widget.course.courseId, ref);
                    if (success && context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content:
                              Text('Visual slides generated successfully!'),
                          backgroundColor: AppTheme.accentGreen,
                        ),
                      );
                    }
                  },
                ),
              ],
            ],
          ),
        ),
      );
    }

    final String viewId =
        'slide-viewer-${widget.course.courseId}-${module.moduleNumber}';
    final String slideUrl =
        AppConstants.slideshowHtmlUrl(widget.course.courseId, module.moduleNumber);

    if (kIsWeb) {
      ui_web.platformViewRegistry.registerViewFactory(
        viewId,
        (int id) => html.IFrameElement()
          ..id = viewId
          ..src = slideUrl
          ..style.border = 'none'
          ..style.width = '100%'
          ..style.height = '100%',
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Left Column: Slide navigation sidebar
        SizedBox(
          width: 320,
          child: Container(
            decoration: const BoxDecoration(
              border: Border(
                right: BorderSide(color: AppTheme.lightGray, width: 1),
              ),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Module selector
                Text(
                  'SELECT CHAPTER',
                  style: GoogleFonts.barlow(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.gray,
                    letterSpacing: 1.2,
                  ),
                ),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  decoration: BoxDecoration(
                    color: AppTheme.lightGray.withOpacity(0.5),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppTheme.lightGray),
                  ),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<int>(
                      value: _activeModuleIndex,
                      isExpanded: true,
                      icon: const Icon(Icons.keyboard_arrow_down,
                          color: AppTheme.primaryBlue),
                      items: List.generate(widget.course.modules.length, (idx) {
                        final mod = widget.course.modules[idx];
                        return DropdownMenuItem<int>(
                          value: idx,
                          child: Text(
                            'Module ${mod.moduleNumber}: ${mod.title}',
                            overflow: TextOverflow.ellipsis,
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
                          setState(() {
                            _activeModuleIndex = val;
                          });
                          ref.read(activeSlideIndexProvider.notifier).state = 0;
                        }
                      },
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  'SLIDES IN DECK',
                  style: GoogleFonts.barlow(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.gray,
                    letterSpacing: 1.2,
                  ),
                ),
                const SizedBox(height: 12),
                Expanded(
                  child: ListView.separated(
                    itemCount: module.slides.length,
                    separatorBuilder: (context, idx) =>
                        const SizedBox(height: 8),
                    itemBuilder: (context, idx) {
                      final slidePlan = module.slides[idx];
                      final isSelected = activeSlideIndex == idx;
                      final layout = slidePlan['layout_type'] ?? 'bullets';

                      return InkWell(
                        onTap: () => _navigateToSlide(idx, viewId),
                        borderRadius: BorderRadius.circular(8),
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: isSelected
                                ? AppTheme.primaryBlue.withOpacity(0.06)
                                : Colors.transparent,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: isSelected
                                  ? AppTheme.primaryBlue.withOpacity(0.3)
                                  : Colors.transparent,
                            ),
                          ),
                          child: Row(
                            children: [
                              Container(
                                width: 28,
                                height: 28,
                                decoration: BoxDecoration(
                                  color: isSelected
                                      ? AppTheme.primaryBlue
                                      : AppTheme.lightGray,
                                  shape: BoxShape.circle,
                                ),
                                child: Center(
                                  child: Text(
                                    '${idx + 1}',
                                    style: GoogleFonts.barlow(
                                      color: isSelected
                                          ? Colors.white
                                          : AppTheme.textBlack,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 12,
                                    ),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      slidePlan['slide_title'] ?? 'Slide Title',
                                      style: GoogleFonts.barlow(
                                        fontWeight: isSelected
                                            ? FontWeight.bold
                                            : FontWeight.w600,
                                        fontSize: 13.5,
                                        color: isSelected
                                            ? AppTheme.primaryBlue
                                            : AppTheme.textBlack,
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      'Layout: ${layout.toString().toUpperCase()}',
                                      style: GoogleFonts.barlow(
                                        fontSize: 10,
                                        color: AppTheme.gray,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ],
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
            ),
          ),
        ),
        // Right Section: Presentation frame & spoken narration audio
        Expanded(
          child: Container(
            color: AppTheme.lightGray.withOpacity(0.2),
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'SLIDE PREVIEW',
                      style: GoogleFonts.barlow(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                        letterSpacing: 1.2,
                      ),
                    ),
                    Row(
                      children: [
                        ElevatedButton.icon(
                          icon: const Icon(Icons.record_voice_over_rounded,
                              size: 14),
                          label: const Text('Go to Scripts'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppTheme.accentOrange,
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 6),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(6)),
                          ),
                          onPressed: () {
                            ref.read(currentTabProvider.notifier).state =
                                4; // Navigate to Scripts tab
                          },
                        ),
                        const SizedBox(width: 8),
                        ElevatedButton.icon(
                          icon: const Icon(Icons.fullscreen, size: 16),
                          label: const Text('Slideshow Mode'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppTheme.primaryBlue,
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 6),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(6)),
                          ),
                          onPressed: () =>
                              _enterFullscreen(viewId, slideUrl, module),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                // The HTML Slide Presentation Viewport
                Expanded(
                  child: Container(
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: AppTheme.pShapeRadius,
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.06),
                          blurRadius: 15,
                          offset: const Offset(0, 4),
                        ),
                      ],
                      border: Border.all(color: AppTheme.lightGray),
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: kIsWeb
                        ? HtmlElementView(
                            viewType: viewId,
                            key: ValueKey(slideUrl),
                          )
                        : const Center(
                            child: Text(
                              'Visual presentations are supported in Web View Mode.',
                              style: TextStyle(fontWeight: FontWeight.bold),
                            ),
                          ),
                  ),
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
