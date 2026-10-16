import { LinearPlaybackGuard } from './linearPlaybackGuard'

it('blocks forward seeking beyond continuously watched progress', () => {
  const guard = new LinearPlaybackGuard(true)
  guard.observePosition(0.5)
  guard.observePosition(1)
  guard.observePosition(1.5)
  expect(guard.furthestWatchedSeconds).toBe(1.5)
  expect(guard.constrainSeek(45)).toBe(1.5)
  expect(guard.constrainSeek(1)).toBe(1)
})

it('does not accept completion before playback reaches the end', () => {
  const guard = new LinearPlaybackGuard(true)
  guard.observePosition(1)
  expect(guard.tryMarkCompleted(50)).toBe(false)
  expect(guard.isRestricted).toBe(true)
  expect(guard.furthestWatchedSeconds).toBe(1)
})

it('unlocks seeking after completion', () => {
  const guard = new LinearPlaybackGuard(true)
  guard.observePosition(59)
  expect(guard.tryMarkCompleted(60)).toBe(true)
  expect(guard.isRestricted).toBe(false)
  expect(guard.constrainSeek(55)).toBe(55)
})

it('does not restrict videos that were already completed', () => {
  const guard = new LinearPlaybackGuard(true, true)
  expect(guard.isRestricted).toBe(false)
  expect(guard.constrainSeek(30)).toBe(30)
})
