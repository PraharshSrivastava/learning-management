// Dart: frontend/lib/features/performance/assignment_detail_dialog.dart:1-668 and the dialog route
// in performance_report_portal.dart:757-765 (_showAssignment).
import * as RadixDialog from '@radix-ui/react-dialog'
import { useRef, useState, type ReactNode } from 'react'
import { errorMessage } from '../api/client'
import {
  parseAssignmentDetailReport,
  type AssignmentModuleReport,
  type AssignmentReportRow,
  type QuizAttemptReport,
} from '../models/performance'
import { Button, IconButton } from '../ui/Button'
import { Icon, type IconName } from '../ui/icons/Icon'
import { ProgressBar } from '../ui/ProgressBar'
import { Spinner } from '../ui/Spinner'
import { AccessGuard } from './AccessGuard'
import { useReport, useReportQuery } from './context'
import { alpha, colors, dialogStatusColor, dialogStatusLabel, dmy, dmyHm, score } from './format'
import { useElementWidth } from './useElementWidth'
import { OVERLAY_LAYER, WINDOW_LAYER } from '../ui/layers'

/**
 * The assignment detail dialog. `assignmentId == null` means closed. The body mounts per
 * assignment, keeps the report context key from open time and sits inside AccessGuard, so the
 * request runs only while the context is unchanged.
 */
export function AssignmentDetailDialog({
  assignmentId,
  onClose,
}: {
  assignmentId: string | null
  onClose: () => void
}) {
  return (
    <RadixDialog.Root open={assignmentId != null} onOpenChange={(open) => !open && onClose()}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={`fixed inset-0 ${OVERLAY_LAYER} bg-black/54`} />
        {assignmentId != null && (
          <GuardedAssignment key={assignmentId} assignmentId={assignmentId} onClose={onClose} />
        )}
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}

function GuardedAssignment({
  assignmentId,
  onClose,
}: {
  assignmentId: string
  onClose: () => void
}) {
  const { contextKey } = useReport()
  const [expected] = useState(contextKey)
  return (
    <AccessGuard expected={expected} onClose={onClose}>
      <AssignmentDialogContent assignmentId={assignmentId} onClose={onClose} />
    </AccessGuard>
  )
}

function AssignmentDialogContent({
  assignmentId,
  onClose,
}: {
  assignmentId: string
  onClose: () => void
}) {
  const detail = useReportQuery(
    'assignments/' + encodeURIComponent(assignmentId),
    {},
    parseAssignmentDetailReport,
  )
  // Same focus return as ui/Dialog.tsx: the dialog opens from state, not from a Radix Trigger.
  const opener = useRef<HTMLElement | null>(null)

  let body
  if (detail.error) {
    body = <Message detail={errorMessage(detail.error)} onClose={onClose} />
  } else if (!detail.data) {
    body = (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    )
  } else {
    body = (
      <AssignmentContent
        row={detail.data.assignment}
        modules={detail.data.modules}
        attempts={detail.data.attempts}
        onClose={onClose}
      />
    )
  }
  return (
    <RadixDialog.Content
      onOpenAutoFocus={() => {
        opener.current =
          document.activeElement instanceof HTMLElement ? document.activeElement : null
      }}
      onCloseAutoFocus={(event) => {
        const target = opener.current
        opener.current = null
        if (target?.isConnected) {
          event.preventDefault()
          target.focus()
        }
      }}
      aria-describedby={undefined}
      className={`fixed top-1/2 left-1/2 ${WINDOW_LAYER} flex h-[min(800px,calc(100%-32px))] w-[min(1080px,calc(100%-32px))] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-3xl bg-white focus:outline-none`}
    >
      {(detail.error || !detail.data) && (
        <RadixDialog.Title className="sr-only">Assignment detail</RadixDialog.Title>
      )}
      {body}
    </RadixDialog.Content>
  )
}

function AssignmentContent({
  row,
  modules,
  attempts,
  onClose,
}: {
  row: AssignmentReportRow
  modules: AssignmentModuleReport[]
  attempts: QuizAttemptReport[]
  onClose: () => void
}) {
  const headerRef = useRef<HTMLDivElement>(null)
  const headerWidth = useElementWidth(headerRef)
  const bodyRef = useRef<HTMLDivElement>(null)
  const width = useElementWidth(bodyRef)
  const titles = new Map(modules.map((module) => [module.moduleId, module.title || 'Module']))
  const progress = Math.min(100, Math.max(0, row.completionPercent))
  const status = dialogStatusLabel(row)
  const statusColor = dialogStatusColor(status)

  const identity = (
    <div className="min-w-0 flex-1">
      <p className="m-0 text-[11px] font-extrabold tracking-[1.4px] text-brand-blue-700">
        ASSIGNMENT DETAIL
      </p>
      <RadixDialog.Title className="m-0 mt-2.5 text-[29px] font-extrabold text-text-black">
        {row.employeeName || 'Employee'}
      </RadixDialog.Title>
      <p className="m-0 text-[18px] font-bold text-primary-blue">{row.courseName || 'Course'}</p>
      {!row.accessAvailable && (
        <p className="m-0 text-text-secondary">
          Access unavailable: {row.accessReason ?? row.courseStatus}
        </p>
      )}
      <p className="m-0 mt-[7px] text-text-secondary">
        {row.completedModules}/{row.totalModules} modules completed
      </p>
    </div>
  )
  const outcome = (
    <div className="flex shrink-0 items-center gap-3.5">
      <StatusPill label={status} color={statusColor} />
      <ProgressRing progress={progress} color={statusColor} />
    </div>
  )
  const close = (
    <IconButton
      icon="close"
      label="Close assignment detail"
      className="shrink-0 text-[#44474e]"
      onClick={onClose}
    />
  )
  // _AssignmentContent metrics Wrap: 3 columns at >= 700, 2 at >= 420, else 1. Equal widths
  // with spacing 10, so a grid gives the same boxes.
  const columns = width >= 700 ? 3 : width >= 420 ? 2 : 1

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div
        ref={headerRef}
        className="bg-linear-to-br from-[#eaf4fc] to-white pt-[22px] pr-5 pb-6 pl-7"
      >
        {headerWidth - 48 < 570 ? (
          <>
            <div className="flex items-start">
              {identity}
              {close}
            </div>
            <div className="mt-3.5 flex">{outcome}</div>
          </>
        ) : (
          <div className="flex items-start">
            {identity}
            {outcome}
            {close}
          </div>
        )}
      </div>
      <div className="px-6 pt-2 pb-6">
        <div ref={bodyRef}>
          <div
            className="grid gap-2.5"
            style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
          >
            <Metric icon="event_outlined" label="Due date" value={dmy(row.deadline)} />
            <Metric
              icon="schedule_outlined"
              label="Last learning activity"
              value={dmy(row.lastLearnerActivityAt)}
            />
            <Metric
              icon="bar_chart_rounded"
              label="Average quiz score"
              value={score(row.averageScore)}
            />
          </div>
          {/* Learning path and quiz panels: a column below 760, else two Expanded. */}
          <div
            className={
              width < 760 ? 'mt-[18px] flex flex-col gap-3' : 'mt-[18px] flex items-start gap-3'
            }
          >
            <div className={width < 760 ? undefined : 'min-w-0 flex-1'}>
              <LearningPath modules={modules} />
            </div>
            <div className={width < 760 ? undefined : 'min-w-0 flex-1'}>
              <QuizPerformance attempts={attempts} titles={titles} />
            </div>
          </div>
          <div className="mt-3.5">
            <Panel title="Key dates">
              <KeyDatesTimeline
                dates={[
                  ['Assigned', row.assignedAt],
                  ['Started', row.startedAt],
                  ['Completed', row.completedAt],
                ]}
              />
            </Panel>
          </div>
        </div>
      </div>
    </div>
  )
}

/** The 64 px CircularProgressIndicator (padding 3, stroke 7) with the percent in the middle. */
function ProgressRing({ progress, color }: { progress: number; color: string }) {
  const radius = (58 - 7) / 2
  const circumference = 2 * Math.PI * radius
  return (
    <div className="relative flex size-16 shrink-0 items-center justify-center">
      <svg
        role="progressbar"
        aria-label="Assignment progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        width={58}
        height={58}
        viewBox="0 0 58 58"
        className="absolute top-[3px] left-[3px] -rotate-90"
      >
        <circle
          cx={29}
          cy={29}
          r={radius}
          fill="none"
          stroke={colors.brandBlue100}
          strokeWidth={7}
        />
        {progress > 0 && (
          <circle
            cx={29}
            cy={29}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={7}
            strokeDasharray={`${(circumference * progress) / 100} ${circumference}`}
          />
        )}
      </svg>
      <span className="relative font-extrabold text-text-black">{progress}%</span>
    </div>
  )
}

/** `_StatusPill`: 10% tint, radius 20, 11 w800. */
function StatusPill({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="shrink-0 rounded-[20px] px-2.5 py-[5px] text-[11px] font-extrabold"
      style={{ color, backgroundColor: alpha(color, 0.1) }}
    >
      {label}
    </span>
  )
}

/** `_card()`: white, light gray border, radius 14 unless given. */
const card = 'border border-light-gray bg-white'

function Metric({ icon, label, value }: { icon: IconName; label: string; value: string }) {
  return (
    <div className={`${card} flex items-center gap-2.5 rounded-[14px] p-3.5`}>
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-brand-blue-100">
        <Icon name={icon} size={20} color={colors.primaryBlue} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="m-0 truncate text-[12px] text-text-secondary">{label}</p>
        <p className="m-0 text-[17px] font-extrabold text-text-black">{value}</p>
      </div>
    </div>
  )
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: ReactNode
}) {
  return (
    <section className={`${card} w-full rounded-[14px] p-4`}>
      <h3 className="m-0 text-[18px] font-extrabold text-text-black">{title}</h3>
      {subtitle != null && <p className="m-0 text-[12px] text-text-secondary">{subtitle}</p>}
      <div className="mt-[13px]">{children}</div>
    </section>
  )
}

function LearningPath({ modules }: { modules: AssignmentModuleReport[] }) {
  return (
    <Panel title="Learning path" subtitle={`${modules.length} modules in this assignment`}>
      {modules.length === 0 ? (
        <p className="m-0">No modules are available for this course.</p>
      ) : (
        modules.map((module, index) => (
          <ModuleStep
            key={module.moduleId || index}
            module={module}
            isLast={index === modules.length - 1}
          />
        ))
      )}
    </Panel>
  )
}

function ModuleStep({ module, isLast }: { module: AssignmentModuleReport; isLast: boolean }) {
  const watched = module.videoWatched
  const hasQuiz = module.numQuestions > 0
  const passed = module.quizPassed
  const complete = watched && (!hasQuiz || passed)
  const color = complete ? colors.completedGreen : colors.accentOrange
  return (
    <div className="flex items-start gap-2.5">
      <div className="flex w-[34px] shrink-0 flex-col items-center">
        <span
          className="flex size-8 items-center justify-center rounded-full"
          style={{ backgroundColor: complete ? '#e6f7f2' : colors.accentLightOrange }}
        >
          {complete ? (
            <Icon name="check" size={18} color={color} />
          ) : (
            // CircleAvatar text: primaryTextTheme.titleMedium (Roboto 16/24), then w800.
            <span
              className="font-roboto text-base leading-6 font-extrabold tracking-[0.15px]"
              style={{ color }}
            >
              {module.moduleNumber}
            </span>
          )}
        </span>
        {!isLast && <span className="h-[68px] w-0.5 bg-light-gray" />}
      </div>
      <div className={`${card} mb-2.5 min-w-0 flex-1 rounded-xl p-3`}>
        <p className="m-0 font-extrabold">{module.title || 'Module'}</p>
        <div className="mt-[7px] flex flex-wrap gap-x-2 gap-y-[5px]">
          <Meta
            icon="play_circle_outline"
            label={watched ? 'Video watched' : 'Video pending'}
            iconColor={watched ? colors.primaryBlue : colors.accentOrange}
          />
          <Meta
            icon="quiz_outlined"
            label={!hasQuiz ? 'No quiz' : passed ? 'Quiz passed' : 'Quiz pending'}
            iconColor={
              !hasQuiz ? colors.textSecondary : passed ? colors.completedGreen : colors.accentOrange
            }
          />
          {hasQuiz && <Meta icon="replay_outlined" label={`${module.attemptCount} attempts`} />}
          {module.latestScore != null && (
            <Meta icon="bar_chart" label={score(module.latestScore)} />
          )}
        </div>
      </div>
    </div>
  )
}

function Meta({
  icon,
  label,
  iconColor = colors.textSecondary,
}: {
  icon: IconName
  label: string
  iconColor?: string
}) {
  return (
    <span className="inline-flex items-center gap-[3px]">
      <Icon name={icon} size={15} color={iconColor} />
      <span className="text-[11px] text-text-secondary">{label}</span>
    </span>
  )
}

function QuizPerformance({
  attempts,
  titles,
}: {
  attempts: QuizAttemptReport[]
  titles: Map<string, string>
}) {
  const compact = attempts.length > 6
  return (
    <Panel title="Quiz performance" subtitle={`${attempts.length} recorded attempts`}>
      {attempts.length === 0 ? (
        <p className="m-0 text-text-secondary">No quiz attempts recorded yet.</p>
      ) : (
        <>
          {compact && <p className="m-0 pb-2 text-[12px] text-text-secondary">Latest attempts</p>}
          {attempts.slice(0, 20).map((attempt, index) => (
            <AttemptRow
              key={index}
              attempt={attempt}
              title={(attempt.moduleId != null && titles.get(attempt.moduleId)) || 'Module'}
              compact={compact}
            />
          ))}
          {attempts.length > 20 && (
            <p className="m-0 pt-2 text-[12px] text-text-secondary">
              Showing the latest 20 of {attempts.length} attempts.
            </p>
          )}
          <p className="m-0 mt-2 text-[11px] text-text-secondary">
            History is available from the reporting upgrade onward.
          </p>
        </>
      )}
    </Panel>
  )
}

function AttemptRow({
  attempt,
  title,
  compact,
}: {
  attempt: QuizAttemptReport
  title: string
  compact: boolean
}) {
  const passed = attempt.passed === true
  const color = passed ? colors.completedGreen : colors.accentRed
  const fraction = attempt.score != null ? Math.min(1, Math.max(0, attempt.score / 100)) : 0
  return (
    <div className={`${card} mb-2 rounded-[11px] p-2.5`}>
      <div className="flex items-center">
        <div className="min-w-0 flex-1">
          <p className="m-0 truncate font-bold">{title}</p>
          <p className="m-0 text-[11px] text-text-secondary">{dmyHm(attempt.occurredAt)}</p>
        </div>
        <span className="ml-1.5 font-extrabold">{score(attempt.score)}</span>
        <span className="ml-[7px] flex">
          <StatusPill label={passed ? 'Passed' : 'Failed'} color={color} />
        </span>
      </div>
      {!compact && (
        <ProgressBar value={fraction} height={6} radius={6} color={color} className="mt-2" />
      )}
    </div>
  )
}

type KeyDate = [label: string, date: string | null]

/** `_KeyDatesTimeline`: a vertical list below 520, else three steps on a line. */
function KeyDatesTimeline({ dates }: { dates: KeyDate[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const width = useElementWidth(ref)
  if (width < 520) {
    return (
      <div ref={ref} className="relative">
        <span
          data-testid="key-dates-vertical-connector"
          className="absolute top-[33px] bottom-[33px] left-[15px] w-0.5 bg-brand-blue-100"
        />
        <div className="relative">
          {dates.map(([label, date]) => (
            <div key={label} className="flex h-[66px] items-center gap-3">
              <DateMarker available={date != null} />
              <div>
                <p className="m-0 font-bold">{label}</p>
                <p className="m-0 text-[12px] text-text-secondary">
                  {date == null ? 'Not yet' : dmy(date)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }
  return (
    <div ref={ref} className="relative">
      <span
        data-testid="key-dates-horizontal-connector"
        className="absolute top-[15px] h-0.5 bg-brand-blue-100"
        style={{ left: width / 6, right: width / 6 }}
      />
      <div className="relative flex">
        {dates.map(([label, date]) => (
          <div key={label} className="flex min-w-0 flex-1 flex-col items-center">
            <DateMarker available={date != null} />
            <p className="m-0 mt-[5px] font-bold">{label}</p>
            <p className="m-0 text-[12px] text-text-secondary">
              {date != null ? dmy(date) : 'Not yet'}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

function DateMarker({ available }: { available: boolean }) {
  return (
    <span
      className="flex size-8 shrink-0 items-center justify-center rounded-full"
      style={{ backgroundColor: available ? colors.brandBlue100 : colors.surfaceSecondary }}
    >
      <Icon
        name={available ? 'check' : 'more_horiz'}
        size={18}
        color={available ? colors.primaryBlue : colors.gray}
      />
    </span>
  )
}

/** `_Message`: the load error with a Close button. */
function Message({ detail, onClose }: { detail: string; onClose: () => void }) {
  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="flex flex-col items-center p-6">
        <Icon name="error_outline" size={34} color={colors.accentRed} />
        <p className="m-0 mt-3 text-[18px] font-extrabold">Could not load assignment</p>
        <p className="m-0 mt-1.5 text-center">{detail}</p>
        <div className="mt-4">
          <Button variant="text" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}
