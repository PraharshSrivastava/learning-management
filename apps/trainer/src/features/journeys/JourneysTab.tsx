// Trainer Journeys tab: build a Learning Journey from existing courses, choose who gets it,
// publish it and follow progress. Laid out like the Assign desk and reusing its controls.
import { errorMessage } from '@lms/shared/api/client'
import { useSession } from '@lms/shared/auth/session'
import type { AssignmentOptions } from '@lms/shared/models'
import { Dialog } from '@lms/shared/ui/Dialog'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import { Spinner } from '@lms/shared/ui/Spinner'
import { useToast } from '@lms/shared/ui/Toast'
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { useBlocker } from '@tanstack/react-router'
import clsx from 'clsx'
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import type { Trainer } from '../../auth/trainer'
import { setPendingLinkedReport } from '../../shell/linkedReport'
import { trainerKeys } from '../../shell/queryKeys'
import { useTrainerSearch, useUpdateTrainerSearch } from '../../shell/search'
import { ActionButton, Notice, Switch } from '../assignments/controls'
import '../assignments/AssignStyles.css'
import {
  createJourney,
  deleteJourney,
  disableJourney,
  duplicateJourney,
  fetchAssignmentOptions,
  fetchCourseOptions,
  fetchJourney,
  fetchJourneyObservers,
  fetchJourneys,
  fetchPreview,
  fetchSavedGroups,
  publishJourney,
  saveJourney,
  saveJourneyObservers,
  savePayload,
  type JourneyDetail,
  type JourneyObserver,
  type JourneyStatus,
  type JourneySummary,
} from './api'
import { orderModeOf, publishSummary, removedWithLearners, type OrderMode } from './editing'
import { JourneyAudience } from './JourneyAudience'
import { JourneyCourses } from './JourneyCourses'
import { JourneyObservers, observersIncomplete } from './JourneyObservers'
import { LearnerPreview } from './LearnerPreview'

const EMPTY_OPTIONS: AssignmentOptions = {
  employees: [],
  departments: [],
  mailingLists: [],
  jobTitles: [],
}

const statusChip: Record<JourneyStatus, { label: string; color: string }> = {
  draft: { label: 'Draft', color: '#8a5a00' },
  published: { label: 'Published', color: '#087f68' },
  disabled: { label: 'Disabled', color: '#667085' },
}

const LEAVE_PROMPT = 'Leave this journey without saving your changes?'

/** Navigation guard shared by the tab and its editor. */
interface Guard {
  /** Records whether the open journey has unsaved changes. */
  setDirty: (dirty: boolean) => void
  /** Lets the next navigation through without asking, after the user already chose. */
  allowNext: () => void
}

export function JourneysTab() {
  const { person } = useSession<Trainer>()
  const queryClient = useQueryClient()
  const toast = useToast()
  const { journey: selectedId } = useTrainerSearch()
  const updateSearch = useUpdateTrainerSearch()
  const list = useQuery({
    queryKey: trainerKeys.journeys,
    queryFn: fetchJourneys,
    enabled: person != null,
  })
  const journeys = list.data?.journeys ?? []
  const selected = journeys.find((j) => j.journeyId === selectedId) ?? null
  const [naming, setNaming] = useState(false)
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)

  const dirty = useRef(false)
  const skip = useRef(false)
  const [guard] = useState<Guard>(() => ({
    setDirty: (value) => {
      dirty.current = value
    },
    allowNext: () => {
      skip.current = true
    },
  }))
  // Switching journeys or tabs, or closing the page, asks before unsaved changes are lost.
  useBlocker({
    shouldBlockFn: () => {
      if (skip.current) {
        skip.current = false
        return false
      }
      return dirty.current && !window.confirm(LEAVE_PROMPT)
    },
    enableBeforeUnload: () => dirty.current,
  })

  const startNew = () => {
    if (dirty.current && !window.confirm(LEAVE_PROMPT)) return
    setName('')
    setNaming(true)
  }

  const create = async () => {
    const title = name.trim()
    if (!title) return
    setCreating(true)
    try {
      const created = await createJourney(title)
      await queryClient.invalidateQueries({ queryKey: trainerKeys.journeys })
      setNaming(false)
      guard.allowNext()
      updateSearch({ journey: created.journeyId })
    } catch (error) {
      toast(errorMessage(error), { tone: 'error' })
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="assign-desk">
      <div className="assign-layout">
        <aside className="assign-sidebar" aria-label="Learning journey navigation">
          <div className="assign-course-list">
            <div className="assign-course-head">
              <h2>Learning journeys</h2>
              <ActionButton
                variant="filled"
                icon="add"
                onClick={startNew}
                className="assign-button"
              >
                New
              </ActionButton>
            </div>
            <div className="assign-course-scroll">
              {list.isPending && person != null ? (
                <div className="flex h-full items-center justify-center p-8">
                  <Spinner label="Loading journeys" />
                </div>
              ) : list.isError ? (
                <p className="p-6 text-center text-sm text-accent-red">
                  {errorMessage(list.error)}
                </p>
              ) : journeys.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-6 text-center">
                  <Icon name="track_changes" size={40} className="text-gray/50" />
                  <p className="mt-3 font-medium text-[#5b6980]">No learning journeys yet</p>
                  <p className="mt-2 text-xs text-[#5b6980]">
                    Create one, then add your published or ready courses in order.
                  </p>
                </div>
              ) : (
                <ul aria-label="Learning journeys">
                  {journeys.map((journey) => (
                    <li key={journey.journeyId}>
                      <button
                        type="button"
                        title={journey.title}
                        aria-current={journey.journeyId === selectedId ? 'true' : undefined}
                        onClick={() => updateSearch({ journey: journey.journeyId })}
                        className={clsx(
                          'assign-course-row',
                          journey.journeyId === selectedId && 'assign-course-selected',
                        )}
                      >
                        <span className="assign-course-icon">
                          <Icon name="track_changes" size={18} />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="assign-course-title">{journey.title}</span>
                          <span className="assign-course-meta">
                            <StatusChip status={journey.status} />
                            <span className="ml-auto">{sidebarMeta(journey)}</span>
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </aside>
        <main className="min-w-0" aria-label="Learning journey workspace">
          {selected == null ? (
            <div className="assign-empty">
              <p className="font-medium text-[#19273e]">Select a learning journey</p>
              <p className="mt-1 text-sm text-[#5b6980]">
                A journey is an ordered set of your existing courses. Each course opens when the one
                before it is passed.
              </p>
            </div>
          ) : (
            <JourneyLoader
              key={selected.journeyId}
              summary={selected}
              others={journeys}
              guard={guard}
            />
          )}
        </main>
      </div>
      <Dialog
        open={naming}
        onOpenChange={(open) => !creating && setNaming(open)}
        title="New learning journey"
        dismissible={!creating}
        actions={
          <>
            <ActionButton variant="text" disabled={creating} onClick={() => setNaming(false)}>
              Cancel
            </ActionButton>
            <ActionButton
              variant="filled"
              disabled={!name.trim() || creating}
              onClick={() => void create()}
            >
              {creating ? 'Creating…' : 'Create'}
            </ActionButton>
          </>
        }
      >
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void create()
          }}
        >
          <label className="block text-xs font-semibold text-[#5b6980]">
            Journey name
            <input
              autoFocus
              className={fieldClass}
              value={name}
              maxLength={200}
              placeholder="For example: New Joiner Induction"
              onChange={(event) => setName(event.target.value)}
            />
          </label>
        </form>
      </Dialog>
    </div>
  )
}

function sidebarMeta(journey: JourneySummary): string {
  if (journey.status === 'draft')
    return `${journey.courseCount} course${journey.courseCount === 1 ? '' : 's'}`
  const percent = journey.assignedCount
    ? Math.round((journey.completedCount / journey.assignedCount) * 100)
    : 0
  return `${journey.assignedCount} learner${journey.assignedCount === 1 ? '' : 's'} · ${percent}% completed`
}

function StatusChip({ status }: { status: JourneyStatus }) {
  const { label, color } = statusChip[status]
  return (
    <span
      className="inline-block rounded-[20px] px-2 py-[3px] font-dm text-[11px] leading-[14px] font-medium"
      style={{ color, backgroundColor: `color-mix(in srgb, ${color} 10%, transparent)` }}
    >
      {label}
    </span>
  )
}

function JourneyLoader({
  summary,
  others,
  guard,
}: {
  summary: JourneySummary
  others: JourneySummary[]
  guard: Guard
}) {
  const detail = useQuery({
    queryKey: [...trainerKeys.journeys, 'detail', summary.journeyId],
    queryFn: () => fetchJourney(summary.journeyId),
  })
  const observers = useQuery({
    queryKey: [...trainerKeys.journeys, 'observers', summary.journeyId],
    queryFn: () => fetchJourneyObservers(summary.journeyId),
  })
  if (detail.isPending || observers.isPending) {
    return (
      <div className="flex items-center justify-center p-12">
        <Spinner label="Loading journey" />
      </div>
    )
  }
  if (detail.isError) return <Notice text={errorMessage(detail.error)} isError />
  if (observers.isError) return <Notice text={errorMessage(observers.error)} isError />
  // The editor keeps its own copy of the saved journey, updated from each save's response, so a
  // background refetch never replaces what the trainer is editing.
  return (
    <JourneyEditor
      initial={detail.data}
      initialObservers={observers.data}
      others={others.filter((j) => j.journeyId !== summary.journeyId)}
      guard={guard}
    />
  )
}

/** Holds a value until it stops changing for `delay` ms. */
function useDebounced<T>(value: T, delay: number): T {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return settled
}

type Busy = 'save' | 'apply' | 'publish' | 'disable' | 'delete' | 'duplicate'
type Confirm = 'publish' | 'disable' | 'delete' | 'remove'

const overlayText: Partial<Record<Busy, string>> = {
  apply: 'Saving and applying your changes to learners…',
  publish: 'Publishing and assigning courses…',
  disable: 'Disabling the journey…',
}

function JourneyEditor({
  initial,
  initialObservers,
  others,
  guard,
}: {
  initial: JourneyDetail
  initialObservers: JourneyObserver[]
  others: JourneySummary[]
  guard: Guard
}) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const updateSearch = useUpdateTrainerSearch()
  const [saved, setSaved] = useState(initial)
  const [draft, setDraft] = useState(initial)
  const [savedObservers, setSavedObservers] = useState(initialObservers)
  const [observers, setObservers] = useState(initialObservers)
  const [mode, setMode] = useState<OrderMode>(() => orderModeOf(initial.stages))
  const [busy, setBusy] = useState<Busy | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<Confirm | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const journeyDirty = JSON.stringify(savePayload(draft)) !== JSON.stringify(savePayload(saved))
  const observersDirty = JSON.stringify(observers) !== JSON.stringify(savedObservers)
  const dirty = journeyDirty || observersDirty
  const journeyId = saved.journeyId
  const live = saved.status === 'published'

  useLayoutEffect(() => {
    guard.setDirty(dirty)
  }, [dirty, guard])
  useEffect(() => () => guard.setDirty(false), [guard])

  const courseOptions = useQuery({
    queryKey: [...trainerKeys.journeys, 'course-options'],
    queryFn: fetchCourseOptions,
  })
  const options = useQuery({ queryKey: ['assignment', 'options'], queryFn: fetchAssignmentOptions })
  const savedGroups = useQuery({
    queryKey: ['assignment', 'saved-groups'],
    queryFn: fetchSavedGroups,
  })
  // A live count of who the unsaved selection matches; Observers are never enrolled.
  const audience = useDebounced(
    { rule: draft.rule, observerIds: observers.map((o) => o.observerEmployeeId) },
    400,
  )
  const preview = useQuery({
    queryKey: [...trainerKeys.journeys, 'preview', journeyId, JSON.stringify(audience)],
    queryFn: () => fetchPreview(journeyId, audience.rule, audience.observerIds),
    placeholderData: keepPreviousData,
  })

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: trainerKeys.journeys })
    void queryClient.invalidateQueries({ queryKey: trainerKeys.courses })
    void queryClient.invalidateQueries({ queryKey: trainerKeys.assignableCourses })
    void queryClient.invalidateQueries({ queryKey: trainerKeys.performance })
  }

  // Learner results live in Performance, next to course results, for trainers and Observers alike.
  const viewPerformance = () => {
    setPendingLinkedReport({ courseId: null, status: null, journeyId })
    void queryClient.invalidateQueries({ queryKey: trainerKeys.performance })
    updateSearch({ tab: 'performance' })
  }

  const run = async (label: Busy, action: () => Promise<void>) => {
    setBusy(label)
    setError(null)
    try {
      await action()
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(null)
    }
  }

  const adopt = (next: JourneyDetail) => {
    setSaved(next)
    setDraft(next)
  }

  /** Saves the journey and its Observers together; returns whether learners were re-checked. */
  const persist = async (): Promise<boolean> => {
    // Observers first: saving a live journey enrols everyone who matches, and a new Observer
    // must already be one by then so they are never enrolled as a learner.
    if (observersDirty) {
      await saveJourneyObservers(journeyId, observers)
      setSavedObservers(observers)
      queryClient.setQueryData([...trainerKeys.journeys, 'observers', journeyId], observers)
    }
    if (!journeyDirty) return false
    try {
      const result = await saveJourney(draft)
      adopt(result.detail)
      return result.learnersRechecked
    } catch (caught) {
      throw new Error(
        observersDirty
          ? `The observers were saved, but the journey was not: ${errorMessage(caught)}`
          : errorMessage(caught),
        { cause: caught },
      )
    }
  }

  const observerProblem = () => {
    if (!observersIncomplete(observers)) return false
    setError('Choose employees or departments for every journey observer, or remove the observer.')
    return true
  }

  const save = () => {
    if (observerProblem()) return
    if (live && removedWithLearners(saved.stages, draft.stages).length > 0) {
      setConfirm('remove')
      return
    }
    void applySave()
  }

  const applySave = () =>
    run(live ? 'apply' : 'save', async () => {
      const rechecked = await persist()
      await refresh()
      toast(
        live
          ? rechecked
            ? 'Saved and applied. Learners now have the updated journey.'
            : 'Saved and applied.'
          : 'Learning journey saved.',
        { tone: 'success' },
      )
    })

  const askPublish = () => {
    if (observerProblem()) return
    setConfirm('publish')
  }

  const publish = () =>
    run('publish', async () => {
      await persist()
      const { detail, newlyAssigned } = await publishJourney(journeyId)
      adopt(detail)
      await refresh()
      toast(
        newlyAssigned > 0
          ? `Published. ${newlyAssigned} employee${newlyAssigned === 1 ? '' : 's'} received this journey.`
          : 'Published. Everyone who matches already has this journey.',
        { tone: 'success' },
      )
    })

  const disable = () =>
    run('disable', async () => {
      adopt(await disableJourney(journeyId))
      await refresh()
      toast('Learning journey disabled for employees.')
    })

  const remove = () =>
    run('delete', async () => {
      await deleteJourney(journeyId)
      guard.setDirty(false)
      guard.allowNext()
      updateSearch({ journey: undefined })
      await refresh()
      toast('Learning journey deleted.')
    })

  const duplicate = () =>
    run('duplicate', async () => {
      const copy = await duplicateJourney(journeyId)
      await refresh()
      updateSearch({ journey: copy.journeyId })
      toast('Copied as a new draft. Observers and learners are not copied.')
    })

  const discard = () => {
    setDraft(saved)
    setObservers(savedObservers)
    setMode(orderModeOf(saved.stages))
    setError(null)
  }

  const update = (patch: Partial<JourneyDetail>) =>
    setDraft((current) => ({ ...current, ...patch }))
  const stepTotal = draft.stages.reduce((sum, stage) => sum + stage.steps.length, 0)
  const canDelete = saved.publishedAt == null && saved.status === 'draft'
  const removed = removedWithLearners(saved.stages, draft.stages)
  const matchText = preview.data
    ? `${preview.data.matchCount} employee${preview.data.matchCount === 1 ? '' : 's'} match`
    : 'Matching employees'
  const prerequisiteTitle =
    others.find((j) => j.journeyId === draft.prerequisiteJourneyId)?.title ?? null
  const unsavedTitle = dirty ? 'Save or discard your changes first.' : undefined

  return (
    <div className="assign-workspace" inert={busy != null} aria-busy={busy != null}>
      <header className="assign-heading sticky top-3 z-20 shadow-[0_4px_16px_#1d3d6414]">
        <div className="min-w-0 flex-1">
          <p className="assign-kicker">Learning journey</p>
          <h2 className="assign-title">{draft.title || 'Untitled journey'}</h2>
          <p className="assign-meta">
            <StatusChip status={saved.status} />
            <span>
              {stepTotal} course{stepTotal === 1 ? '' : 's'}
            </span>
            {saved.status !== 'draft' && <span>{saved.assignedCount} learners</span>}
            {dirty && (
              <span className="rounded-[20px] bg-[#fff4d6] px-2 py-[3px] text-[11px] font-medium text-[#8a5a00]">
                Unsaved changes
              </span>
            )}
          </p>
        </div>
        <div className="assign-actions" role="toolbar" aria-label="Journey actions">
          <ActionButton
            icon="school_outlined"
            onClick={() => setPreviewing(true)}
            className="assign-button"
          >
            Preview as learner
          </ActionButton>
          <ActionButton
            icon="add"
            disabled={dirty}
            title={unsavedTitle}
            onClick={() => void duplicate()}
            className="assign-button"
          >
            Duplicate
          </ActionButton>
          {canDelete && (
            <ActionButton
              icon="delete_outline"
              onClick={() => setConfirm('delete')}
              className="assign-button"
            >
              Delete
            </ActionButton>
          )}
          {live && (
            <ActionButton
              icon="person_off_outlined"
              disabled={dirty}
              title={unsavedTitle}
              onClick={() => setConfirm('disable')}
              className="assign-button"
            >
              Disable
            </ActionButton>
          )}
          {dirty && (
            <ActionButton icon="replay_outlined" onClick={discard} className="assign-button">
              Discard
            </ActionButton>
          )}
          {live ? (
            <ActionButton
              variant="filled"
              icon="save_outlined"
              disabled={!dirty}
              onClick={save}
              className="assign-button assign-primary"
            >
              Save &amp; apply
            </ActionButton>
          ) : (
            <>
              <ActionButton
                icon="save_outlined"
                disabled={!dirty}
                onClick={save}
                className="assign-button"
              >
                {busy === 'save' ? 'Saving…' : saved.status === 'draft' ? 'Save draft' : 'Save'}
              </ActionButton>
              <ActionButton
                variant="filled"
                icon="send_outlined"
                disabled={stepTotal === 0}
                onClick={askPublish}
                className="assign-button assign-primary"
              >
                {saved.status === 'disabled' ? 'Re-publish' : 'Publish & assign'}
              </ActionButton>
            </>
          )}
        </div>
      </header>
      {error != null && (
        <div className="mb-4">
          <Notice text={error} isError onDismiss={() => setError(null)} />
        </div>
      )}
      {saved.warnings.length > 0 && (
        <div className="mb-4">
          <Notice text={saved.warnings.join(' ')} isError={false} />
        </div>
      )}
      {saved.status === 'disabled' && (
        <div className="mb-4">
          <Notice
            text="This journey is disabled. Employees no longer see it, and courses only it gave them were removed. Re-publish to restore it."
            isError={false}
          />
        </div>
      )}
      <div className="assign-grid">
        <div className="assign-column">
          <Section title="Details" icon="edit_outlined">
            <Details draft={draft} others={others} update={update} />
          </Section>
          <Section title="Courses" icon="format_list_numbered">
            <JourneyCourses
              stages={draft.stages}
              options={courseOptions.data ?? []}
              mode={mode}
              onModeChange={setMode}
              onChange={(stages) => update({ stages })}
            />
          </Section>
        </div>
        <div className="assign-column">
          <Section
            title="Who gets it"
            icon="people_outline"
            description={
              live
                ? 'Save & apply gives the journey to anyone new who matches. People keep it once they have it.'
                : 'Applies when you publish. People keep the journey once they have it.'
            }
          >
            <JourneyAudience
              rule={draft.rule}
              options={options.data ?? EMPTY_OPTIONS}
              savedGroups={savedGroups.data ?? []}
              preview={{
                pending: preview.isPending,
                error: preview.isError ? preview.error : null,
                matchCount: preview.data?.matchCount ?? 0,
                employees: preview.data?.employees ?? [],
              }}
              onChange={(rule) => update({ rule })}
            />
          </Section>
          <Section
            title="Journey observers"
            icon="visibility_outlined"
            description="Observers follow every course in this journey for the people they watch, in their Performance view. They are never enrolled in this journey. Saved with the journey."
          >
            <JourneyObservers
              value={observers}
              onChange={setObservers}
              employees={(options.data ?? EMPTY_OPTIONS).employees}
            />
          </Section>
          {saved.status !== 'draft' && (
            <Section
              title="Learner progress"
              icon="analytics_outlined"
              description="Where each learner is, deadlines, recent activity and certificates are in Performance, under Journeys, beside your course results."
            >
              <ActionButton icon="analytics_outlined" onClick={viewPerformance}>
                View in Performance
              </ActionButton>
            </Section>
          )}
        </div>
      </div>
      <LearnerPreview
        open={previewing}
        onOpenChange={setPreviewing}
        journey={draft}
        prerequisiteTitle={prerequisiteTitle}
      />
      <Dialog
        open={confirm != null}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={
          confirm === 'publish'
            ? saved.status === 'disabled'
              ? 'Re-publish this learning journey?'
              : 'Publish this learning journey?'
            : confirm === 'disable'
              ? 'Disable this learning journey?'
              : confirm === 'remove'
                ? 'Remove courses learners already have?'
                : 'Delete this draft?'
        }
        actions={
          <>
            <ActionButton variant="text" onClick={() => setConfirm(null)}>
              Cancel
            </ActionButton>
            <ActionButton
              variant="filled"
              onClick={() => {
                const action = confirm
                setConfirm(null)
                if (action === 'publish') void publish()
                else if (action === 'disable') void disable()
                else if (action === 'remove') void applySave()
                else if (action === 'delete') void remove()
              }}
            >
              {confirm === 'publish'
                ? saved.status === 'disabled'
                  ? 'Re-publish'
                  : 'Publish'
                : confirm === 'disable'
                  ? 'Disable'
                  : confirm === 'remove'
                    ? 'Save & apply'
                    : 'Delete'}
            </ActionButton>
          </>
        }
      >
        {confirm === 'publish' ? (
          <>
            {matchText} and will receive it. {publishSummary(draft.stages)} Ready courses in this
            journey become visible to those learners.
            {dirty && ' Your unsaved changes are saved first.'}
          </>
        ) : confirm === 'disable' ? (
          'Employees stop seeing this journey. Courses they received only through it are removed; their completed results are kept.'
        ) : confirm === 'remove' ? (
          <>
            <ul className="mb-3 list-disc pl-5">
              {removed.map((course) => (
                <li key={course.courseId}>
                  <b>{course.courseName}</b>: {course.learnerCount} learner
                  {course.learnerCount === 1 ? ' has' : 's have'} it.{' '}
                  {course.startedCount > 0 &&
                    `${course.startedCount} started or finished it and keep${course.startedCount === 1 ? 's' : ''} it. `}
                  {course.learnerCount - course.startedCount > 0 &&
                    `${course.learnerCount - course.startedCount} who ${course.learnerCount - course.startedCount === 1 ? 'has' : 'have'} not started lose${course.learnerCount - course.startedCount === 1 ? 's' : ''} it.`}
                </li>
              ))}
            </ul>
            Someone who also has the course from another journey or its own assignment keeps it. The
            course stays in your Courses library, and completed results are always kept.
          </>
        ) : (
          'This draft and its courses list are removed. Your courses are not affected.'
        )}
      </Dialog>
      {busy != null && overlayText[busy] && (
        <div
          role="status"
          aria-live="polite"
          className="fixed inset-0 z-50 flex items-center justify-center bg-white/70"
        >
          <div className="flex items-center gap-3 rounded-xl bg-white px-6 py-4 shadow-[0_8px_32px_#1d3d6426]">
            <Spinner label={overlayText[busy]} />
            <span className="text-sm font-medium text-[#19273e]">{overlayText[busy]}</span>
          </div>
        </div>
      )}
    </div>
  )
}

function Section({
  title,
  icon,
  description,
  children,
}: {
  title: string
  icon: IconName
  description?: string
  children: ReactNode
}) {
  return (
    <section aria-label={title} className="assign-panel">
      <header className="assign-panel-head">
        <span className="assign-panel-icon">
          <Icon name={icon} size={18} />
        </span>
        <div className="min-w-0">
          <h3>{title}</h3>
          {description && <p>{description}</p>}
        </div>
      </header>
      {children}
    </section>
  )
}

const fieldClass =
  'mt-1 w-full rounded-lg border border-input-border bg-white px-3 py-2 text-sm text-[#19273e] focus-visible:outline-2 focus-visible:outline-brand-blue-light'

function Details({
  draft,
  others,
  update,
}: {
  draft: JourneyDetail
  others: JourneySummary[]
  update: (patch: Partial<JourneyDetail>) => void
}) {
  return (
    <div className="flex flex-col gap-3">
      <label className="block text-xs font-semibold text-[#5b6980]">
        Journey name
        <input
          className={fieldClass}
          value={draft.title}
          maxLength={200}
          onChange={(event) => update({ title: event.target.value })}
        />
      </label>
      <label className="block text-xs font-semibold text-[#5b6980]">
        Description
        <textarea
          className={clsx(fieldClass, 'min-h-[72px]')}
          value={draft.description}
          maxLength={2000}
          placeholder="What learners will be able to do after this journey"
          onChange={(event) => update({ description: event.target.value })}
        />
      </label>
      <label className="block text-xs font-semibold text-[#5b6980]">
        Starts after
        <select
          className={fieldClass}
          value={draft.prerequisiteJourneyId ?? ''}
          onChange={(event) => update({ prerequisiteJourneyId: event.target.value || null })}
        >
          <option value="">No earlier journey</option>
          {others.map((journey) => (
            <option key={journey.journeyId} value={journey.journeyId}>
              {journey.title}
              {journey.status === 'published' ? '' : ` (${statusChip[journey.status].label})`}
            </option>
          ))}
        </select>
        <span className="mt-1 block font-normal">
          Only people who also have that journey wait for it.
        </span>
      </label>
      <label className="assign-switch-row">
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-[#19273e]">
            Certificate on completion
          </span>
          <span className="block text-xs text-[#5b6980]">
            Learners download a PDF certificate from PhillipCapital India Pvt Ltd.
          </span>
        </span>
        <Switch
          checked={draft.certificateEnabled}
          label="Certificate on completion"
          onChange={(certificateEnabled) => update({ certificateEnabled })}
        />
      </label>
    </div>
  )
}
