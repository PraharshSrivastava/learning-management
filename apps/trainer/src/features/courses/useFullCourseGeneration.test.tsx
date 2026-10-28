import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { stubBrowser, stubFetch } from '../documents/test/renderDocuments'
import { courseJson, renderCourses } from './test/renderCourses'
import { useFullCourseGeneration, useFullCourseGenerationOverlay } from './useFullCourseGeneration'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

/** Stands in for TrainerShell: it owns the overlay and outlives a tab or course change. */
function Shell({ showEditor, onToggle }: { showEditor: boolean; onToggle: () => void }) {
  useFullCourseGenerationOverlay()
  return (
    <>
      <button type="button" onClick={onToggle}>
        Switch tab
      </button>
      {showEditor && <Editor />}
    </>
  )
}

/** Stands in for BlueprintEditor: it starts the job, then can unmount while the job keeps running. */
function Editor() {
  const generation = useFullCourseGeneration()
  return (
    <button type="button" onClick={() => generation.start('c1', false)}>
      Generate
    </button>
  )
}

function Harness() {
  const [showEditor, setShowEditor] = useState(true)
  return <Shell showEditor={showEditor} onToggle={() => setShowEditor((current) => !current)} />
}

describe('full course generation overlay', () => {
  it('stays up after the editor unmounts, until the job ends', async () => {
    stubBrowser()
    let polls = 0
    stubFetch((url, init) => {
      const key = `${init?.method ?? 'GET'} ${url.pathname}`
      if (key === 'POST /api/courses/c1/generation-jobs') {
        return { id: 'j1', course_id: 'c1', status: 'queued' }
      }
      if (key === 'GET /api/generation-jobs/j1') {
        polls += 1
        return { id: 'j1', course_id: 'c1', status: polls >= 2 ? 'completed' : 'running' }
      }
      if (url.pathname === '/api/courses') return [courseJson()]
      if (url.pathname === '/api/courses/c1') return courseJson()
      return null
    })
    renderCourses(Harness)
    vi.useFakeTimers({ shouldAdvanceTime: true })

    fireEvent.click(await screen.findByRole('button', { name: 'Generate' }))
    expect(await screen.findByText('Generating course content')).toBeInTheDocument()

    // Back/Forward or a tab change unmounts the editor while the job keeps polling.
    fireEvent.click(screen.getByRole('button', { name: 'Switch tab' }))
    expect(screen.queryByRole('button', { name: 'Generate' })).not.toBeInTheDocument()
    expect(screen.getByText('Generating course content')).toBeInTheDocument()

    await act(() => vi.advanceTimersByTimeAsync(4000))
    expect(screen.getByText('Generating course content')).toBeInTheDocument()
    await act(() => vi.advanceTimersByTimeAsync(4000))

    await waitFor(() =>
      expect(screen.queryByText('Generating course content')).not.toBeInTheDocument(),
    )
    expect(polls).toBe(2)
  })

  it('shows module video progress when the Video Generator makes the videos', async () => {
    stubBrowser()
    const inProgress = courseJson({
      modules: [
        { module_number: 1, title: 'One', video_path: 'assets/videos/c1/module_1.mp4' },
        {
          module_number: 2,
          title: 'Two',
          video_service: { status: 'processing', stage: 'rendering', progress: 82 },
        },
      ],
    })
    stubFetch((url, init) => {
      const key = `${init?.method ?? 'GET'} ${url.pathname}`
      if (url.pathname === '/api/generation/config') return { video_generation_mode: 'external' }
      if (key === 'POST /api/courses/c1/generation-jobs') {
        return { id: 'j1', course_id: 'c1', status: 'queued' }
      }
      if (key === 'GET /api/generation-jobs/j1')
        return { id: 'j1', course_id: 'c1', status: 'running' }
      if (url.pathname === '/api/courses') return [inProgress]
      if (url.pathname === '/api/courses/c1') return inProgress
      return null
    })
    renderCourses(Harness)
    vi.useFakeTimers({ shouldAdvanceTime: true })

    fireEvent.click(await screen.findByRole('button', { name: 'Generate' }))
    expect(
      await screen.findByText(/the Video Generator produces each module video/),
    ).toBeInTheDocument()
    await act(() => vi.advanceTimersByTimeAsync(4000))
    expect(
      await screen.findByText(/Module videos ready: 1 of 2\s+Module 2: rendering 82%/),
    ).toBeInTheDocument()
  })
})
