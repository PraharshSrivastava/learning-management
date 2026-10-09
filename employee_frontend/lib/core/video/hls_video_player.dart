import 'dart:async';
import 'dart:html' as html;
import 'dart:js' as js;
import 'dart:js_util' as js_util;
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';

import 'linear_playback_guard.dart';

class HlsVideoPlayer extends StatefulWidget {
  final String hlsUrl;
  final String fallbackUrl;
  final VoidCallback? onEnded;
  final bool enforceLinearPlayback;
  final bool initiallyCompleted;
  final bool fitToWidth;

  const HlsVideoPlayer({
    super.key,
    required this.hlsUrl,
    required this.fallbackUrl,
    this.onEnded,
    this.enforceLinearPlayback = false,
    this.initiallyCompleted = false,
    this.fitToWidth = false,
  });

  @override
  State<HlsVideoPlayer> createState() => _HlsVideoPlayerState();
}

class _HlsVideoPlayerState extends State<HlsVideoPlayer> {
  static Future<void>? _hlsJsLoad;

  late final html.VideoElement _video;
  late final html.Element _container;
  double _captionHeight = 0;
  late final String _viewType;
  StreamSubscription<html.Event>? _endedSubscription;
  StreamSubscription<html.Event>? _timeUpdateSubscription;
  StreamSubscription<html.Event>? _seekingSubscription;
  late final LinearPlaybackGuard _playbackGuard;
  Object? _hls;
  bool _disposed = false;
  int _sourceRequest = 0;
  bool _correctingSeek = false;

  @override
  void initState() {
    super.initState();
    _playbackGuard = LinearPlaybackGuard(
      enabled: widget.enforceLinearPlayback,
      initiallyCompleted: widget.initiallyCompleted,
    );
    _viewType = 'hls-video-${identityHashCode(this)}';
    _video = html.VideoElement()
      ..controls = true
      ..preload = 'auto'
      ..style.width = '100%'
      ..style.height = '100%'
      ..style.backgroundColor = '#000'
      ..style.objectFit = 'contain';
    _endedSubscription = _video.onEnded.listen(_handleEnded);
    _timeUpdateSubscription = _video.onTimeUpdate.listen(_handleTimeUpdate);
    _seekingSubscription = _video.onSeeking.listen(_handleSeeking);
    final player = js_util.getProperty(js_util.globalThis, 'LmsCaptionPlayer');
    _container = player == null
        ? _video
        : js_util.callMethod(player, 'create', [
            _video,
            js.allowInterop((num height) {
              if (mounted && (height.toDouble() - _captionHeight).abs() > .5) {
                setState(() => _captionHeight = height.toDouble());
              }
            }),
            js.allowInterop(
                (num time) => _playbackGuard.constrainSeek(time.toDouble())),
          ]) as html.Element;
    if (player != null) _video.controls = false;
    ui_web.platformViewRegistry
        .registerViewFactory(_viewType, (_) => _container);
    _attachSource();
  }

  void _handleTimeUpdate(html.Event _) {
    if (_correctingSeek || _video.seeking == true) return;
    _playbackGuard.observePosition(_video.currentTime.toDouble());
  }

  void _handleSeeking(html.Event _) {
    if (_correctingSeek) return;
    final requested = _video.currentTime.toDouble();
    final allowed = _playbackGuard.constrainSeek(requested);
    if ((requested - allowed).abs() < 0.01) return;

    _correctingSeek = true;
    _video.currentTime = allowed;
    scheduleMicrotask(() => _correctingSeek = false);
  }

  void _handleEnded(html.Event _) {
    if (!_playbackGuard.tryMarkCompleted(_video.duration.toDouble())) {
      _video.currentTime = _playbackGuard.furthestWatchedSeconds;
      return;
    }
    widget.onEnded?.call();
  }

  @override
  void didUpdateWidget(covariant HlsVideoPlayer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.hlsUrl != widget.hlsUrl ||
        oldWidget.fallbackUrl != widget.fallbackUrl) {
      _destroyHls();
      _attachSource();
    }
  }

  Future<void> _attachSource() async {
    final request = ++_sourceRequest;
    final hlsUrl = widget.hlsUrl;
    final fallbackUrl = widget.fallbackUrl;
    if (js_util.hasProperty(_container, 'loadCaptions')) {
      js_util.callMethod(_container, 'loadCaptions', [fallbackUrl]);
    }
    final playlistExists = await _hlsPlaylistExists(hlsUrl);
    if (_disposed || request != _sourceRequest) return;
    if (!playlistExists) {
      _video.src = fallbackUrl;
      return;
    }

    if (_canPlayNativeHls()) {
      _video.src = hlsUrl;
      return;
    }

    try {
      await _loadHlsJs();
      if (_disposed || request != _sourceRequest) return;
      final hlsConstructor = js_util.getProperty(js_util.globalThis, 'Hls');
      final isSupported = hlsConstructor != null &&
          js_util.callMethod(hlsConstructor, 'isSupported', []) == true;
      if (isSupported) {
        final hls = js_util.callConstructor(hlsConstructor, []);
        _hls = hls;
        js_util.callMethod(hls, 'loadSource', [hlsUrl]);
        js_util.callMethod(hls, 'attachMedia', [_video]);
        return;
      }
    } catch (_) {
      // Fall back to the progressive MP4 below.
    }

    if (!_disposed && request == _sourceRequest) _video.src = fallbackUrl;
  }

  Future<bool> _hlsPlaylistExists(String hlsUrl) async {
    try {
      final response = await html.HttpRequest.request(hlsUrl, method: 'HEAD');
      return response.status != null &&
          response.status! >= 200 &&
          response.status! < 300;
    } catch (_) {
      return false;
    }
  }

  bool _canPlayNativeHls() {
    return _video.canPlayType('application/vnd.apple.mpegurl').isNotEmpty ||
        _video.canPlayType('application/x-mpegURL').isNotEmpty;
  }

  static Future<void> _loadHlsJs() {
    final existing = js_util.getProperty(js_util.globalThis, 'Hls');
    if (existing != null) return Future.value();
    return _hlsJsLoad ??= _injectHlsJs();
  }

  static Future<void> _injectHlsJs() {
    final completer = Completer<void>();
    final script = html.ScriptElement()
      ..src = 'https://cdn.jsdelivr.net/npm/hls.js@1.6.15/dist/hls.min.js'
      ..async = true;
    script.onLoad.first.then((_) => completer.complete());
    script.onError.first.then((_) {
      if (!completer.isCompleted) {
        completer.completeError(StateError('Unable to load hls.js'));
      }
    });
    html.document.head?.append(script);
    return completer.future;
  }

  void _destroyHls() {
    final hls = _hls;
    if (hls != null) {
      js_util.callMethod(hls, 'destroy', []);
      _hls = null;
    }
    _video.removeAttribute('src');
    _video.load();
  }

  @override
  void dispose() {
    _disposed = true;
    _endedSubscription?.cancel();
    if (js_util.hasProperty(_container, 'disposePlayer')) {
      js_util.callMethod(_container, 'disposePlayer', []);
    }
    _timeUpdateSubscription?.cancel();
    _seekingSubscription?.cancel();
    _destroyHls();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.fitToWidth) {
      return LayoutBuilder(
          builder: (context, constraints) => SizedBox(
                height: constraints.maxWidth * 9 / 16 + _captionHeight,
                child: HtmlElementView(viewType: _viewType),
              ));
    }
    return HtmlElementView(viewType: _viewType);
  }
}
