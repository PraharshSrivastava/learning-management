import { act, cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { courseJson, moduleJson } from '../test/fixtures'
import { FakeSocket, renderDashboard, stubFetch, stubSocket } from '../test/renderApp'
import { RECONNECT_BASE_MS } from './useEmployeeCourses'

// Each link object the report got. A new object opens the link again.
const linkedReports = vi.hoisted(() => [] as unknown[])

// This suite checks navigation; playback has its own player and completion tests.
vi.mock('@lms/shared/video/HlsVideoPlayer', () => ({
  HlsVideoPlayer: () => <div data-testid="player" />,
}))

vi.mock('@lms/shared/performance/PerformanceReport', () => ({
  PerformanceReport: ({ linkedReport }: { linkedReport: unknown }) => {
    linkedReports.push(linkedReport)
    return <div data-testid="performance">{JSON.stringify(linkedReport)}</div>
  },
}))

const DAY = 24 * 60 * 60 * 1000
const iso = (offsetDays: number) => new Date(Date.now() + offsetDays * DAY).toISOString()

const courses = [
  courseJson({
    course_id: 'done',
    course_name: 'Excel basics',
    assigned_at: iso(-20),
    modules: [moduleJson(1)],
    module_progress: { '1': { video_watched: true, quiz_passed: true, quiz_score: 1 } },
  }),
  courseJson({ course_id: 'late', course_name: 'Late course', deadline: iso(-1) }),
  courseJson({
    course_id: 'new',
    course_name: 'New compliance',
    assigned_at: iso(-1),
    deadline: iso(3),
  }),
  courseJson({
    course_id: 'started',
    course_name: 'Communication',
    assigned_at: iso(-10),
    module_progress: { '1': { video_watched: true } },
  }),
]

let performanceViews: string[] = []

beforeEach(() => {
  performanceViews = []
  linkedReports.length = 0
  stubSocket()
  stubFetch((url) => {
    if (url.pathname.endsWith('/api/me/courses')) return courses
    if (url.pathname.endsWith('/api/lms/me')) return { performance_views: performanceViews }
    if (url.pathname.endsWith('/api/media-ticket')) return { ticket: 't' }
    return new Response('{}', { status: 404 })
  })
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const cardTitles = (section: HTMLElement) =>
  within(section)
    .getAllByRole('heading', { level: 3 })
    .map((heading) => heading.textContent)

describe('EmployeeDashboard', () => {
  it('shows metrics and orders assigned and attempted courses', async () => {
    renderDashboard()
    await screen.findByText('Late course')
    const metrics = screen.getByRole('group', { name: 'Learning metrics' })
    expect(
      within(metrics).getByRole('button', { name: 'Show Assigned courses' }),
    ).toHaveTextContent('3')
    expect(within(metrics).getByRole('button', { name: 'Show Passed courses' })).toHaveTextContent(
      '1',
    )
    expect(screen.getByText('You have 2 courses ready for your attention.')).toBeInTheDocument()
    const main = screen.getByRole('main')
    // Overdue first, then pending, then in progress. Attempted is newest assignment first.
    expect(cardTitles(main)).toEqual([
      'Late course',
      'New compliance',
      'Communication',
      'Communication',
      'Excel basics',
    ])
  })

  it('filters the courses from a metric', async () => {
    const user = userEvent.setup()
    renderDashboard()
    await screen.findByText('Late course')
    await user.click(screen.getByRole('button', { name: 'Show Passed courses' }))
    expect(screen.getByRole('button', { name: 'Show Passed courses' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('heading', { name: 'Passed courses' })).toBeInTheDocument()
    expect(cardTitles(screen.getByRole('main'))).toEqual(['Excel basics'])
  })

  it('marks new assignments as read when the notifications open', async () => {
    const user = userEvent.setup()
    renderDashboard()
    const bell = await screen.findByRole('button', { name: '1 unread notifications' })
    await user.click(bell)
    const dialog = await screen.findByRole('dialog', { name: 'Learning notifications' })
    expect(within(dialog).getByText('New course: New compliance')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('button', { name: /unread notifications/ })).not.toBeInTheDocument()
  })

  it('opens a course and keeps it in the URL', async () => {
    const user = userEvent.setup()
    const { router } = renderDashboard()
    await user.click(await screen.findByRole('button', { name: 'Start Late course' }))
    expect(router.state.location.search).toEqual({ course_id: 'late' })
    expect(await screen.findByRole('heading', { name: 'Module title 1' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back to dashboard' }))
    expect(router.state.location.search).toEqual({})
  })

  it('loads thumbnails without a media ticket and shows the fallback on error', async () => {
    stubFetch((url) => {
      if (url.pathname.endsWith('/api/me/courses')) {
        return [
          courseJson({ course_id: 'cdn', thumbnail_path: 'https://cdn.example.com/cdn.png' }),
          courseJson({ course_id: 'own', thumbnail_path: 'assets/images/own.png' }),
        ]
      }
      if (url.pathname.endsWith('/api/lms/me')) return { performance_views: [] }
      return new Response('{}', { status: 500 })
    })
    const { container } = renderDashboard()
    await waitFor(() => expect(container.querySelectorAll('article img')).toHaveLength(2))
    const [cdn, own] = container.querySelectorAll<HTMLImageElement>('article img')
    expect(cdn!.getAttribute('src')).toBe('https://cdn.example.com/cdn.png')
    expect(own!.getAttribute('src')).toMatch(/assets\/images\/own\.png$/)
    act(() => own!.dispatchEvent(new Event('error')))
    expect(container.querySelectorAll('article img')).toHaveLength(1)
  })

  it('drops a deep link to a course that is not assigned', async () => {
    const { router } = renderDashboard('/?view=course&course_id=missing')
    await screen.findByText('Late course')
    await waitFor(() => expect(router.state.location.search).toEqual({}))
  })

  it('hides Performance without report access', async () => {
    renderDashboard('/?view=performance')
    await screen.findByText('Late course')
    expect(screen.queryByRole('button', { name: 'Performance' })).not.toBeInTheDocument()
    expect(screen.queryByTestId('performance')).not.toBeInTheDocument()
  })

  it('shows Performance with report access and passes the linked report', async () => {
    performanceViews = ['team']
    renderDashboard('/?view=team-performance&course_id=c9&status=passed')
    expect(await screen.findByTestId('performance')).toHaveTextContent(
      '{"courseId":"c9","status":"passed"}',
    )
    expect(screen.getByRole('button', { name: 'Performance' })).toBeInTheDocument()
    // Flutter showed no label here, as its label list has no Performance entry.
    expect(within(screen.getByRole('banner')).getByText('Performance')).toBeInTheDocument()
  })

  it('keeps the same linked report object when the dashboard renders again', async () => {
    performanceViews = ['team']
    renderDashboard('/?view=team-performance&course_id=c9&status=passed')
    await screen.findByTestId('performance')
    act(() => FakeSocket.instances[0]!.send(courses))
    await waitFor(() => expect(linkedReports.length).toBeGreaterThan(1))
    expect(new Set(linkedReports).size).toBe(1)
  })

  it('replaces the list from the socket and reconnects after a close', async () => {
    renderDashboard()
    await screen.findByText('Late course')
    const socket = FakeSocket.instances[0]!
    expect(socket.url).toContain('/api/me/courses/ws')
    act(() => socket.send([courseJson({ course_id: 'only', course_name: 'Socket course' })]))
    expect(await screen.findByText('Socket course')).toBeInTheDocument()
    expect(screen.queryByText('Late course')).not.toBeInTheDocument()

    vi.useFakeTimers()
    act(() => socket.onclose?.())
    expect(FakeSocket.instances).toHaveLength(1)
    act(() => vi.advanceTimersByTime(RECONNECT_BASE_MS))
    expect(FakeSocket.instances).toHaveLength(2)
  })

  it('keeps a socket list that arrives while the first GET is pending', async () => {
    let finish!: () => void
    const pending = new Promise<void>((resolve) => (finish = resolve))
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.endsWith('/api/me/courses')) {
          await pending
          return new Response(JSON.stringify([courseJson({ course_name: 'Old list' })]))
        }
        return new Response(JSON.stringify({ performance_views: [] }))
      }),
    )
    renderDashboard()
    await waitFor(() => expect(FakeSocket.instances).toHaveLength(1))
    act(() => FakeSocket.instances[0]!.send([courseJson({ course_name: 'Socket list' })]))
    expect(await screen.findByText('Socket list')).toBeInTheDocument()
    await act(async () => finish())
    await waitFor(() => expect(screen.queryByText('Old list')).not.toBeInTheDocument())
    expect(screen.getByText('Socket list')).toBeInTheDocument()
  })

  it('closes the socket on unmount', async () => {
    const { unmount } = renderDashboard()
    await screen.findByText('Late course')
    unmount()
    expect(FakeSocket.instances.every((socket) => socket.closed)).toBe(true)
  })
})
