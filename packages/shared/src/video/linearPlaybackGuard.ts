const SEEK_TOLERANCE_SECONDS = 0.05
const COMPLETION_TOLERANCE_SECONDS = 2

/**
 * Tracks continuous playback and prevents an incomplete video from being
 * advanced beyond the furthest position the learner has genuinely reached.
 */
export class LinearPlaybackGuard {
  private completed: boolean
  private furthest = 0

  constructor(
    readonly enabled: boolean,
    initiallyCompleted = false,
  ) {
    this.completed = initiallyCompleted
  }

  get isRestricted(): boolean {
    return this.enabled && !this.completed
  }

  get furthestWatchedSeconds(): number {
    return this.furthest
  }

  observePosition(positionSeconds: number): void {
    if (!this.isRestricted || !Number.isFinite(positionSeconds) || positionSeconds < 0) return
    if (positionSeconds > this.furthest) this.furthest = positionSeconds
  }

  constrainSeek(requestedSeconds: number): number {
    if (!this.isRestricted || !Number.isFinite(requestedSeconds)) return requestedSeconds
    if (requestedSeconds > this.furthest + SEEK_TOLERANCE_SECONDS) return this.furthest
    return requestedSeconds < 0 ? 0 : requestedSeconds
  }

  tryMarkCompleted(durationSeconds: number): boolean {
    const validDuration = Number.isFinite(durationSeconds) && durationSeconds > 0
    if (this.isRestricted && validDuration) {
      const required =
        durationSeconds > COMPLETION_TOLERANCE_SECONDS
          ? durationSeconds - COMPLETION_TOLERANCE_SECONDS
          : 0
      if (this.furthest < required) return false
    }
    this.completed = true
    if (validDuration && durationSeconds > this.furthest) this.furthest = durationSeconds
    return true
  }
}
