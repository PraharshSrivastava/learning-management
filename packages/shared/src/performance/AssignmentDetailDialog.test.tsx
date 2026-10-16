// Dart: frontend/test/assignment_detail_dialog_test.dart, plus the access line, the latest 20
// attempts text, the load error and the access guard.
import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { AssignmentDetailDialog } from './AssignmentDetailDialog'
import { useReport } from './context'
import { colors } from './format'
import { renderReport, stubReportApi, stubResize } from './testUtils'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const detail = ({ completed = true }: { completed?: boolean } = {}) => ({
  assignment: {
    employee_name: 'Aarav Desai',
    course_name: 'Compliance Essentials',
    status: completed ? 'completed' : 'overdue',
    completion_percent: completed ? 100 : 33,
    completed_modules: completed ? 3 : 1,
    total_modules: 3,
    assigned_at: '2026-08-22T10:00:00',
    deadline: '2026-09-14T10:00:00',
    started_at: '2026-08-28T10:00:00',
    completed_at: completed ? '2026-09-11T10:00:00' : null,
    last_learner_activity_at: '2026-09-11T10:00:00',
    average_score: completed ? 70.0 : 30.0,
  },
  modules: [
    {
      module_id: 'm1',
      module_number: 1,
      title: 'Policies and conduct',
      num_questions: 0,
      video_watched: true,
      quiz_passed: false,
      attempt_count: 0,
      latest_score: null,
    },
    {
      module_id: 'm2',
      module_number: 2,
      title: 'KYC checks',
      num_questions: 5,
      video_watched: completed,
      quiz_passed: completed,
      attempt_count: 2,
      latest_score: completed ? 70.0 : 30.0,
    },
  ],
  attempts: [
    { module_id: 'm2', occurred_at: '2026-09-11T14:46:00', score: 30.0, passed: false },
    ...(completed
      ? [{ module_id: 'm2', occurred_at: '2026-09-11T14:46:00', score: 70.0, passed: true }]
      : []),
  ],
})

/** Opens the dialog once the access loaded, like a click in the loaded report. */
function Opened({ assignmentId, onClose }: { assignmentId: string; onClose: () => void }) {
  const { views } = useReport()
  return (
    <AssignmentDetailDialog
      assignmentId={views.length > 0 ? assignmentId : null}
      onClose={onClose}
    />
  )
}

/** The fills of the Meta icons next to `label`. */
const metaIconColors = (label: string) =>
  screen.getAllByText(label).map((text) => text.previousElementSibling?.getAttribute('fill'))

it('shows the learning path and quiz results', async () => {
  stubResize()
  const fetchMock = stubReportApi(['all_courses'], () => detail())
  renderReport(<Opened assignmentId="a/1" onClose={() => {}} />)

  expect(await screen.findByRole('dialog', { name: 'Aarav Desai' })).toBeInTheDocument()
  expect(screen.getByText('Learning path')).toBeInTheDocument()
  expect(screen.getByText('Quiz performance')).toBeInTheDocument()
  expect(screen.getByText('Key dates')).toBeInTheDocument()
  expect(screen.getAllByText('Completed').length).toBeGreaterThan(0)
  expect(screen.getAllByText('70.0%').length).toBeGreaterThan(0)
  expect(screen.getByTestId('key-dates-horizontal-connector')).toBeInTheDocument()
  expect(metaIconColors('Video watched')).toContain(colors.primaryBlue)
  expect(metaIconColors('Quiz passed')).toContain(colors.completedGreen)
  expect(screen.getByText('3/3 modules completed')).toBeInTheDocument()
  expect(screen.getByText('History is available from the reporting upgrade onward.')).toBeVisible()
  const urls = fetchMock.mock.calls.map(([input]) => String(input))
  expect(urls.some((url) => url.includes('/api/trainer/performance/assignments/a%2F1?'))).toBe(true)
})

it('keeps status visible on a narrow screen', async () => {
  stubResize(340)
  stubReportApi(['all_courses'], () => detail({ completed: false }))
  renderReport(<Opened assignmentId="a1" onClose={() => {}} />)

  expect(await screen.findByText('Overdue')).toBeInTheDocument()
  expect(screen.getAllByText('Overdue')).toHaveLength(1)
  expect(screen.getAllByText('33%')).toHaveLength(1)
  expect(screen.getAllByText('No quiz')).toHaveLength(1)
  expect(screen.getByTestId('key-dates-vertical-connector')).toBeInTheDocument()
  expect(screen.getByText('Not yet')).toBeInTheDocument()
})

it('shows the access line and only the latest 20 attempts', async () => {
  stubResize()
  const attempts = Array.from({ length: 21 }, () => ({
    module_id: 'm2',
    occurred_at: '2026-09-11T14:46:00',
    score: 30.0,
    passed: false,
  }))
  stubReportApi(['all_courses'], () => ({
    ...detail(),
    assignment: { ...detail().assignment, access_available: false, course_status: 'archived' },
    attempts,
  }))
  renderReport(<Opened assignmentId="a1" onClose={() => {}} />)

  expect(await screen.findByText('Access unavailable: archived')).toBeInTheDocument()
  expect(screen.getByText('21 recorded attempts')).toBeInTheDocument()
  expect(screen.getByText('Latest attempts')).toBeInTheDocument()
  expect(screen.getByText('Showing the latest 20 of 21 attempts.')).toBeInTheDocument()
  expect(screen.getAllByText('Failed')).toHaveLength(20)
  // Compact rows have no score bar.
  expect(screen.queryAllByRole('progressbar')).toHaveLength(1)
})

it('shows the load error with a Close button', async () => {
  stubResize()
  stubReportApi(['all_courses'], () => new Response('{}', { status: 404 }))
  const onClose = vi.fn()
  renderReport(<Opened assignmentId="a1" onClose={onClose} />)

  const dialog = await screen.findByRole('dialog', { name: 'Assignment detail' })
  expect(await within(dialog).findByText('Could not load assignment')).toBeInTheDocument()
  expect(within(dialog).getByText('Unable to load performance data (404)')).toBeInTheDocument()
  await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
  expect(onClose).toHaveBeenCalledTimes(1)
})

function ChangeFilter() {
  const { dispatch, state } = useReport()
  return (
    <button
      type="button"
      onClick={() => dispatch({ type: 'filter', filter: { ...state.filter, courseId: 'c2' } })}
    >
      Change filter
    </button>
  )
}

it('closes from the header and shows the guard when the report context changes', async () => {
  stubResize()
  stubReportApi(['all_courses'], () => detail())
  const onClose = vi.fn()
  renderReport(
    <>
      <ChangeFilter />
      <Opened assignmentId="a1" onClose={onClose} />
    </>,
  )

  await screen.findByRole('dialog', { name: 'Aarav Desai' })
  fireEvent.click(screen.getByRole('button', { name: 'Close assignment detail' }))
  expect(onClose).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByText('Change filter'))
  expect(screen.getByRole('dialog', { name: 'Performance access changed' })).toBeInTheDocument()
  expect(screen.queryByText('Aarav Desai')).not.toBeInTheDocument()
})
