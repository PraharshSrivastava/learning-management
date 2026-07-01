import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:video_player/video_player.dart';

import '../theme.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../constants.dart';

class VideoView extends ConsumerStatefulWidget {
  final Course course;

  const VideoView({super.key, required this.course});

  @override
  ConsumerState<VideoView> createState() => _VideoViewState();
}

class _VideoViewState extends ConsumerState<VideoView> {
  int? _selectedModuleIndex;

  @override
  void initState() {
    super.initState();
    _initSelection();
  }

  @override
  void didUpdateWidget(covariant VideoView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.course.id != widget.course.id) {
      _initSelection();
    }
  }

  void _initSelection() {
    if (widget.course.modules.isNotEmpty) {
      _selectedModuleIndex = 0;
    } else {
      _selectedModuleIndex = null;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.course.modules.isEmpty) {
      return Center(
        child: Text(
          'This course has no modules. Generate course outline first.',
          style: GoogleFonts.barlow(color: AppTheme.gray),
        ),
      );
    }

    final isMobile = MediaQuery.of(context).size.width < 900;
    if (isMobile) {
      return _buildMobileLayout();
    } else {
      return _buildDesktopLayout();
    }
  }

  Widget _buildDesktopLayout() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 320,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Course Modules',
                style: GoogleFonts.inter(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryBlue,
                ),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: _buildModuleList(isMobile: false),
              ),
            ],
          ),
        ),
        const SizedBox(width: 24),
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: AppTheme.pShapeRadius,
              border: Border.all(color: AppTheme.lightGray, width: 1),
            ),
            child: _buildVideoDetailPane(),
          ),
        ),
      ],
    );
  }

  Widget _buildMobileLayout() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Select Module Video',
          style: GoogleFonts.inter(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: AppTheme.primaryBlue,
          ),
        ),
        const SizedBox(height: 8),
        _buildModuleList(isMobile: true),
        const SizedBox(height: 16),
        Container(
          height: 500,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: AppTheme.pShapeRadius,
            border: Border.all(color: AppTheme.lightGray, width: 1),
          ),
          child: _buildVideoDetailPane(),
        ),
      ],
    );
  }

  Widget _buildModuleList({required bool isMobile}) {
    return ListView.builder(
      shrinkWrap: isMobile,
      physics: isMobile ? const NeverScrollableScrollPhysics() : const ClampingScrollPhysics(),
      itemCount: widget.course.modules.length,
      itemBuilder: (context, index) {
        final m = widget.course.modules[index];
        final isSelected = _selectedModuleIndex == index;
        final hasVideo = m.videoPath != null && m.videoPath!.isNotEmpty;

        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          decoration: BoxDecoration(
            color: isSelected ? AppTheme.primaryBlue.withOpacity(0.06) : Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: isSelected ? AppTheme.primaryBlue : AppTheme.lightGray,
              width: isSelected ? 1.5 : 1,
            ),
          ),
          child: ListTile(
            dense: true,
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            title: Text(
              'Module ${m.moduleNumber}',
              style: GoogleFonts.inter(
                fontWeight: FontWeight.bold,
                fontSize: 12,
                color: isSelected ? AppTheme.primaryBlue : AppTheme.gray,
              ),
            ),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 4),
                Text(
                  m.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                    color: AppTheme.textBlack,
                  ),
                ),
              ],
            ),
            trailing: Icon(
              hasVideo ? Icons.play_circle_fill : Icons.video_call,
              color: hasVideo ? AppTheme.accentGreen : AppTheme.gray,
              size: 24,
            ),
            onTap: () {
              setState(() {
                _selectedModuleIndex = index;
              });
            },
          ),
        );
      },
    );
  }

  Widget _buildVideoDetailPane() {
    if (_selectedModuleIndex == null) {
      return const Center(child: Text('Select a module to view video details.'));
    }

    final module = widget.course.modules[_selectedModuleIndex!];
    final hasVideo = module.videoPath != null && module.videoPath!.isNotEmpty;
    final hasSlides = module.slides.isNotEmpty;

    if (!hasSlides) {
      return Center(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 450),
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.slideshow, size: 64, color: AppTheme.gray),
              const SizedBox(height: 16),
              Text(
                'Slides Not Generated Yet',
                style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.primaryBlue),
              ),
              const SizedBox(height: 8),
              Text(
                'To generate a slideshow video, you must plan and generate the visual slides first.\nGo to the Slides tab and click "Generate Slides".',
                textAlign: TextAlign.center,
                style: GoogleFonts.barlow(color: AppTheme.gray),
              ),
            ],
          ),
        ),
      );
    }

    if (!hasVideo) {
      return Center(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 450),
          padding: const EdgeInsets.all(32),
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
                  Icons.video_library_rounded,
                  size: 64,
                  color: AppTheme.primaryBlue,
                ),
              ),
              const SizedBox(height: 24),
              Text(
                'No Video Compiled for Module ${module.moduleNumber}',
                style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.primaryBlue),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                'Create a consolidated slideshow video syncing slide layout pages with narration audio files automatically.',
                textAlign: TextAlign.center,
                style: GoogleFonts.barlow(color: AppTheme.gray),
              ),
              const SizedBox(height: 32),
              ElevatedButton.icon(
                onPressed: () {
                  ref.read(videoGenerationProvider.notifier).generateVideo(
                        widget.course.id,
                        module.moduleNumber,
                        ref,
                      );
                },
                icon: const Icon(Icons.bolt),
                label: const Text('Generate Video'),
              ),
            ],
          ),
        ),
      );
    }

    final videoUrl = '${AppConstants.apiBaseUrl}/${module.videoPath!}';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(20),
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: AppTheme.lightGray, width: 1)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Module ${module.moduleNumber} Course Video',
                      style: GoogleFonts.inter(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      module.title,
                      style: GoogleFonts.barlow(
                        fontSize: 14,
                        color: AppTheme.gray,
                      ),
                    ),
                  ],
                ),
              ),
              ElevatedButton.icon(
                onPressed: () {
                  ref.read(videoGenerationProvider.notifier).generateVideo(
                        widget.course.id,
                        module.moduleNumber,
                        ref,
                      );
                },
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Regenerate Video'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  backgroundColor: AppTheme.lightGray,
                  foregroundColor: AppTheme.primaryBlue,
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 800),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Expanded(
                      child: Container(
                        decoration: BoxDecoration(
                          color: Colors.black,
                          borderRadius: AppTheme.pShapeRadius,
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.15),
                              blurRadius: 15,
                              offset: const Offset(0, 5),
                            ),
                          ],
                        ),
                        clipBehavior: Clip.antiAlias,
                        child: ModuleVideoPlayer(url: videoUrl, key: ValueKey(videoUrl)),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class ModuleVideoPlayer extends StatefulWidget {
  final String url;

  const ModuleVideoPlayer({super.key, required this.url});

  @override
  State<ModuleVideoPlayer> createState() => _ModuleVideoPlayerState();
}

class _ModuleVideoPlayerState extends State<ModuleVideoPlayer> {
  late VideoPlayerController _controller;
  bool _isHovering = false;
  String? _errorMsg;

  @override
  void initState() {
    super.initState();
    _controller = VideoPlayerController.networkUrl(Uri.parse(widget.url))
      ..initialize().then((_) {
        setState(() {});
      }).catchError((err) {
        setState(() {
          _errorMsg = err.toString();
        });
      });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  String _formatDuration(Duration d) {
    String minutes = d.inMinutes.toString().padLeft(2, '0');
    String seconds = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    if (_errorMsg != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, color: AppTheme.accentRed, size: 48),
              const SizedBox(height: 16),
              Text(
                'Failed to load video player',
                style: GoogleFonts.inter(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 16),
              ),
              const SizedBox(height: 8),
              Text(
                _errorMsg!,
                textAlign: TextAlign.center,
                style: GoogleFonts.barlow(color: Colors.white70, fontSize: 13),
              ),
            ],
          ),
        ),
      );
    }

    if (!_controller.value.isInitialized) {
      return const Center(
        child: CircularProgressIndicator(
          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
        ),
      );
    }

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovering = true),
      onExit: (_) => setState(() => _isHovering = false),
      child: Stack(
        alignment: Alignment.bottomCenter,
        children: [
          Center(
            child: AspectRatio(
              aspectRatio: _controller.value.aspectRatio,
              child: VideoPlayer(_controller),
            ),
          ),
          
          // Custom controls bar overlaid on hovering
          AnimatedOpacity(
            opacity: _isHovering || !_controller.value.isPlaying ? 1.0 : 0.0,
            duration: const Duration(milliseconds: 250),
            child: Container(
              color: Colors.black.withOpacity(0.5),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Progress bar
                  VideoProgressIndicator(
                    _controller,
                    allowScrubbing: true,
                    colors: VideoProgressColors(
                      playedColor: AppTheme.accentCyan,
                      bufferedColor: Colors.white24,
                      backgroundColor: Colors.white10,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      // Playback Buttons
                      Row(
                        children: [
                          IconButton(
                            icon: Icon(
                              _controller.value.isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded,
                              color: Colors.white,
                            ),
                            onPressed: () {
                              setState(() {
                                if (_controller.value.isPlaying) {
                                  _controller.pause();
                                } else {
                                  _controller.play();
                                }
                              });
                            },
                          ),
                          const SizedBox(width: 8),
                          // Text durations
                          ValueListenableBuilder(
                            valueListenable: _controller,
                            builder: (context, VideoPlayerValue value, child) {
                              return Text(
                                '${_formatDuration(value.position)} / ${_formatDuration(_controller.value.duration)}',
                                style: GoogleFonts.barlow(color: Colors.white, fontSize: 13),
                              );
                            },
                          ),
                        ],
                      ),
                      
                      // Volume controls
                      Row(
                        children: [
                          Icon(
                            _controller.value.volume == 0 ? Icons.volume_off_rounded : Icons.volume_up_rounded,
                            color: Colors.white,
                            size: 20,
                          ),
                          const SizedBox(width: 4),
                          SizedBox(
                            width: 100,
                            child: SliderTheme(
                              data: SliderTheme.of(context).copyWith(
                                trackHeight: 3,
                                thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
                                activeTrackColor: Colors.white,
                                inactiveTrackColor: Colors.white24,
                                thumbColor: Colors.white,
                              ),
                              child: Slider(
                                value: _controller.value.volume,
                                min: 0,
                                max: 1,
                                onChanged: (val) {
                                  setState(() {
                                    _controller.setVolume(val);
                                  });
                                },
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
