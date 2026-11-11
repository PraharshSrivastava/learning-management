import { Icon } from '@lms/shared/ui/icons/Icon'
import clsx from 'clsx'
import { useEffect, useRef, useState, type FocusEvent } from 'react'

/** Shown when the trainer turns Video Engine off for a document without images. */
export const VIDEO_ENGINE_RECOMMENDED_TEXT =
  'Video Engine is recommended for this course. As the source document contains no images or ' +
  'screenshots, Video Engine will deliver smoother, more visually engaging animations for your ' +
  'learners.'

/** Shown when the trainer turns Video Engine on for a document with images. */
export const STANDARD_RECOMMENDED_TEXT =
  'This document contains images and screenshots that support learner understanding. Video ' +
  'Engine does not include document images in its videos, so standard course generation is ' +
  'recommended to retain these visuals.'

const READING_WORDS_PER_MINUTE = 200
const SETTLE_MS = 4000
const MIN_MS = 8000
const FADE_MS = 300

/** Time to read the message at an average pace, plus a moment to notice it: about 13 s here. */
export function noticeDurationMs(text: string): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length
  return Math.max(MIN_MS, Math.round((words / READING_WORDS_PER_MINUTE) * 60_000) + SETTLE_MS)
}

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

interface VideoEngineNoticeProps {
  message: string
  onDismiss: () => void
}

/**
 * Amber advisory under the Blueprint toolbar. It stays for the message's reading time, pauses
 * while the pointer is over it or focus is inside it, then fades out. Re-mount it (a new `key`)
 * to show it again from the start.
 */
export function VideoEngineNotice({ message, onDismiss }: VideoEngineNoticeProps) {
  const duration = noticeDurationMs(message)
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const remaining = useRef(duration)
  const dismissRef = useRef(onDismiss)
  useEffect(() => {
    dismissRef.current = onDismiss
  }, [onDismiss])
  const paused = hovered || focused

  const close = () => setLeaving(true)

  useEffect(() => {
    if (paused || leaving) return
    const started = Date.now()
    const timer = setTimeout(() => setLeaving(true), remaining.current)
    return () => {
      clearTimeout(timer)
      remaining.current = Math.max(0, remaining.current - (Date.now() - started))
    }
  }, [paused, leaving])

  useEffect(() => {
    if (!leaving) return
    if (prefersReducedMotion()) {
      dismissRef.current()
      return
    }
    const timer = setTimeout(() => dismissRef.current(), FADE_MS)
    return () => clearTimeout(timer)
  }, [leaving])

  const onBlur = (event: FocusEvent<HTMLDivElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false)
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className={clsx(
        'video-engine-notice relative mt-3 overflow-hidden border-l-4 border-accent-orange bg-accent-light-orange',
        'motion-safe:transition-opacity motion-safe:duration-300',
        leaving ? 'opacity-0' : 'opacity-100',
      )}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={onBlur}
      onKeyDown={(event) => {
        if (event.key === 'Escape') close()
      }}
    >
      <div className="flex items-start gap-2.5 px-3.5 pt-3 pb-3.5">
        <Icon
          name="warning_amber_rounded"
          size={20}
          className="mt-px shrink-0 text-accent-orange"
        />
        <div className="min-w-0 flex-1">
          <p className="m-0 text-sm font-semibold text-text-black">
            Not recommended for this document
          </p>
          <p className="m-0 mt-0.5 text-sm leading-[1.55] text-text-black">{message}</p>
        </div>
        <button
          type="button"
          aria-label="Dismiss"
          onClick={close}
          className="-mt-0.5 -mr-1 inline-flex size-7 shrink-0 items-center justify-center rounded-full text-text-secondary hover:bg-black/5 focus-visible:outline-2 focus-visible:outline-brand-blue-light"
        >
          <Icon name="close" size={18} />
        </button>
      </div>
      <div
        aria-hidden
        data-testid="video-engine-notice-timer"
        className="video-engine-notice-timer absolute bottom-0 left-0 h-[3px] w-full origin-left bg-accent-orange motion-reduce:hidden"
        style={{
          animationDuration: `${duration}ms`,
          animationPlayState: paused ? 'paused' : 'running',
        }}
      />
    </div>
  )
}
