import { configureApi } from '@lms/shared/api/client'
import { createQueryClient } from '@lms/shared/api/queryClient'
import { parseCourse, type Course } from '@lms/shared/models'
import { ToastProvider } from '@lms/shared/ui/Toast'
import { TooltipProvider } from '@lms/shared/ui/Tooltip'
import { QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { OverlayProvider } from '../../shell/overlay'
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

function renderView(ui: ReactNode) {
  const client = createQueryClient()
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  const view = render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <ToastProvider>
          <OverlayProvider>{ui}</OverlayProvider>
        </ToastProvider>
      </TooltipProvider>
    </QueryClientProvider>,
  )
  return { ...view, invalidate }
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

describe('TrainingView content', () => {
  it('shows the first module with video, notes, transcript and quiz', () => {
    renderView(<TrainingView course={course()} />)
    expect(screen.getByRole('heading', { name: 'Code of conduct', level: 2 })).toBeInTheDocument()
    expect(screen.getAllByText('MODULE 1')).toHaveLength(2)
    expect(screen.getByTestId('player').textContent).toContain('m1_hls/master.m3u8')
    expect(screen.getByText('Read this first.')).toBeInTheDocument()
    expect(screen.getByText('Welcome.')).toBeInTheDocument()
    expect(screen.queryByText('Hidden')).not.toBeInTheDocument()
    expect(screen.getByText('2 Questions')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download Video' })).toBeInTheDocument()
  })

  it('shows the empty course card when there are no modules', () => {
    renderView(<TrainingView course={course({ modules: [] })} />)
    expect(screen.getByText('No Modules Available')).toBeInTheDocument()
  })

  it('shows placeholders for a module without video, notes, script and quiz', async () => {
    const user = userEvent.setup()
    renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    expect(screen.getByText('No Video Compiled Yet')).toBeInTheDocument()
    expect(screen.queryByTestId('player')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Download Video' })).not.toBeInTheDocument()
    expect(
      screen.getByText(/Generate narration scripts to create learner notes/),
    ).toBeInTheDocument()
    expect(screen.getByText(/No slide narration script/)).toBeInTheDocument()
    expect(screen.getByText('No Quiz Available for this Module')).toBeInTheDocument()
  })

  it('marks the active module in the list', async () => {
    const user = userEvent.setup()
    renderView(<TrainingView course={course()} />)
    const [first, second] = screen.getAllByRole('button', { name: /^MODULE \d/ })
    expect(first).toHaveAttribute('aria-current', 'true')
    await user.click(second!)
    expect(second).toHaveAttribute('aria-current', 'true')
    expect(first).not.toHaveAttribute('aria-current')
  })

  it('uses a dropdown on narrow screens', () => {
    mockViewport(true)
    renderView(<TrainingView course={course()} />)
    const select = screen.getByRole('combobox', { name: 'Module' })
    fireEvent.change(select, { target: { value: '1' } })
    expect(screen.getByRole('heading', { name: 'Reporting', level: 2 })).toBeInTheDocument()
    expect(screen.queryByText('COURSE CONTENT')).not.toBeInTheDocument()
  })

  it('goes back to the first module when another course opens', async () => {
    const user = userEvent.setup()
    const { rerender } = renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    expect(screen.getByRole('heading', { name: 'Reporting', level: 2 })).toBeInTheDocument()
    rerender(
      <QueryClientProvider client={createQueryClient()}>
        <TooltipProvider>
          <ToastProvider>
            <OverlayProvider>
              <TrainingView course={course({ course_id: 'c2' })} />
            </OverlayProvider>
          </ToastProvider>
        </TooltipProvider>
      </QueryClientProvider>,
    )
    expect(screen.getByRole('heading', { name: 'Code of conduct', level: 2 })).toBeInTheDocument()
  })

  it('keeps a valid module when the course loses modules', () => {
    const { rerender } = renderView(<TrainingView course={course()} />)
    const fewer = course({ modules: courseJson().modules.slice(0, 1) })
    rerender(
      <QueryClientProvider client={createQueryClient()}>
        <TooltipProvider>
          <ToastProvider>
            <OverlayProvider>
              <TrainingView course={fewer} />
            </OverlayProvider>
          </ToastProvider>
        </TooltipProvider>
      </QueryClientProvider>,
    )
    expect(screen.getByRole('heading', { name: 'Code of conduct', level: 2 })).toBeInTheDocument()
  })
})

describe('TrainingView quiz', () => {
  it('checks an answer, shows the result and the explanation, and updates the score', async () => {
    const user = userEvent.setup()
    renderView(<TrainingView course={course()} />)
    const check = screen.getAllByRole('button', { name: 'Check Answer' })[0]!
    expect(check).toBeDisabled()
    const group = screen.getByRole('radiogroup', { name: 'Question 1 options' })
    await user.click(within(group).getByRole('radio', { name: /First/ }))
    expect(check).toBeEnabled()
    await user.click(check)
    expect(screen.getByText('Why Q one')).toBeInTheDocument()
    expect(screen.getByText('1 / 2', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('In Progress')).toBeInTheDocument()
  })

  it('locks the options after the answer is checked', async () => {
    const user = userEvent.setup()
    renderView(<TrainingView course={course()} />)
    const group = screen.getByRole('radiogroup', { name: 'Question 1 options' })
    await user.click(within(group).getByRole('radio', { name: /Second/ }))
    await user.click(screen.getAllByRole('button', { name: 'Check Answer' })[0]!)
    await user.click(within(group).getByRole('radio', { name: /First/ }))
    expect(within(group).getByRole('radio', { name: /Second/ })).toHaveAttribute(
      'aria-checked',
      'true',
    )
  })

  it('shows Completed when every question is checked and Reset Quiz clears the answers', async () => {
    const user = userEvent.setup()
    renderView(<TrainingView course={course()} />)
    for (const index of [1, 2]) {
      const group = screen.getByRole('radiogroup', { name: `Question ${index} options` })
      await user.click(within(group).getAllByRole('radio')[0]!)
      await user.click(screen.getAllByRole('button', { name: 'Check Answer' })[0]!)
    }
    expect(screen.getByText('Completed!')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reset Quiz' }))
    expect(screen.getByText('In Progress')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Check Answer' })).toHaveLength(2)
  })

  it('keeps answers per module when the user switches modules', async () => {
    const user = userEvent.setup()
    renderView(<TrainingView course={course()} />)
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
  it('disables both generation buttons but keeps download', async () => {
    const user = userEvent.setup()
    renderView(<TrainingView course={course()} readOnly />)
    expect(screen.getByRole('button', { name: 'Download Video' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    expect(screen.getByRole('button', { name: 'Compile Module Video' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Generate Quiz Now' })).toBeDisabled()
  })
})

describe('TrainingView generation', () => {
  function stubFetch(handler: (url: string) => Promise<Response>) {
    const fetchMock = vi.fn((input: RequestInfo | URL) => handler(String(input)))
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

  it('compiles a module video with the module number, shows the overlay, and refreshes courses', async () => {
    const user = userEvent.setup()
    let finish: (response: Response) => void = () => {}
    const fetchMock = stubFetch(() => new Promise((resolve) => (finish = resolve)))
    const { invalidate } = renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    await user.click(screen.getByRole('button', { name: 'Compile Module Video' }))
    expect(await screen.findByText('Generating video')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]![0]).toContain('/api/courses/c1/modules/2/generate-video')
    expect(screen.getByRole('button', { name: 'Compile Module Video' })).toBeDisabled()
    await act(async () => finish(json(courseJson())))
    await waitFor(() => expect(screen.queryByText('Generating video')).not.toBeInTheDocument())
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['courses'] })
  })

  it('sends one request only when the quiz button is clicked twice', async () => {
    const user = userEvent.setup()
    stubFetch(() => new Promise(() => {}))
    renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    const button = screen.getByRole('button', { name: 'Generate Quiz Now' })
    await user.click(button)
    await user.click(button)
    expect(await screen.findByText('Generating quizzes')).toBeInTheDocument()
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1)
    expect(vi.mocked(fetch).mock.calls[0]![0]).toContain('/api/courses/c1/generate-quiz')
  })

  it('shows the server error in a toast and removes the overlay', async () => {
    const user = userEvent.setup()
    stubFetch(() => Promise.resolve(json({ detail: 'Not enough slides.' }, 400)))
    renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    await user.click(screen.getByRole('button', { name: 'Compile Module Video' }))
    expect(await screen.findByText('Not enough slides.')).toBeInTheDocument()
    expect(screen.queryByText('Generating video')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Compile Module Video' })).toBeEnabled()
  })

  it('removes the overlay when the view unmounts during a request', async () => {
    const user = userEvent.setup()
    stubFetch(() => new Promise(() => {}))
    const { unmount } = renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: /Reporting/ }))
    await user.click(screen.getByRole('button', { name: 'Compile Module Video' }))
    expect(await screen.findByText('Generating video')).toBeInTheDocument()
    unmount()
    expect(screen.queryByText('Generating video')).not.toBeInTheDocument()
  })
})

describe('TrainingView download', () => {
  it('downloads the video as a named file', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('mp4', { status: 200 })))
    URL.createObjectURL = vi.fn(() => 'blob:video')
    URL.revokeObjectURL = vi.fn()
    const clicked: HTMLAnchorElement[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push(this)
    })
    renderView(<TrainingView course={course()} />)
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
    renderView(<TrainingView course={course()} />)
    await user.click(screen.getByRole('button', { name: 'Download Video' }))
    await waitFor(() => expect(clicked).toHaveLength(1))
    expect(clicked[0]!.target).toBe('_blank')
    expect(clicked[0]!.href).toContain('assets/videos/c1/m1.mp4')
  })
})
