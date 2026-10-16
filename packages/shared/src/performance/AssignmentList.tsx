// Dart: frontend/lib/features/performance/employee_assignment_list.dart:1-343
// (EmployeeAssignmentList, _TableHeader, _TableRow, _CompactRow, _Avatar, _Progress, _StatusPill).
import { useRef } from 'react'
import type { AssignmentReportRow } from '../models/performance'
import { Icon } from '../ui/icons/Icon'
import { ProgressBar } from '../ui/ProgressBar'
import { colors, dMonY, initials, listStatusColor, mix, score, statusLabel } from './format'
import { useElementWidth } from './useElementWidth'

/** Scannable assignment rows: a table at 940 px and wider, compact rows below. */
export function AssignmentList({
  rows,
  onOpenAssignment,
}: {
  rows: AssignmentReportRow[]
  onOpenAssignment: (assignmentId: string) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const table = useElementWidth(ref) >= 940
  return (
    <div ref={ref}>
      {table && <TableHeader />}
      {rows.map((row) => {
        const Row = table ? TableRow : CompactRow
        return (
          <Row
            key={row.assignmentId}
            row={row}
            onClick={() => onOpenAssignment(row.assignmentId)}
          />
        )
      })}
    </div>
  )
}

const COLUMNS = [
  ['EMPLOYEE', 25],
  ['COURSE', 22],
  ['PROGRESS', 15],
  ['QUIZ SCORE', 12],
  ['DUE DATE', 14],
  ['LAST ACTIVE', 14],
  ['STATUS', 13],
] as const

function TableHeader() {
  return (
    <div className="flex items-center rounded-lg bg-[#f3f7fc] px-3.5 py-3">
      {COLUMNS.map(([label, flex]) => (
        <span
          key={label}
          className="min-w-0 truncate text-[10px] font-extrabold tracking-[0.5px] text-text-secondary"
          style={{ flex }}
        >
          {label}
        </span>
      ))}
      <span className="w-[18px] shrink-0" />
    </div>
  )
}

interface RowProps {
  row: AssignmentReportRow
  onClick: () => void
}

const rowClass =
  'flex w-full border-b border-[#e6edf5] bg-white text-left hover:bg-black/4 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-blue-light'

function TableRow({ row, onClick }: RowProps) {
  const label = statusLabel(row)
  const color = listStatusColor(label)
  const name = row.employeeName || 'Employee'
  // The due date takes the status color only for the warning colors.
  const dueColor =
    color === colors.accentRed || color === colors.accentOrange ? color : colors.textBlack
  return (
    <button type="button" onClick={onClick} className={`${rowClass} items-center px-3.5 py-3`}>
      <span className="flex min-w-0 items-center gap-2.5" style={{ flex: 25 }}>
        <Avatar name={name} />
        <span className="block min-w-0 flex-1">
          <span className="block truncate font-extrabold">{name}</span>
          {row.department && (
            <span className="block truncate text-[11px] text-text-secondary">{row.department}</span>
          )}
        </span>
      </span>
      <span className="line-clamp-2 min-w-0" style={{ flex: 22 }}>
        {row.courseName || 'Course'}
      </span>
      <span className="block min-w-0" style={{ flex: 15 }}>
        <Progress row={row} />
      </span>
      <span className="block min-w-0 font-bold" style={{ flex: 12 }}>
        {score(row.averageScore)}
      </span>
      <span className="block min-w-0 truncate font-semibold" style={{ flex: 14, color: dueColor }}>
        {dMonY(row.deadline)}
      </span>
      <span className="block min-w-0 truncate text-text-secondary" style={{ flex: 14 }}>
        {dMonY(row.lastLearnerActivityAt)}
      </span>
      <span className="block min-w-0" style={{ flex: 13 }}>
        <Status row={row} label={label} color={color} />
      </span>
      <Icon name="chevron_right" size={18} className="text-text-secondary" />
    </button>
  )
}

function CompactRow({ row, onClick }: RowProps) {
  const label = statusLabel(row)
  const name = row.employeeName || 'Employee'
  return (
    <button type="button" onClick={onClick} className={`${rowClass} flex-col px-1 py-3.5`}>
      <span className="flex w-full items-center">
        <Avatar name={name} />
        <span className="ml-2.5 block min-w-0 flex-1">
          <span className="block truncate font-extrabold">{name}</span>
          <span className="block truncate text-[12px] text-text-secondary">
            {row.courseName || 'Course'}
          </span>
        </span>
        <Status row={row} label={label} color={listStatusColor(label)} />
        <Icon name="chevron_right" size={18} className="ml-0.5 text-text-secondary" />
      </span>
      <span className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-text-secondary">
        <span>
          {row.completedModules}/{row.totalModules} modules
        </span>
        <span>Score {score(row.averageScore)}</span>
        <span>Due {dMonY(row.deadline)}</span>
        <span>Active {dMonY(row.lastLearnerActivityAt)}</span>
      </span>
    </button>
  )
}

/** `_Avatar`: radius 19 circle with the initials. */
function Avatar({ name }: { name: string }) {
  return (
    <span className="inline-flex size-[38px] shrink-0 items-center justify-center rounded-full bg-brand-blue-100 text-[12px] font-extrabold text-primary-blue">
      {initials(name)}
    </span>
  )
}

/** `_Progress`: module count over an 82 px bar. */
function Progress({ row }: { row: AssignmentReportRow }) {
  const { completedModules: completed, totalModules: total } = row
  return (
    <>
      <span className="block text-[11px] font-bold">
        {completed}/{total} modules
      </span>
      <ProgressBar
        className="mt-1.5 w-[82px]!"
        value={total === 0 ? 0 : completed / total}
        height={5}
        radius={5}
        color={colors.accentBlue}
        trackColor={colors.brandBlue100}
      />
    </>
  )
}

/** `_StatusPill`, plus the access line when the course is no longer available. */
function Status({ row, label, color }: { row: AssignmentReportRow; label: string; color: string }) {
  return (
    <span className="block min-w-0">
      <span
        className="inline-block max-w-full truncate rounded-[20px] px-[9px] py-[5px] text-[11px] font-extrabold"
        style={{ color, backgroundColor: mix(color, 0.1) }}
      >
        {label}
      </span>
      {!row.accessAvailable && (
        <span className="block text-[10px] text-text-secondary">
          Access unavailable · {row.courseStatus}
        </span>
      )}
    </span>
  )
}
