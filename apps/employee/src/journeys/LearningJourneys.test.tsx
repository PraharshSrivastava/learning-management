import { cleanup, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { courseJson, moduleJson } from '../test/fixtures'
import { renderDashboard, stubFetch, stubSocket } from '../test/renderApp'

vi.mock('@lms/shared/video/HlsVideoPlayer', () => ({
  HlsVideoPlayer: () => <div data-testid="player" />,
}))

const place = (step: number) => [
  { journey_id: 'j1', title: 'Markets Foundation', step, step_count: 3 },
]

const courses = [
  courseJson({
    course_id: 'c1',
    course_name: 'Indian Market Structure',
    assignment_status: 'completed',
    modules: [moduleJson(1)],
    module_progress: { '1': { video_watched: true, quiz_passed: true, quiz_score: 1 } },
    journeys: place(1),
  }),
  courseJson({ course_id: 'c2', course_name: 'Equity Basics', journeys: place(2) }),
]

const journey = {
  journey_id: 'j1',
  title: 'Markets Foundation',
  description: 'How Indian capital markets work.',
  certificate_enabled: true,
  status: 'started',
  deadline: '2026-12-15T23:59:59',
  step_count: 3,
  passed_count: 1,
  required_count: 3,
  next_course_id: 'c2',
  prerequisite: null,
  stages: [
    {
      title: 'Market basics',
      steps: [
        {
          course_id: 'c1',
          course_name: 'Indian Market Structure',
          module_count: 1,
          step_number: 1,
          state: 'passed',
        },
        {
          course_id: 'c2',
          course_name: 'Equity Basics',
          module_count: 2,
          step_number: 2,
          state: 'available',
        },
        {
          course_id: 'c3',
          course_name: 'Order Types',
          module_count: 4,
          step_number: 3,
          state: 'locked',
          locked_by_course_name: 'Equity Basics',
        },
      ],
    },
  ],
}

let journeysReply: unknown = { enabled: true, journeys: [journey] }

beforeEach(() => {
  journeysReply = { enabled: true, journeys: [journey] }
  stubSocket()
  stubFetch((url) => {
    if (url.pathname.endsWith('/api/me/courses')) return courses
    if (url.pathname.endsWith('/api/me/learning-journeys')) return journeysReply
    if (url.pathname.endsWith('/api/lms/me')) return { performance_views: [] }
    if (url.pathname.endsWith('/api/media-ticket')) return { ticket: 't' }
    return new Response('{}', { status: 404 })
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('Learning Journeys for employees', () => {
  it('adds the menu item and the dashboard section when enabled', async () => {
    renderDashboard()
    expect(await screen.findByRole('button', { name: 'Learning Journeys' })).toBeInTheDocument()
    const section = await screen.findByRole('region', { name: 'Your learning journeys' })
    expect(within(section).getByText('1 of 3 courses passed')).toBeInTheDocument()
    expect(within(section).getByText('Equity Basics')).toBeInTheDocument()
    // Course cards show where they sit in the journey.
    expect(screen.getAllByText('Markets Foundation · Step 2 of 3').length).toBeGreaterThan(0)
  })

  it('hides everything when the feature is off', async () => {
    journeysReply = { enabled: false, journeys: [] }
    renderDashboard()
    await screen.findAllByText('Equity Basics')
    expect(screen.queryByRole('button', { name: 'Learning Journeys' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Your learning journeys' })).not.toBeInTheDocument()
  })

  it('shows the roadmap with locked steps and opens an unlocked course with the journey bar', async () => {
    const user = userEvent.setup()
    const { router } = renderDashboard('/?view=journeys')
    await user.click(await screen.findByRole('button', { name: 'View journey' }))
    expect(router.state.location.search).toEqual({ view: 'journeys', journey_id: 'j1' })
    expect(await screen.findByRole('heading', { name: 'Markets Foundation' })).toBeInTheDocument()
    expect(screen.getByText('Opens after you pass Equity Basics')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Open Order Types' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Open Equity Basics' }))
    expect(router.state.location.search).toEqual({
      view: 'journeys',
      course_id: 'c2',
      journey_id: 'j1',
    })
    expect(await screen.findByText('Step 2 of 3', { exact: false })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back to journey' }))
    expect(router.state.location.search).toEqual({ view: 'journeys', journey_id: 'j1' })
  })
})
