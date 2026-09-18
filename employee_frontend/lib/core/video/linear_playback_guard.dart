/// Tracks continuous playback and prevents an incomplete video from being
/// advanced beyond the furthest position the learner has genuinely reached.
class LinearPlaybackGuard {
  static const double _seekToleranceSeconds = 0.05;
  static const double _completionToleranceSeconds = 2.0;

  LinearPlaybackGuard({
    required this.enabled,
    bool initiallyCompleted = false,
  }) : _completed = initiallyCompleted;

  final bool enabled;
  bool _completed;
  double _furthestWatchedSeconds = 0;

  bool get isRestricted => enabled && !_completed;
  double get furthestWatchedSeconds => _furthestWatchedSeconds;

  void observePosition(double positionSeconds) {
    if (!isRestricted || !positionSeconds.isFinite || positionSeconds < 0) {
      return;
    }
    if (positionSeconds > _furthestWatchedSeconds) {
      _furthestWatchedSeconds = positionSeconds;
    }
  }

  double constrainSeek(double requestedSeconds) {
    if (!isRestricted || !requestedSeconds.isFinite) {
      return requestedSeconds;
    }
    if (requestedSeconds > _furthestWatchedSeconds + _seekToleranceSeconds) {
      return _furthestWatchedSeconds;
    }
    return requestedSeconds < 0 ? 0 : requestedSeconds;
  }

  bool tryMarkCompleted(double durationSeconds) {
    if (isRestricted && durationSeconds.isFinite && durationSeconds > 0) {
      final requiredPosition = durationSeconds > _completionToleranceSeconds
          ? durationSeconds - _completionToleranceSeconds
          : 0.0;
      if (_furthestWatchedSeconds < requiredPosition) return false;
    }

    _completed = true;
    if (durationSeconds.isFinite && durationSeconds > 0) {
      if (durationSeconds > _furthestWatchedSeconds) {
        _furthestWatchedSeconds = durationSeconds;
      }
    }
    return true;
  }
}
