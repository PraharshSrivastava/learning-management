// Dart: frontend/lib/features/performance/performance_report_portal.dart:331-578 (_overview),
// :988-1089 (_KpiCard), :1091-1120 (_SectionHeader), :1122-1190 (_AttentionCard),
// :1192-1223 (_AttentionLink), :1225-1322 (_WatchlistHeader, _WatchlistRow), :1410-1434 (_Bar).
import clsx from 'clsx'
import { useRef, type ReactNode } from 'react'
import {
  parsePerformanceOverview,
  type AssignmentReportRow,
  type PerformanceOverview,
  type ReportBreakdown,
  type ReportSummary,
} from '../models/performance'
import { Icon, type IconName } from '../ui/icons/Icon'
import { ProgressBar } from '../ui/ProgressBar'
import { useReport } from './context'
import { colors, dmy, mix, statusLabel } from './format'
import { Box, Heading, StatusBadge } from './primitives'
import { StatusChart } from './StatusChart'
import { useElementWidth } from './useElementWidth'

// Flutter keeps rendering the empty maps while the first request loads, so every count reads 0.
const emptyOverview = parsePerformanceOverview({})

// InkWell hover: a 4% black overlay above the fill, below the content.
const ink =
  'cursor-pointer text-left hover:shadow-[inset_0_0_0_999px_rgb(0_0_0/0.04)] focus-visible:outline-2 focus-visible:outline-brand-blue-light'

export function Overview({
  overview,
  isLoading,
  onOpenAssignment,
}: {
  overview: PerformanceOverview | undefined
  isLoading: boolean
  onOpenAssignment: (assignmentId: string) => void
}) {
  if (!overview && !isLoading) return <Box>No performance data available.</Box>
  return <OverviewBody data={overview ?? emptyOverview} onOpenAssignment={onOpenAssignment} />
}

function OverviewBody({
  data,
  onOpenAssignment,
}: {
  data: PerformanceOverview
  onOpenAssignment: (assignmentId: string) => void
}) {
  const { dispatch } = useReport()
  const rootRef = useRef<HTMLDivElement>(null)
  const width = useElementWidth(rootRef)
  const { summary, breakdowns, watchlist } = data
  const setStatus = (status: string | null) => dispatch({ type: 'status', status })

  const metrics: {
    label: string
    value: string
    caption: string
    status?: string
    color: string
    icon: IconName
  }[] = [
    {
      label: 'Assigned',
      value: `${summary.assigned}`,
      caption: `${summary.uniqueLearners} unique employees`,
      color: colors.primaryBlue,
      icon: 'assignment_outlined',
    },
    {
      label: 'Completed',
      value: `${summary.completionRate}%`,
      caption: `${summary.completed} assignments`,
      status: 'completed',
      color: colors.accentGreen,
      icon: 'task_alt_rounded',
    },
    {
      label: 'On-time compliance',
      value: summary.onTimeCompliance == null ? '-' : `${summary.onTimeCompliance}%`,
      caption: `${summary.onTimeDenominator} deadlines passed`,
      color: colors.accentBlue,
      icon: 'verified_outlined',
    },
    {
      label: 'Average quiz score',
      value: summary.averageScore == null ? '-' : `${summary.averageScore}%`,
      caption: `${summary.scoredModules} scored modules`,
      color: colors.purple,
      icon: 'bar_chart_rounded',
    },
  ]
  const columns = width >= 1100 ? 4 : width >= 560 ? 2 : 1
  const cardWidth = columns === 1 ? width : (width - 12 * (columns - 1)) / columns
  // The model reads a missing due_soon_days or inactive_days as 0; Flutter shows 2 and 14.
  const dueSoonDays = data.dueSoonDays || 2
  const inactiveDays = data.inactiveDays || 14
  const attention = (
    <AttentionPanel
      summary={summary}
      dueSoonDays={dueSoonDays}
      inactiveDays={inactiveDays}
      setStatus={setStatus}
    />
  )
  const watchlistPanel = (
    <WatchlistPanel
      watchlist={watchlist}
      setStatus={setStatus}
      onOpenAssignment={onOpenAssignment}
    />
  )

  const coursePanel = (
    <Box>
      <SectionHeader
        title="Completion by course"
        subtitle="Compare completion across courses."
        onViewAll={() => dispatch({ type: 'tab', view: 1 })}
      />
      {breakdowns.courses.slice(0, 5).map((item, index) => (
        <Bar key={index} item={item} />
      ))}
      {breakdowns.courses.length === 0 && <p className="m-0">No assigned courses yet.</p>}
    </Box>
  )
  const departmentPanel = (
    <Box>
      <Heading title="Department comparison" subtitle="Completion by department." />
      {breakdowns.departments.map((item, index) => (
        <Bar key={index} item={item} />
      ))}
      {breakdowns.departments.length === 0 && <p className="m-0">No department data yet.</p>}
    </Box>
  )
  const mailingPanel = (
    <Box>
      <Heading title="Mailing list comparison" subtitle="Employees may belong to multiple lists." />
      {breakdowns.mailingLists.map((item, index) => (
        <Bar key={index} item={item} />
      ))}
      {breakdowns.mailingLists.length === 0 && <p className="m-0">No mailing list data yet.</p>}
    </Box>
  )

  return (
    <div ref={rootRef}>
      <p className="m-0 pb-3">
        {summary.currentAssignments} current assignments · {summary.historicalAssignments} retained
        historical records
      </p>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-3">
          {metrics.map((item) => (
            <KpiCard
              key={item.label}
              width={cardWidth}
              label={item.label}
              value={item.value}
              caption={item.caption}
              color={item.color}
              icon={item.icon}
              compact={cardWidth < 220}
              status={item.status}
              setStatus={setStatus}
            />
          ))}
        </div>
        <StatusChart summary={summary} />
        {width < 1080 ? (
          <div className="flex flex-col gap-3">
            {attention}
            {watchlistPanel}
          </div>
        ) : (
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-[5_1_0%]">{attention}</div>
            <div className="min-w-0 flex-[6_1_0%]">{watchlistPanel}</div>
          </div>
        )}
        {width >= 1200 ? (
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">{coursePanel}</div>
            <div className="min-w-0 flex-1">{departmentPanel}</div>
            <div className="min-w-0 flex-1">{mailingPanel}</div>
          </div>
        ) : width < 760 ? (
          <div className="flex flex-col gap-3">
            {coursePanel}
            {departmentPanel}
            {mailingPanel}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {coursePanel}
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">{departmentPanel}</div>
              <div className="min-w-0 flex-1">{mailingPanel}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/** "Needs attention": three attention cards (3 per row from 600 wide) and the quiz link. */
function AttentionPanel({
  summary,
  dueSoonDays,
  inactiveDays,
  setStatus,
}: {
  summary: ReportSummary
  dueSoonDays: number
  inactiveDays: number
  setStatus: (status: string | null) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const width = useElementWidth(ref)
  const cardWidth = width >= 600 ? (width - 16) / 3 : width
  return (
    <Box>
      <SectionHeader
        title="Needs attention"
        subtitle="Start with employees who need a follow-up."
        onViewAll={() => setStatus(null)}
      />
      <div ref={ref} className="flex flex-wrap gap-2">
        <AttentionCard
          width={cardWidth}
          label="Overdue"
          count={summary.overdue}
          detail="Incomplete past due date"
          icon="error_outline_rounded"
          color={colors.accentRed}
          onClick={() => setStatus('overdue')}
        />
        <AttentionCard
          width={cardWidth}
          label="Due soon"
          count={summary.dueSoon}
          detail={`Within ${dueSoonDays} days`}
          icon="schedule_rounded"
          color={colors.accentOrange}
          onClick={() => setStatus('due_soon')}
        />
        <AttentionCard
          width={cardWidth}
          label="No learning activity"
          count={summary.inactive}
          detail={`For ${inactiveDays} days`}
          icon="person_off_outlined"
          color={colors.accentBlue}
          onClick={() => setStatus('inactive')}
        />
      </div>
      <div className="mt-2">
        <AttentionLink
          label="Repeated quiz failures"
          count={summary.repeatedFailures}
          onClick={() => setStatus('repeated_failures')}
        />
      </div>
    </Box>
  )
}

/** "Assignment watchlist": the first 5 rows, a table from 620 wide. */
function WatchlistPanel({
  watchlist,
  setStatus,
  onOpenAssignment,
}: {
  watchlist: AssignmentReportRow[]
  setStatus: (status: string | null) => void
  onOpenAssignment: (assignmentId: string) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const wide = useElementWidth(ref) >= 620
  return (
    <Box>
      <SectionHeader
        title="Assignment watchlist"
        subtitle="The most urgent assignments in this scope."
        onViewAll={() => setStatus(null)}
      />
      <div ref={ref}>
        {watchlist.length === 0 && (
          <p className="m-0 py-8 text-center">No assignments currently need attention.</p>
        )}
        {watchlist.length > 0 && wide && <WatchlistHeader />}
        {watchlist.slice(0, 5).map((row) => (
          <WatchlistRow
            key={row.assignmentId}
            row={row}
            wide={wide}
            onClick={() => onOpenAssignment(row.assignmentId)}
          />
        ))}
        {watchlist.length > 5 && (
          <p className="m-0 pt-2 text-[12px] text-text-secondary">
            {watchlist.length - 5} more in this watchlist
          </p>
        )}
      </div>
    </Box>
  )
}

/** `_KpiCard`: 112 high, r14. Below 220 wide the icon tile goes and the label wraps. */
function KpiCard({
  width,
  label,
  value,
  caption,
  color,
  icon,
  compact,
  status,
  setStatus,
}: {
  width: number
  label: string
  value: string
  caption: string
  color: string
  icon: IconName
  compact: boolean
  /** The status the card opens. Without it the card is not clickable. */
  status?: string
  setStatus: (status: string | null) => void
}) {
  const body = compact ? (
    <span className="flex h-full flex-col">
      <span className="flex items-center gap-1.5">
        <Icon name={icon} size={19} color={color} />
        <span className="line-clamp-2 min-w-0 flex-1 text-[11px] text-text-secondary">{label}</span>
      </span>
      <span className="mt-auto text-[24px] font-extrabold text-text-black">{value}</span>
      <span className="truncate text-[10px] text-text-secondary">{caption}</span>
    </span>
  ) : (
    <span className="flex items-start gap-2.5">
      <span
        className="flex size-9 shrink-0 items-center justify-center rounded-[11px]"
        style={{ backgroundColor: mix(color, 0.11) }}
      >
        <Icon name={icon} size={20} color={color} />
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-[12px] text-text-secondary">{label}</span>
        <span className="mt-[3px] text-[25px] font-extrabold text-text-black">{value}</span>
        <span className="truncate text-[11px] text-text-secondary">{caption}</span>
      </span>
    </span>
  )
  const className = clsx(
    'block h-28 overflow-hidden rounded-[14px] border border-[#dde6f1] bg-white',
    compact ? 'p-2.5' : 'p-[13px]',
  )
  if (status == null) {
    return (
      <div className={className} style={{ width }}>
        {body}
      </div>
    )
  }
  return (
    <button
      type="button"
      onClick={() => setStatus(status)}
      className={clsx(className, ink)}
      style={{ width }}
    >
      {body}
    </button>
  )
}

/** `_SectionHeader`: 17 w800 title, 12 secondary subtitle, "View all" text button. */
function SectionHeader({
  title,
  subtitle,
  onViewAll,
}: {
  title: string
  subtitle: string
  onViewAll: () => void
}) {
  return (
    <div className="flex items-start pb-3">
      <div className="min-w-0 flex-1">
        <h3 className="m-0 text-[17px] font-extrabold">{title}</h3>
        <p className="m-0 text-[12px] text-text-secondary">{subtitle}</p>
      </div>
      {/* TextButton at compact desktop density: 36 high, 12 px side padding. */}
      <button
        type="button"
        onClick={onViewAll}
        className="inline-flex h-9 min-w-9 shrink-0 items-center justify-center rounded-full px-3 text-[14px] leading-5 font-bold tracking-[0.1px] text-primary-blue hover:bg-brand-blue-50 focus-visible:outline-2 focus-visible:outline-brand-blue-light"
      >
        View all
      </button>
    </div>
  )
}

/** `_AttentionCard`: tinted 148 high card with the count in the accent color. */
function AttentionCard({
  width,
  label,
  count,
  detail,
  icon,
  color,
  onClick,
}: {
  width: number
  label: string
  count: number
  detail: string
  icon: IconName
  color: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx('flex h-37 flex-col overflow-hidden rounded-xl border p-[13px]', ink)}
      style={{ width, backgroundColor: mix(color, 0.055), borderColor: mix(color, 0.2) }}
    >
      <span className="flex w-full items-center gap-1.5">
        <Icon name={icon} size={21} color={color} />
        <span className="line-clamp-2 min-w-0 flex-1 font-bold">{label}</span>
      </span>
      <span className="mt-[9px] text-[30px] font-extrabold" style={{ color }}>
        {count}
      </span>
      <span className="mt-auto flex w-full items-center">
        <span className="line-clamp-2 min-w-0 flex-1 text-[11px] text-text-secondary">
          {detail}
        </span>
        <Icon name="arrow_forward" size={17} color={color} />
      </span>
    </button>
  )
}

/** `_AttentionLink`: one row with the quiz icon, the count and a chevron. */
function AttentionLink({
  label,
  count,
  onClick,
}: {
  label: string
  count: number
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx('flex w-full items-center rounded-lg px-1 py-[9px]', ink)}
    >
      <Icon name="quiz_outlined" size={18} color={colors.accentBlue} />
      <span className="ml-[9px] min-w-0 flex-1 font-semibold">{label}</span>
      <span className="font-extrabold">{count}</span>
      {/* Material default icon color: black 87%. */}
      <Icon name="chevron_right" size={18} color="rgb(0 0 0 / 0.867)" className="ml-1" />
    </button>
  )
}

/** Flutter Expanded(flex: n) in a Row. */
const flex = { 2: 'min-w-0 flex-[2_1_0%]', 3: 'min-w-0 flex-[3_1_0%]' } as const

function WatchlistHeader() {
  return (
    <div className="flex px-2 pt-1 pb-2">
      <span className={flex[3]}>EMPLOYEE</span>
      <span className={flex[3]}>COURSE</span>
      <span className={flex[2]}>DUE</span>
      <span className={flex[2]}>PROGRESS</span>
      <span className={flex[2]}>STATUS</span>
      <span className="w-[18px] shrink-0" />
    </div>
  )
}

/** `_WatchlistRow`: a table row from 620 wide, a ListTile below. */
function WatchlistRow({
  row,
  wide,
  onClick,
}: {
  row: AssignmentReportRow
  wide: boolean
  onClick: () => void
}) {
  const completed = row.completedModules
  const total = row.totalModules
  const progress = total === 0 ? 0 : Math.min(1, Math.max(0, completed / total))
  const status = statusLabel(row)
  const employee = row.employeeName || 'Employee'
  const course = row.courseName || 'Course'
  if (!wide) {
    // ListTile: compact two-line tile, 4 px side padding, 16 px gap before the trailing badge.
    return (
      <button
        type="button"
        onClick={onClick}
        className={clsx('flex min-h-16 w-full items-center gap-4 px-1 py-2', ink)}
      >
        <span className="min-w-0 flex-1">
          <span className="block text-[15px] font-bold text-[#191c20]">{employee}</span>
          <span className="block text-[14px] text-[#44474e]">
            {course} • {completed}/{total} modules • Due {dmy(row.deadline)}
          </span>
        </span>
        <StatusBadge label={status} />
      </button>
    )
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx('flex w-full items-center border-t border-[#e6edf5] px-2 py-[11px]', ink)}
    >
      <span className={clsx(flex[3], 'truncate font-bold')}>{employee}</span>
      <span className={clsx(flex[3], 'truncate')}>{course}</span>
      <span className={clsx(flex[2], 'truncate')}>{dmy(row.deadline)}</span>
      <span className={clsx(flex[2], 'flex items-center')}>
        <span className="min-w-0 flex-1">
          <ProgressBar
            value={progress}
            height={5}
            radius={4}
            color={colors.accentBlue}
            trackColor={colors.brandBlue100}
            label={`${completed} of ${total} modules`}
          />
        </span>
        <span className="mr-1.5 ml-[5px] text-[11px]">
          {completed}/{total}
        </span>
      </span>
      <span className={clsx(flex[2], 'flex')}>
        <StatusBadge label={status} />
      </span>
      <Icon name="chevron_right" size={18} color={colors.textSecondary} />
    </button>
  )
}

/** `_Bar`: label, completion bar and rate. */
function Bar({ item }: { item: ReportBreakdown }): ReactNode {
  const rate = Math.min(100, Math.max(0, item.completionRate))
  return (
    <div className="flex items-center py-2">
      <span className="w-[130px] shrink-0 truncate">{item.label}</span>
      <span className="min-w-0 flex-1">
        <ProgressBar
          value={rate / 100}
          height={9}
          color={colors.primaryBlue}
          trackColor={colors.brandBlue100}
          label={item.label}
        />
      </span>
      <span className="ml-2.5">{rate}%</span>
    </div>
  )
}
