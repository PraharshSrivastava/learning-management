// Trainer Journeys tab: build a Learning Journey from existing courses, choose who gets it,
// publish it and follow progress. Laid out like the Assign desk and reusing its controls.
import { errorMessage } from '@lms/shared/api/client'
import { useSession } from '@lms/shared/auth/session'
import {
  emptyAssignmentGroup,
  type AssignmentOptions,
  type SavedAssignmentGroup,
} from '@lms/shared/models'
import { Dialog } from '@lms/shared/ui/Dialog'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import { Spinner } from '@lms/shared/ui/Spinner'
import { useToast } from '@lms/shared/ui/Toast'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState, type ReactNode } from 'react'
import type { Trainer } from '../../auth/trainer'
import { trainerKeys } from '../../shell/queryKeys'
import { useTrainerSearch, useUpdateTrainerSearch } from '../../shell/search'
import { ActionButton, ChoiceChip, Notice, Switch } from '../assignments/controls'
import { todayInKolkata } from '../assignments/dates'
import { GroupList, OutlinedNumberField } from '../assignments/groups'
import '../assignments/AssignStyles.css'
import {
  createJourney,
  deleteJourney,
  disableJourney,
  fetchAssignmentOptions,
  fetchCourseOptions,
  fetchJourney,
  fetchJourneys,
  fetchPreview,
  fetchProgress,
  fetchSavedGroups,
  publishJourney,
  saveJourney,
  type CourseOption,
  type JourneyDetail,
  type JourneyStage,
  type JourneyStatus,
  type JourneySummary,
  type ProgressRow,
} from './api'
import { moveStep } from './editing'
import { JourneyObservers } from './JourneyObservers'

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
  const [creating, setCreating] = useState(false)

  const create = async () => {
    setCreating(true)
    try {
      const created = await createJourney('Untitled journey')
      await queryClient.invalidateQueries({ queryKey: trainerKeys.journeys })
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
                disabled={creating}
                onClick={() => void create()}
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
                            <span className="ml-auto">
                              {journey.courseCount} course{journey.courseCount === 1 ? '' : 's'}
                            </span>
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
            <JourneyLoader key={selected.journeyId} summary={selected} others={journeys} />
          )}
        </main>
      </div>
    </div>
  )
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

function JourneyLoader({ summary, others }: { summary: JourneySummary; others: JourneySummary[] }) {
  const detail = useQuery({
    queryKey: [...trainerKeys.journeys, 'detail', summary.journeyId],
    queryFn: () => fetchJourney(summary.journeyId),
  })
  if (detail.isPending) {
    return (
      <div className="flex items-center justify-center p-12">
        <Spinner label="Loading journey" />
      </div>
    )
  }
  if (detail.isError) return <Notice text={errorMessage(detail.error)} isError />
  return (
    <JourneyEditor
      key={`${detail.data.journeyId}:${detail.data.updatedAt}`}
      saved={detail.data}
      others={others.filter((j) => j.journeyId !== summary.journeyId)}
    />
  )
}

function JourneyEditor({ saved, others }: { saved: JourneyDetail; others: JourneySummary[] }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const updateSearch = useUpdateTrainerSearch()
  const [draft, setDraft] = useState<JourneyDetail>(saved)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<'publish' | 'disable' | 'delete' | null>(null)
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved)
  const courseOptions = useQuery({
    queryKey: [...trainerKeys.journeys, 'course-options'],
    queryFn: fetchCourseOptions,
  })
  const options = useQuery({ queryKey: ['assignment', 'options'], queryFn: fetchAssignmentOptions })
  const savedGroups = useQuery({
    queryKey: ['assignment', 'saved-groups'],
    queryFn: fetchSavedGroups,
  })

  const refresh = async (detail?: JourneyDetail) => {
    if (detail)
      queryClient.setQueryData([...trainerKeys.journeys, 'detail', detail.journeyId], detail)
    await queryClient.invalidateQueries({ queryKey: trainerKeys.journeys })
    void queryClient.invalidateQueries({ queryKey: trainerKeys.courses })
    void queryClient.invalidateQueries({ queryKey: trainerKeys.assignableCourses })
  }

  const run = async (label: string, action: () => Promise<void>) => {
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

  const save = () =>
    run('save', async () => {
      const next = await saveJourney(draft)
      await refresh(next)
      toast('Learning journey saved.')
    })

  const publish = () =>
    run('publish', async () => {
      if (dirty) await saveJourney(draft)
      const { detail, newlyAssigned } = await publishJourney(draft.journeyId)
      await refresh(detail)
      toast(
        newlyAssigned > 0
          ? `Published. ${newlyAssigned} employee${newlyAssigned === 1 ? '' : 's'} received this journey.`
          : 'Published. Everyone who matches already has this journey.',
        { tone: 'success' },
      )
    })

  const disable = () =>
    run('disable', async () => {
      await refresh(await disableJourney(draft.journeyId))
      toast('Learning journey disabled for employees.')
    })

  const remove = () =>
    run('delete', async () => {
      await deleteJourney(draft.journeyId)
      updateSearch({ journey: undefined })
      await refresh()
      toast('Learning journey deleted.')
    })

  const update = (patch: Partial<JourneyDetail>) =>
    setDraft((current) => ({ ...current, ...patch }))
  const setStages = (stages: JourneyStage[]) => update({ stages })
  const usedCourses = new Set(
    draft.stages.flatMap((stage) => stage.steps.map((step) => step.courseId)),
  )
  const stepTotal = usedCourses.size
  const canDelete = saved.publishedAt == null && saved.status === 'draft'

  return (
    <div className="assign-workspace" inert={busy != null} aria-busy={busy != null}>
      <header className="assign-heading">
        <div className="min-w-0 flex-1">
          <p className="assign-kicker">Learning journey</p>
          <h2 className="assign-title">{saved.title}</h2>
          <p className="assign-meta">
            <StatusChip status={saved.status} />
            <span>
              {saved.courseCount} course{saved.courseCount === 1 ? '' : 's'}
            </span>
            {saved.status !== 'draft' && <span>{saved.assignedCount} assigned</span>}
          </p>
        </div>
        <div className="assign-actions" role="toolbar" aria-label="Journey actions">
          {canDelete && (
            <ActionButton
              icon="delete_outline"
              onClick={() => setConfirm('delete')}
              className="assign-button"
            >
              Delete
            </ActionButton>
          )}
          {saved.status === 'published' && (
            <ActionButton
              icon="person_off_outlined"
              onClick={() => setConfirm('disable')}
              className="assign-button"
            >
              Disable
            </ActionButton>
          )}
          <ActionButton
            icon="save_outlined"
            disabled={!dirty}
            onClick={() => void save()}
            className="assign-button"
          >
            {busy === 'save' ? 'Saving…' : 'Save'}
          </ActionButton>
          <ActionButton
            variant="filled"
            icon="send_outlined"
            disabled={stepTotal === 0}
            onClick={() => setConfirm('publish')}
            className="assign-button assign-primary"
          >
            {busy === 'publish'
              ? 'Publishing…'
              : saved.status === 'published'
                ? 'Publish changes'
                : 'Publish & Assign'}
          </ActionButton>
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
            text="This journey is disabled. Employees no longer see it, and courses only it gave them were removed. Publish again to restore it."
            isError={false}
          />
        </div>
      )}
      <div className="assign-grid">
        <div className="assign-column">
          <Section title="Details" icon="edit_outlined">
            <Details draft={draft} others={others} update={update} />
          </Section>
          <Section
            title="Stages and courses"
            icon="format_list_numbered"
            description="Courses open in this order. An open course can be taken at any time."
          >
            <Stages
              stages={draft.stages}
              options={courseOptions.data ?? []}
              usedCourses={usedCourses}
              onChange={setStages}
            />
          </Section>
        </div>
        <div className="assign-column">
          <Section
            title="Who gets it"
            icon="people_outline"
            description="Applies when you publish. People keep the journey once they have it."
          >
            <WhoGetsIt
              draft={draft}
              options={options.data ?? EMPTY_OPTIONS}
              savedGroups={savedGroups.data ?? []}
              update={update}
            />
          </Section>
          <Section
            title="Journey observers"
            icon="visibility_outlined"
            description="Observers follow every course in this journey for the people they watch, in their Performance view. They are never enrolled in this journey."
          >
            <JourneyObservers
              journeyId={saved.journeyId}
              employees={(options.data ?? EMPTY_OPTIONS).employees}
            />
          </Section>
          <Section title="What employees will see" icon="school_outlined">
            <EmployeeView draft={draft} />
            <MatchPreview journeyId={saved.journeyId} rule={saved.rule} dirty={dirty} />
          </Section>
          {saved.status !== 'draft' && (
            <Section
              title="Progress"
              icon="analytics_outlined"
              description="Everyone who has this journey."
            >
              <Progress journeyId={saved.journeyId} version={saved.updatedAt} />
            </Section>
          )}
        </div>
      </div>
      <Dialog
        open={confirm != null}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={
          confirm === 'publish'
            ? 'Publish this learning journey?'
            : confirm === 'disable'
              ? 'Disable this learning journey?'
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
                else if (action === 'delete') void remove()
              }}
            >
              {confirm === 'publish' ? 'Publish' : confirm === 'disable' ? 'Disable' : 'Delete'}
            </ActionButton>
          </>
        }
      >
        {confirm === 'publish'
          ? 'Matching employees receive the journey. Only the first course is assigned now; each next course is assigned when the one before it is passed. Ready courses in this journey become visible to those learners.'
          : confirm === 'disable'
            ? 'Employees stop seeing this journey. Courses they received only through it are removed; their completed results are kept.'
            : 'This draft and its stages are removed. Your courses are not affected.'}
      </Dialog>
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
        Target audience
        <input
          className={fieldClass}
          value={draft.targetAudience}
          maxLength={200}
          placeholder="For example: all employees"
          onChange={(event) => update({ targetAudience: event.target.value })}
        />
      </label>
      <label className="block text-xs font-semibold text-[#5b6980]">
        Description
        <textarea
          className={clsx(fieldClass, 'min-h-[72px]')}
          value={draft.description}
          maxLength={2000}
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
            </option>
          ))}
        </select>
        <span className="mt-1 block font-normal">
          Only people who also have that journey wait for it.
        </span>
      </label>
      <label className="assign-switch-row">
        <span className="min-w-0 flex-1 text-sm font-medium text-[#19273e]">
          Show a certificate on completion
        </span>
        <Switch
          checked={draft.certificateEnabled}
          label="Show a certificate on completion"
          onChange={(certificateEnabled) => update({ certificateEnabled })}
        />
      </label>
    </div>
  )
}

function Stages({
  stages,
  options,
  usedCourses,
  onChange,
}: {
  stages: JourneyStage[]
  options: CourseOption[]
  usedCourses: Set<string>
  onChange: (stages: JourneyStage[]) => void
}) {
  const [picking, setPicking] = useState<number | null>(null)
  const [pick, setPick] = useState('')
  const available = options.filter((option) => option.eligible && !usedCourses.has(option.courseId))
  const unavailable = options.filter(
    (option) => !option.eligible && !usedCourses.has(option.courseId),
  )
  const total = stages.reduce((sum, stage) => sum + stage.steps.length, 0)
  // Step numbers run across the whole journey: the first step of a stage follows the last of the one before.
  const firstNumber = stages.map((_, index) =>
    stages.slice(0, index).reduce((sum, stage) => sum + stage.steps.length, 1),
  )

  const setStage = (index: number, stage: JourneyStage) =>
    onChange(stages.map((item, i) => (i === index ? stage : item)))

  return (
    <div className="flex flex-col gap-3">
      {stages.map((stage, stageIndex) => (
        <div key={stageIndex} className="rounded-xl border border-[#e6e9ef] bg-[#f7f9fc] p-3">
          <div className="flex items-center gap-2">
            <input
              aria-label={`Stage ${stageIndex + 1} name`}
              className={clsx(fieldClass, 'mt-0 font-semibold')}
              value={stage.title}
              maxLength={200}
              onChange={(event) => setStage(stageIndex, { ...stage, title: event.target.value })}
            />
            <ActionButton
              variant="text"
              icon="delete_outline"
              aria-label={`Remove stage ${stageIndex + 1}`}
              disabled={stages.length < 2}
              onClick={() => onChange(stages.filter((_, i) => i !== stageIndex))}
            />
          </div>
          <ol className="mt-2 flex list-none flex-col gap-2 p-0">
            {stage.steps.map((step, stepIndex) => {
              const position = (firstNumber[stageIndex] ?? 1) + stepIndex
              return (
                <li
                  key={step.courseId}
                  className="flex flex-col gap-2 rounded-lg border border-[#e6e9ef] bg-white p-2.5"
                >
                  {/* Name on its own row, so narrow columns never squash the course title. */}
                  <div className="flex items-center gap-2">
                    <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-blue-100 text-xs font-bold text-primary-blue">
                      {position}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-[#19273e]">
                        {step.courseName}
                      </span>
                      <span
                        className={clsx(
                          'block text-xs',
                          step.eligible ? 'text-[#5b6980]' : 'text-accent-red',
                        )}
                      >
                        {step.eligible
                          ? `${step.moduleCount} module${step.moduleCount === 1 ? '' : 's'}`
                          : (step.reason ?? 'Not available')}
                      </span>
                    </span>
                    <ActionButton
                      variant="text"
                      icon="close"
                      aria-label={`Remove ${step.courseName}`}
                      onClick={() =>
                        setStage(stageIndex, {
                          ...stage,
                          steps: stage.steps.filter((_, i) => i !== stepIndex),
                        })
                      }
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-2 pl-9">
                    <select
                      aria-label={`When ${step.courseName} opens`}
                      className="rounded-lg border border-input-border bg-white px-2 py-1.5 text-xs"
                      value={step.unlockRule}
                      onChange={(event) =>
                        setStage(stageIndex, {
                          ...stage,
                          steps: stage.steps.map((item, i) =>
                            i === stepIndex
                              ? {
                                  ...item,
                                  unlockRule:
                                    event.target.value === 'open' ? 'open' : 'after_previous',
                                }
                              : item,
                          ),
                        })
                      }
                    >
                      <option value="after_previous">After the previous course is passed</option>
                      <option value="open">Open from the start</option>
                    </select>
                    <label className="flex items-center gap-1.5 text-xs text-[#19273e]">
                      <input
                        type="checkbox"
                        checked={step.isRequired}
                        onChange={(event) =>
                          setStage(stageIndex, {
                            ...stage,
                            steps: stage.steps.map((item, i) =>
                              i === stepIndex
                                ? { ...item, isRequired: event.target.checked }
                                : item,
                            ),
                          })
                        }
                      />
                      Required
                    </label>
                    <ActionButton
                      variant="text"
                      icon="arrow_upward"
                      aria-label={`Move ${step.courseName} up`}
                      disabled={position === 1}
                      onClick={() => onChange(moveStep(stages, stageIndex, stepIndex, -1))}
                    />
                    <ActionButton
                      variant="text"
                      icon="arrow_downward"
                      aria-label={`Move ${step.courseName} down`}
                      disabled={position === total}
                      onClick={() => onChange(moveStep(stages, stageIndex, stepIndex, 1))}
                    />
                  </div>
                </li>
              )
            })}
          </ol>
          {picking === stageIndex ? (
            <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-brand-blue-light bg-white p-2.5">
              <select
                aria-label="Course to add"
                className="min-w-0 flex-1 rounded-lg border border-input-border bg-white px-2 py-1.5 text-sm"
                value={pick}
                onChange={(event) => setPick(event.target.value)}
              >
                <option value="">Choose a course</option>
                {available.map((option) => (
                  <option key={option.courseId} value={option.courseId}>
                    {option.courseName} ({option.moduleCount} modules)
                  </option>
                ))}
                {unavailable.map((option) => (
                  <option key={option.courseId} value={option.courseId} disabled>
                    {option.courseName}: {option.reason}
                  </option>
                ))}
              </select>
              <ActionButton
                variant="filled"
                disabled={!pick}
                onClick={() => {
                  const option = available.find((item) => item.courseId === pick)
                  if (!option) return
                  setStage(stageIndex, {
                    ...stage,
                    steps: [
                      ...stage.steps,
                      {
                        courseId: option.courseId,
                        courseName: option.courseName,
                        moduleCount: option.moduleCount,
                        unlockRule: 'after_previous',
                        isRequired: true,
                        eligible: true,
                        reason: null,
                      },
                    ],
                  })
                  setPick('')
                  setPicking(null)
                }}
              >
                Add
              </ActionButton>
              <ActionButton variant="text" onClick={() => setPicking(null)}>
                Cancel
              </ActionButton>
            </div>
          ) : (
            <ActionButton
              variant="text"
              icon="add"
              className="mt-1"
              onClick={() => {
                setPick('')
                setPicking(stageIndex)
              }}
            >
              Add existing course
            </ActionButton>
          )}
        </div>
      ))}
      <div>
        <ActionButton
          icon="add"
          onClick={() => onChange([...stages, { title: `Stage ${stages.length + 1}`, steps: [] }])}
        >
          Add stage
        </ActionButton>
      </div>
      {options.length > 0 && available.length === 0 && (
        <p className="text-xs text-[#5b6980]">
          All your eligible courses are in this journey. Only fully generated courses you created
          can be added.
        </p>
      )}
    </div>
  )
}

function WhoGetsIt({
  draft,
  options,
  savedGroups,
  update,
}: {
  draft: JourneyDetail
  options: AssignmentOptions
  savedGroups: SavedAssignmentGroup[]
  update: (patch: Partial<JourneyDetail>) => void
}) {
  const rule = draft.rule
  const setRule = (patch: Partial<JourneyDetail['rule']>) => update({ rule: { ...rule, ...patch } })
  return (
    <div className="flex flex-col gap-4">
      <label className="assign-switch-row">
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-[#19273e]">All active employees</span>
          <span className="block text-xs text-[#5b6980]">
            Start from everyone, then apply exclusions.
          </span>
        </span>
        <Switch
          checked={rule.includeAll}
          label="All active employees"
          onChange={(includeAll) =>
            setRule({
              includeAll,
              includeGroups:
                !includeAll && rule.includeGroups.length === 0
                  ? [emptyAssignmentGroup({ name: 'Group 1' })]
                  : rule.includeGroups,
            })
          }
        />
      </label>
      {!rule.includeAll && (
        <div>
          <p className="mb-2 text-xs font-semibold text-[#5b6980]">Include</p>
          <GroupList
            label="Include"
            pickerTitle="Add employee"
            groups={rule.includeGroups}
            savedGroups={savedGroups.filter((g) => g.groupType === 'include')}
            options={options}
            onChange={(includeGroups) => setRule({ includeGroups })}
          />
        </div>
      )}
      <div className="assign-subsection" role="group" aria-label="Exclusions">
        <p className="mb-2 text-xs font-semibold text-[#5b6980]">Exclude</p>
        <GroupList
          label="Exclude"
          pickerTitle="Exclude employee"
          allowJoinedFilter={false}
          groups={rule.excludeGroups}
          savedGroups={savedGroups.filter((g) => g.groupType === 'exclude')}
          options={options}
          onChange={(excludeGroups) => setRule({ excludeGroups })}
        />
      </div>
      <div>
        <p className="mb-2 text-xs font-semibold text-[#5b6980]">Deadline</p>
        <div className="flex flex-wrap gap-3">
          <ChoiceChip
            selected={rule.deadlineMode === 'relative'}
            onClick={() => setRule({ deadlineMode: 'relative' })}
          >
            Days after it opens
          </ChoiceChip>
          <ChoiceChip
            selected={rule.deadlineMode === 'fixed'}
            onClick={() => setRule({ deadlineMode: 'fixed' })}
          >
            Specific date
          </ChoiceChip>
        </div>
        <div className="mt-3">
          {rule.deadlineMode === 'relative' ? (
            <div className="w-[260px]">
              <OutlinedNumberField
                label="Days to finish the journey"
                value={rule.deadlineDays}
                onChange={(days) => setRule({ deadlineDays: Math.max(1, days ?? 1) })}
              />
            </div>
          ) : (
            <input
              type="date"
              aria-label="Journey deadline date"
              className="rounded-lg border border-input-border bg-white px-3 py-2 text-sm"
              min={todayInKolkata()}
              value={rule.deadlineDate ?? ''}
              onChange={(event) => setRule({ deadlineDate: event.target.value || null })}
            />
          )}
          <p className="pt-2 text-xs text-[#5b6980]">
            {rule.deadlineMode === 'relative'
              ? 'Counted from the day the journey opens for each person. Each course gets the journey deadline.'
              : 'Due by the end of this date (Asia/Kolkata). Each course gets the journey deadline.'}
          </p>
        </div>
      </div>
    </div>
  )
}

function EmployeeView({ draft }: { draft: JourneyDetail }) {
  const steps = draft.stages.flatMap((stage) => stage.steps)
  if (steps.length === 0)
    return <p className="text-sm text-[#5b6980]">Add courses to see the order.</p>
  return (
    <ol className="m-0 flex list-none flex-col gap-1.5 p-0">
      {steps.map((step, index) => {
        const open = index === 0 || step.unlockRule === 'open'
        return (
          <li key={step.courseId} className="flex items-center gap-2 text-sm text-[#19273e]">
            <Icon
              name={open ? 'play_circle_outline' : 'lock_outline'}
              size={18}
              color={open ? 'var(--color-primary-blue)' : 'var(--color-gray)'}
            />
            <span className="min-w-0 flex-1 truncate">{step.courseName}</span>
            {!step.isRequired && <span className="text-xs text-[#5b6980]">Optional</span>}
          </li>
        )
      })}
    </ol>
  )
}

function MatchPreview({
  journeyId,
  rule,
  dirty,
}: {
  journeyId: string
  rule: unknown
  dirty: boolean
}) {
  const preview = useQuery({
    queryKey: [...trainerKeys.journeys, 'preview', journeyId, JSON.stringify(rule)],
    queryFn: () => fetchPreview(journeyId),
  })
  return (
    <div className="mt-4 rounded-lg bg-[#f7f9fc] p-3 text-sm text-[#19273e]">
      {preview.isPending ? (
        <Spinner label="Counting employees" />
      ) : preview.isError ? (
        <span className="text-accent-red">{errorMessage(preview.error)}</span>
      ) : (
        <>
          <b>{preview.data.matchCount}</b> employee{preview.data.matchCount === 1 ? '' : 's'} match
          the saved rule{dirty ? ' (save to update)' : ''}.
          {preview.data.names.length > 0 && (
            <span className="mt-1 block text-xs text-[#5b6980]">
              {preview.data.names.join(', ')}
              {preview.data.matchCount > preview.data.names.length ? ' and others' : ''}
            </span>
          )}
        </>
      )}
    </div>
  )
}

const progressLabels: Record<string, { label: string; color: string }> = {
  waiting: { label: 'Waiting', color: '#667085' },
  pending: { label: 'Not started', color: '#00317a' },
  started: { label: 'In progress', color: '#087e8b' },
  overdue: { label: 'Overdue', color: '#d92d20' },
  completed: { label: 'Completed', color: '#00a878' },
}

function Progress({ journeyId, version }: { journeyId: string; version: string }) {
  const rows = useQuery({
    queryKey: [...trainerKeys.journeys, 'progress', journeyId, version],
    queryFn: () => fetchProgress(journeyId),
  })
  const [shown, setShown] = useState(20)
  if (rows.isPending) return <Spinner label="Loading progress" />
  if (rows.isError) return <Notice text={errorMessage(rows.error)} isError />
  if (rows.data.length === 0)
    return <p className="text-sm text-[#5b6980]">No one has this journey yet.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr className="text-[#5b6980]">
            <th className="py-2 pr-3 font-semibold">Employee</th>
            <th className="py-2 pr-3 font-semibold">Current course</th>
            <th className="py-2 pr-3 font-semibold">Passed</th>
            <th className="py-2 font-semibold">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.data.slice(0, shown).map((row: ProgressRow) => {
            const status = progressLabels[row.status] ?? { label: row.status, color: '#667085' }
            return (
              <tr key={row.employeeId} className="border-t border-[#e6e9ef] text-[#19273e]">
                <td className="py-2 pr-3">
                  <span className="block font-semibold">{row.name}</span>
                  <span className="text-[#5b6980]">{row.department}</span>
                </td>
                <td className="py-2 pr-3">
                  {row.currentCourseName ? `${row.currentStep}. ${row.currentCourseName}` : '–'}
                </td>
                <td className="py-2 pr-3 tabular-nums">
                  {row.passedCount} of {row.requiredCount}
                </td>
                <td className="py-2" style={{ color: status.color }}>
                  {status.label}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {rows.data.length > shown && (
        <ActionButton variant="text" className="mt-2" onClick={() => setShown((n) => n + 50)}>
          Show more
        </ActionButton>
      )}
    </div>
  )
}
