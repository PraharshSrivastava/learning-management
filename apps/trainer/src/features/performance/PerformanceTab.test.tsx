import { useMainReport, useReport, ReportProvider } from '@lms/shared/performance/context'
import { renderReport, stubReportApi } from '@lms/shared/performance/testUtils'
import { act, cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StrictMode, useSyncExternalStore } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { setPendingLinkedReport, takePendingLinkedReport } from '../../shell/linkedReport'
import type { TrainerTab } from '../../shell/search'
import { PerformanceTab } from './PerformanceTab'

// The open shell tab. `openTab` switches it, as the URL does in TrainerShell.
const shellTab = vi.hoisted(() => {
  let tab: string = 'performance'
  const listeners = new Set<() => void>()
  return {
    get: () => tab,
    set: (next: string) => {
      tab = next
      listeners.forEach((listener) => listener())
    },
    subscribe: (listener: () => void) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
})

vi.mock('../../shell/search', () => ({
  useTrainerSearch: () => ({
    tab: useSyncExternalStore(shellTab.subscribe, shellTab.get),
  }),
}))

function openTab(tab: TrainerTab) {
  act(() => shellTab.set(tab))
}

// The tab only hands the link to the report. The stand-in mounts the real provider and requests,
// so the test checks the state and the requests that the link gives.
vi.mock('@lms/shared/performance/PerformanceReport', () => ({
  PerformanceReport: ({
    app,
    linkedReport,
  }: {
    app: 'trainer' | 'employee'
    linkedReport?: { courseId: string | null; status: string | null } | null
  }) => (
    <ReportProvider app={app} linkedReport={linkedReport}>
      <Report />
    </ReportProvider>
  ),
}))

function Report() {
  const { state, dispatch } = useReport()
  useMainReport()
  return (
    <>
      <p>
        view {state.view}, summary {String(state.employeeSummary)}, course{' '}
        {state.filter.courseId ?? 'none'}
      </p>
      <p>report view {state.reportView}</p>
      <button type="button" onClick={() => dispatch({ type: 'reportView', view: 'my_courses' })}>
        My Courses
      </button>
    </>
  )
}

afterEach(() => {
  cleanup()
  setPendingLinkedReport(null)
  shellTab.set('performance')
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const report = { rows: [], total: 0, page: 1, page_size: 25 }

function stubApi() {
  return stubReportApi(['all_courses'], () => report)
}

function assignmentRequests(fetchMock: ReturnType<typeof stubApi>) {
  return fetchMock.mock.calls
    .map(([input]) => new URL(String(input), 'http://localhost'))
    .filter((url) => url.pathname === '/api/trainer/performance/assignments')
}

it('opens a pending link on the assignment list with the course filter', async () => {
  const fetchMock = stubApi()
  setPendingLinkedReport({ courseId: 'c1', status: 'overdue' })
  renderReport(<PerformanceTab />, { withReport: false })

  expect(await screen.findByText('view 2, summary false, course c1')).toBeInTheDocument()
  await waitFor(() => expect(assignmentRequests(fetchMock)).toHaveLength(1))
  const params = assignmentRequests(fetchMock)[0]!.searchParams
  expect(params.get('view')).toBe('all_courses')
  expect(params.get('course_id')).toBe('c1')
  expect(params.get('status')).toBe('overdue')
  expect(params.get('page')).toBe('1')
})

it('opens the overview without a link', async () => {
  const fetchMock = stubApi()
  renderReport(<PerformanceTab />, { withReport: false })

  expect(await screen.findByText('view 0, summary true, course none')).toBeInTheDocument()
  await waitFor(() => expect(assignmentRequests(fetchMock)).toHaveLength(1))
  expect(assignmentRequests(fetchMock)[0]!.searchParams.has('course_id')).toBe(false)
})

it('takes the pending link once, also in StrictMode', async () => {
  stubApi()
  setPendingLinkedReport({ courseId: 'c1', status: null })
  const { unmount } = renderReport(
    <StrictMode>
      <PerformanceTab />
    </StrictMode>,
    { withReport: false },
  )

  expect(await screen.findByText('view 2, summary false, course c1')).toBeInTheDocument()
  expect(takePendingLinkedReport()).toBeNull()

  // A later mount (TrainerShell remounts the tab by key) starts without the old link.
  unmount()
  renderReport(<PerformanceTab />, { withReport: false })
  expect(await screen.findByText('view 0, summary true, course none')).toBeInTheDocument()
})

it('opens a later link when the tab is already mounted', async () => {
  const fetchMock = stubApi()
  renderReport(<PerformanceTab />, { withReport: false })
  expect(await screen.findByText('view 0, summary true, course none')).toBeInTheDocument()

  // TrainerShell keeps the visited tab mounted. "View Performance" on the Courses tab leaves a
  // link and opens the Performance tab again.
  openTab('courses')
  setPendingLinkedReport({ courseId: 'c2', status: null })
  openTab('performance')

  expect(await screen.findByText('view 2, summary false, course c2')).toBeInTheDocument()
  expect(takePendingLinkedReport()).toBeNull()
  await waitFor(() =>
    expect(
      assignmentRequests(fetchMock).some((url) => url.searchParams.get('course_id') === 'c2'),
    ).toBe(true),
  )
})

it('keeps the report view when a later link opens', async () => {
  stubReportApi(['all_courses', 'my_courses'], () => report)
  renderReport(<PerformanceTab />, { withReport: false })
  expect(await screen.findByText('report view all_courses')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'My Courses' }))
  expect(await screen.findByText('report view my_courses')).toBeInTheDocument()

  openTab('courses')
  setPendingLinkedReport({ courseId: 'c3', status: null })
  openTab('performance')

  // Flutter openLinkedReport changes the filter of the open report, not its view.
  expect(await screen.findByText('view 2, summary false, course c3')).toBeInTheDocument()
  expect(screen.getByText('report view my_courses')).toBeInTheDocument()
})
