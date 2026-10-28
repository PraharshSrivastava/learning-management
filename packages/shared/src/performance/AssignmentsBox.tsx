// Dart: frontend/lib/features/performance/performance_report_portal.dart:48-64 (search, searchDelay),
// :629-755 (_assignments), :1376-1408 (_Drop) and :1436-1467 (_StatusFilterChip).
import clsx from 'clsx'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { AssignmentListReport } from '../models/performance'
import { IconButton } from '../ui/Button'
import { Select, TextField } from '../ui/TextField'
import { AssignmentList } from './AssignmentList'
import { useReport } from './context'
import { Box, Heading } from './primitives'

/** The 350 ms search Timer. `schedule` replaces a pending call. Unmount cancels it. */
export function useSearchDelay() {
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const cancel = useCallback(() => clearTimeout(timer.current), [])
  const schedule = useCallback((run: () => void) => {
    clearTimeout(timer.current)
    timer.current = setTimeout(run, 350)
  }, [])
  useEffect(() => cancel, [cancel])
  return { schedule, cancel }
}

const quickStatuses: [string, string | null][] = [
  ['All', null],
  ['Overdue', 'overdue'],
  ['Due soon', 'due_soon'],
  ['Completed', 'completed'],
]

const otherStatuses: Record<string, string> = {
  pending: 'Pending',
  started: 'Started',
  inactive: 'Inactive',
  repeated_failures: 'Repeated failures',
}

const sorts: Record<string, string> = {
  deadline: 'Due date',
  employee: 'Employee',
  course: 'Course',
  progress: 'Progress',
  score: 'Score',
  last_activity: 'Last activity',
  status: 'Status',
}

interface Props {
  assignments: AssignmentListReport | undefined
  onOpenAssignment: (assignmentId: string) => void
}

/** `_assignments`. A new employeeResetVersion remounts the box, so the search text clears. */
export function AssignmentsBox(props: Props) {
  const { state } = useReport()
  return <Assignments key={state.employeeResetVersion} {...props} />
}

function Assignments({ assignments, onOpenAssignment }: Props) {
  const { state, dispatch, contextKey, isCurrent } = useReport()
  // The Dart controller lives in the portal, so the text survives a tab switch. Start from the
  // applied search.
  const [search, setSearch] = useState(state.search)
  const { schedule, cancel } = useSearchDelay()
  // ref.listen(reportContextProvider): a context change cancels the pending search.
  useEffect(() => cancel, [cancel, contextKey])

  const rows = assignments?.rows ?? []
  const total = assignments?.total ?? 0
  const size = assignments?.pageSize || 25
  const { page } = state
  const setStatus = (status: string | null) => dispatch({ type: 'status', status })

  return (
    <Box>
      <Heading title="Employee assignments" subtitle="One record per employee–course assignment." />
      <div className="mt-1 flex flex-wrap items-center gap-2.5">
        <TextField
          dense
          icon="search"
          fieldClassName="w-[300px]"
          aria-label="Search employee name, ID or course"
          placeholder="Search employee name, ID or course"
          enterKeyHint="search"
          value={search}
          onChange={(event) => {
            const value = event.target.value
            setSearch(value)
            const expected = contextKey
            schedule(() => {
              if (isCurrent(expected)) dispatch({ type: 'search', search: value })
            })
          }}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return
            cancel()
            dispatch({ type: 'search', search })
          }}
        />
        {quickStatuses.map(([label, status]) => (
          <StatusFilterChip
            key={label}
            label={label}
            selected={state.status === status}
            onClick={() => setStatus(status)}
          />
        ))}
        <Drop
          label="More statuses"
          allLabel="More"
          value={state.status}
          width={165}
          items={otherStatuses}
          onChange={setStatus}
        />
        <Drop
          label="Sort by"
          value={state.sort}
          width={160}
          items={sorts}
          onChange={(sort) => {
            if (sort != null) dispatch({ type: 'sort', sort })
          }}
        />
        <IconButton
          icon={state.descending ? 'arrow_downward' : 'arrow_upward'}
          label={state.descending ? 'Sort ascending' : 'Sort descending'}
          className="text-[#44474e]"
          onClick={() => dispatch({ type: 'toggleSort' })}
        />
        <span className="text-text-secondary">{total} assignments</span>
      </div>
      <div className="h-4" />
      {rows.length === 0 ? (
        <p className="m-0 p-[30px] text-center">No matching assignments.</p>
      ) : (
        <AssignmentList rows={rows} onOpenAssignment={onOpenAssignment} />
      )}
      {total > size && (
        <div className="flex items-center pt-3">
          <span className="flex-1 text-xs text-text-secondary">
            Showing {(page - 1) * size + 1}–{Math.min(page * size, total)} of {total}
          </span>
          <IconButton
            icon="chevron_left"
            label="Previous page"
            className="text-[#44474e]"
            disabled={page <= 1}
            onClick={() => dispatch({ type: 'page', page: page - 1 })}
          />
          <span>
            Page {page} of {Math.ceil(total / size)}
          </span>
          <IconButton
            icon="chevron_right"
            label="Next page"
            className="text-[#44474e]"
            disabled={page * size >= total}
            onClick={() => dispatch({ type: 'page', page: page + 1 })}
          />
        </div>
      )}
    </Box>
  )
}

/** `_Drop`: native select with an "all" entry ('' sentinel) that gives null. */
function Drop({
  label,
  allLabel = 'All',
  value,
  items,
  width,
  onChange,
}: {
  label: string
  allLabel?: string
  value: string | null
  items: Record<string, string>
  width: number
  onChange: (value: string | null) => void
}) {
  const options = [
    { value: '', label: allLabel },
    ...Object.entries(items).map(([key, text]) => ({ value: key, label: text })),
  ]
  return (
    <div className="shrink-0" style={{ width }}>
      <Select
        dense
        label={label}
        value={value != null && Object.hasOwn(items, value) ? value : ''}
        options={options}
        onChange={(next) => onChange(next === '' ? null : next)}
      />
    </div>
  )
}

/** `_StatusFilterChip`: r8 outlined chip, 12 px label. */
export function StatusFilterChip({
  label,
  selected,
  onClick,
}: {
  label: string
  selected: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={clsx(
        'rounded-lg border px-[13px] py-2.5 text-xs leading-[18px] focus-visible:outline-2 focus-visible:outline-brand-blue-light',
        selected
          ? 'border-accent-blue bg-brand-blue-100 font-extrabold text-primary-blue'
          : 'border-[#dde6f1] bg-white font-semibold text-text-secondary hover:bg-black/4',
      )}
    >
      {label}
    </button>
  )
}
