// Course lifecycle actions next to the publish button (Flutter CourseActionsMenu).
import { useSession } from '@lms/shared/auth/session'
import type { Course } from '@lms/shared/models'
import { Dialog } from '@lms/shared/ui/Dialog'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { Menu, type MenuItem } from '@lms/shared/ui/Menu'
import { TextField } from '@lms/shared/ui/TextField'
import { useToast } from '@lms/shared/ui/Toast'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import { useState } from 'react'
import type { Trainer } from '../../auth/trainer'
import { asRecord, detailOr, isOk, paths, type Requester } from './api'
import { ActionButton } from './controls'

type Action = 'Disable' | 'Delete'

const descriptions: Record<Action, string> = {
  Disable:
    'Employees lose course access and Observers are suspended. Progress and completed results are preserved. You can Enable this course again.',
  Delete:
    'Permanently delete this unused course and generated content. The source document is retained. Type DELETE to confirm.',
}

interface CourseActionsMenuProps {
  course: Course
  request: Requester
  onEnable: () => Promise<void>
  /** Reloads course lists, the assignment workspace and reports after a change. */
  onChanged: (action: Action) => Promise<void>
}

interface Pending {
  action: Action
  description: string
  resolve: (approved: boolean) => void
}

export function CourseActionsMenu({
  course,
  request,
  onEnable,
  onChanged,
}: CourseActionsMenuProps) {
  const { person } = useSession<Trainer>()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState<Pending | null>(null)
  // The parent remounts on a course, trainer or token change. The confirm dialog unmounts
  // with it, so its promise never settles and no request is sent for a stale course.

  if (person?.trainerId !== course.trainerId) return null
  const actions: string[] = [
    ...(course.lifecycleState === 'active' ? ['Disable'] : []),
    ...(course.lifecycleState === 'disabled' ? ['Enable'] : []),
    ...(course.canDelete ? ['Delete'] : []),
  ]
  const enabled =
    !busy &&
    actions.length > 0 &&
    course.generationStatus !== 'pending' &&
    course.generationStatus !== 'running'

  const act = async (action: string) => {
    if (busy) return
    if (action === 'Enable') {
      await onEnable()
      return
    }
    const kind = action as Action
    setBusy(true)
    let changed = false
    try {
      let impact = ''
      if (kind === 'Disable') {
        const [assignment, observers] = await Promise.all([
          request(paths.assignment(course.courseId)),
          request(paths.observers(course.courseId)),
        ])
        if (assignment.status !== 200 || observers.status !== 200) {
          throw new Error('Could not load the action preview. Refresh and try again.')
        }
        const a = asRecord(assignment.body)
        if (a.lifecycle_revision !== course.lifecycleRevision) {
          throw new Error('Course availability changed. Refresh before continuing.')
        }
        const list = asRecord(observers.body).observers
        const applied = Array.isArray(list)
          ? list.filter((o) => asRecord(o).is_active === true).length
          : 0
        impact = `${String(a.total_assigned_count ?? 0)} current employee assignments; ${applied} Observer selections are applied.\n\n`
      }
      const approved = await new Promise<boolean>((resolve) =>
        setPending({ action: kind, description: impact + descriptions[kind], resolve }),
      )
      setPending(null)
      if (!approved) return
      const reply =
        kind === 'Delete'
          ? await request(paths.deleteCourse(course.courseId, course.lifecycleRevision), {
              method: 'DELETE',
            })
          : await request(paths.lifecycle(course.courseId), {
              method: 'POST',
              json: { action: 'disable', expected_revision: course.lifecycleRevision },
            })
      if (!isOk(reply)) {
        throw new Error(detailOr(reply, 'Course action failed. Refresh and try again.'))
      }
      changed = true
      await onChanged(kind)
      toast(`${kind} completed.`)
    } catch (error) {
      toast(
        changed
          ? 'Action completed. Refresh course and report data to see the result.'
          : error instanceof Error
            ? error.message
            : String(error),
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Menu
        items={actions.map((action): MenuItem => ({
          key: action,
          label: action,
          onSelect: () => void act(action),
        }))}
        align="start"
        trigger={
          <Tooltip content="Course actions">
            <button
              type="button"
              disabled={!enabled}
              aria-label="Course actions"
              className="inline-flex items-center rounded p-2.5 text-sm text-text-black hover:bg-black/4 focus-visible:outline-2 focus-visible:outline-brand-blue-light disabled:text-gray disabled:hover:bg-transparent"
            >
              {busy ? 'Working…' : 'Actions'}
              <Icon name="expand_more" />
            </button>
          </Tooltip>
        }
      />
      {pending && (
        <ConfirmAction
          key={pending.action}
          action={pending.action}
          courseName={course.courseName}
          description={pending.description}
          onClose={pending.resolve}
        />
      )}
    </>
  )
}

function ConfirmAction({
  action,
  courseName,
  description,
  onClose,
}: {
  action: Action
  courseName: string
  description: string
  onClose: (approved: boolean) => void
}) {
  const [typed, setTyped] = useState('')
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose(false)
      }}
      title={`${action} ${courseName}?`}
      actions={
        <>
          <ActionButton variant="text" onClick={() => onClose(false)}>
            Cancel
          </ActionButton>
          <ActionButton
            variant="filled"
            disabled={action === 'Delete' && typed !== 'DELETE'}
            onClick={() => onClose(true)}
          >
            {action}
          </ActionButton>
        </>
      }
    >
      <p className="whitespace-pre-line">{description}</p>
      {action === 'Delete' && (
        <TextField
          label="Type DELETE"
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          fieldClassName="mt-4"
        />
      )}
    </Dialog>
  )
}
