// Dart: frontend/lib/features/performance/employee_summary_panel.dart:406-826 (EmployeeDetailDrawer,
// _LearningSnapshot, _SignalChip, _EmployeeCourseTable), :828-1020 (helpers) and
// performance_report_portal.dart:767-790 (_showEmployee).
import * as RadixDialog from '@radix-ui/react-dialog'
import { useRef, useState, type ReactNode } from 'react'
import { errorMessage } from '../api/client'
import type {
  AssignmentReportRow,
  EmployeeDetailReport,
  EmployeeReportRow,
} from '../models/performance'
import { parseEmployeeDetailReport } from '../models/performance'
import { IconButton } from '../ui/Button'
import { Icon, type IconName } from '../ui/icons/Icon'
import { Spinner } from '../ui/Spinner'
import { Tooltip } from '../ui/Tooltip'
import { AccessGuard } from './AccessGuard'
import { useReport, useReportQuery } from './context'
import { alpha, colors, courseStatusColor, courseStatusLabel, dMonY, percent } from './format'
import { scopeParams, without } from './state'
import { Badge, Completion, Identity, Metric } from './employeeParts'
import { useElementWidth } from './useElementWidth'
import { OVERLAY_LAYER, WINDOW_LAYER } from '../ui/layers'

/** Employee `_date`: local date, "Not recorded" when missing. */
const date = (value: string | null) => dMonY(value, 'Not recorded', true)

/**
 * Right drawer with one employee's report (`_showEmployee`). `employeeId == null` means closed.
 * The report context at open time guards the content, as ReportAccessGuard does.
 */
export function EmployeeDrawer({
  employeeId,
  onClose,
  onOpenAssignment,
}: {
  employeeId: string | null
  onClose: () => void
  onOpenAssignment: (assignmentId: string) => void
}) {
  const { contextKey } = useReport()
  // Keep the context key from the moment the drawer opened for this employee.
  const [opened, setOpened] = useState<{ id: string; expected: string } | null>(null)
  if (employeeId !== (opened?.id ?? null)) {
    setOpened(employeeId == null ? null : { id: employeeId, expected: contextKey })
  }
  // Same focus return as ui/Dialog.tsx: the drawer opens from state, not from a Radix Trigger.
  const opener = useRef<HTMLElement | null>(null)
  return (
    <RadixDialog.Root
      open={employeeId != null}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={`fixed inset-0 ${OVERLAY_LAYER} bg-black/38`} />
        <AccessGuard expected={opened?.expected ?? contextKey} onClose={onClose}>
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
            className={`fixed top-0 right-0 ${WINDOW_LAYER} flex h-full w-[min(100vw,900px)] flex-col overflow-hidden rounded-l-[22px] bg-white focus:outline-none`}
          >
            <div className="flex items-center pt-4 pr-3 pb-3 pl-6">
              <RadixDialog.Title className="m-0 min-w-0 flex-1 text-[21px] font-extrabold">
                Employee performance
              </RadixDialog.Title>
              <IconButton
                icon="close"
                label="Close employee detail"
                className="size-12! text-[#44474e]"
                onClick={onClose}
              />
            </div>
            {employeeId != null && (
              <DrawerBody employeeId={employeeId} onOpenAssignment={onOpenAssignment} />
            )}
          </RadixDialog.Content>
        </AccessGuard>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}

function DrawerBody({
  employeeId,
  onOpenAssignment,
}: {
  employeeId: string
  onOpenAssignment: (assignmentId: string) => void
}) {
  const { state } = useReport()
  const detail = useReportQuery(
    'employees/' + encodeURIComponent(employeeId),
    without(scopeParams(state), 'employee_id'),
    parseEmployeeDetailReport,
  )
  if (detail.error != null) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center p-6">
        <p className="m-0">Could not load employee detail. {errorMessage(detail.error)}</p>
      </div>
    )
  }
  if (!detail.data) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center">
        <Spinner />
      </div>
    )
  }
  return <EmployeeDetail detail={detail.data} onOpenAssignment={onOpenAssignment} />
}

function EmployeeDetail({
  detail: { employee, assignments },
  onOpenAssignment,
}: {
  detail: EmployeeDetailReport
  onOpenAssignment: (assignmentId: string) => void
}) {
  const metricsRef = useRef<HTMLDivElement>(null)
  const metricsWidth = useElementWidth(metricsRef)
  const columns = metricsWidth >= 650 ? 4 : metricsWidth >= 290 ? 2 : 1
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="bg-[#f0f6fd] p-6">
        <Identity employee={employee} prominent />
        <p className="m-0 mt-2.5 text-xs text-text-secondary">Employee ID: {employee.employeeId}</p>
      </div>
      <div className="p-6">
        <div
          ref={metricsRef}
          className="grid gap-2.5"
          style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
        >
          <Metric label="Assigned courses" value={employee.assigned} icon="menu_book_outlined" />
          <Metric
            label="Completed"
            value={employee.completed}
            icon="check_circle_outline"
            color={colors.green}
          />
          <Metric label="In progress" value={employee.inProgress} icon="timelapse" />
          <Metric
            label="Not started"
            value={employee.notStarted}
            icon="pause_circle_outline"
            color={colors.textSecondary}
          />
        </div>
        <div className="mt-[18px]">
          <LearningSnapshot employee={employee} />
        </div>
        <h3 className="m-0 mt-6 text-lg font-extrabold">Course breakdown</h3>
        <p className="m-0 mt-1.5 text-xs text-text-secondary">
          {assignments.length} courses within your current reporting scope. Select a course for
          module results.
        </p>
        <div className="mt-3.5">
          <CourseTable assignments={assignments} onOpenAssignment={onOpenAssignment} />
        </div>
        <p className="m-0 mt-4 text-[11px] text-text-secondary">
          Completion counts completed courses. Overdue and due soon are deadline flags. Scores
          exclude unattempted modules.
        </p>
      </div>
    </div>
  )
}

/** `_Surface`: white, #E3EBF5 border, radius 16, padding 20. */
function Surface({ children }: { children: ReactNode }) {
  return <div className="rounded-2xl border border-[#e3ebf5] bg-white p-5">{children}</div>
}

/** `_LearningSnapshot`: completion and quiz side by side at 560 px, then the signal chips. */
function LearningSnapshot({ employee }: { employee: EmployeeReportRow }) {
  const ref = useRef<HTMLDivElement>(null)
  const wide = useElementWidth(ref) >= 560
  const completion = (
    <div>
      <p className="m-0 text-xs text-text-secondary">Overall completion</p>
      <div className="mt-2 flex items-center gap-[18px]">
        <span className="text-[30px] font-extrabold">{percent(employee.completionRate)}</span>
        <div className="min-w-0 flex-1">
          <Completion rate={employee.completionRate} showLabel={false} />
        </div>
      </div>
      <p className="m-0 mt-2 text-[13px] text-text-secondary">
        {employee.completed} of {employee.assigned} courses completed
      </p>
    </div>
  )
  const quiz = (
    <div>
      <p className="m-0 text-xs text-text-secondary">Average quiz score</p>
      <p className="m-0 mt-1 text-[28px] font-extrabold">{percent(employee.averageScore)}</p>
      <p className="m-0 mt-1 text-xs text-text-secondary">
        Last activity: {date(employee.lastLearnerActivityAt)}
      </p>
    </div>
  )
  const signal = (count: number, warn: string) => (count > 0 ? warn : colors.textSecondary)
  const failures = employee.repeatedFailures
  return (
    <Surface>
      <h4 className="m-0 text-[17px] font-extrabold">Learning snapshot</h4>
      <div ref={ref} className="mt-[18px]">
        {wide ? (
          <div className="flex items-center">
            <div className="min-w-0 flex-[3]">{completion}</div>
            <div className="mx-6 h-[85px] w-px shrink-0 bg-[#e3ebf5]" />
            <div className="min-w-0 flex-[2]">{quiz}</div>
          </div>
        ) : (
          <div className="flex flex-col gap-[18px]">
            {completion}
            {quiz}
          </div>
        )}
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        <SignalChip
          text={`${employee.overdue} overdue`}
          icon="event_busy_outlined"
          color={signal(employee.overdue, colors.red)}
        />
        <SignalChip
          text={`${employee.dueSoon} due soon`}
          icon="schedule_outlined"
          color={signal(employee.dueSoon, colors.amber)}
        />
        <SignalChip
          text={`${employee.inactive} inactive courses`}
          tooltip="Incomplete courses with no learning activity for 14+ days."
          icon="pause_circle_outline"
          color={signal(employee.inactive, colors.amber)}
        />
        <SignalChip
          text={`Repeated quiz failures · ${failures} ${failures === 1 ? 'course' : 'courses'}`}
          icon={failures > 0 ? 'warning_amber_rounded' : 'fact_check_outlined'}
          color={signal(failures, colors.amber)}
        />
      </div>
    </Surface>
  )
}

/** `_SignalChip`: tinted chip with a tooltip (the text when no tooltip is given). */
function SignalChip({
  text,
  tooltip,
  icon,
  color,
}: {
  text: string
  tooltip?: string
  icon: IconName
  color: string
}) {
  return (
    <Tooltip content={tooltip ?? text}>
      <span
        className="flex max-w-full items-center gap-[7px] rounded-[10px] px-3 py-[9px]"
        style={{ backgroundColor: alpha(color, 0.07) }}
      >
        <Icon name={icon} size={17} color={color} />
        <span className="min-w-0 text-xs font-semibold" style={{ color }}>
          {text}
        </span>
      </span>
    </Tooltip>
  )
}

const headerText = 'text-[10px] font-extrabold text-text-secondary'

/** `_EmployeeCourseTable`: a table at 700 px and wider, stacked rows below. */
function CourseTable({
  assignments,
  onOpenAssignment,
}: {
  assignments: AssignmentReportRow[]
  onOpenAssignment: (assignmentId: string) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const wide = useElementWidth(ref) >= 700
  return (
    <div ref={ref} className="overflow-hidden rounded-xl border border-[#e3ebf5]">
      {wide && (
        <div className="flex bg-[#f3f7fc] px-4 py-[13px]">
          <span className={`min-w-0 flex-[5] ${headerText}`}>COURSE</span>
          <span className={`min-w-0 flex-[4] ${headerText}`}>PROGRESS</span>
          <span className={`min-w-0 flex-[2] ${headerText}`}>QUIZ</span>
          <span className={`min-w-0 flex-[3] ${headerText}`}>DUE DATE</span>
          <span className={`min-w-0 flex-[3] ${headerText}`}>STATUS</span>
          <span className="w-5 shrink-0" />
        </div>
      )}
      {assignments.length === 0 && (
        <p className="m-0 p-6">No courses in the current reporting scope.</p>
      )}
      {assignments.map((row) => (
        <button
          key={row.assignmentId}
          type="button"
          onClick={() => onOpenAssignment(row.assignmentId)}
          className="block w-full cursor-pointer border-b border-[#e6edf5] bg-white p-4 text-left hover:bg-black/4 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-blue-light"
        >
          {wide ? <WideRow row={row} /> : <NarrowRow row={row} />}
        </button>
      ))}
    </div>
  )
}

const chevron = <Icon name="chevron_right" size={20} color={colors.textSecondary} />

function Progress({ row }: { row: AssignmentReportRow }) {
  return (
    <span className="block">
      <span className="block text-[11px] text-text-secondary">
        {row.completedModules}/{row.totalModules} modules
      </span>
      <span className="mt-1.5 block">
        <Completion rate={row.completionPercent} />
      </span>
    </span>
  )
}

function WideRow({ row }: { row: AssignmentReportRow }) {
  return (
    <span className="flex items-center">
      <span className="min-w-0 flex-[5] pr-3 text-[13px] font-bold">{row.courseName}</span>
      <span className="min-w-0 flex-[4] pr-5">
        <Progress row={row} />
      </span>
      <span className="min-w-0 flex-[2] text-xs">{percent(row.averageScore)}</span>
      <span className="min-w-0 flex-[3] text-xs">{date(row.deadline)}</span>
      <span className="min-w-0 flex-[3]">
        <Badge text={courseStatusLabel(row.status)} color={courseStatusColor(row.status)} />
      </span>
      {chevron}
    </span>
  )
}

function NarrowRow({ row }: { row: AssignmentReportRow }) {
  return (
    <span className="block">
      <span className="flex items-center">
        <span className="min-w-0 flex-1 font-bold">{row.courseName}</span>
        {chevron}
      </span>
      <span className="mt-3 block">
        <Progress row={row} />
      </span>
      <span className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="text-xs">Quiz {percent(row.averageScore)}</span>
        <span className="text-xs">Due {date(row.deadline)}</span>
        <Badge text={courseStatusLabel(row.status)} color={courseStatusColor(row.status)} />
      </span>
    </span>
  )
}
