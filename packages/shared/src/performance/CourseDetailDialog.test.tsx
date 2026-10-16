// Dart: frontend/test/course_detail_dialog_test.dart:1-96, plus the _showCourse route in
// performance_report_portal.dart:793-811 (request, View employees, access guard).
import { cleanup, fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { useReport } from './context'
import { CourseDetailDialog } from './CourseDetailDialog'
import { renderReport, stubReportApi, stubResize } from './testUtils'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const detail = () => ({
  course: {
    course_id: 'c1',
    course_name: 'Client Conversations',
    assigned: 100,
    completed: 40,
    overdue: 18,
    completion_rate: 40,
  },
  modules: [
    { module_id: 'm1', module_number: 1, title: 'Preparation', assigned: 100, watched: 70 },
    {
      module_id: 'm2',
      module_number: 2,
      title: 'Active listening',
      assigned: 100,
      watched: 70,
      num_questions: 5,
      passed: 40,
      attempts: 139,
      average_score: 63.1,
    },
    {
      module_id: 'm3',
      module_number: 3,
      title: 'Follow-up',
      assigned: 100,
      watched: 40,
      num_questions: 5,
      passed: 40,
      attempts: 79,
      average_score: 80.4,
    },
  ],
  generated_at: '2026-10-01T10:00:00Z',
})

/** The portal side: open state, plus the report state the dialog changes. */
function Portal() {
  const { state, dispatch, views } = useReport()
  const [courseId, setCourseId] = useState<string | null>(null)
  return (
    <>
      <p>
        view {state.view}, course {state.filter.courseId ?? 'none'}, summary{' '}
        {String(state.employeeSummary)}
      </p>
      <button
        type="button"
        onClick={() => dispatch({ type: 'filter', filter: { ...state.filter, department: 'Ops' } })}
      >
        Change filter
      </button>
      {views.length > 0 && (
        <button type="button" onClick={() => setCourseId('c1')}>
          Open course
        </button>
      )}
      <CourseDetailDialog courseId={courseId} onClose={() => setCourseId(null)} />
    </>
  )
}

function stubDetail(handler: (url: URL) => unknown = () => detail()) {
  return stubReportApi(['all_courses'], (url) => {
    if (url.pathname.endsWith('/performance/courses/c1')) return handler(url)
    return {}
  })
}

/** Opens the dialog once the access loaded, like a click in the loaded report. */
function Opened({ courseId }: { courseId: string }) {
  const { views } = useReport()
  return <CourseDetailDialog courseId={views.length > 0 ? courseId : null} onClose={() => {}} />
}

it('shows course learning path and opens employees', async () => {
  stubResize(1040 - 48)
  const fetchMock = stubDetail()
  renderReport(<Portal />)
  fireEvent.click(await screen.findByRole('button', { name: 'Open course' }))

  expect(await screen.findByRole('dialog', { name: 'Client Conversations' })).toBeInTheDocument()
  expect(screen.getByText('Module outcomes')).toBeInTheDocument()
  expect(screen.getByText('3 modules in this course')).toBeInTheDocument()
  expect(screen.getByText('Preparation')).toBeInTheDocument()
  expect(screen.getByText('Active listening')).toBeInTheDocument()
  expect(screen.getByText('Follow-up')).toBeInTheDocument()
  expect(screen.getByText('No quiz')).toBeInTheDocument()
  expect(screen.getAllByText('40 passed')).toHaveLength(2)
  expect(screen.getByText('139 attempts')).toBeInTheDocument()
  expect(screen.getByText('Average 63.1%')).toBeInTheDocument()
  expect(screen.getByText('Average -')).toBeInTheDocument()
  // Wide: the summary column stacks the numbers under the ring.
  expect(screen.getByText('assigned')).toBeInTheDocument()

  const url = fetchMock.mock.calls
    .map(([input]) => new URL(String(input), 'http://localhost'))
    .find((call) => call.pathname.endsWith('/courses/c1'))!
  expect(url.searchParams.get('view')).toBe('all_courses')
  expect(url.searchParams.has('course_id')).toBe(false)

  await userEvent.click(screen.getByRole('button', { name: 'View employees' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByText('view 2, course c1, summary false')).toBeInTheDocument()
})

it('fits the course detail on a narrow screen', async () => {
  stubResize(420 - 32 - 48)
  stubDetail()
  renderReport(<Portal />)
  fireEvent.click(await screen.findByRole('button', { name: 'Open course' }))

  expect(await screen.findByText('40%')).toBeInTheDocument()
  expect(screen.getByText('100 assigned')).toBeInTheDocument()
  expect(screen.getByText('18 overdue')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'View employees' })).toBeInTheDocument()
})

it('shows the load error and closes', async () => {
  stubResize()
  stubDetail(() => new Response('{}', { status: 404 }))
  renderReport(<Portal />)
  fireEvent.click(await screen.findByRole('button', { name: 'Open course' }))

  expect(await screen.findByText('Could not load course detail')).toBeInTheDocument()
  expect(screen.getByText('Unable to load performance data (404)')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('encodes a course id with slashes and query characters in the request path', async () => {
  stubResize()
  const fetchMock = stubReportApi(['all_courses'], () => detail())
  renderReport(<Opened courseId="c/1?x" />)

  await screen.findByRole('dialog', { name: 'Client Conversations' })
  const urls = fetchMock.mock.calls.map(([input]) => String(input))
  expect(urls.some((url) => url.includes('/api/trainer/performance/courses/c%2F1%3Fx?'))).toBe(true)
})

it('shows the access guard when the report context changes', async () => {
  stubResize()
  stubDetail()
  renderReport(<Portal />)
  fireEvent.click(await screen.findByRole('button', { name: 'Open course' }))

  expect(await screen.findByRole('dialog', { name: 'Client Conversations' })).toBeInTheDocument()
  fireEvent.click(screen.getByText('Change filter'))
  expect(screen.getByRole('dialog', { name: 'Performance access changed' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
