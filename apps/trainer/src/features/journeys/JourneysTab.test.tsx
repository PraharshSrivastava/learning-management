import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { takePendingLinkedReport } from '../../shell/linkedReport'
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

const stepOne = {
  course_id: 'c1',
  course_name: 'Indian Market Structure',
  module_count: 5,
  unlock_rule: 'after_previous',
  is_required: true,
  eligible: true,
  learner_count: 0,
  started_count: 0,
}

const draftDetail = {
  ...summary,
  description: '',
  target_audience: 'All employees',
  certificate_enabled: true,
  stages: [{ title: 'Market basics', steps: [stepOne] }],
  rule: { include_all: true, deadline_mode: 'relative', deadline_days: 45 },
}

const liveDetail = {
  ...draftDetail,
  status: 'published',
  published_at: '2026-10-01T10:00:00',
  assigned_count: 6,
  stages: [
    {
      title: 'Market basics',
      steps: [
        { ...stepOne, learner_count: 6, started_count: 2 },
        {
          ...stepOne,
          course_id: 'c2',
          course_name: 'Equity Basics',
          learner_count: 0,
          started_count: 0,
        },
      ],
    },
  ],
}

const courseOptions = [
  { course_id: 'c1', course_name: 'Indian Market Structure', module_count: 5, eligible: true },
  {
    course_id: 'c2',
    course_name: 'Equity Basics',
    module_count: 6,
    eligible: true,
    journeys: [{ journey_id: 'j9', title: 'Compliance & Ethics' }],
  },
  {
    course_id: 'c3',
    course_name: 'Draft course',
    module_count: 2,
    eligible: false,
    reason: 'Generate the full course first.',
  },
]

interface Call {
  method: string
  path: string
  body: unknown
}

let calls: Call[] = []
let detail: Record<string, unknown> = draftDetail

const sent = (method: string, suffix: string) =>
  calls.filter((call) => call.method === method && call.path.endsWith(suffix))

beforeEach(() => {
  calls = []
  detail = draftDetail
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), 'http://localhost').pathname
      const method = init?.method ?? 'GET'
      calls.push({ method, path, body: init?.body ? JSON.parse(String(init.body)) : null })
      const json = (body: unknown) => new Response(JSON.stringify(body))
      if (path.endsWith('/api/learning-journeys')) {
        if (method === 'POST')
          return json({ ...draftDetail, journey_id: 'j2', title: 'Wealth basics', stages: [] })
        return json({ enabled: true, journeys: [{ ...summary, status: detail.status }] })
      }
      if (path.endsWith('/course-options')) return json(courseOptions)
      if (path.endsWith('/preview'))
        return json({
          match_count: 12,
          preview_employees: [{ employee_id: 'e1', name: 'Asha Verma', department: 'Sales' }],
        })
      if (path.endsWith('/observers')) return json({ observers: [] })
      if (path.endsWith('/api/observer/options'))
        return json({ departments: [{ department_id: 'd1', name: 'Sales' }] })
      if (path.endsWith('/api/assignment/options'))
        return json({
          employees: [
            { employee_id: 'e5', name: 'Meera Iyer', department: 'Compliance', status: 'active' },
          ],
          departments: [],
        })
      if (path.endsWith('/api/assignment/saved-groups')) return json([])
      if (path.endsWith('/api/learning-journeys/j1')) {
        if (method === 'PUT') return json({ ...detail, updated_at: 'v2' })
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
  it('adds an existing course in order and saves the draft', async () => {
    const user = userEvent.setup()
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    const courses = await screen.findByRole('region', { name: 'Courses' })
    expect(within(courses).getByText('Indian Market Structure')).toBeInTheDocument()
    // One section only: no section name to fill in.
    expect(within(courses).queryByRole('textbox', { name: /Section 1 name/ })).toBeNull()
    expect(await screen.findByText('12 employees')).toBeInTheDocument()
    // The live count uses the unsaved rule.
    expect(sent('POST', '/preview')[0]?.body).toMatchObject({
      rule: { include_all: true, deadline_days: 45 },
      observer_employee_ids: [],
    })

    await user.click(within(courses).getByRole('button', { name: 'Add existing course' }))
    const picker = within(courses).getByRole('combobox', { name: 'Course to add' })
    // A course that is not fully generated is listed but cannot be picked.
    expect(within(picker).getByRole('option', { name: /Draft course/ })).toBeDisabled()
    await user.selectOptions(picker, 'c2')
    await user.click(within(courses).getByRole('button', { name: 'Add' }))
    expect(within(courses).getByText('Equity Basics')).toBeInTheDocument()
    expect(within(courses).getByText('Also in Compliance & Ethics')).toBeInTheDocument()
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Save draft' }))
    await waitFor(() => expect(sent('PUT', '/j1')).toHaveLength(1))
    expect(sent('PUT', '/j1')[0]?.body).toMatchObject({
      expected_updated_at: 'v1',
      stages: [
        {
          title: 'Market basics',
          steps: [
            { course_id: 'c1', unlock_rule: 'after_previous', is_required: true },
            { course_id: 'c2', unlock_rule: 'after_previous', is_required: true },
          ],
        },
      ],
      rule: { include_all: true, deadline_mode: 'relative', deadline_days: 45 },
    })
    // Only the journey changed, so Observers are not re-sent.
    expect(sent('PUT', '/observers')).toHaveLength(0)
  })

  it('describes an any-order journey correctly before publishing', async () => {
    const user = userEvent.setup()
    detail = {
      ...draftDetail,
      stages: [
        {
          title: 'Basics',
          steps: [stepOne, { ...stepOne, course_id: 'c2', course_name: 'Equity Basics' }],
        },
      ],
    }
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    const courses = await screen.findByRole('region', { name: 'Courses' })
    await user.click(within(courses).getByRole('button', { name: 'In any order' }))
    await user.click(screen.getByRole('button', { name: 'Publish & assign' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent(
      'All 2 courses are assigned now, and learners can take them in any order.',
    )
    expect(dialog).not.toHaveTextContent('Only the first course')
  })

  it('warns before removing a course learners already have from a live journey', async () => {
    const user = userEvent.setup()
    detail = liveDetail
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    const courses = await screen.findByRole('region', { name: 'Courses' })
    expect(screen.getByRole('button', { name: 'Save & apply' })).toBeDisabled()

    await user.click(
      within(courses).getByRole('button', { name: 'Remove Indian Market Structure' }),
    )
    await user.click(screen.getByRole('button', { name: 'Save & apply' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('6 learners have it.')
    expect(dialog).toHaveTextContent('2 started or finished it and keep it.')
    expect(dialog).toHaveTextContent('4 who have not started lose it.')
    expect(sent('PUT', '/j1')).toHaveLength(0)

    await user.click(within(dialog).getByRole('button', { name: 'Save & apply' }))
    await waitFor(() => expect(sent('PUT', '/j1')).toHaveLength(1))
  })

  it('asks for a name before creating a journey', async () => {
    const user = userEvent.setup()
    renderCourses(JourneysTab, { url: '/?tab=journeys' })
    await user.click(await screen.findByRole('button', { name: 'New' }))
    const dialog = await screen.findByRole('dialog', { name: 'New learning journey' })
    const create = within(dialog).getByRole('button', { name: 'Create' })
    expect(create).toBeDisabled()
    await user.type(within(dialog).getByRole('textbox', { name: 'Journey name' }), 'Wealth basics')
    await user.click(create)
    await waitFor(() => expect(sent('POST', '/api/learning-journeys')).toHaveLength(1))
    expect(sent('POST', '/api/learning-journeys')[0]?.body).toEqual({ title: 'Wealth basics' })
  })

  it('saves a new Observer before applying a live journey, so they are never enrolled', async () => {
    const user = userEvent.setup()
    detail = liveDetail
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    const observers = await screen.findByRole('region', { name: 'Journey observers' })
    await user.click(within(observers).getByRole('button', { name: 'Add observer' }))
    await user.click(await screen.findByText('Meera Iyer'))
    const observer = await within(observers).findByRole('region', { name: 'Observer Meera Iyer' })
    await user.click(within(observer).getByRole('button', { name: 'Departments' }))
    await user.click(await screen.findByRole('checkbox', { name: 'Sales' }))
    await user.click(screen.getByRole('button', { name: 'Apply' }))
    await user.clear(screen.getByRole('textbox', { name: 'Description' }))
    await user.type(screen.getByRole('textbox', { name: 'Description' }), 'Markets 101')

    await user.click(screen.getByRole('button', { name: 'Save & apply' }))
    await waitFor(() => expect(sent('PUT', '/j1')).toHaveLength(1))
    const order = calls
      .filter((call) => call.method === 'PUT')
      .map((call) => call.path.split('/').pop())
    expect(order).toEqual(['observers', 'j1'])
    expect(sent('PUT', '/observers')[0]?.body).toEqual({
      observers: [{ observer_employee_id: 'e5', employee_ids: [], department_ids: ['d1'] }],
    })
  })

  it('sends trainers to Performance for learner progress', async () => {
    const user = userEvent.setup()
    detail = liveDetail
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    const progress = await screen.findByRole('region', { name: 'Learner progress' })
    expect(screen.queryByRole('region', { name: 'Progress' })).toBeNull()
    await user.click(within(progress).getByRole('button', { name: 'View in Performance' }))
    expect(takePendingLinkedReport()).toEqual({ courseId: null, status: null, journeyId: 'j1' })
  })
})
