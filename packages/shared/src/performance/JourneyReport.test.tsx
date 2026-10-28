// The Journeys tab of the Performance report and its journey detail dialog.
import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { parseJourneyDetailReport } from '../models/performance'
import { journeyLearnersCsv, journeyStatusLabel } from './JourneyDetailDialog'
import { PerformanceReport } from './PerformanceReport'
import { initialReportState, reportReducer } from './state'
import { renderReport, stubReportApi, stubResize } from './testUtils'

beforeEach(() => stubResize())

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const journey = {
  journey_id: 'j1',
  title: 'Markets Foundation',
  journey_status: 'published',
  step_count: 2,
  required_count: 2,
  certificate_enabled: true,
  assigned: 3,
  unique_learners: 3,
  completed: 1,
  started: 1,
  pending: 0,
  waiting: 0,
  overdue: 1,
  removed: 0,
  due_soon: 0,
  inactive: 0,
  completion_rate: 33,
  average_progress: 50,
  certificates: 1,
}

const learner = (patch: Record<string, unknown>) => ({
  journey_id: 'j1',
  employee_id: 'e1',
  employee_name: 'Asha Verma',
  employee_status: 'active',
  department: 'Sales',
  status: 'started',
  assigned_at: '2026-10-01T10:00:00',
  deadline: '2026-10-31T10:00:00',
  passed_count: 1,
  required_count: 2,
  completion_percent: 50,
  current_step: 2,
  current_course_id: 'c2',
  current_course_name: 'Equity Basics',
  due_soon: false,
  inactive: false,
  ...patch,
})

const detail = {
  journey,
  steps: [
    {
      course_id: 'c1',
      course_name: 'Indian Market Structure',
      step_number: 1,
      is_required: true,
      unlock_rule: 'open',
      learners: 3,
      passed: 2,
      in_progress: 0,
      available: 1,
      locked: 0,
      unavailable: 0,
    },
    {
      course_id: 'c2',
      course_name: 'Equity Basics',
      step_number: 2,
      is_required: true,
      unlock_rule: 'after_previous',
      learners: 3,
      passed: 1,
      in_progress: 1,
      available: 0,
      locked: 1,
      unavailable: 0,
    },
  ],
  learners: [
    learner({}),
    learner({
      employee_id: 'e2',
      employee_name: 'Rohan Mehta',
      status: 'completed',
      passed_count: 2,
      completion_percent: 100,
      current_step: null,
      current_course_name: null,
      completed_at: '2026-10-20T10:00:00',
      certificate_number: 'PCIL-LJ-AAAA-BBBB-CCCC',
    }),
    learner({ employee_id: 'e3', employee_name: 'Meera Iyer', status: 'overdue', passed_count: 0 }),
  ],
  generated_at: '2026-10-27T10:00:00',
}

const requests: URL[] = []

function stubJourneys(enabled = true) {
  requests.length = 0
  return stubReportApi(['all_courses'], (url) => {
    requests.push(url)
    const path = url.pathname
    if (path.endsWith('/options'))
      return { courses: [], departments: [], mailing_lists: [], journeys_enabled: enabled }
    if (path.endsWith('/performance/journeys'))
      return { enabled, journeys: [journey], generated_at: '2026-10-27T10:00:00' }
    if (path.endsWith('/performance/journeys/j1')) return detail
    if (path.includes('/certificates/'))
      return new Response(new Blob(['%PDF-1.4']), { status: 200 })
    return {}
  })
}

const requested = (suffix: string) => requests.filter((url) => url.pathname.endsWith(suffix))

it('adds a Journeys tab with the course cards layout', async () => {
  stubJourneys()
  renderReport(<PerformanceReport app="trainer" />, { withReport: false })
  const tab = await screen.findByRole('tab', { name: 'Journeys' })
  expect(screen.getAllByRole('tab').map((item) => item.textContent)).toEqual([
    'Overview',
    'Courses',
    'Journeys',
    'Employees',
  ])
  // Journeys are worked out only once their tab opens.
  expect(requested('/performance/journeys')).toHaveLength(0)
  await userEvent.click(tab)
  expect(screen.getByText('Journey performance')).toBeInTheDocument()
  const card = await screen.findByRole('button', { name: /Markets Foundation/ })
  expect(card).toHaveTextContent('2 courses')
  expect(card).toHaveTextContent('33%')
  expect(card).toHaveTextContent('3assigned')
  expect(card).toHaveTextContent('1overdue')
  expect(screen.getByText('1 matching learning journeys')).toBeInTheDocument()
})

it('hides the Journeys tab when Learning Journeys are off', async () => {
  stubJourneys(false)
  renderReport(
    <PerformanceReport
      app="trainer"
      linkedReport={{ courseId: null, status: null, journeyId: 'j1' }}
    />,
    {
      withReport: false,
    },
  )
  await waitFor(() =>
    expect(screen.getByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'true'),
  )
  expect(screen.queryByRole('tab', { name: 'Journeys' })).toBeNull()
  expect(requested('/performance/journeys/j1')).toHaveLength(0)
})

it('opens a journey with its courses, learners, CSV and certificates', async () => {
  const user = userEvent.setup()
  const fetchMock = stubJourneys()
  const created = vi.fn(() => 'blob:certificate')
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() }))
  renderReport(
    <PerformanceReport
      app="trainer"
      linkedReport={{ courseId: null, status: null, journeyId: 'j1' }}
    />,
    { withReport: false },
  )
  const dialog = await screen.findByRole('dialog', { name: 'Markets Foundation' })
  // The open dialog hides the page behind it from assistive technology.
  expect(screen.getByRole('tab', { name: 'Journeys', hidden: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  expect(within(dialog).getByText('Course outcomes')).toBeInTheDocument()
  expect(within(dialog).getByText('2 courses in this journey')).toBeInTheDocument()
  expect(within(dialog).getByText('2/3 completed')).toBeInTheDocument()
  expect(within(dialog).getByText('Opens anytime')).toBeInTheDocument()
  expect(within(dialog).getByText('1 certificate earned')).toBeInTheDocument()
  expect(within(dialog).getAllByText('Step 2 · Equity Basics')).toHaveLength(2)
  expect(within(dialog).getByText('Finished 20 Oct 2026')).toBeInTheDocument()

  // Status filters show only the statuses someone has, plus the usual ones.
  const filters = within(dialog)
    .getAllByRole('button', { pressed: false })
    .map((button) => button.textContent)
  expect(filters).toEqual(['Pending', 'Started', 'Overdue', 'Completed'])
  await user.click(within(dialog).getByRole('button', { name: 'Overdue' }))
  expect(within(dialog).getByText('1 of 3 learners')).toBeInTheDocument()
  expect(within(dialog).queryByText('Asha Verma')).toBeNull()
  await user.click(within(dialog).getByRole('button', { name: 'All' }))
  await user.type(within(dialog).getByRole('textbox', { name: 'Search learners' }), 'rohan')
  expect(within(dialog).getByText('1 of 3 learners')).toBeInTheDocument()

  await user.click(
    within(dialog).getByRole('button', { name: 'Download certificate for Rohan Mehta' }),
  )
  await waitFor(() => expect(created).toHaveBeenCalled())
  const certificate = fetchMock.mock.calls
    .map(([input]) => new URL(String(input), 'http://localhost'))
    .find((url) => url.pathname.includes('/certificates/'))
  expect(certificate?.pathname).toBe('/api/trainer/performance/journeys/j1/certificates/e2')
  expect(certificate?.searchParams.get('view')).toBe('all_courses')
})

it('opens the Journeys tab from a link and closes the detail', () => {
  const state = initialReportState('trainer', { courseId: null, status: null, journeyId: 'j1' })
  expect(state.view).toBe(3)
  expect(state.openJourneyId).toBe('j1')
  const closed = reportReducer(state, { type: 'openJourney', journeyId: null })
  expect(closed.openJourneyId).toBeNull()
  const relinked = reportReducer(
    { ...closed, view: 0, status: 'overdue' },
    { type: 'openLinked', courseId: null, status: null, journeyId: 'j2' },
  )
  expect([relinked.view, relinked.openJourneyId, relinked.status]).toEqual([3, 'j2', null])
  expect(relinked.filter.courseStatus).toBe('active')
})

it('opens a disabled journey with the history choice, which it is only listed under', () => {
  const link = { courseId: null, status: null, journeyId: 'j1', courseStatus: 'all' }
  expect(initialReportState('trainer', link).filter.courseStatus).toBe('all')
  const state = initialReportState('trainer')
  const relinked = reportReducer(state, { type: 'openLinked', ...link })
  expect([relinked.view, relinked.openJourneyId, relinked.filter.courseStatus]).toEqual([
    3,
    'j1',
    'all',
  ])
})

it('words learner statuses like the course rows and exports them as CSV', () => {
  const { learners } = parseJourneyDetailReport({
    ...detail,
    learners: [
      learner({ employee_name: 'Rao, Anil "AR"', status: 'started', due_soon: true }),
      learner({ employee_id: 'e9', status: 'removed' }),
    ],
  })
  expect(learners.map(journeyStatusLabel)).toEqual(['Due soon', 'Removed'])
  const [header, first] = journeyLearnersCsv(learners).replace('﻿', '').split('\r\n')
  expect(header).toMatch(/^Employee ID,Name,Department,Status/)
  expect(first).toBe(
    'e1,"Rao, Anil ""AR""",Sales,Due soon,1,2,Equity Basics,1 Oct 2026,31 Oct 2026,,,',
  )
})
