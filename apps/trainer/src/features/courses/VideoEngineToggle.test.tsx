import { setMediaTicket } from '@lms/shared/api/client'
import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { stubBrowser, stubFetch } from '../documents/test/renderDocuments'
import { BlueprintTab } from './BlueprintTab'
import { setCourseFilter } from './courseQueries'
import { accessJson, courseJson, renderCourses } from './test/renderCourses'
import {
  noticeDurationMs,
  STANDARD_RECOMMENDED_TEXT,
  VIDEO_ENGINE_RECOMMENDED_TEXT,
} from './VideoEngineNotice'

beforeEach(() => {
  stubBrowser()
  setCourseFilter('all')
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  setMediaTicket(null)
})

const config = (overrides: Record<string, unknown> = {}) => ({
  video_generation_mode: 'external',
  video_engine_toggle_enabled: true,
  video_engine_available: true,
  ...overrides,
})

/** A text-only course (recommended On) unless overridden. */
const engineCourse = (overrides: Record<string, unknown> = {}) =>
  courseJson({
    video_engine: true,
    video_engine_recommended: true,
    meaningful_image_count: 0,
    ...overrides,
  })

/** Serves one course; PUT echoes the stored course with the requested engine. */
function api({
  course = engineCourse(),
  generationConfig = config(),
  put,
}: {
  course?: Record<string, unknown>
  generationConfig?: Record<string, unknown>
  put?: (body: Record<string, unknown>) => unknown
} = {}) {
  let current = course
  return stubFetch((url, init) => {
    const method = init?.method ?? 'GET'
    if (url.pathname === '/api/lms/me') return accessJson()
    if (url.pathname === '/api/generation/config') return generationConfig
    if (url.pathname === '/api/courses') return [current]
    if (url.pathname === '/api/courses/c1' && method === 'PUT') {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>
      if (put) return put(body)
      current = { ...current, video_engine: body.video_engine }
      return current
    }
    if (url.pathname === '/api/courses/c1') return current
    return null
  })
}

/** The JSON body of the engine save (the PUT to the course). */
function putBody(fetchMock: ReturnType<typeof stubFetch>): unknown {
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
  return call ? JSON.parse(String(call[1]?.body)) : undefined
}

const open = () => renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
const toggle = () => screen.findByRole('switch', { name: 'Video Engine' })

describe('Video Engine toggle', () => {
  it('sits in the Blueprint toolbar with the recommendation for a text-only document', async () => {
    api()
    open()
    const control = await toggle()
    expect(control).toHaveAttribute('aria-checked', 'true')
    expect(
      screen.getByText('Recommended: On · no images in the source document'),
    ).toBeInTheDocument()
    // The advisory appears only after a change, never on load.
    expect(screen.queryByText('Not recommended for this document')).not.toBeInTheDocument()
  })

  it('defaults off and counts the images for a document with screenshots', async () => {
    api({
      course: engineCourse({
        video_engine: false,
        video_engine_recommended: false,
        meaningful_image_count: 6,
      }),
    })
    open()
    expect(await toggle()).toHaveAttribute('aria-checked', 'false')
    expect(
      screen.getByText('Recommended: Off · 6 images in the source document'),
    ).toBeInTheDocument()
  })

  it('is hidden when the server has the toggle switched off', async () => {
    api({ generationConfig: { video_generation_mode: 'external' } })
    open()
    await screen.findByRole('button', { name: /Save Changes/ })
    expect(screen.queryByRole('switch', { name: 'Video Engine' })).not.toBeInTheDocument()
  })

  it('saves the change at once and advises against leaving the recommendation', async () => {
    const fetchMock = api()
    open()
    await userEvent.click(await toggle())
    await waitFor(() => expect(putBody(fetchMock)).toEqual({ video_engine: false }))
    expect(await screen.findByText(VIDEO_ENGINE_RECOMMENDED_TEXT)).toBeInTheDocument()
    expect(screen.getByText('Not recommended for this document')).toBeInTheDocument()
    expect(screen.getByTestId('video-engine-off-recommendation')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole('switch', { name: 'Video Engine' })).toHaveAttribute(
        'aria-checked',
        'false',
      ),
    )

    // Back to the recommendation: the notice and the amber dot go.
    await userEvent.click(screen.getByRole('switch', { name: 'Video Engine' }))
    await waitFor(() =>
      expect(screen.queryByText(VIDEO_ENGINE_RECOMMENDED_TEXT)).not.toBeInTheDocument(),
    )
    expect(screen.queryByTestId('video-engine-off-recommendation')).not.toBeInTheDocument()
  })

  it('shows the screenshot advice when Video Engine is turned on for an image document', async () => {
    api({
      course: engineCourse({
        video_engine: false,
        video_engine_recommended: false,
        meaningful_image_count: 1,
      }),
    })
    open()
    await userEvent.click(await toggle())
    expect(await screen.findByText(STANDARD_RECOMMENDED_TEXT)).toBeInTheDocument()
  })

  it('asks first when switching would clear generated content', async () => {
    const fetchMock = api({
      course: engineCourse({
        thumbnail_path: '/assets/thumbs/c1.png',
        modules: [
          {
            module_number: 1,
            title: 'Basics',
            source_text: 'Basics text',
            num_questions: 0,
            notes: 'Notes',
            video_path: '/assets/videos/c1/module_1.mp4',
          },
        ],
      }),
    })
    open()
    await userEvent.click(await toggle())
    const dialog = await screen.findByRole('dialog', { name: 'Switch video engine?' })
    expect(
      within(dialog).getByText(/generated videos, quizzes, notes and thumbnail/),
    ).toBeInTheDocument()

    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false)

    await userEvent.click(await toggle())
    await userEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Switch engine' }),
    )
    await waitFor(() => expect(putBody(fetchMock)).toEqual({ video_engine: false }))
  })

  it('is disabled while the course is generating', async () => {
    api({ course: engineCourse({ generation: { status: 'running' } }) })
    open()
    expect(await toggle()).toBeDisabled()
  })

  it('cannot be turned on when the Video Generator is not configured', async () => {
    api({
      course: engineCourse({ video_engine: false }),
      generationConfig: config({ video_engine_available: false }),
    })
    open()
    expect(await toggle()).toBeDisabled()
  })

  it('shows the server message when the save fails', async () => {
    api({
      put: () =>
        new Response(
          JSON.stringify({
            detail: 'Wait for the current generation to finish before switching engines.',
          }),
          { status: 409 },
        ),
    })
    open()
    await userEvent.click(await toggle())
    expect(
      await screen.findByText(
        'Wait for the current generation to finish before switching engines.',
      ),
    ).toBeInTheDocument()
  })
})

describe('Video Engine notice timing', () => {
  it('stays for the reading time of about 30 words', () => {
    expect(noticeDurationMs(VIDEO_ENGINE_RECOMMENDED_TEXT)).toBeGreaterThanOrEqual(12_000)
    expect(noticeDurationMs(VIDEO_ENGINE_RECOMMENDED_TEXT)).toBeLessThanOrEqual(14_000)
    expect(noticeDurationMs(STANDARD_RECOMMENDED_TEXT)).toBeGreaterThanOrEqual(12_000)
    expect(noticeDurationMs('Short')).toBe(8_000)
  })

  it('hides itself after the reading time, pausing while hovered', async () => {
    api()
    open()
    await userEvent.click(await toggle())
    const notice = (await screen.findByText(VIDEO_ENGINE_RECOMMENDED_TEXT)).closest(
      '[role="status"]',
    ) as HTMLElement
    vi.useFakeTimers()
    const duration = noticeDurationMs(VIDEO_ENGINE_RECOMMENDED_TEXT)

    fireEvent.mouseEnter(notice)
    await act(async () => {
      vi.advanceTimersByTime(duration + 1_000)
    })
    expect(screen.getByText(VIDEO_ENGINE_RECOMMENDED_TEXT)).toBeInTheDocument()

    fireEvent.mouseLeave(notice)
    await act(async () => {
      vi.advanceTimersByTime(duration)
    })
    // Then the 300 ms fade.
    await act(async () => {
      vi.advanceTimersByTime(400)
    })
    expect(screen.queryByText(VIDEO_ENGINE_RECOMMENDED_TEXT)).not.toBeInTheDocument()
  })

  it('closes with the dismiss button and with Escape', async () => {
    api()
    open()
    await userEvent.click(await toggle())
    await screen.findByText(VIDEO_ENGINE_RECOMMENDED_TEXT)
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    await waitFor(() =>
      expect(screen.queryByText(VIDEO_ENGINE_RECOMMENDED_TEXT)).not.toBeInTheDocument(),
    )

    await userEvent.click(screen.getByRole('switch', { name: 'Video Engine' }))
    await userEvent.click(screen.getByRole('switch', { name: 'Video Engine' }))
    await screen.findByText(VIDEO_ENGINE_RECOMMENDED_TEXT)
    fireEvent.keyDown(screen.getByRole('button', { name: 'Dismiss' }), { key: 'Escape' })
    await waitFor(() =>
      expect(screen.queryByText(VIDEO_ENGINE_RECOMMENDED_TEXT)).not.toBeInTheDocument(),
    )
  })
})
