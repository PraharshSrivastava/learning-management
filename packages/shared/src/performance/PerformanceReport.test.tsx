import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { PerformanceReport } from './PerformanceReport'
import { renderReport, stubReportApi, stubResize } from './testUtils'

beforeEach(() => stubResize())

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const requests: URL[] = []

function stubReport(views = ['all_courses', 'my_courses'], fail?: string) {
  requests.length = 0
  return stubReportApi(views, (url) => {
    requests.push(url)
    if (fail != null && url.pathname.endsWith(`/${fail}`)) return new Response('', { status: 500 })
    if (url.pathname.endsWith('/overview')) return { generated_at: '2026-10-16T09:05:00' }
    return {}
  })
}

const requested = (path: string) =>
  requests.filter((url) => url.pathname.endsWith(`/api/trainer/performance/${path}`))

it('shows the header, the view picker and the overview tab', async () => {
  stubReport()
  renderReport(<PerformanceReport app="trainer" />, { withReport: false })
  expect(screen.getByRole('heading', { name: 'Performance' })).toBeInTheDocument()
  expect(screen.getByText('Learning outcomes and assignments that need attention.')).toBeVisible()
  expect(await screen.findByText('Updated 16/10/2026 09:05')).toBeInTheDocument()
  const picker = screen.getByRole('combobox', { name: 'Report view' })
  expect(
    within(picker)
      .getAllByRole('option')
      .map((option) => option.textContent),
  ).toEqual(['All Courses', 'My Courses'])
  expect(screen.getByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('button', { name: 'Export assignments CSV' })).toBeInTheDocument()
})

it('loads the report again for another view', async () => {
  stubReport()
  renderReport(<PerformanceReport app="trainer" />, { withReport: false })
  await waitFor(() => expect(requested('overview')).toHaveLength(1))
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Report view' }), 'my_courses')
  await waitFor(() =>
    expect(requested('overview').at(-1)?.searchParams.get('view')).toBe('my_courses'),
  )
})

it('switches the tabs and hides the assignment export on the employee summary', async () => {
  stubReport()
  renderReport(<PerformanceReport app="trainer" />, { withReport: false })
  await userEvent.click(screen.getByRole('tab', { name: 'Courses' }))
  expect(screen.getByText('Course performance')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('tab', { name: 'Employees' }))
  expect(screen.getByRole('tab', { name: 'Employees' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.queryByRole('button', { name: 'Export assignments CSV' })).not.toBeInTheDocument()
})

it('opens a linked report on the course assignments', async () => {
  stubReport()
  renderReport(
    <PerformanceReport app="trainer" linkedReport={{ courseId: 'c1', status: null }} />,
    { withReport: false },
  )
  expect(screen.getByRole('tab', { name: 'Employees' })).toHaveAttribute('aria-selected', 'true')
  await waitFor(() =>
    expect(requested('assignments').at(-1)?.searchParams.get('course_id')).toBe('c1'),
  )
  expect(screen.getByRole('button', { name: 'Export assignments CSV' })).toBeInTheDocument()
})

it('shows the empty access text of each app', async () => {
  stubReport([])
  const { unmount } = renderReport(<PerformanceReport app="trainer" />, { withReport: false })
  expect(await screen.findByText('Performance access unavailable')).toBeInTheDocument()
  unmount()
  renderReport(<PerformanceReport app="employee" />, { app: 'employee', withReport: false })
  expect(await screen.findByText('Performance access is unavailable.')).toBeInTheDocument()
})

it('shows a failed request in an error box', async () => {
  stubReport(['all_courses'], 'overview')
  renderReport(<PerformanceReport app="trainer" />, { withReport: false })
  expect(await screen.findByText('Unable to load performance data (500)')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Refresh' })).toBeEnabled()
})
