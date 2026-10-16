// Dart: frontend/lib/features/performance/employee_summary_panel.dart:1-405 (EmployeeSummaryPanel,
// EmployeeSummaryTable) and :820-1020 (_Surface, _Metric, _Identity, _Completion, _Badge, _Select,
// helpers). Mount: performance_report_portal.dart:614-623 (scopeKey, revision, resetVersion).
import { useQuery, type QueryKey } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { errorMessage } from '../api/client'
import { parseEmployeeListReport, type EmployeeReportRow } from '../models/performance'
import { Button, IconButton } from '../ui/Button'
import { Icon, type IconName } from '../ui/icons/Icon'
import { ProgressBar } from '../ui/ProgressBar'
import { Select, TextField } from '../ui/TextField'
import { useMainReport, useReport, useViewAllowed } from './context'
import { colors, percent } from './format'
import { scopeParams, without, type Params } from './state'
import { Badge, Completion, Identity, Metric } from './employeeParts'
import { useElementWidth } from './useElementWidth'

const attentionOptions = [
  { value: 'all', label: 'All employees' },
  { value: 'needs_attention', label: 'Needs attention' },
  { value: 'overdue', label: 'Has overdue courses' },
  { value: 'completed', label: 'All courses completed' },
] as const

const sortOptions = [
  { value: 'employee', label: 'Employee name' },
  { value: 'assigned', label: 'Assigned courses' },
  { value: 'completion', label: 'Completion rate' },
  { value: 'overdue', label: 'Overdue courses' },
  { value: 'score', label: 'Quiz score' },
] as const

type Attention = (typeof attentionOptions)[number]['value']
type Sort = (typeof sortOptions)[number]['value']

interface PanelState {
  /** The text box. */
  text: string
  /** `submittedSearch`: the text of the last search. */
  search: string
  attention: Attention
  sort: Sort
  descending: boolean
  page: number
}

const initialPanel: PanelState = {
  text: '',
  search: '',
  attention: 'all',
  sort: 'employee',
  descending: false,
  page: 1,
}

// InkWell hover: a 4% black overlay above the fill, below the content.
const ink =
  'cursor-pointer text-left hover:shadow-[inset_0_0_0_999px_rgb(0_0_0/0.04)] focus-visible:outline-2 focus-visible:outline-brand-blue-light'

/** The "Employee summary" list of the Employees tab. It owns its search, filter, sort and page. */
export function EmployeeSummaryPanel({
  onOpenEmployee,
  onExport,
}: {
  onOpenEmployee: (employeeId: string) => void
  onExport: (params: Params) => Promise<void>
}) {
  const { state, contextKey, baseKey, get } = useReport()
  const allowed = useViewAllowed()
  const [panel, setPanel] = useState(initialPanel)
  const [exporting, setExporting] = useState(false)
  const searchDelay = useRef<ReturnType<typeof setTimeout>>(undefined)

  // revision: the overview generated_at, so Refresh reloads the list. The last known value is
  // kept while a new overview loads.
  const generatedAt = useMainReport().overview?.generatedAt
  const [revision, setRevision] = useState(generatedAt ?? '')
  if (generatedAt != null && generatedAt !== revision) setRevision(generatedAt)

  // didUpdateWidget: a new reset version clears the controls. A new scope, revision or reset
  // version submits the text box again and goes back to page 1.
  const resetVersion = state.employeeResetVersion
  const scopeKey = `${contextKey}|${state.filter.joinedLessThanDaysAgo}|${revision}`
  const [seen, setSeen] = useState({ resetVersion, scopeKey })
  if (seen.resetVersion !== resetVersion || seen.scopeKey !== scopeKey) {
    setSeen({ resetVersion, scopeKey })
    setPanel(
      seen.resetVersion !== resetVersion
        ? initialPanel
        : (current) => ({ ...current, search: current.text.trim(), page: 1 }),
    )
  }
  useEffect(() => () => clearTimeout(searchDelay.current), [resetVersion, scopeKey])

  const filters: Params = {
    ...(panel.search ? { search: panel.search } : {}),
    ...(panel.attention !== 'all' ? { attention: panel.attention } : {}),
    sort: panel.sort,
    descending: String(panel.descending),
  }
  const params: Params = {
    ...without(scopeParams(state), 'employee_id'),
    ...filters,
    page: String(panel.page),
  }
  const query = useQuery({
    queryKey: [...baseKey, 'employees', params, revision] as QueryKey,
    queryFn: async () => parseEmployeeListReport(await get('employees', params)),
    enabled: allowed,
    // `_load` runs on every change, also when the answer for these params is cached.
    staleTime: 0,
  })
  const loading = query.isFetching || query.isPending
  // `_load` empties the data before each request, so the results hide while one runs.
  const data = loading ? undefined : query.data
  const error = loading || query.error == null ? null : errorMessage(query.error)

  const update = (change: Partial<PanelState>) => setPanel((current) => ({ ...current, ...change }))

  // _search: always loads, also when the search did not change.
  const submit = (text: string) => {
    clearTimeout(searchDelay.current)
    const search = text.trim()
    if (search === panel.search && panel.page === 1) void query.refetch()
    else update({ search, page: 1 })
  }

  const runExport = async () => {
    setExporting(true)
    try {
      await onExport(filters)
    } finally {
      setExporting(false)
    }
  }

  const summary = data?.summary ?? {}
  const total = data?.total ?? 0
  const size = data?.pageSize || 25
  const page = panel.page
  return (
    <div className="rounded-2xl border border-[#e3ebf5] bg-white p-5">
      <h3 className="m-0 text-[19px] font-extrabold">Employee performance</h3>
      <p className="m-0 mt-1 text-xs text-text-secondary">
        One row per employee · Your selected reporting scope and current filters.
      </p>
      <div className="mt-[18px] flex flex-wrap items-center gap-2.5">
        <div className="relative w-[270px]">
          <TextField
            dense
            icon="search"
            type="search"
            aria-label="Search employee name or ID"
            placeholder="Search employee name or ID"
            className="pr-11 [&::-webkit-search-cancel-button]:hidden"
            value={panel.text}
            onChange={(event) => {
              const text = event.target.value
              update({ text })
              clearTimeout(searchDelay.current)
              searchDelay.current = setTimeout(() => submit(text), 350)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') submit(panel.text)
            }}
          />
          <IconButton
            icon="close"
            size={18}
            label="Clear employee search"
            className="absolute top-0 right-0"
            onClick={() => {
              update({ text: '' })
              submit('')
            }}
          />
        </div>
        <Button disabled={loading} onClick={() => submit(panel.text)}>
          Search
        </Button>
        <Select
          dense
          label="Attention"
          className="w-[195px]"
          value={panel.attention}
          options={attentionOptions}
          onChange={(attention) => update({ attention, page: 1 })}
        />
        <Select
          dense
          label="Sort by"
          className="w-[195px]"
          value={panel.sort}
          options={sortOptions}
          onChange={(sort) => update({ sort, page: 1 })}
        />
        <IconButton
          icon={panel.descending ? 'arrow_downward' : 'arrow_upward'}
          label={panel.descending ? 'Sort ascending' : 'Sort descending'}
          onClick={() => update({ descending: !panel.descending, page: 1 })}
        />
        <Button
          variant="secondary"
          icon="download_outlined"
          disabled={loading || exporting || error != null || data == null}
          onClick={() => void runExport()}
        >
          {exporting ? 'Exporting…' : 'Export employees CSV'}
        </Button>
      </div>
      {loading && <ProgressBar className="mt-4" label="Loading employees" />}
      {error != null && (
        <div className="flex flex-col items-start py-5">
          <p className="m-0 text-[#f44336]">Could not load employees. Exception: {error}</p>
          <Button variant="text" onClick={() => void query.refetch()}>
            Retry
          </Button>
        </div>
      )}
      {data && (
        <>
          <Metrics summary={summary} />
          <div className="h-[18px]" />
          {data.rows.length === 0 ? (
            <p className="m-0 p-[30px] text-center">No matching employees.</p>
          ) : (
            <EmployeeSummaryTable rows={data.rows} onOpenEmployee={onOpenEmployee} />
          )}
          <p className="m-0 mt-3 text-xs text-text-secondary">
            Select an employee to see their courses. Completion = completed courses ÷ assigned
            courses.
          </p>
          {total > size && (
            <div className="flex items-center">
              <span className="flex-1 text-xs">
                Showing {(page - 1) * size + 1}–{Math.min(page * size, total)} of {total} employees
              </span>
              <IconButton
                icon="chevron_left"
                label="Previous employee page"
                disabled={page <= 1}
                onClick={() => update({ page: page - 1 })}
              />
              <span>
                {page} / {Math.ceil(total / size)}
              </span>
              <IconButton
                icon="chevron_right"
                label="Next employee page"
                disabled={page * size >= total}
                onClick={() => update({ page: page + 1 })}
              />
            </div>
          )}
        </>
      )}
    </div>
  )
}

/** The four `_Metric` cards: 4 columns above 750, 2 above 390, else 1. */
function Metrics({ summary }: { summary: Record<string, number> }) {
  const ref = useRef<HTMLDivElement>(null)
  const width = useElementWidth(ref)
  const count = width > 750 ? 4 : width > 390 ? 2 : 1
  const metrics: { label: string; key: string; icon: IconName; color: string }[] = [
    { label: 'Employees', key: 'employees', icon: 'people_outline', color: colors.primaryBlue },
    {
      label: 'Assigned courses',
      key: 'assigned',
      icon: 'menu_book_outlined',
      color: colors.primaryBlue,
    },
    {
      label: 'Completed courses',
      key: 'completed',
      icon: 'check_circle_outline',
      color: colors.green,
    },
    { label: 'Overdue assignments', key: 'overdue', icon: 'error_outline', color: colors.red },
  ]
  return (
    <div
      ref={ref}
      className="mt-[18px] grid gap-2.5"
      style={{ gridTemplateColumns: `repeat(${count}, minmax(0, 1fr))` }}
    >
      {metrics.map((metric) => (
        <Metric
          key={metric.key}
          label={metric.label}
          value={summary[metric.key] ?? 0}
          icon={metric.icon}
          color={metric.color}
        />
      ))}
    </div>
  )
}

const header = 'text-[10px] font-extrabold text-text-secondary'

/** EmployeeSummaryTable: a table at 850 and wider, stacked rows below. */
function EmployeeSummaryTable({
  rows,
  onOpenEmployee,
}: {
  rows: EmployeeReportRow[]
  onOpenEmployee: (employeeId: string) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const wide = useElementWidth(ref) >= 850
  return (
    <div ref={ref}>
      {wide && (
        <div className="flex items-center rounded-lg bg-[#f3f7fc] p-3.5">
          <span className={`${header} flex-[3]`}>EMPLOYEE</span>
          <span className={`${header} flex-1`}>ASSIGNED</span>
          <span className={`${header} flex-1`}>COMPLETED</span>
          <span className={`${header} flex-[2]`}>COMPLETION</span>
          <span className={`${header} flex-1`}>OVERDUE</span>
          <span className={`${header} flex-1`}>AVG. QUIZ</span>
          <span className="w-6" />
        </div>
      )}
      {rows.map((row) => (
        <button
          key={row.employeeId}
          type="button"
          className={`${ink} block w-full border-b border-[#e6edf5] bg-white px-3.5 py-4`}
          onClick={() => onOpenEmployee(row.employeeId)}
        >
          {wide ? <WideRow row={row} /> : <NarrowRow row={row} />}
        </button>
      ))}
    </div>
  )
}

const overdueColor = (row: EmployeeReportRow) =>
  row.overdue > 0 ? colors.red : colors.textSecondary

function WideRow({ row }: { row: EmployeeReportRow }) {
  return (
    <div className="flex items-center">
      <div className="min-w-0 flex-[3]">
        <Identity employee={row} />
      </div>
      <span className="flex-1 font-bold">{row.assigned}</span>
      <span className="flex-1">{row.completed}</span>
      <div className="min-w-0 flex-[2] pr-6">
        <Completion rate={row.completionRate} />
      </div>
      <div className="flex-1">
        <Badge text={String(row.overdue)} color={overdueColor(row)} />
      </div>
      <span className="flex-1">{percent(row.averageScore)}</span>
      <Icon name="chevron_right" size={24} className="text-text-secondary" />
    </div>
  )
}

function NarrowRow({ row }: { row: EmployeeReportRow }) {
  return (
    <>
      <div className="flex items-center">
        <div className="min-w-0 flex-1">
          <Identity employee={row} />
        </div>
        <Icon name="chevron_right" size={24} />
      </div>
      <div className="mt-3">
        <Completion rate={row.completionRate} />
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1.5">
        <span>{row.assigned} assigned</span>
        <span>{row.completed} completed</span>
        <span style={{ color: overdueColor(row) }}>{row.overdue} overdue</span>
        <span>Quiz {percent(row.averageScore)}</span>
      </div>
    </>
  )
}
