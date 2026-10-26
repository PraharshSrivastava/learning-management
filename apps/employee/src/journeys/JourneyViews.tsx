// Learner views of Learning Journeys: dashboard cards, the journeys page and its roadmap,
// and the slim bar shown above a journey course in the existing course player.
import type { EmployeeCourse } from '@lms/shared/models'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import { ProgressBar } from '@lms/shared/ui/ProgressBar'
import { Spinner } from '@lms/shared/ui/Spinner'
import clsx from 'clsx'
import { PageFrame } from '../dashboard/PageFrame'
import { dueDateLabel } from '../dashboard/progress'
import { journeyProgress, type LearnerJourney, type LearnerStep, type StepState } from './api'

const statusChips: Record<LearnerJourney['status'], { label: string; color: string }> = {
  waiting: { label: 'Waiting', color: '#667085' },
  pending: { label: 'Not started', color: '#00317a' },
  started: { label: 'In progress', color: '#087e8b' },
  overdue: { label: 'Overdue', color: '#d92d20' },
  completed: { label: 'Completed', color: '#00a878' },
}

const stepLooks: Record<StepState, { icon: IconName; color: string; label: string }> = {
  passed: { icon: 'check_circle', color: '#00a878', label: 'Passed' },
  in_progress: { icon: 'play_circle_outline', color: '#087e8b', label: 'In progress' },
  available: { icon: 'play_circle_outline', color: '#00317a', label: 'Ready to start' },
  locked: { icon: 'lock_outline', color: '#8b94a3', label: 'Locked' },
  unavailable: { icon: 'remove_circle_outline', color: '#8b94a3', label: 'Not available' },
}

function Chip({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="inline-flex items-center rounded-2xl px-2 py-[5px] text-[11px] leading-[1.5] font-bold"
      style={{ color, backgroundColor: `${color}1c` }}
    >
      {label}
    </span>
  )
}

const stepName = (journey: LearnerJourney, courseId: string | null) =>
  journey.stages.flatMap((stage) => stage.steps).find((step) => step.courseId === courseId)
    ?.courseName

export function JourneyCard({
  journey,
  onOpenJourney,
  onOpenCourse,
}: {
  journey: LearnerJourney
  onOpenJourney: () => void
  onOpenCourse: (courseId: string) => void
}) {
  const status = statusChips[journey.status]
  const nextCourseId = journey.status === 'completed' ? null : journey.nextCourseId
  const next = stepName(journey, journey.nextCourseId)
  const progress = journeyProgress(journey)
  return (
    <article className="flex flex-col gap-2.5 rounded-2xl border border-light-gray bg-white p-[18px]">
      <div className="flex flex-wrap gap-1.5">
        <Chip {...status} />
        {journey.deadline && journey.status !== 'completed' && (
          <Chip label={`Due ${dueDateLabel(journey.deadline)}`} color="#8a5a00" />
        )}
        {journey.prerequisite && !journey.prerequisite.met && (
          <Chip label={`After ${journey.prerequisite.title}`} color="#667085" />
        )}
      </div>
      <h3 className="m-0 font-barlow text-[19px] leading-tight font-bold text-[#101828]">
        {journey.title}
      </h3>
      {journey.description && (
        <p className="m-0 line-clamp-2 text-[13px] leading-[1.4] text-[#667085]">
          {journey.description}
        </p>
      )}
      <div className="flex items-center text-[12px]">
        <span className="flex-1 text-[#667085]">
          {journey.passedCount} of {journey.requiredCount} courses passed
        </span>
        <span className="font-bold text-primary-blue">{Math.round(progress * 100)}%</span>
      </div>
      <ProgressBar
        value={progress}
        height={5}
        radius={3}
        color={journey.status === 'completed' ? '#00a878' : undefined}
        label={`${journey.title} progress`}
      />
      <div className="rounded-[10px] bg-[#f7f9fc] px-3 py-2.5 text-[12px] text-[#667085]">
        {journey.status === 'completed' ? (
          <b className="block text-[13px] text-[#101828]">
            All courses passed{journey.certificateEnabled ? ' · Certificate earned' : ''}
          </b>
        ) : journey.status === 'waiting' ? (
          <b className="block text-[13px] text-[#101828]">
            Opens after {journey.prerequisite?.title ?? 'the earlier journey'}
          </b>
        ) : next ? (
          <>
            Up next
            <b className="block text-[13px] text-[#101828]">{next}</b>
          </>
        ) : (
          <b className="block text-[13px] text-[#101828]">No course is open right now</b>
        )}
      </div>
      <div className="mt-1 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onOpenJourney}
          className="inline-flex h-9 items-center justify-center rounded-full bg-primary-blue px-4 text-[14px] font-bold text-white hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light"
        >
          View journey
        </button>
        {nextCourseId != null && (
          <button
            type="button"
            onClick={() => onOpenCourse(nextCourseId)}
            aria-label={`Continue ${next ?? 'course'}`}
            className="inline-flex h-9 items-center justify-center rounded-full border border-light-gray px-4 text-[14px] font-bold text-primary-blue hover:bg-brand-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light"
          >
            Continue course
          </button>
        )}
      </div>
    </article>
  )
}

/** Dashboard section above the metric tiles. Renders nothing without journeys. */
export function JourneyStrip({
  journeys,
  onOpenJourney,
  onOpenCourse,
  onSeeAll,
}: {
  journeys: LearnerJourney[]
  onOpenJourney: (journeyId: string) => void
  onOpenCourse: (courseId: string) => void
  onSeeAll: () => void
}) {
  if (journeys.length === 0) return null
  return (
    <section aria-label="Your learning journeys" className="mb-8">
      <div className="mb-3 flex items-end justify-between gap-3">
        <h2 className="m-0 text-[18px] font-bold text-[#101828]">Your learning journeys</h2>
        <button
          type="button"
          onClick={onSeeAll}
          className="text-[13px] font-semibold text-primary-blue"
        >
          See all
        </button>
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
        {journeys.map((journey) => (
          <JourneyCard
            key={journey.journeyId}
            journey={journey}
            onOpenJourney={() => onOpenJourney(journey.journeyId)}
            onOpenCourse={onOpenCourse}
          />
        ))}
      </div>
    </section>
  )
}

export function LearningJourneysPage({
  journeys,
  isLoading,
  error,
  openJourneyId,
  onOpenJourney,
  onOpenCourse,
}: {
  journeys: LearnerJourney[]
  isLoading: boolean
  error: string | null
  openJourneyId: string | null
  onOpenJourney: (journeyId: string | null) => void
  onOpenCourse: (courseId: string) => void
}) {
  const open = journeys.find((journey) => journey.journeyId === openJourneyId) ?? null
  if (open)
    return <Roadmap journey={open} onBack={() => onOpenJourney(null)} onOpenCourse={onOpenCourse} />
  return (
    <PageFrame
      title="Learning journeys"
      subtitle="Step-by-step learning paths. Each step is a course; the next one opens when you pass the one before it."
    >
      {isLoading && journeys.length === 0 ? (
        <div className="flex justify-center py-16">
          <Spinner label="Loading your journeys" />
        </div>
      ) : error != null && journeys.length === 0 ? (
        <p className="text-[#d92d20]">{error}</p>
      ) : journeys.length === 0 ? (
        <p className="text-[#667085]">No learning journeys are assigned to you yet.</p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
          {journeys.map((journey) => (
            <JourneyCard
              key={journey.journeyId}
              journey={journey}
              onOpenJourney={() => onOpenJourney(journey.journeyId)}
              onOpenCourse={onOpenCourse}
            />
          ))}
        </div>
      )}
    </PageFrame>
  )
}

function Roadmap({
  journey,
  onBack,
  onOpenCourse,
}: {
  journey: LearnerJourney
  onBack: () => void
  onOpenCourse: (courseId: string) => void
}) {
  const progress = journeyProgress(journey)
  return (
    <div className="h-full overflow-y-auto p-6 [scrollbar-width:none]">
      <div className="mx-auto max-w-[1100px]">
        <button
          type="button"
          onClick={onBack}
          className="mb-4 inline-flex items-center gap-1 text-[13px] font-semibold text-primary-blue"
        >
          <Icon name="arrow_back" size={16} /> Learning journeys
        </button>
        <section className="mb-6 flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-light-gray bg-white p-5">
          <div className="min-w-0 flex-1">
            <h1 className="m-0 text-[28px] font-bold text-[#101828]">{journey.title}</h1>
            {journey.description && (
              <p className="m-0 mt-1.5 text-[14px] text-[#667085]">{journey.description}</p>
            )}
          </div>
          <div className="w-full max-w-[260px]">
            <div className="mb-1.5 flex justify-between text-[13px]">
              <b>{Math.round(progress * 100)}% complete</b>
              <span className="text-[#667085]">{journey.stepCount} courses</span>
            </div>
            <ProgressBar
              value={progress}
              height={6}
              radius={3}
              label={`${journey.title} progress`}
            />
          </div>
        </section>
        {journey.status === 'waiting' && (
          <p className="mb-5 rounded-xl bg-[#fff7e8] p-3 text-[13px] text-[#704a00]">
            This journey opens when you complete{' '}
            {journey.prerequisite?.title ?? 'the earlier journey'}.
          </p>
        )}
        <ol className="m-0 list-none p-0">
          {journey.stages.map((stage, index) => {
            const done =
              stage.steps.length > 0 &&
              stage.steps.every((s) => s.state === 'passed' || s.state === 'unavailable')
            const live =
              !done && stage.steps.some((s) => s.state === 'available' || s.state === 'in_progress')
            return (
              <li key={index} className="grid grid-cols-[40px_1fr] gap-3.5">
                <div className="flex flex-col items-center">
                  <span
                    className={clsx(
                      'flex size-[34px] shrink-0 items-center justify-center rounded-full border-2 font-bold',
                      done
                        ? 'border-[#00a878] bg-[#00a878] text-white'
                        : live
                          ? 'border-primary-blue bg-primary-blue text-white'
                          : 'border-light-gray bg-white text-[#667085]',
                    )}
                  >
                    {done ? <Icon name="check" size={18} /> : index + 1}
                  </span>
                  {index < journey.stages.length - 1 && (
                    <span className="my-1 w-0.5 flex-1 bg-light-gray" />
                  )}
                </div>
                <div className="flex min-w-0 flex-col gap-2.5 pb-6">
                  <div>
                    <p className="m-0 text-[11px] font-bold tracking-[0.08em] text-[#667085] uppercase">
                      Stage {index + 1}
                    </p>
                    <h2 className="m-0 text-[17px] font-bold text-[#101828]">{stage.title}</h2>
                  </div>
                  {stage.steps.map((step) => (
                    <StepRow
                      key={step.courseId}
                      step={step}
                      onOpen={() => onOpenCourse(step.courseId)}
                    />
                  ))}
                </div>
              </li>
            )
          })}
        </ol>
        {journey.certificateEnabled && (
          <p className="mt-2 flex items-center gap-2 rounded-xl border border-dashed border-light-gray p-4 text-[13px] text-[#667085]">
            <Icon name="verified_outlined" size={20} color="#d59a00" />
            {journey.status === 'completed'
              ? 'Certificate earned. You passed every required course in this journey.'
              : 'A certificate is shown when every required course in this journey is passed.'}
          </p>
        )}
      </div>
    </div>
  )
}

function StepRow({ step, onOpen }: { step: LearnerStep; onOpen: () => void }) {
  const look = stepLooks[step.state]
  const openable =
    step.state === 'passed' || step.state === 'available' || step.state === 'in_progress'
  const detail =
    step.state === 'locked'
      ? step.lockedByCourseName
        ? `Opens after you pass ${step.lockedByCourseName}`
        : 'Opens later in this journey'
      : step.state === 'unavailable'
        ? 'This course is not available right now'
        : `${step.moduleCount} module${step.moduleCount === 1 ? '' : 's'}${step.isRequired ? '' : ' · Optional'}`
  const body = (
    <>
      <Icon name={look.icon} size={26} color={look.color} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] font-bold text-[#101828]">
          {step.stepNumber}. {step.courseName}
        </span>
        <span className="block text-[12px] text-[#667085]">{detail}</span>
      </span>
      <Chip label={look.label} color={look.color} />
    </>
  )
  if (!openable) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-dashed border-light-gray bg-[#f7f9fc] p-3">
        {body}
      </div>
    )
  }
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`${step.state === 'passed' ? 'Review' : 'Open'} ${step.courseName}`}
      className="flex w-full items-center gap-3 rounded-xl border border-light-gray bg-white p-3 text-left hover:border-brand-blue-light focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light"
    >
      {body}
    </button>
  )
}

/** Slim bar above a journey course in the existing course player. */
export function JourneyBar({
  course,
  journeys,
  onOpenJourney,
}: {
  course: EmployeeCourse
  journeys: LearnerJourney[]
  onOpenJourney: (journeyId: string) => void
}) {
  const place = course.journeys[0]
  if (!place) return null
  const journey = journeys.find((item) => item.journeyId === place.journeyId)
  const steps = journey?.stages.flatMap((stage) => stage.steps) ?? []
  const next = steps.find((step) => step.stepNumber === place.step + 1)
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-[#d0dbf4] bg-brand-blue-100 px-5 py-2.5 text-[13px] text-[#101828]">
      <Icon name="track_changes" size={18} color="var(--color-primary-blue)" />
      <span className="min-w-0 flex-1">
        <b>{place.title}</b> · Step {place.step} of {place.stepCount}
        {next && (
          <span className="text-[#667085]">
            {' '}
            · Next: {next.courseName}
            {next.state === 'locked' ? ' (opens when you pass this course)' : ''}
          </span>
        )}
      </span>
      <button
        type="button"
        onClick={() => onOpenJourney(place.journeyId)}
        className="font-semibold text-primary-blue"
      >
        Back to journey
      </button>
    </div>
  )
}
