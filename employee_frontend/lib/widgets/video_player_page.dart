import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';
import 'package:google_fonts/google_fonts.dart';

import '../theme.dart';
import '../constants.dart';
import '../providers/employee_providers.dart';

class VideoPlayerPage extends ConsumerStatefulWidget {
  final String courseId;
  final int moduleNumber;
  final String videoFilename;

  const VideoPlayerPage({
    super.key,
    required this.courseId,
    required this.moduleNumber,
    required this.videoFilename,
  });

  @override
  ConsumerState<VideoPlayerPage> createState() => _VideoPlayerPageState();
}

class _VideoPlayerPageState extends ConsumerState<VideoPlayerPage> {
  late VideoPlayerController _controller;
  bool _isError = false;
  bool _markedWatched = false;
  bool _isHovering = false;
  String? _errorMsg;

  @override
  void initState() {
    super.initState();
    final videoUrl = AppConstants.videoAssetUrl(widget.videoFilename);
    _controller = VideoPlayerController.networkUrl(Uri.parse(videoUrl))
      ..initialize().then((_) {
        setState(() {});
        _controller.play();
      }).catchError((error) {
        print("Video Error: \$error");
        setState(() {
          _isError = true;
          _errorMsg = error.toString();
        });
      });

    _controller.addListener(() {
      if (_controller.value.isInitialized && 
          !_controller.value.isPlaying && 
          _controller.value.duration == _controller.value.position &&
          !_markedWatched) {
        _markWatched();
      }
    });
  }

  Future<void> _markWatched() async {
    if (_markedWatched) return;
    _markedWatched = true;
    
    await ref.read(employeeCourseListProvider.notifier).updateModuleProgress(
      widget.courseId,
      widget.moduleNumber,
      {"video_watched": true},
    );

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Video completed! Quiz unlocked.', style: TextStyle(color: Colors.white)), backgroundColor: AppTheme.accentGreen),
      );
    }
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
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        iconTheme: const IconThemeData(color: Colors.white),
        title: Text(
          'Module ${widget.moduleNumber} Video',
          style: GoogleFonts.barlow(color: Colors.white),
        ),
      ),
      body: SafeArea(
        child: _buildVideoBody(),
      ),
    );
  }

  Widget _buildVideoBody() {
    if (_isError && _errorMsg != null) {
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
