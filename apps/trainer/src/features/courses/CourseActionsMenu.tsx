import { ApiError, apiRequest, errorDetail } from '@lms/shared/api/client'
import { useSession } from '@lms/shared/auth/session'
import type { Course } from '@lms/shared/models'
import { Dialog } from '@lms/shared/ui/Dialog'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { Menu } from '@lms/shared/ui/Menu'
import { useToast } from '@lms/shared/ui/Toast'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useId, useRef, useState } from 'react'
import type { Trainer } from '../../auth/trainer'
import { trainerKeys } from '../../shell/queryKeys'
import { useTrainerSearch, useUpdateTrainerSearch } from '../../shell/search'
import { courseActions, isGenerationBusy, type CourseAction } from './courseLogic'

const DESCRIPTIONS = {
  Disable:
    'Employees lose course access and Observers are suspended. Progress and completed results are preserved. You can Enable this course again.',
  Delete:
    'Permanently delete this unused course and generated content. The source document is retained. Type DELETE to confirm.',
} as const

export type ConfirmAction = keyof typeof DESCRIPTIONS

const PREVIEW_ERROR = 'Could not load the action preview. Refresh and try again.'
const ACTION_ERROR = 'Course action failed. Refresh and try again.'

/** A failure that already has its user text. */
class ActionFailure extends Error {}

const coursePath = (courseId: string) => `/api/courses/${encodeURIComponent(courseId)}`

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

/** "N current employee assignments; M Observer selections are applied." for the Disable dialog. */
async function disableImpact(course: Course): Promise<string> {
  let assignment: unknown
  let observers: unknown
  try {
    ;[assignment, observers] = await Promise.all([
      apiRequest(`${coursePath(course.courseId)}/assignment`),
      apiRequest(`${coursePath(course.courseId)}/observers`),
    ])
  } catch {
    throw new ActionFailure(PREVIEW_ERROR)
  }
  const rule = isRecord(assignment) ? assignment : {}
  if (rule.lifecycle_revision !== course.lifecycleRevision) {
    throw new ActionFailure('Course availability changed. Refresh before continuing.')
  }
  const list = isRecord(observers) && Array.isArray(observers.observers) ? observers.observers : []
  const applied = list.filter((item) => isRecord(item) && item.is_active === true).length
  const assigned = rule.total_assigned_count ?? 0
  return `${String(assigned)} current employee assignments; ${applied} Observer selections are applied.\n\n`
}

async function runAction(action: ConfirmAction, course: Course): Promise<void> {
  try {
    if (action === 'Delete') {
      await apiRequest(
        `${coursePath(course.courseId)}?expected_revision=${course.lifecycleRevision}`,
        { method: 'DELETE' },
      )
    } else {
      await apiRequest(`${coursePath(course.courseId)}/lifecycle`, {
        method: 'POST',
        json: { action: 'disable', expected_revision: course.lifecycleRevision },
      })
    }
  } catch (error) {
    const detail = error instanceof ApiError && error.status > 0 ? errorDetail(error.body) : null
    throw new ActionFailure(detail ?? ACTION_ERROR)
  }
}

interface CourseActionsMenuProps {
  course: Course
  /** Text and icon color of the trigger. Default is the body text color. */
  foregroundColor?: string
  /** Replaces the default Enable step (open the Assign tab). The Assign tab asks to publish. */
  onEnable?: () => Promise<void>
  /** Runs after the course lists refresh. The Assign tab reloads its saved rule here. */
  onChanged?: (action: ConfirmAction) => Promise<void>
}

/**
 * Owner-only lifecycle menu: Disable, Enable, Delete. Enable opens the Assign tab, because
 * publishing an assignment enables the course. Disable and Delete ask for confirmation first.
 */
export function CourseActionsMenu({
  course,
  foregroundColor,
  onEnable,
  onChanged,
}: CourseActionsMenuProps) {
  const { person, token } = useSession<Trainer>()
  const queryClient = useQueryClient()
  const updateSearch = useUpdateTrainerSearch()
  const { course: selectedId } = useTrainerSearch()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState<{ action: ConfirmAction; description: string } | null>(
    null,
  )

  // The latest identity and course. A reply for an old one is dropped, as the Flutter guards did.
  const context = { courseId: course.courseId, token, trainerId: person?.trainerId }
  const latest = useRef(context)
  useEffect(() => {
    latest.current = context
  })
  const sameUser = (captured: typeof context) =>
    latest.current.token === captured.token && latest.current.trainerId === captured.trainerId

  if (!person || person.trainerId !== course.trainerId) return null

  const actions = courseActions(course)
  const enabled = !busy && actions.length > 0 && !isGenerationBusy(course)

  const select = async (action: CourseAction) => {
    if (busy) return
    if (action === 'Enable') {
      if (onEnable) await onEnable()
      else updateSearch({ course: course.courseId, tab: 'assign' })
      return
    }
    setBusy(true)
    const captured = context
    try {
      const impact = action === 'Disable' ? await disableImpact(course) : ''
      if (!sameUser(captured) || latest.current.courseId !== captured.courseId) {
        setBusy(false)
        return
      }
      setConfirm({ action, description: impact + DESCRIPTIONS[action] })
    } catch (error) {
      toast(error instanceof Error ? error.message : PREVIEW_ERROR)
      setBusy(false)
    }
  }

  const cancel = () => {
    setConfirm(null)
    setBusy(false)
  }

  const execute = async (action: ConfirmAction) => {
    setConfirm(null)
    const captured = context
    const target = course
    let changed = false
    try {
      await runAction(action, target)
      changed = true
      if (!sameUser(captured)) return
      if (action === 'Delete') {
        queryClient.removeQueries({ queryKey: trainerKeys.course(target.courseId), exact: true })
        // A deleted course must not stay selected (Flutter left it in the detail pane).
        if (selectedId === target.courseId) updateSearch({ course: undefined }, { replace: true })
      }
      const refresh = { throwOnError: true }
      await queryClient.invalidateQueries({ queryKey: trainerKeys.courses }, refresh)
      await queryClient.invalidateQueries({ queryKey: trainerKeys.assignableCourses }, refresh)
      await onChanged?.(action)
      await queryClient.invalidateQueries({ queryKey: trainerKeys.performance }, refresh)
      toast(`${action} completed.`)
    } catch (error) {
      if (changed && !sameUser(captured)) return
      toast(
        changed
          ? 'Action completed. Refresh course and report data to see the result.'
          : error instanceof Error
            ? error.message
            : ACTION_ERROR,
      )
    } finally {
      setBusy(false)
    }
  }

  const trigger = (
    <button
      type="button"
      disabled={!enabled}
      aria-label="Course actions"
      className="inline-flex shrink-0 items-center p-[10px] text-sm leading-6 enabled:hover:bg-black/4 disabled:cursor-default focus-visible:outline-2 focus-visible:outline-white"
      style={{ color: foregroundColor ?? 'var(--color-text-black)' }}
    >
      <span>{busy ? 'Working…' : 'Actions'}</span>
      <Icon name="expand_more" size={24} />
    </button>
  )

  return (
    <>
      <Tooltip content="Course actions">
        <span className="inline-flex">
          <Menu
            align="start"
            trigger={trigger}
            items={actions.map((action) => ({
              key: action,
              label: action,
              onSelect: () => void select(action),
            }))}
          />
        </span>
      </Tooltip>
      {confirm && (
        <ConfirmationDialog
          action={confirm.action}
          courseName={course.courseName}
          description={confirm.description}
          onCancel={cancel}
          onConfirm={() => void execute(confirm.action)}
        />
      )}
    </>
  )
}

interface ConfirmationDialogProps {
  action: ConfirmAction
  courseName: string
  description: string
  onCancel: () => void
  onConfirm: () => void
}

/** Flutter _CourseActionConfirmation. Delete stays disabled until the text is exactly DELETE. */
function ConfirmationDialog({
  action,
  courseName,
  description,
  onCancel,
  onConfirm,
}: ConfirmationDialogProps) {
  const [typed, setTyped] = useState('')
  const fieldId = useId()
  const blocked = action === 'Delete' && typed !== 'DELETE'
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onCancel()
      }}
      width={1360}
      // The Flutter AlertDialog sizes to its text.
      className="w-max! max-w-[calc(100%-80px)]!"
      title={`${action} ${courseName}?`}
      actions={
        <>
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex h-9 items-center rounded-full px-3 font-dm text-sm font-bold text-primary-blue hover:bg-primary-blue/8"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={blocked}
            onClick={onConfirm}
            className={clsx(
              'inline-flex h-9 items-center rounded-full px-6 font-dm text-sm font-bold',
              blocked
                ? 'cursor-not-allowed bg-surface-disabled text-gray'
                : 'bg-primary-blue text-white hover:bg-[#0a3d8a]',
            )}
          >
            {action}
          </button>
        </>
      }
    >
      <p className="m-0 text-sm leading-[21px] whitespace-pre-line text-text-black">
        {description}
      </p>
      {action === 'Delete' && (
        <div className="group relative h-12 border-b-2 border-[#ececf2] focus-within:border-brand-blue-light">
          <label
            htmlFor={fieldId}
            className={clsx(
              'pointer-events-none absolute left-0 text-[#52545d] transition-all',
              typed
                ? 'top-0.5 text-xs leading-4'
                : 'top-[13px] text-base leading-6 group-focus-within:top-0.5 group-focus-within:text-xs group-focus-within:leading-4 group-focus-within:text-brand-blue-light',
            )}
          >
            Type DELETE
          </label>
          <input
            id={fieldId}
            value={typed}
            autoComplete="off"
            onChange={(event) => setTyped(event.target.value)}
            className="absolute inset-x-0 bottom-1 h-6 bg-transparent text-base leading-6 text-text-black outline-none"
          />
        </div>
      )}
    </Dialog>
  )
}
