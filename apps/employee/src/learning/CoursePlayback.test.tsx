import { act, cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { courseJson, moduleJson, quizQuestion } from '../test/fixtures'
import { FakeSocket, renderDashboard, stubFetch, stubSocket } from '../test/renderApp'

// The player ends the video on a button click.
vi.mock('@lms/shared/video/HlsVideoPlayer', () => ({
  HlsVideoPlayer: ({ hlsUrl, onEnded }: { hlsUrl: string; onEnded?: () => void }) => (
    <button type="button" data-testid="player" onClick={onEnded}>
      {hlsUrl}
    </button>
  ),
}))

const course = courseJson({
  course_id: 'c1',
  course_name: 'Safety',
  modules: [
    moduleJson(1, { quiz: [quizQuestion('First'), quizQuestion('Second', 'B')] }),
    moduleJson(2),
  ],
})

type Grade = { passed: boolean } | Response | Promise<Response>
let grade: Grade = { passed: true }
let fetchMock: ReturnType<typeof stubFetch>
let videoSave: unknown = {}

beforeEach(() => {
  // jsdom has no scrolling.
  Element.prototype.scrollBy = () => {}
  Element.prototype.scrollTo = () => {}
  grade = { passed: true }
  videoSave = {}
  stubSocket()
  fetchMock = stubFetch((url, init) => {
    if (url.pathname.endsWith('/api/me/courses')) return [course]
    if (url.pathname.endsWith('/api/lms/me')) return { performance_views: [] }
    if (url.pathname.endsWith('/api/media-ticket')) return { ticket: 't' }
    if (url.pathname.includes('/modules/') && init?.method === 'PUT') {
      const body = JSON.parse(String(init.body)) as Record<string, unknown>
      if ('video_watched' in body) return videoSave
      if (grade instanceof Response || grade instanceof Promise) return grade
      return {
        quiz_passed: grade.passed,
        quiz_score: grade.passed ? 1 : 0.5,
        correct_count: grade.passed ? 2 : 1,
        total_questions: 2,
        pass_mark: 2 / 3,
        answer_results: { '0': true, '1': grade.passed },
      }
    }
    return new Response('{}', { status: 404 })
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const putBodies = () =>
  fetchMock.mock.calls
    .filter(([, init]) => init?.method === 'PUT')
    .map(([input, init]) => [String(input), JSON.parse(String(init?.body))] as const)

async function openAndWatch() {
  const user = userEvent.setup()
  renderDashboard('/?view=course&course_id=c1')
  expect(await screen.findByText('Quiz locked')).toBeInTheDocument()
  await user.click(screen.getByTestId('player'))
  expect(await screen.findByText('Video completed. Quiz unlocked.')).toBeInTheDocument()
  return { user, quiz: screen.getByRole('region', { name: 'Module quiz' }) }
}

async function answer(user: ReturnType<typeof userEvent.setup>, quiz: HTMLElement) {
  const first = within(quiz).getByRole('radiogroup', { name: 'First question' })
  const second = within(quiz).getByRole('radiogroup', { name: 'Second question' })
  await user.click(within(first).getByRole('radio', { name: 'First first' }))
  const submit = within(quiz).getByRole('button', { name: 'Submit Quiz' })
  expect(submit).toBeDisabled()
  await user.click(within(second).getByRole('radio', { name: 'Second second' }))
  expect(submit).toBeEnabled()
  await user.click(submit)
}

describe('CoursePlayback', () => {
  it('fetches fresh progress before choosing the resumed module from a cached list', async () => {
    const stale = courseJson({
      course_id: 'c1',
      course_name: 'Safety',
      modules: [moduleJson(1), moduleJson(2), moduleJson(3)],
    })
    const fresh = {
      ...stale,
      module_progress: {
        '1': { video_watched: true, quiz_passed: true },
        '2': { video_watched: true, quiz_passed: true },
      },
    }
    let courseReads = 0
    fetchMock.mockImplementation(
      async (input) =>
        new Response(
          JSON.stringify(
            String(input).endsWith('/api/me/courses')
              ? ++courseReads === 1
                ? [stale]
                : [fresh]
              : {},
          ),
        ),
    )
    const user = userEvent.setup()
    renderDashboard()
    await user.click(await screen.findByRole('button', { name: 'Start Safety' }))
    expect(
      await screen.findByRole('heading', { name: 'Module title 3', level: 2 }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Module title 1', level: 2 }),
    ).not.toBeInTheDocument()
    expect(courseReads).toBeGreaterThanOrEqual(2)
  })
  it('blocks stale module playback when fresh entry progress fails and permits retry', async () => {
    let courseReads = 0
    let fail = true
    fetchMock.mockImplementation(async (input) => {
      if (String(input).endsWith('/api/me/courses')) {
        courseReads += 1
        return courseReads > 1 && fail
          ? new Response('{}', { status: 500 })
          : new Response(JSON.stringify([course]))
      }
      return new Response('{}')
    })
    const user = userEvent.setup()
    renderDashboard()
    await user.click(await screen.findByRole('button', { name: 'Start Safety' }))
    expect(
      await screen.findByText(
        'Could not load your latest progress. Retry before opening the course.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('player')).not.toBeInTheDocument()
    fail = false
    await user.click(screen.getByRole('button', { name: 'Retry course' }))
    expect(
      await screen.findByRole('heading', { name: 'Module title 1', level: 2 }),
    ).toBeInTheDocument()
  })
  it('does not invent a zero score when saved passed progress has no quiz score', async () => {
    const saved = courseJson({
      course_id: 'c1',
      modules: [moduleJson(1)],
      module_progress: { '1': { video_watched: true, quiz_passed: true } },
    })
    fetchMock.mockImplementation(
      async (input) =>
        new Response(JSON.stringify(String(input).endsWith('/api/me/courses') ? [saved] : {})),
    )
    renderDashboard('/?view=course&course_id=c1')
    expect(await screen.findByText('Saved score unavailable')).toBeInTheDocument()
    expect(screen.queryByText('0.0%')).not.toBeInTheDocument()
  })
  it('keeps an unsubmitted selection during a background refresh', async () => {
    const { user, quiz } = await openAndWatch()
    const first = within(quiz).getByRole('radiogroup', { name: 'First question' })
    await user.click(within(first).getByRole('radio', { name: 'First first' }))
    await act(() => FakeSocket.instances[0]!.send([course]))
    expect(within(first).getByRole('radio', { name: 'First first' })).toBeChecked()
    expect(within(quiz).getByText('Answered 1 of 2')).toHaveClass('text-gray')
  })
  it('keeps a manually selected module and saved answers during a background update', async () => {
    const resumed = courseJson({
      ...course,
      module_progress: {
        '1': {
          video_watched: true,
          quiz_passed: true,
          quiz_score: 1,
          selected_answers: { '0': 'A', '1': 'B' },
        },
      },
    })
    fetchMock.mockImplementation(
      async (input) =>
        new Response(JSON.stringify(String(input).endsWith('/api/me/courses') ? [resumed] : {})),
    )
    const user = userEvent.setup()
    renderDashboard('/?view=course&course_id=c1')
    expect(
      await screen.findByRole('heading', { name: 'Module title 2', level: 2 }),
    ).toBeInTheDocument()
    await user.click(
      within(screen.getByRole('list', { name: 'Course modules' })).getAllByRole('button')[0]!,
    )
    expect(screen.getByRole('heading', { name: 'Module title 1', level: 2 })).toBeInTheDocument()
    await act(() => FakeSocket.instances[0]!.send([resumed]))
    expect(screen.getByRole('heading', { name: 'Module title 1', level: 2 })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /First first/ })).toBeChecked()
  })
  it('locks the next module until the quiz passes', async () => {
    renderDashboard('/?view=course&course_id=c1')
    const list = await screen.findByRole('list', { name: 'Course modules' })
    const items = within(list).getAllByRole('button')
    expect(items[1]).toBeDisabled()
    expect(items[1]).toHaveTextContent('Locked')
  })

  it('saves the video and waits for Continue before opening the next module', async () => {
    const { user, quiz } = await openAndWatch()
    await waitFor(() =>
      expect(putBodies()).toContainEqual([
        expect.stringContaining('/api/me/courses/c1/modules/1'),
        { video_watched: true },
      ]),
    )
    await answer(user, quiz)
    expect(putBodies()).toContainEqual([
      expect.stringContaining('/modules/1'),
      { selected_answers: { '0': 'A', '1': 'B' } },
    ])
    expect(await screen.findByText('Quiz passed')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Module title 1', level: 2 })).toBeInTheDocument()
    expect(screen.queryByText(/Answered/)).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Continue to next module' }))
    expect(screen.getByRole('heading', { name: 'Module title 2', level: 2 })).toBeInTheDocument()
  })

  it('fails the quiz and asks for the video again', async () => {
    grade = { passed: false }
    const { user, quiz } = await openAndWatch()
    await answer(user, quiz)
    expect(await screen.findByText('Quiz not passed')).toBeInTheDocument()
    expect(within(quiz).getByRole('status')).toHaveTextContent('1 of 2 correct')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('Your answer · Incorrect')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Rewatch lesson' }))
    expect(quiz).not.toBeInTheDocument()
    expect(screen.getByText('Quiz locked')).toBeInTheDocument()
  })

  it('keeps the answers when the submit fails', async () => {
    grade = new Response(JSON.stringify({ detail: 'Grading is down' }), { status: 500 })
    const { user, quiz } = await openAndWatch()
    await answer(user, quiz)
    expect(await screen.findByText('Grading is down')).toBeInTheDocument()
    expect(within(quiz).getByRole('button', { name: 'Submit Quiz' })).toBeEnabled()
  })

  it('shows inline results and Finish course after the final module', async () => {
    const single = courseJson({ course_id: 'c1', modules: [moduleJson(1)] })
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.endsWith('/api/me/courses')) return new Response(JSON.stringify([single]))
      if (init?.method === 'PUT' && String(init.body).includes('selected_answers')) {
        return new Response(
          JSON.stringify({
            quiz_passed: true,
            quiz_score: 1,
            correct_count: 1,
            total_questions: 1,
            pass_mark: 2 / 3,
          }),
        )
      }
      return new Response('{}')
    })
    const user = userEvent.setup()
    renderDashboard('/?view=course&course_id=c1')
    await user.click(await screen.findByTestId('player'))
    const quiz = await screen.findByRole('region', { name: 'Module quiz' })
    await user.click(within(quiz).getByRole('radio', { name: 'Q1 first' }))
    await act(() => user.click(within(quiz).getByRole('button', { name: 'Submit Quiz' })))
    expect(await screen.findByText('Quiz passed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Finish course' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows the saved answers of a passed quiz for review', async () => {
    const passed = courseJson({
      course_id: 'c1',
      modules: [moduleJson(1, { quiz: [quizQuestion('Q1', 'B', true)] }), moduleJson(2)],
      module_progress: {
        '1': {
          video_watched: true,
          quiz_passed: true,
          quiz_score: 1,
          selected_answers: { '0': 'B' },
        },
      },
    })
    fetchMock.mockImplementation(async (input) =>
      String(input).endsWith('/api/me/courses')
        ? new Response(JSON.stringify([passed]))
        : new Response('{}'),
    )
    renderDashboard('/?view=course&course_id=c1')
    const list = await screen.findByRole('list', { name: 'Course modules' })
    expect(screen.getByRole('heading', { name: 'Module title 2', level: 2 })).toBeInTheDocument()
    await userEvent.setup().click(within(list).getAllByRole('button')[0]!)
    const quiz = await screen.findByRole('region', { name: 'Module quiz' })
    expect(quiz).toHaveTextContent('Quiz already passed')
    const group = within(quiz).getByRole('radiogroup', { name: 'Q1 question' })
    expect(within(group).getByRole('radio', { name: /Q1 second/ })).toBeChecked()
    for (const radio of within(group).getAllByRole('radio')) expect(radio).toBeDisabled()
    expect(within(quiz).queryByText('Why Q1')).not.toBeInTheDocument()
    expect(within(quiz).queryByRole('button', { name: 'Submit Quiz' })).not.toBeInTheDocument()
  })

  it('saves the video again on submit when the first save failed', async () => {
    videoSave = new Response(JSON.stringify({ detail: 'Save failed' }), { status: 500 })
    const user = userEvent.setup()
    renderDashboard('/?view=course&course_id=c1')
    await user.click(await screen.findByTestId('player'))
    expect(
      await screen.findByText('Could not save video progress. Save failed'),
    ).toBeInTheDocument()
    const quiz = screen.getByRole('region', { name: 'Module quiz' })
    videoSave = {}
    await answer(user, quiz)
    expect(await screen.findByText('Quiz passed')).toBeInTheDocument()
    expect(putBodies().map(([, body]) => body)).toEqual([
      { video_watched: true },
      { video_watched: true },
      { selected_answers: { '0': 'A', '1': 'B' } },
    ])
  })

  it('waits for a pending video save before it submits the quiz', async () => {
    let finishSave!: (body: unknown) => void
    videoSave = new Promise((resolve) => (finishSave = resolve))
    const { user, quiz } = await openAndWatch()
    await answer(user, quiz)
    expect(within(quiz).getByRole('button', { name: 'Submitted' })).toBeDisabled()
    // The server rejects a quiz before the video completion is saved.
    expect(putBodies().map(([, body]) => body)).toEqual([{ video_watched: true }])
    finishSave({})
    expect(await screen.findByText('Quiz passed')).toBeInTheDocument()
    expect(putBodies().map(([, body]) => body)).toEqual([
      { video_watched: true },
      { selected_answers: { '0': 'A', '1': 'B' } },
    ])
  })

  it('keeps the next module locked until the video of a module without a quiz is saved', async () => {
    const noQuiz = courseJson({
      course_id: 'c1',
      modules: [moduleJson(1, { quiz: [] }), moduleJson(2)],
    })
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.endsWith('/api/me/courses')) return new Response(JSON.stringify([noQuiz]))
      if (init?.method === 'PUT') {
        return videoSave instanceof Response ? videoSave : new Response('{}')
      }
      return new Response('{}')
    })
    videoSave = new Response(JSON.stringify({ detail: 'Save failed' }), { status: 500 })
    const user = userEvent.setup()
    renderDashboard('/?view=course&course_id=c1')
    await user.click(await screen.findByTestId('player'))
    const notice = await screen.findByRole('alert')
    expect(notice).toHaveTextContent('Video progress was not saved.')
    const list = screen.getByRole('list', { name: 'Course modules' })
    expect(within(list).getAllByRole('button')[1]).toBeDisabled()
    videoSave = {}
    await user.click(within(notice).getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    expect(within(list).getAllByRole('button')[1]).toBeEnabled()
    expect(putBodies().map(([, body]) => body)).toEqual([
      { video_watched: true },
      { video_watched: true },
    ])
  })

  it('keeps the module while the quiz is graded', async () => {
    let finish!: (response: Response) => void
    grade = new Promise<Response>((resolve) => (finish = resolve))
    const { user, quiz } = await openAndWatch()
    await answer(user, quiz)
    const list = screen.getByRole('list', { name: 'Course modules' })
    await user.click(within(list).getAllByRole('button')[0]!)
    // Without the guard, the click resets the quiz and enables a second submit.
    expect(within(quiz).getByRole('button', { name: 'Submitted' })).toBeDisabled()
    finish(
      new Response(
        JSON.stringify({
          quiz_passed: true,
          quiz_score: 1,
          correct_count: 2,
          total_questions: 2,
          pass_mark: 2 / 3,
        }),
      ),
    )
    expect(await screen.findByText('Quiz passed')).toBeInTheDocument()
    expect(putBodies().filter(([, body]) => 'selected_answers' in body)).toHaveLength(1)
  })
})
