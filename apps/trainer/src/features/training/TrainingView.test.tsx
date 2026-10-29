import { configureApi } from '@lms/shared/api/client'
import { createQueryClient } from '@lms/shared/api/queryClient'
import { parseCourse, type Course } from '@lms/shared/models'
import { ToastProvider } from '@lms/shared/ui/Toast'
import { TooltipProvider } from '@lms/shared/ui/Tooltip'
import { QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import userEvent from '@testing-library/user-event'
import { useSyncExternalStore, type ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { OverlayProvider } from '../../shell/overlay'
import { trainerSearchSchema, useUpdateTrainerSearch } from '../../shell/search'
import { TrainingView } from './TrainingView'

vi.mock('@lms/shared/video/HlsVideoPlayer', () => ({
  HlsVideoPlayer: ({ hlsUrl }: { hlsUrl: string }) => <div data-testid="player">{hlsUrl}</div>,
}))

const question = (text: string, correct = 'A') => ({
  question_text: text,
  options: [
    { key: 'A', text: 'First' },
    { key: 'B', text: 'Second' },
  ],
  correct_option: correct,
  explanation: `Why ${text}`,
})

function courseJson(overrides: Record<string, unknown> = {}) {
  return {
    course_id: 'c1',
    course_name: 'Compliance',
    modules: [
      {
        module_number: 1,
        title: 'Code of conduct',
        video_path: 'assets/videos/c1/m1.mp4',
        notes: 'Read this first.',
        slides: [
          { slide_title: 'Intro', script: 'Welcome.' },
          { slide_title: 'Hidden', script: ' ' },
        ],
        quiz: { questions: [question('Q one'), question('Q two', 'B')] },
      },
      { module_number: 2, title: 'Reporting', notes: '', slides: [] },
    ],
    ...overrides,
  }
}

const course = (overrides?: Record<string, unknown>): Course => parseCourse(courseJson(overrides))

/** Renders the view under a memory router at `url`. `show` swaps the view, as a new course does. */
async function renderView(ui: ReactNode, { url = '/?tab=courses&course=c1' } = {}) {
  let current = ui
  const listeners = new Set<() => void>()
  const subscribe = (listener: () => void) => {
    listeners.add(listener)
    return () => listeners.delete(listener)
  }
  const Page = () => useSyncExternalStore(subscribe, () => current)
  const rootRoute = createRootRoute({ component: Outlet })
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    validateSearch: trainerSearchSchema,
    component: Page,
  })
  const router = createRouter({
    routeTree: rootRoute.addChildren([indexRoute]),
    history: createMemoryHistory({ initialEntries: [url] }),
  })
  const client = createQueryClient()
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  const view = render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <ToastProvider>
          <OverlayProvider>
            <RouterProvider router={router} />
          </OverlayProvider>
        </ToastProvider>
      </TooltipProvider>
    </QueryClientProvider>,
  )
  const show = (next: ReactNode) => {
    current = next
    act(() => listeners.forEach((listener) => listener()))
  }
  const search = () => router.state.location.search as Record<string, unknown>
  // The router renders the route after it loads, on a later tick.
  await act(() => router.load())
  return { ...view, router, client, invalidate, show, search }
}

function mockViewport(mobile: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: mobile && query.includes('max-width'),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
}

beforeEach(() => {
  configureApi({ app: 'trainer', publicMount: '/lms/trainer', configuredApiBase: undefined })
  mockViewport(false)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

/** Stands in for the sidebar, which opens another course through the shared search update. */
function CourseSwitch() {
  const updateSearch = useUpdateTrainerSearch()
  return (
    <button type="button" onClick={() => updateSearch({ course: 'c2' })}>
      Open c2
    </button>
  )
}

describe('TrainingView content', () => {
  it('shows the first module with video, notes, transcript and quiz', async () => {
    await renderView(<TrainingView course={course()} />)
    expect(screen.getByRole('heading', { name: 'Code of conduct', level: 2 })).toBeInTheDocument()
    expect(screen.getAllByText('MODULE 1')).toHaveLength(2)
    expect(screen.getByTestId('player').textContent).toContain('m1_hls/master.m3u8')
    expect(screen.getByText('Read this first.')).toBeInTheDocument()
    expect(screen.getByText('Welcome.')).toBeInTheDocument()
    expect(screen.queryByText('Hidden')).not.toBeInTheDocument()
    expect(screen.getByText('2 Questions')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download Video' })).toBeInTheDocument()
  })

  it('shows the empty course card when there are no modules', async () => {
    await renderView(<TrainingView course={course({ modules: [] })} />)
    expect(screen.getByText('No Modules Available')).toBeInTheDocument()
  })

  it('shows placeholders for a module without video, notes, script and quiz', async () => {
    const user = userEvent.setup()
    await renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    expect(screen.getByText('No Video Compiled Yet')).toBeInTheDocument()
    expect(screen.queryByTestId('player')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Download Video' })).not.toBeInTheDocument()
    expect(
      screen.getByText(/Learner notes appear here after course generation/),
    ).toBeInTheDocument()
    expect(screen.getByText(/No slide narration script/)).toBeInTheDocument()
    expect(screen.getByText('No Quiz Available for this Module')).toBeInTheDocument()
  })

  it('marks the active module in the list', async () => {
    const user = userEvent.setup()
    await renderView(<TrainingView course={course()} />)
    const [first, second] = screen.getAllByRole('button', { name: /^MODULE \d/ })
    expect(first).toHaveAttribute('aria-current', 'true')
    await user.click(second!)
    expect(second).toHaveAttribute('aria-current', 'true')
    expect(first).not.toHaveAttribute('aria-current')
  })

  it('uses a dropdown on narrow screens', async () => {
    mockViewport(true)
    await renderView(<TrainingView course={course()} />)
    const select = screen.getByRole('combobox', { name: 'Module' })
    fireEvent.change(select, { target: { value: '1' } })
    expect(await screen.findByRole('heading', { name: 'Reporting', level: 2 })).toBeInTheDocument()
    expect(screen.queryByText('COURSE CONTENT')).not.toBeInTheDocument()
  })

  it('opens another course at its first module', async () => {
    const user = userEvent.setup()
    const { search } = await renderView(
      <>
        <TrainingView course={course()} />
        <CourseSwitch />
      </>,
    )
    await user.click(await screen.findByRole('button', { name: /Reporting/ }))
    expect(search().module).toBe(2)
    await user.click(screen.getByRole('button', { name: 'Open c2' }))
    expect(search()).toEqual({ tab: 'courses', course: 'c2' })
    expect(screen.getByRole('heading', { name: 'Code of conduct', level: 2 })).toBeInTheDocument()
  })

  it('keeps the module in the URL, so reload and Back restore it', async () => {
    const user = userEvent.setup()
    const { router, search } = await renderView(<TrainingView course={course()} />, {
      url: '/?tab=courses&course=c1&module=2',
    })
    expect(await screen.findByRole('heading', { name: 'Reporting', level: 2 })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Code of conduct/ }))
    expect(search().module).toBeUndefined()
    expect(screen.getByRole('heading', { name: 'Code of conduct', level: 2 })).toBeInTheDocument()
    await act(async () => router.history.back())
    await waitFor(() => expect(search().module).toBe(2))
    expect(screen.getByRole('heading', { name: 'Reporting', level: 2 })).toBeInTheDocument()
  })

  it('ignores a module number that is not in the URL schema', async () => {
    await renderView(<TrainingView course={course()} />, {
      url: '/?tab=courses&course=c1&module=x',
    })
    expect(
      await screen.findByRole('heading', { name: 'Code of conduct', level: 2 }),
    ).toBeInTheDocument()
  })

  it('keeps a valid module when the course loses modules', async () => {
    const { show } = await renderView(<TrainingView course={course()} />, {
      url: '/?tab=courses&course=c1&module=2',
    })
    await screen.findByRole('heading', { name: 'Reporting', level: 2 })
    show(<TrainingView course={course({ modules: courseJson().modules.slice(0, 1) })} />)
    expect(screen.getByRole('heading', { name: 'Code of conduct', level: 2 })).toBeInTheDocument()
  })
})

describe('TrainingView quiz', () => {
  it('checks an answer, shows the result and the explanation, and updates the score', async () => {
    const user = userEvent.setup()
    await renderView(<TrainingView course={course()} />)
    const check = screen.getAllByRole('button', { name: 'Check Answer' })[0]!
    expect(check).toBeDisabled()
    const group = screen.getByRole('radiogroup', { name: 'Question 1 options' })
    await user.click(within(group).getByRole('radio', { name: /First/ }))
    expect(check).toBeEnabled()
    await user.click(check)
    expect(screen.getByText('Why Q one')).toBeInTheDocument()
    // The bar counts answered questions; the score is labelled on its own.
    const progress = screen.getByRole('region', { name: 'Quiz progress' })
    expect(within(progress).getByText('1 of 2 answered')).toBeInTheDocument()
    expect(within(progress).getByText('1 of 2 correct')).toBeInTheDocument()
    expect(
      within(progress).getByRole('progressbar', { name: 'Questions answered' }),
    ).toHaveAttribute('aria-valuenow', '50')
  })

  it('does not read a wrong answer as a finished score', async () => {
    const user = userEvent.setup()
    await renderView(<TrainingView course={course()} />)
    const group = screen.getByRole('radiogroup', { name: 'Question 1 options' })
    await user.click(within(group).getByRole('radio', { name: /Second/ }))
    await user.click(screen.getAllByRole('button', { name: 'Check Answer' })[0]!)
    const progress = screen.getByRole('region', { name: 'Quiz progress' })
    expect(within(progress).getByText('1 of 2 answered')).toBeInTheDocument()
    expect(within(progress).getByText('0 of 2 correct')).toBeInTheDocument()
  })

  it('locks the options after the answer is checked', async () => {
    const user = userEvent.setup()
    await renderView(<TrainingView course={course()} />)
    const group = screen.getByRole('radiogroup', { name: 'Question 1 options' })
    await user.click(within(group).getByRole('radio', { name: /Second/ }))
    await user.click(screen.getAllByRole('button', { name: 'Check Answer' })[0]!)
    await user.click(within(group).getByRole('radio', { name: /First/ }))
    expect(within(group).getByRole('radio', { name: /Second/ })).toHaveAttribute(
      'aria-checked',
      'true',
    )
  })

  it('shows every question answered and Reset Quiz clears the answers', async () => {
    const user = userEvent.setup()
    await renderView(<TrainingView course={course()} />)
    expect(screen.getByRole('button', { name: 'Reset Quiz' })).toBeDisabled()
    for (const index of [1, 2]) {
      const group = screen.getByRole('radiogroup', { name: `Question ${index} options` })
      await user.click(within(group).getAllByRole('radio')[0]!)
      await user.click(screen.getAllByRole('button', { name: 'Check Answer' })[0]!)
    }
    expect(screen.getByText('2 of 2 answered')).toBeInTheDocument()
    expect(screen.getByText('All questions answered.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reset Quiz' }))
    expect(screen.getByText('0 of 2 answered')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Check Answer' })).toHaveLength(2)
  })

  it('moves and selects with arrow keys and keeps one tab stop per question', async () => {
    const user = userEvent.setup()
    await renderView(<TrainingView course={course()} />)
    const group = await screen.findByRole('radiogroup', { name: 'Question 1 options' })
    const [first, second] = within(group).getAllByRole('radio')
    expect(first).toHaveAttribute('tabindex', '0')
    expect(second).toHaveAttribute('tabindex', '-1')
    first!.focus()
    await user.keyboard('{ArrowDown}')
    expect(second).toHaveFocus()
    expect(second).toHaveAttribute('aria-checked', 'true')
    expect(second).toHaveAttribute('tabindex', '0')
    expect(first).toHaveAttribute('tabindex', '-1')
    await user.keyboard('{ArrowRight}')
    expect(first).toHaveFocus()
    expect(first).toHaveAttribute('aria-checked', 'true')
    await user.keyboard('{ArrowUp}')
    expect(second).toHaveFocus()
    await user.tab()
    expect(screen.getAllByRole('button', { name: 'Check Answer' })[0]).toHaveFocus()
  })

  it('keeps answers per module when the user switches modules', async () => {
    const user = userEvent.setup()
    await renderView(<TrainingView course={course()} />)
    const group = screen.getByRole('radiogroup', { name: 'Question 1 options' })
    await user.click(within(group).getByRole('radio', { name: /First/ }))
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    await user.click(screen.getByRole('button', { name: /Code of conduct/ }))
    expect(
      within(screen.getByRole('radiogroup', { name: 'Question 1 options' })).getByRole('radio', {
        name: /First/,
      }),
    ).toHaveAttribute('aria-checked', 'true')
  })
})

describe('TrainingView read-only mode', () => {
  it('keeps the module out of the URL', async () => {
    const user = userEvent.setup()
    const { search } = await renderView(<TrainingView course={course()} readOnly />)
    await user.click(await screen.findByRole('button', { name: /Reporting/ }))
    expect(screen.getByRole('heading', { name: 'Reporting', level: 2 })).toBeInTheDocument()
    expect(search().module).toBeUndefined()
  })

  it('disables both generation buttons but keeps download', async () => {
    const user = userEvent.setup()
    await renderView(<TrainingView course={course()} readOnly />)
    expect(screen.getByRole('button', { name: 'Download Video' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    expect(screen.getByRole('button', { name: 'Compile Module Video' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Generate Quiz Now' })).toBeDisabled()
  })
})

describe('TrainingView generation', () => {
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

  /** Routes `METHOD /path` to a handler. The generation config answers with `mode`. */
  function stubApi(
    routes: Record<string, () => Response | Promise<Response>>,
    mode: 'local' | 'external' = 'local',
  ) {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), 'http://localhost')
      const key = `${init?.method ?? 'GET'} ${url.pathname.replace(/^\/lms\/trainer/, '')}`
      if (key.endsWith(' /api/generation/config')) {
        return Promise.resolve(json({ video_generation_mode: mode }))
      }
      const route = routes[key]
      return Promise.resolve(route ? route() : json(null))
    })
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }
  const requested = (fetchMock: ReturnType<typeof stubApi>, fragment: string) =>
    fetchMock.mock.calls.filter(([input]) => String(input).includes(fragment)).length

  const job = (status: string) => () => json({ id: 'j1', course_id: 'c1', status })

  it('runs the module video as a background job without blocking the page', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let polls = 0
    const fetchMock = stubApi({
      'POST /api/courses/c1/modules/2/video-jobs': job('pending'),
      'GET /api/generation-jobs/j1': () => {
        polls += 1
        return job(polls >= 2 ? 'completed' : 'running')()
      },
    })
    const { invalidate } = await renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    await user.click(screen.getByRole('button', { name: 'Compile Module Video' }))

    expect(await screen.findByText('Starting video generation…')).toBeInTheDocument()
    // No blocking overlay: the rest of the page stays usable while the job runs.
    expect(screen.queryByText('Generating video')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Compile Module Video' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Generate Quiz Now' })).toBeEnabled()
    expect(requested(fetchMock, '/modules/2/video-jobs')).toBe(1)
    expect(requested(fetchMock, '/generate-video')).toBe(0)

    await act(() => vi.advanceTimersByTimeAsync(5000))
    await act(() => vi.advanceTimersByTimeAsync(5000))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Compile Module Video' })).toBeEnabled(),
    )
    expect(polls).toBe(2)
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['courses'] })
    vi.useRealTimers()
  })

  it('shows the module failure cause when the video job fails', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    vi.useFakeTimers({ shouldAdvanceTime: true })
    stubApi({
      'POST /api/courses/c1/modules/2/video-jobs': job('pending'),
      'GET /api/generation-jobs/j1': () =>
        json({ id: 'j1', course_id: 'c1', status: 'failed', error: 'Pipeline exited with 1' }),
    })
    const failed = course({
      modules: [
        courseJson().modules[0],
        {
          module_number: 2,
          title: 'Reporting',
          video_service: { status: 'failed', error: 'TTS down' },
        },
      ],
    })
    const { client } = await renderView(<TrainingView course={course()} />)
    client.setQueryData(['courses', 'detail', 'c1'], failed)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    await user.click(screen.getByRole('button', { name: 'Compile Module Video' }))
    await act(() => vi.advanceTimersByTimeAsync(5000))
    expect(await screen.findByText('TTS down')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('shows the server error when the job cannot start', async () => {
    const user = userEvent.setup()
    stubApi({
      'POST /api/courses/c1/modules/2/video-jobs': () =>
        json({ detail: 'Not enough slides.' }, 400),
    })
    await renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    await user.click(screen.getByRole('button', { name: 'Compile Module Video' }))
    expect(await screen.findByText('Not enough slides.')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Compile Module Video' })).toBeEnabled(),
    )
  })

  it('stores the generated course even when the reload fails', async () => {
    const user = userEvent.setup()
    const generated = courseJson({ course_name: 'Compliance v2' })
    stubApi({
      'POST /api/courses/c1/generate-quiz': () => json(generated),
      'GET /api/courses': () => json({ detail: 'down' }, 500),
    })
    const { client } = await renderView(<TrainingView course={course()} />)
    client.setQueryData(['courses'], [course()])
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    await user.click(screen.getByRole('button', { name: 'Generate Quiz Now' }))
    await waitFor(() => expect(screen.queryByText('Generating quizzes')).not.toBeInTheDocument())
    expect(client.getQueryData<Course>(['courses', 'detail', 'c1'])?.courseName).toBe(
      'Compliance v2',
    )
    expect(client.getQueryData<Course[]>(['courses'])?.[0]?.courseName).toBe('Compliance v2')
  })

  it('sends one request only when the quiz button is clicked twice', async () => {
    const user = userEvent.setup()
    const fetchMock = stubApi({ 'POST /api/courses/c1/generate-quiz': () => new Promise(() => {}) })
    await renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    const button = screen.getByRole('button', { name: 'Generate Quiz Now' })
    await user.click(button)
    await user.click(button)
    expect(await screen.findByText('Generating quizzes')).toBeInTheDocument()
    expect(requested(fetchMock, '/generate-quiz')).toBe(1)
  })

  it('regenerates an existing video after confirmation', async () => {
    const user = userEvent.setup()
    const fetchMock = stubApi({
      'POST /api/courses/c1/modules/1/video-jobs': () => new Promise(() => {}),
    })
    await renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: 'Regenerate Video' }))
    expect(screen.getByRole('heading', { name: 'Regenerate module video?' })).toBeInTheDocument()
    expect(requested(fetchMock, '/video-jobs')).toBe(0)
    await user.click(screen.getByRole('button', { name: 'Regenerate' }))
    await waitFor(() => expect(requested(fetchMock, '/modules/1/video-jobs')).toBe(1))
    expect(await screen.findByRole('button', { name: 'Regenerating…' })).toBeDisabled()
    // The current video keeps playing until the new one replaces it.
    expect(screen.getByTestId('player')).toBeInTheDocument()
  })
})

describe('TrainingView with the external Video Generator', () => {
  const json = (body: unknown) =>
    new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } })
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          json(
            String(input).includes('/api/generation/config')
              ? { video_generation_mode: 'external' }
              : null,
          ),
        ),
      ),
    )
  })

  const externalCourse = (videoService: Record<string, unknown> | null) =>
    course({
      modules: [
        courseJson().modules[0],
        {
          module_number: 2,
          title: 'Reporting',
          notes: '',
          slides: [],
          video_service: videoService,
        },
      ],
    })

  it('shows live service progress and blocks a second start', async () => {
    const user = userEvent.setup()
    await renderView(
      <TrainingView
        course={externalCourse({ status: 'processing', stage: 'audio', progress: 68 })}
      />,
    )
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    expect(await screen.findByText('Video Generator: audio (68%)')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Video generation progress' })).toHaveAttribute(
      'aria-valuenow',
      '68',
    )
    expect(screen.getByText('Generating Module Video')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generate Module Video' })).toBeDisabled()
    // Service videos have burned-in subtitles and no slide script.
    expect(screen.queryByText('Slide Script / Transcript')).not.toBeInTheDocument()
  })

  it('offers a retry with the failure cause', async () => {
    const user = userEvent.setup()
    await renderView(
      <TrainingView course={externalCourse({ status: 'failed', error: 'TTS endpoint down' })} />,
    )
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    expect(await screen.findByText('Last video run failed: TTS endpoint down')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry Module Video' })).toBeEnabled()
  })

  it('explains where the video comes from before the first run', async () => {
    const user = userEvent.setup()
    await renderView(<TrainingView course={externalCourse(null)} />)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    expect(
      await screen.findByText(/The Video Generator creates this module video/),
    ).toBeInTheDocument()
    expect(screen.getByText('No Video Yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generate Module Video' })).toBeEnabled()
  })
})

describe('TrainingView download', () => {
  it('downloads the video as a named file', async () => {
    const user = userEvent.setup()
    // A fresh body for each call: the generation config request reads one too.
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response('mp4', { status: 200 }))),
    )
    URL.createObjectURL = vi.fn(() => 'blob:video')
    URL.revokeObjectURL = vi.fn()
    const clicked: HTMLAnchorElement[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push(this)
    })
    await renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: 'Download Video' }))
    await waitFor(() => expect(clicked).toHaveLength(1))
    expect(clicked[0]!.download).toBe('c1-module-1-code-of-conduct.mp4')
    expect(clicked[0]!.href).toBe('blob:video')
  })

  it('opens the direct URL in a new tab when the fetch fails', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
    const clicked: HTMLAnchorElement[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push(this)
    })
    await renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: 'Download Video' }))
    await waitFor(() => expect(clicked).toHaveLength(1))
    expect(clicked[0]!.target).toBe('_blank')
    expect(clicked[0]!.href).toContain('assets/videos/c1/m1.mp4')
  })
})
