// Dart: frontend/test/employee_summary_panel_test.dart:1-145 (panel and table parts).
import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { useReport } from './context'
import { EmployeeSummaryPanel } from './EmployeeSummaryPanel'
import { renderReport, stubReportApi, stubResize } from './testUtils'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const employee = {
  employee_id: 'e1',
  employee_name: 'Kavya Nair',
  department: 'Sales',
  assigned: 8,
  completed: 5,
  in_progress: 2,
  not_started: 1,
  completion_rate: 62.5,
  overdue: 1,
  due_soon: 2,
  average_score: 78.0,
  needs_attention: true,
  repeated_failures: 1,
}

const page = (extra: Record<string, unknown> = {}) => ({
  rows: [employee],
  total: 1,
  page_size: 25,
  summary: { employees: 1, assigned: 8, completed: 5, overdue: 1 },
  ...extra,
})

/** Stubs the API. `employees` answers the list request; it gets the request URL. */
function stubApi(employees: (url: URL) => unknown) {
  const calls: URL[] = []
  stubReportApi(['all_courses'], (url) => {
    if (url.pathname.endsWith('/overview')) return { generated_at: '2026-10-16T10:00:00Z' }
    if (url.pathname.endsWith('/employees')) {
      calls.push(url)
      return employees(url)
    }
    return {}
  })
  return calls
}

/** Gives the test the report dispatch. */
function Harness({
  onOpenEmployee = () => {},
  onExport = async () => {},
}: {
  onOpenEmployee?: (id: string) => void
  onExport?: (params: Record<string, string>) => Promise<void>
}) {
  const { dispatch } = useReport()
  return (
    <>
      <button type="button" onClick={() => dispatch({ type: 'clearFilters' })}>
        Clear filters
      </button>
      <EmployeeSummaryPanel onOpenEmployee={onOpenEmployee} onExport={onExport} />
    </>
  )
}

const exportButton = () => screen.getByRole('button', { name: /Export employees CSV|Exporting/ })

/** The first answer has no overview revision yet, so the list loads twice (Dart parity). */
async function settled(calls: URL[], count = 2) {
  await waitFor(() => {
    expect(calls).toHaveLength(count)
    expect(screen.queryByRole('progressbar', { name: 'Loading employees' })).toBeNull()
    expect(exportButton()).toBeEnabled()
  })
}

it.each([
  [1100, true],
  [375, false],
])('opens the employee detail at width %i', async (width, wide) => {
  stubResize(width)
  const calls = stubApi(() => page())
  const opened: string[] = []
  renderReport(<Harness onOpenEmployee={(id) => opened.push(id)} />)
  await settled(calls)
  expect(screen.getByText('Kavya Nair')).toBeInTheDocument()
  expect(screen.getByText('62.5%')).toBeInTheDocument()
  expect(screen.queryByText('EMPLOYEE') != null).toBe(wide)
  expect(screen.queryByText('8 assigned') == null).toBe(wide)
  await userEvent.click(screen.getByText('Kavya Nair'))
  expect(opened).toEqual(['e1'])
})

it('debounces typing, Enter submits the full name and export takes the filters', async () => {
  stubResize()
  const calls = stubApi(() => page())
  const exports: Record<string, string>[] = []
  renderReport(<Harness onExport={async (params) => void exports.push(params)} />)
  await settled(calls)
  await userEvent.click(exportButton())
  expect(exports.at(-1)).toEqual({ sort: 'employee', descending: 'false' })

  const box = screen.getByRole('searchbox', { name: 'Search employee name or ID' })
  vi.useFakeTimers()
  fireEvent.change(box, { target: { value: 'ka' } })
  act(() => void vi.advanceTimersByTime(200))
  expect(calls).toHaveLength(2)
  fireEvent.change(box, { target: { value: 'Kavya Nair' } })
  fireEvent.keyDown(box, { key: 'Enter' })
  act(() => void vi.advanceTimersByTime(1000))
  vi.useRealTimers()
  await settled(calls, 3)
  expect(calls.at(-1)!.searchParams.get('search')).toBe('Kavya Nair')
  expect(calls.at(-1)!.searchParams.get('page')).toBe('1')

  await userEvent.click(exportButton())
  expect(exports.at(-1)).toEqual({ search: 'Kavya Nair', sort: 'employee', descending: 'false' })
  await userEvent.selectOptions(screen.getByLabelText('Attention'), 'Needs attention')
  await settled(calls, 4)
  await userEvent.click(exportButton())
  expect(exports.at(-1)).toEqual({
    search: 'Kavya Nair',
    attention: 'needs_attention',
    sort: 'employee',
    descending: 'false',
  })
})

it('submits the search 350 ms after the last keystroke', async () => {
  stubResize()
  const calls = stubApi(() => page())
  renderReport(<Harness />)
  await settled(calls)
  vi.useFakeTimers()
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: ' Kavya ' } })
  act(() => void vi.advanceTimersByTime(349))
  expect(calls).toHaveLength(2)
  act(() => void vi.advanceTimersByTime(1))
  vi.useRealTimers()
  await settled(calls, 3)
  expect(calls.at(-1)!.searchParams.get('search')).toBe('Kavya')
})

it('disables export while loading, after an error and while exporting', async () => {
  stubResize()
  let fail = true
  let finish = () => {}
  const calls = stubApi(() =>
    fail ? new Response('{}', { status: 400 }) : page({ total: 1, summary: {} }),
  )
  renderReport(<Harness onExport={() => new Promise<void>((resolve) => void (finish = resolve))} />)
  expect(exportButton()).toBeDisabled()
  expect(
    await screen.findByText(
      'Could not load employees. Exception: Unable to load performance data (400)',
    ),
  ).toBeInTheDocument()
  expect(exportButton()).toBeDisabled()
  fail = false
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
  await settled(calls, calls.length)
  await userEvent.click(exportButton())
  expect(exportButton()).toHaveTextContent('Exporting…')
  expect(exportButton()).toBeDisabled()
  act(() => finish())
  await waitFor(() => expect(exportButton()).toHaveTextContent('Export employees CSV'))
  expect(exportButton()).toBeEnabled()
})

it('pages the list and goes back to page 1 when the report refreshes', async () => {
  stubResize()
  let generatedAt = 'g1'
  const calls: URL[] = []
  stubReportApi(['all_courses'], (url) => {
    if (url.pathname.endsWith('/overview')) return { generated_at: generatedAt }
    if (url.pathname.endsWith('/employees')) {
      calls.push(url)
      return page({ total: 30 })
    }
    return {}
  })
  const { client } = renderReport(<Harness />)
  await settled(calls)
  expect(screen.getByText('Showing 1–25 of 30 employees')).toBeInTheDocument()
  expect(screen.getByText('1 / 2')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Previous employee page' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Next employee page' }))
  await settled(calls, 3)
  expect(calls.at(-1)!.searchParams.get('page')).toBe('2')
  expect(screen.getByText('Showing 26–30 of 30 employees')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Next employee page' })).toBeDisabled()

  generatedAt = 'g2'
  await act(() => client.refetchQueries({ predicate: (query) => query.queryKey[3] === 'overview' }))
  await settled(calls, 4)
  expect(calls.at(-1)!.searchParams.get('page')).toBe('1')
})

it('clears the controls when the filters are cleared', async () => {
  stubResize()
  const calls = stubApi(() => page())
  renderReport(<Harness />)
  await settled(calls)
  await userEvent.type(screen.getByRole('searchbox'), 'Kavya{Enter}')
  await userEvent.selectOptions(screen.getByLabelText('Sort by'), 'Quiz score')
  await userEvent.click(screen.getByRole('button', { name: 'Sort descending' }))
  await waitFor(() => expect(calls.at(-1)!.searchParams.get('descending')).toBe('true'))
  expect(calls.at(-1)!.searchParams.get('sort')).toBe('score')
  expect(calls.at(-1)!.searchParams.get('search')).toBe('Kavya')

  await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
  await waitFor(() => expect(calls.at(-1)!.searchParams.get('sort')).toBe('employee'))
  expect(calls.at(-1)!.searchParams.get('descending')).toBe('false')
  expect(calls.at(-1)!.searchParams.has('search')).toBe(false)
  expect(screen.getByRole('searchbox')).toHaveValue('')
  expect(screen.getByLabelText('Sort by')).toHaveValue('employee')
  expect(screen.getByRole('button', { name: 'Sort descending' })).toBeInTheDocument()
})

it('shows the empty text when no employee matches', async () => {
  stubResize()
  const calls = stubApi(() => page({ rows: [], total: 0 }))
  renderReport(<Harness />)
  await settled(calls)
  expect(screen.getByText('No matching employees.')).toBeInTheDocument()
})
