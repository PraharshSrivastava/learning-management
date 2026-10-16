// The Flutter tests have no _assignments case. These cover the contract in
// performance-contracts.md (d): status chips, the 350 ms search, the reset and the pager.
import { act, cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { parseAssignmentListReport } from '../models/performance'
import { AssignmentsBox } from './AssignmentsBox'
import { useReport } from './context'
import { defaultFilter } from './state'
import { renderReport, stubReportApi, stubResize } from './testUtils'

beforeEach(() => {
  stubResize()
  stubReportApi(['all_courses'], () => ({}))
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const row = (index: number) => ({
  assignment_id: `a${index}`,
  employee_name: `Employee ${index}`,
  course_name: 'Excel Basics',
  status: 'started',
  completed_modules: 1,
  total_modules: 3,
})

const list = (total: number, count = Math.min(total, 25)) =>
  parseAssignmentListReport({
    rows: Array.from({ length: count }, (_, index) => row(index)),
    total,
    page_size: 25,
  })

/** Shows the report state and dispatches the actions the tests need. */
function Probe() {
  const { state, dispatch } = useReport()
  return (
    <>
      <output aria-label="state">
        {JSON.stringify({ status: state.status, search: state.search, page: state.page })}
      </output>
      <output aria-label="sort">{`${state.sort} ${state.descending}`}</output>
      <button onClick={() => dispatch({ type: 'clearFilters' })}>clear</button>
      <button
        onClick={() => dispatch({ type: 'filter', filter: { ...defaultFilter, courseId: 'c9' } })}
      >
        scope
      </button>
    </>
  )
}

const state = () =>
  JSON.parse(screen.getByLabelText('state').textContent) as Record<string, unknown>

function renderBox(data = list(3), onOpen = vi.fn()) {
  return renderReport(
    <>
      <Probe />
      <AssignmentsBox assignments={data} onOpenAssignment={onOpen} />
    </>,
  )
}

it('status chips and the More statuses select set the status', async () => {
  renderBox()
  await userEvent.click(screen.getByRole('button', { name: 'Overdue' }))
  expect(state().status).toBe('overdue')
  expect(screen.getByRole('button', { name: 'Overdue' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('combobox', { name: 'More statuses' })).toHaveValue('')
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'More statuses' }), 'pending')
  expect(state().status).toBe('pending')
  expect(screen.getByRole('button', { name: 'Overdue' })).toHaveAttribute('aria-pressed', 'false')
  await userEvent.click(screen.getByRole('button', { name: 'All' }))
  expect(state().status).toBeNull()
})

it('sort select and direction button update the sort', async () => {
  renderBox()
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sort by' }), 'score')
  expect(screen.getByLabelText('sort')).toHaveTextContent('score false')
  await userEvent.click(screen.getByRole('button', { name: 'Sort descending' }))
  expect(screen.getByLabelText('sort')).toHaveTextContent('score true')
  expect(screen.getByRole('button', { name: 'Sort ascending' })).toBeInTheDocument()
})

const searchBox = () => screen.getByRole('textbox', { name: 'Search employee name, ID or course' })

function fakeTimers() {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
}

it('assignment typing is debounced for 350 ms', async () => {
  const user = fakeTimers()
  renderBox()
  await user.type(searchBox(), 'Ad')
  act(() => vi.advanceTimersByTime(200))
  await user.type(searchBox(), 'itya ')
  act(() => vi.advanceTimersByTime(200))
  expect(state().search).toBe('')
  act(() => vi.advanceTimersByTime(160))
  expect(state().search).toBe('Aditya')
})

it('Enter applies the search at once', async () => {
  const user = fakeTimers()
  renderBox()
  await user.type(searchBox(), 'Neha{Enter}')
  expect(state().search).toBe('Neha')
})

it('a scope change cancels the pending search', async () => {
  const user = fakeTimers()
  renderBox()
  await user.type(searchBox(), 'Neha')
  await user.click(screen.getByRole('button', { name: 'scope' }))
  act(() => vi.advanceTimersByTime(400))
  expect(state().search).toBe('')
})

it('a filter reset clears the search text and cancels the pending search', async () => {
  const user = fakeTimers()
  renderBox()
  await user.type(searchBox(), 'Neha')
  await user.click(screen.getByRole('button', { name: 'clear' }))
  expect(searchBox()).toHaveValue('')
  act(() => vi.advanceTimersByTime(400))
  expect(state().search).toBe('')
})

it('shows the pager when the total is above the page size', async () => {
  renderBox(list(60))
  expect(screen.getByText('60 assignments')).toBeInTheDocument()
  expect(screen.getByText('Showing 1–25 of 60')).toBeInTheDocument()
  expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
  await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
  expect(screen.getByText('Showing 51–60 of 60')).toBeInTheDocument()
  expect(screen.getByText('Page 3 of 3')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
})

it('opens a row and shows the empty text', async () => {
  const onOpen = vi.fn()
  renderBox(list(3), onOpen)
  expect(screen.queryByText('Showing', { exact: false })).not.toBeInTheDocument()
  await userEvent.click(screen.getByText('Employee 1'))
  expect(onOpen).toHaveBeenCalledWith('a1')
  cleanup()
  renderBox(list(0))
  expect(screen.getByText('No matching assignments.')).toBeInTheDocument()
  expect(screen.getByText('0 assignments')).toBeInTheDocument()
})
