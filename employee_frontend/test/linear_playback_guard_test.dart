import 'package:employee_frontend/core/video/linear_playback_guard.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('blocks forward seeking beyond continuously watched progress', () {
    final guard = LinearPlaybackGuard(enabled: true);

    guard.observePosition(0.5);
    guard.observePosition(1.0);
    guard.observePosition(1.5);

    expect(guard.furthestWatchedSeconds, 1.5);
    expect(guard.constrainSeek(45), 1.5);
    expect(guard.constrainSeek(1), 1);
  });

  test('does not accept completion before playback reaches the end', () {
    final guard = LinearPlaybackGuard(enabled: true);

    guard.observePosition(1);

    expect(guard.tryMarkCompleted(50), isFalse);
    expect(guard.isRestricted, isTrue);
    expect(guard.furthestWatchedSeconds, 1);
  });

  test('blocks accelerated playback until completion', () {
    final guard = LinearPlaybackGuard(enabled: true);

    expect(guard.constrainPlaybackRate(2), 1);
    expect(guard.constrainPlaybackRate(0.75), 0.75);
  });

  test('unlocks seeking and playback speed after completion', () {
    final guard = LinearPlaybackGuard(enabled: true);
    guard.observePosition(59);

    expect(guard.tryMarkCompleted(60), isTrue);
    expect(guard.isRestricted, isFalse);
    expect(guard.constrainSeek(55), 55);
    expect(guard.constrainPlaybackRate(2), 2);
  });

  test('does not restrict videos that were already completed', () {
    final guard = LinearPlaybackGuard(
      enabled: true,
      initiallyCompleted: true,
    );

    expect(guard.isRestricted, isFalse);
    expect(guard.constrainSeek(30), 30);
    expect(guard.constrainPlaybackRate(1.5), 1.5);
  });
}
