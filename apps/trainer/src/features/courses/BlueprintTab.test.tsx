import { setMediaTicket } from '@lms/shared/api/client'
import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { trainerKeys } from '../../shell/queryKeys'
import { stubBrowser, stubFetch } from '../documents/test/renderDocuments'
import { BlueprintTab } from './BlueprintTab'
import { setCourseFilter } from './courseQueries'
import { accessJson, courseJson, renderCourses } from './test/renderCourses'

beforeEach(() => {
  stubBrowser()
  setCourseFilter('all')
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  setMediaTicket(null)
})

const courses = [
  courseJson(),
  courseJson({ course_id: 'c2', course_name: 'Legacy Training', lifecycle_state: 'disabled' }),
  courseJson({ course_id: 'c3', course_name: 'Risk Management', lifecycle_state: 'draft' }),
]

type Routes = Record<string, unknown>

/** Answers by path. `/api/lms/me` defaults to an author without library access. */
function api(routes: Routes = {}) {
  return stubFetch((url, init) => {
    const key = `${init?.method ?? 'GET'} ${url.pathname}`
    if (key in routes) {
      const body = routes[key]
      return typeof body === 'function' ? (body as (url: URL) => unknown)(url) : body
    }
    if (url.pathname === '/api/lms/me') return accessJson()
    if (url.pathname === '/api/courses') return courses
    if (url.pathname.startsWith('/api/courses/')) return courseJson()
    return null
  })
}

const sidebar = () => screen.getByRole('list', { name: 'My courses' })

describe('My Courses sidebar', () => {
  it('lists the courses with the count and the empty selection', async () => {
    api()
    renderCourses(BlueprintTab)
    expect(await screen.findByText('Legacy Training')).toBeInTheDocument()
    expect(screen.getByText('3 courses')).toBeInTheDocument()
    expect(within(sidebar()).getByText('Disabled')).toBeInTheDocument()
    expect(screen.getByText('No Course Selected')).toBeInTheDocument()
  })

  it('filters by availability', async () => {
    api()
    renderCourses(BlueprintTab)
    await screen.findByText('Legacy Training')
    await userEvent.selectOptions(screen.getByLabelText('Course availability'), 'draft')
    expect(screen.getByText('1 courses')).toBeInTheDocument()
    expect(within(sidebar()).getByText('Risk Management')).toBeInTheDocument()
    expect(within(sidebar()).queryByText('Legacy Training')).not.toBeInTheDocument()
  })

  it('shows the empty state', async () => {
    api({ 'GET /api/courses': [] })
    renderCourses(BlueprintTab)
    expect(await screen.findByText('No courses created yet')).toBeInTheDocument()
  })

  it('shows the load error', async () => {
    // A 4xx reply is final. A 5xx reply is retried once first.
    api({ 'GET /api/courses': () => new Response('{"detail":"Boom"}', { status: 403 }) })
    renderCourses(BlueprintTab)
    expect(await screen.findByText('Error loading courses')).toBeInTheDocument()
  })

  it('selects a course into the URL and reloads its detail', async () => {
    api()
    const { search, invalidate } = renderCourses(BlueprintTab)
    await userEvent.click(await screen.findByText('Legacy Training'))
    await waitFor(() => expect(search().course).toBe('c2'))
    expect(invalidate).toHaveBeenCalledWith({ queryKey: trainerKeys.course('c2') })
  })
})

describe('Blueprint editor', () => {
  it('loads the selected course into the form', async () => {
    api()
    renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    expect(await screen.findByLabelText('Course Name')).toHaveValue('Compliance Essentials')
    expect(screen.getByLabelText('Difficulty')).toHaveValue('Medium')
    expect(screen.getByLabelText('Module 2 title')).toHaveValue('Reporting')
    expect(screen.getByRole('button', { name: /Generate Course/ })).toBeEnabled()
  })

  it('requires a course name before saving', async () => {
    const fetchMock = api()
    renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    await userEvent.clear(await screen.findByLabelText('Course Name'))
    await userEvent.click(screen.getByRole('button', { name: /Save Changes/ }))
    expect(await screen.findByText('Required')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false)
  })

  it('saves the edited blueprint, without blank modules', async () => {
    const fetchMock = api({ 'PUT /api/courses/c1': courseJson({ course_name: 'Renamed' }) })
    renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    const name = await screen.findByLabelText('Course Name')
    await userEvent.clear(name)
    await userEvent.type(name, 'Renamed')
    await userEvent.selectOptions(screen.getByLabelText('Difficulty'), 'Hard')
    await userEvent.click(screen.getByRole('button', { name: 'Add Module' }))
    const firstQuiz = screen.getAllByLabelText('Quiz questions:')[0]!
    await userEvent.clear(firstQuiz)
    await userEvent.type(firstQuiz, '5')
    await userEvent.click(screen.getByRole('button', { name: /Save Changes/ }))
    expect(await screen.findByText('Course blueprint successfully saved!')).toBeInTheDocument()
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
    expect(JSON.parse(String(put?.[1]?.body))).toMatchObject({
      course_name: 'Renamed',
      course_difficulty: 'Hard',
      modules: [
        { title: 'Basics', num_questions: 5 },
        { title: 'Reporting', num_questions: 3 },
      ],
    })
  })

  it('shows the save error', async () => {
    api({ 'PUT /api/courses/c1': () => new Response('{"detail":"Nope"}', { status: 400 }) })
    renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    await userEvent.click(await screen.findByRole('button', { name: /Save Changes/ }))
    expect(await screen.findByText(/Nope/)).toBeInTheDocument()
  })

  it('deletes a module and Reset brings it back', async () => {
    api()
    renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    await screen.findByLabelText('Module 2 title')
    await userEvent.click(screen.getAllByRole('button', { name: 'Delete module' })[0]!)
    expect(screen.queryByLabelText('Module 2 title')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Module 1 title')).toHaveValue('Reporting')
    await userEvent.click(screen.getByRole('button', { name: 'Reset' }))
    expect(screen.getByLabelText('Module 1 title')).toHaveValue('Basics')
  })

  it('reorders modules with the keyboard', async () => {
    api()
    renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    await screen.findByLabelText('Module 2 title')
    const handles = screen.getAllByRole('button', { name: /Reorder module/ })
    handles[0]!.focus()
    await userEvent.keyboard('{ArrowDown}')
    expect(screen.getByLabelText('Module 1 title')).toHaveValue('Reporting')
  })
})

describe('Blueprint detail pane', () => {
  it('shows the course detail load error instead of the spinner', async () => {
    api({
      'GET /api/courses': [courseJson({ modules: [] })],
      'GET /api/courses/c1': () => new Response('{"detail":"Forbidden"}', { status: 403 }),
    })
    renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    expect(await screen.findByText('Error loading course')).toBeInTheDocument()
  })

  it('retries a broken image when the media ticket arrives', async () => {
    const image = { image_id: 'i1', caption: 'Chart', file_path: 'assets/img/chart.png' }
    api({ 'GET /api/courses/c1': courseJson({ images: [image] }) })
    renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    fireEvent.error(await screen.findByAltText('Chart'))
    expect(screen.queryByAltText('Chart')).not.toBeInTheDocument()
    act(() => setMediaTicket('t1'))
    expect(screen.getByAltText('Chart').getAttribute('src')).toContain('media_ticket=t1')
  })
})

describe('Full course generation', () => {
  const generated = courseJson({
    thumbnail_path: 'assets/t.png',
    modules: [
      {
        module_number: 1,
        title: 'Basics',
        source_text: 'Basics text',
        num_questions: 0,
        video_path: 'assets/v.mp4',
        quiz: { questions: [] },
      },
    ],
    module_count: 1,
  })
  const calls = (fetchMock: ReturnType<typeof api>) =>
    fetchMock.mock.calls.map(
      ([input, init]) => `${init?.method ?? 'GET'} ${new URL(String(input), 'http://x').pathname}`,
    )

  it('saves, starts a job, polls it, and opens the Courses tab', async () => {
    let polls = 0
    let done = false
    const fetchMock = api({
      'PUT /api/courses/c1': courseJson(),
      'POST /api/courses/c1/generation-jobs': { id: 'j1', course_id: 'c1', status: 'queued' },
      'GET /api/generation-jobs/j1': () => {
        polls += 1
        done = polls >= 2
        return { id: 'j1', course_id: 'c1', status: done ? 'completed' : 'running' }
      },
      'GET /api/courses/c1': () => (done ? generated : courseJson()),
    })
    const { search } = renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fireEvent.click(await screen.findByRole('button', { name: /Generate Course/ }))
    await waitFor(() => expect(calls(fetchMock)).toContain('POST /api/courses/c1/generation-jobs'))
    expect(calls(fetchMock).indexOf('PUT /api/courses/c1')).toBeLessThan(
      calls(fetchMock).indexOf('POST /api/courses/c1/generation-jobs'),
    )
    await act(() => vi.advanceTimersByTimeAsync(4000))
    await act(() => vi.advanceTimersByTimeAsync(4000))
    await waitFor(() => expect(search().tab).toBe('courses'))
    expect(polls).toBe(2)
  })

  it('shows a failed job and stays on the Blueprint tab', async () => {
    api({
      'PUT /api/courses/c1': courseJson(),
      'POST /api/courses/c1/generation-jobs': { id: 'j1', course_id: 'c1', status: 'queued' },
      'GET /api/generation-jobs/j1': {
        id: 'j1',
        course_id: 'c1',
        status: 'failed',
        error: 'Out of credits',
      },
    })
    const { search } = renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fireEvent.click(await screen.findByRole('button', { name: /Generate Course/ }))
    await act(() => vi.advanceTimersByTimeAsync(4000))
    expect(await screen.findByText('Out of credits')).toBeInTheDocument()
    expect(search().tab).toBe('blueprint')
  })

  it('does not start a job when the save fails', async () => {
    const fetchMock = api({
      'PUT /api/courses/c1': () => new Response('{"detail":"Nope"}', { status: 400 }),
    })
    renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    await userEvent.click(await screen.findByRole('button', { name: /Generate Course/ }))
    expect(await screen.findByText(/Nope/)).toBeInTheDocument()
    expect(calls(fetchMock)).not.toContain('POST /api/courses/c1/generation-jobs')
  })

  it('resumes from the checkpoint without a save', async () => {
    const failed = courseJson({
      generation: { status: 'failed', failed_checkpoint: 'wave_1', error: 'Timed out' },
    })
    const fetchMock = api({
      'GET /api/courses': [failed],
      'GET /api/courses/c1': failed,
      'POST /api/courses/c1/continue-generation': generated,
    })
    const { search } = renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
    await userEvent.click(await screen.findByRole('button', { name: /Continue generation/ }))
    await waitFor(() => expect(search().tab).toBe('courses'))
    expect(calls(fetchMock)).toContain('POST /api/courses/c1/continue-generation')
    expect(calls(fetchMock)).not.toContain('PUT /api/courses/c1')
  })
})

describe('Course library access', () => {
  it('hides the My/All switch without the capability', async () => {
    api()
    renderCourses(BlueprintTab)
    await screen.findByText('Legacy Training')
    expect(screen.queryByRole('button', { name: 'All Courses' })).not.toBeInTheDocument()
  })

  it('opens the read-only library and a course in it', async () => {
    const fetchMock = api({
      'GET /api/lms/me': accessJson({ library: true }),
      'GET /api/trainer/course-library': {
        total: 1,
        items: [
          {
            course_id: 'x1',
            course_name: 'Data Privacy Primer',
            creator_name: 'Tara Menon',
            status: 'draft',
          },
        ],
      },
      'GET /api/courses/x1': courseJson({
        course_id: 'x1',
        trainer_id: 'tara',
        course_name: 'Data Privacy Primer',
        creator_name: 'Tara Menon',
        can_manage: false,
        read_only_reason: 'Only its creator can make changes.',
      }),
      'GET /api/courses/x1/assignment': { rule: { deadline_days: 14, is_active: true } },
    })
    const { search } = renderCourses(BlueprintTab)
    const all = await screen.findByRole('button', { name: 'All Courses' })
    expect(screen.getByRole('button', { name: 'My Courses' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await userEvent.click(all)
    expect(all).toHaveAttribute('aria-pressed', 'true')
    const row = await screen.findByRole('button', { name: /Data Privacy Primer/ })
    expect(row).toHaveTextContent('Created by Tara Menon · draft · Not generated')
    expect(screen.getByText('1 courses')).toBeInTheDocument()
    const listCall = fetchMock.mock.calls.find(([input]) =>
      String(input).includes('course-library'),
    )
    expect(String(listCall?.[0])).toContain('scope=all&limit=25&offset=0')

    await userEvent.click(row)
    expect(await screen.findByRole('heading', { name: 'Data Privacy Primer' })).toBeInTheDocument()
    expect(screen.getByText('Only its creator can make changes.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit' })).toBeDisabled()
    expect(screen.getByText('Deadline: 14 days')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /View Performance/ }))
    await waitFor(() => expect(search().tab).toBe('performance'))
  })

  it('filters the library by status', async () => {
    const fetchMock = api({
      'GET /api/lms/me': accessJson({ library: true }),
      'GET /api/trainer/course-library': { total: 0, items: [] },
    })
    renderCourses(BlueprintTab)
    await userEvent.click(await screen.findByRole('button', { name: 'All Courses' }))
    await screen.findByText('0 courses')
    await userEvent.selectOptions(screen.getByLabelText('Course status'), 'ready')
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([input]) => String(input).includes('status=ready'))).toBe(
        true,
      ),
    )
  })
})
