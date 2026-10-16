// The Flutter tests have no overview case. These cover the contract in performance-contracts.md (b).
import { cleanup, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { parsePerformanceOverview } from '../models/performance'
import { useReport } from './context'
import { Overview } from './Overview'
import { renderReport, stubReportApi, stubResize } from './testUtils'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const row = (index: number) => ({
  assignment_id: `a${index}`,
  employee_id: `e${index}`,
  employee_name: `Employee ${index}`,
  course_id: 'c1',
  course_name: 'Excel Basics',
  status: 'overdue',
  deadline: '2026-10-11T00:00:00Z',
  completed_modules: 1,
  total_modules: 3,
})

const overview = (summary: Record<string, unknown> = {}, watchlist = [row(1)]) =>
  parsePerformanceOverview({
    summary: {
      current_assignments: 20,
      historical_assignments: 1,
      assigned: 20,
      unique_learners: 9,
      pending: 6,
      started: 5,
      completed: 5,
      overdue: 4,
      due_soon: 3,
      inactive: 2,
      repeated_failures: 1,
      completion_rate: 25,
      on_time_compliance: 80,
      on_time_denominator: 5,
      average_score: 91.5,
      scored_modules: 17,
      ...summary,
    },
    breakdowns: {
      courses: [{ label: 'Excel Basics', completion_rate: 40 }],
      departments: [],
      mailing_lists: [],
    },
    watchlist,
    due_soon_days: 3,
    inactive_days: 14,
  })

/** Shows the report state so a test can read the dispatched view and status. */
function Probe() {
  const { state } = useReport()
  return (
    <output aria-label="state">
      {state.view}:{state.status ?? 'none'}:{String(state.employeeSummary)}
    </output>
  )
}

function renderOverview(data = overview(), onOpenAssignment = vi.fn()) {
  stubResize()
  stubReportApi(['all_courses'], () => ({}))
  renderReport(
    <>
      <Overview overview={data} isLoading={false} onOpenAssignment={onOpenAssignment} />
      <Probe />
    </>,
  )
  return onOpenAssignment
}

/**
 * The card button that holds `text`. jsdom has no Tailwind, so the card spans stay inline and
 * the accessible name joins them without spaces. Find the card by its text instead.
 */
async function cardButton(text: string) {
  const button = (await screen.findByText(text)).closest('button')
  if (!button) throw new Error(`No button holds "${text}"`)
  return button
}

it('shows the KPI values and the scope line', async () => {
  renderOverview()
  expect(
    await screen.findByText('20 current assignments · 1 retained historical records'),
  ).toBeInTheDocument()
  expect(screen.getByText('9 unique employees')).toBeInTheDocument()
  expect(screen.getByText('25%')).toBeInTheDocument()
  expect(screen.getByText('5 assignments')).toBeInTheDocument()
  expect(screen.getByText('80%')).toBeInTheDocument()
  expect(screen.getByText('5 deadlines passed')).toBeInTheDocument()
  expect(screen.getByText('91.5%')).toBeInTheDocument()
  expect(screen.getByText('17 scored modules')).toBeInTheDocument()
})

it("shows '-' for a missing compliance and score", async () => {
  renderOverview(overview({ on_time_compliance: null, average_score: null }))
  await screen.findByText('On-time compliance')
  expect(screen.getAllByText('-')).toHaveLength(2)
})

it('opens the completed assignments from the Completed card', async () => {
  renderOverview()
  expect(screen.getByLabelText('state')).toHaveTextContent('0:none:true')
  await userEvent.click(await cardButton('5 assignments'))
  expect(screen.getByLabelText('state')).toHaveTextContent('2:completed:false')
})

it('opens each attention status', async () => {
  renderOverview()
  const state = screen.getByLabelText('state')
  const overdue = await cardButton('Incomplete past due date')
  expect(overdue).toHaveTextContent('Overdue4')
  await userEvent.click(overdue)
  expect(state).toHaveTextContent('2:overdue:false')
  const dueSoon = await cardButton('Within 3 days')
  expect(dueSoon).toHaveTextContent('Due soon3')
  await userEvent.click(dueSoon)
  expect(state).toHaveTextContent('2:due_soon:false')
  const inactive = await cardButton('For 14 days')
  expect(inactive).toHaveTextContent('No learning activity2')
  await userEvent.click(inactive)
  expect(state).toHaveTextContent('2:inactive:false')
  const failures = await cardButton('Repeated quiz failures')
  expect(failures).toHaveTextContent('Repeated quiz failures1')
  await userEvent.click(failures)
  expect(state).toHaveTextContent('2:repeated_failures:false')
})

it('lists 5 watchlist rows and counts the rest', async () => {
  const onOpen = renderOverview(overview({}, [1, 2, 3, 4, 5, 6, 7].map(row)))
  expect(await screen.findByText('EMPLOYEE')).toBeInTheDocument()
  expect(screen.getByText('Employee 5')).toBeInTheDocument()
  expect(screen.queryByText('Employee 6')).not.toBeInTheDocument()
  expect(screen.getByText('2 more in this watchlist')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Employee 2/ }))
  expect(onOpen).toHaveBeenCalledWith('a2')
})

it('shows the empty texts', async () => {
  renderOverview(overview({}, []))
  expect(await screen.findByText('No assignments currently need attention.')).toBeInTheDocument()
  expect(screen.getByText('No department data yet.')).toBeInTheDocument()
  expect(screen.getByText('No mailing list data yet.')).toBeInTheDocument()
})

it('opens the courses tab from Completion by course', async () => {
  renderOverview()
  const panel = (await screen.findByText('Completion by course')).closest('div')!.parentElement!
  await userEvent.click(within(panel).getByRole('button', { name: 'View all' }))
  expect(screen.getByLabelText('state')).toHaveTextContent('1:none:true')
})

it('shows the empty box when there is no data and nothing loads', async () => {
  stubResize()
  stubReportApi(['all_courses'], () => ({}))
  renderReport(<Overview overview={undefined} isLoading={false} onOpenAssignment={vi.fn()} />)
  expect(await screen.findByText('No performance data available.')).toBeInTheDocument()
})

it('shows zero counts while the first overview loads', async () => {
  stubResize()
  stubReportApi(['all_courses'], () => ({}))
  renderReport(<Overview overview={undefined} isLoading onOpenAssignment={vi.fn()} />)
  expect(
    await screen.findByText('0 current assignments · 0 retained historical records'),
  ).toBeInTheDocument()
  expect(screen.queryByText('No performance data available.')).not.toBeInTheDocument()
})
