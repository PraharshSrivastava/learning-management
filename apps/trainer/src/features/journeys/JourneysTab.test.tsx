import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderCourses } from '../courses/test/renderCourses'
import { JourneysTab } from './JourneysTab'

const summary = {
  journey_id: 'j1',
  title: 'Markets Foundation',
  status: 'draft',
  updated_at: 'v1',
  course_count: 1,
  stage_count: 1,
  warnings: [],
}

const detail = {
  ...summary,
  description: '',
  target_audience: 'All employees',
  certificate_enabled: true,
  stages: [
    {
      title: 'Market basics',
      steps: [
        {
          course_id: 'c1',
          course_name: 'Indian Market Structure',
          module_count: 5,
          unlock_rule: 'open',
          is_required: true,
          eligible: true,
        },
      ],
    },
  ],
  rule: { include_all: true, deadline_mode: 'relative', deadline_days: 45 },
}

const courseOptions = [
  { course_id: 'c1', course_name: 'Indian Market Structure', module_count: 5, eligible: true },
  { course_id: 'c2', course_name: 'Equity Basics', module_count: 6, eligible: true },
  {
    course_id: 'c3',
    course_name: 'Draft course',
    module_count: 2,
    eligible: false,
    reason: 'Generate the full course first.',
  },
]

const puts: unknown[] = []

beforeEach(() => {
  puts.length = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), 'http://localhost').pathname
      const json = (body: unknown) => new Response(JSON.stringify(body))
      if (path.endsWith('/api/learning-journeys'))
        return json({ enabled: true, journeys: [summary] })
      if (path.endsWith('/course-options')) return json(courseOptions)
      if (path.endsWith('/preview')) return json({ match_count: 12, preview_employees: [] })
      if (path.endsWith('/api/assignment/options')) return json({ employees: [], departments: [] })
      if (path.endsWith('/api/assignment/saved-groups')) return json([])
      if (path.endsWith('/api/learning-journeys/j1')) {
        if (init?.method === 'PUT') {
          puts.push(JSON.parse(String(init.body)))
          return json({ ...detail, updated_at: 'v2' })
        }
        return json(detail)
      }
      return new Response('{}', { status: 404 })
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('JourneysTab', () => {
  it('adds an existing course in order and saves the journey', async () => {
    const user = userEvent.setup()
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    const stages = await screen.findByRole('region', { name: 'Stages and courses' })
    expect(within(stages).getByText('Indian Market Structure')).toBeInTheDocument()
    expect(await screen.findByText(/12/)).toBeInTheDocument()

    await user.click(within(stages).getByRole('button', { name: 'Add existing course' }))
    const picker = within(stages).getByRole('combobox', { name: 'Course to add' })
    // A course that is not fully generated is listed but cannot be picked.
    expect(within(picker).getByRole('option', { name: /Draft course/ })).toBeDisabled()
    await user.selectOptions(picker, 'c2')
    await user.click(within(stages).getByRole('button', { name: 'Add' }))
    expect(within(stages).getByText('Equity Basics')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0]).toMatchObject({
      expected_updated_at: 'v1',
      stages: [
        {
          title: 'Market basics',
          steps: [
            { course_id: 'c1', unlock_rule: 'open', is_required: true },
            { course_id: 'c2', unlock_rule: 'after_previous', is_required: true },
          ],
        },
      ],
      rule: { include_all: true, deadline_mode: 'relative', deadline_days: 45 },
    })
  })
})
