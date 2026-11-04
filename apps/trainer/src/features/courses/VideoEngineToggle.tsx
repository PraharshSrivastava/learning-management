import type { Course, GenerationConfig } from '@lms/shared/models'
import { Dialog } from '@lms/shared/ui/Dialog'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { Switch } from '@lms/shared/ui/Switch'
import { useToast } from '@lms/shared/ui/Toast'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import clsx from 'clsx'
import { useId, useState, type ReactNode } from 'react'
import { ActionButton } from '../assignments/controls'
import { courseVideoMode } from '../training/videoMode'
import { updateErrorMessage, useUpdateVideoEngine } from './courseQueries'
import {
  STANDARD_RECOMMENDED_TEXT,
  VIDEO_ENGINE_RECOMMENDED_TEXT,
  VideoEngineNotice,
} from './VideoEngineNotice'

/** True when switching engines would clear generated output (as a blueprint edit does). */
export function hasGeneratedContent(course: Course): boolean {
  if (course.thumbnailPath) return true
  return course.modules.some(
    (module) =>
      Boolean(module.videoPath) ||
      module.videoService != null ||
      module.quiz != null ||
      module.notes !== '' ||
      module.slides.length > 0,
  )
}

/** "Recommended: On · no images in the source document", or null without a recommendation. */
export function recommendationText(course: Course): string | null {
  if (course.videoEngineRecommended == null) return null
  if (course.videoEngineRecommended) return 'Recommended: On · no images in the source document'
  const count = course.meaningfulImageCount ?? 0
  const images = count === 1 ? '1 image' : `${count} images`
  return `Recommended: Off · ${images} in the source document`
}

interface Options {
  course: Course
  config: GenerationConfig
  /** A full-course run or module video job is in progress. */
  generating: boolean
  /** The blueprint save is running. */
  saving: boolean
}

interface VideoEngineToggleParts {
  /** Toolbar control, between Save Changes and Generate Course. */
  control: ReactNode
  /** Helper line, advisory notice and confirm dialog, under the toolbar. */
  details: ReactNode
  /** An engine change is being saved; generation waits for it. */
  pending: boolean
}

/**
 * The Blueprint tab's Video Engine toggle. On: module videos come from the Video Generator.
 * Off: standard generation. Each change is saved at once. Picking the setting the source document
 * does not suit shows an amber advisory that hides itself after its reading time.
 */
export function useVideoEngineToggle({
  course,
  config,
  generating,
  saving,
}: Options): VideoEngineToggleParts {
  const id = useId()
  const toast = useToast()
  const update = useUpdateVideoEngine()
  const [notice, setNotice] = useState<{ key: number; message: string } | null>(null)
  const [confirming, setConfirming] = useState<boolean | null>(null)

  // Wait for the course detail, which carries the course's own engine: the list summary alone
  // would briefly show the server default instead of the trainer's choice.
  if (!config.toggleEnabled || course.videoEngine == null) {
    return { control: null, details: null, pending: false }
  }

  const enabled = courseVideoMode(course, config) === 'external'
  const recommended = course.videoEngineRecommended
  const unavailable = !config.videoEngineAvailable && !enabled
  // The Blueprint editor only opens the trainer's own courses, and the server checks ownership.
  const disabledReason = generating
    ? 'Wait for generation to finish to switch engines.'
    : unavailable
      ? "Video Engine isn't available on this server."
      : null
  const disabled = disabledReason != null || saving || update.isPending

  const apply = (next: boolean) => {
    update.mutate(
      { courseId: course.courseId, videoEngine: next },
      {
        onSuccess: () => {
          if (recommended != null && next !== recommended) {
            setNotice((current) => ({
              key: (current?.key ?? 0) + 1,
              message: recommended ? VIDEO_ENGINE_RECOMMENDED_TEXT : STANDARD_RECOMMENDED_TEXT,
            }))
          } else {
            setNotice(null)
          }
        },
        onError: (error) => toast(updateErrorMessage(error), { tone: 'error' }),
      },
    )
  }

  const change = (next: boolean) => {
    if (hasGeneratedContent(course)) setConfirming(next)
    else apply(next)
  }

  const switchControl = (
    <div
      className={clsx(
        'video-engine-toggle inline-flex h-9 items-center gap-2.5 rounded-lg border border-slate-200 bg-white pr-1.5 pl-3 text-sm text-text-black',
        disabled && 'opacity-70',
      )}
    >
      <label
        htmlFor={id}
        className={clsx(
          'inline-flex items-center gap-2 whitespace-nowrap',
          disabled ? 'cursor-not-allowed' : 'cursor-pointer',
        )}
      >
        <Icon name="ondemand_video_outlined" size={16} className="text-primary-blue" />
        Video Engine
      </label>
      <Switch id={id} size="labelled" checked={enabled} disabled={disabled} onChange={change} />
    </div>
  )

  const hint = recommendationText(course)
  const offRecommendation = recommended != null && enabled !== recommended

  return {
    pending: update.isPending,
    control: disabledReason ? (
      <Tooltip content={disabledReason}>
        <span className="inline-flex">{switchControl}</span>
      </Tooltip>
    ) : (
      switchControl
    ),
    details: (
      <>
        {notice && (
          <VideoEngineNotice
            key={notice.key}
            message={notice.message}
            onDismiss={() => setNotice(null)}
          />
        )}
        {hint && (
          <p className="m-0 mt-1.5 flex items-center justify-end gap-1.5 text-xs text-slate-500">
            {offRecommendation && (
              <span
                aria-hidden
                data-testid="video-engine-off-recommendation"
                className="inline-block size-1.5 rounded-full bg-accent-orange"
              />
            )}
            {hint}
          </p>
        )}
        <Dialog
          open={confirming != null}
          onOpenChange={(open) => {
            if (!open) setConfirming(null)
          }}
          title="Switch video engine?"
          actions={
            <>
              <ActionButton variant="text" onClick={() => setConfirming(null)}>
                Cancel
              </ActionButton>
              <ActionButton
                variant="filled"
                onClick={() => {
                  const next = confirming
                  setConfirming(null)
                  if (next != null) apply(next)
                }}
              >
                Switch engine
              </ActionButton>
            </>
          }
        >
          This course&apos;s generated videos, quizzes, notes and thumbnail will be cleared.
          Generate the course again to rebuild them with the selected engine.
        </Dialog>
      </>
    ),
  }
}
