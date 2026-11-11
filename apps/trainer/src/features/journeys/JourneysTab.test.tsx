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
let preview: Record<string, unknown> = {}

/** The journey's Observer configuration: after a save it is pending, after Apply active. */
const observerReply = (revision: number, applied: boolean) => {
  const scope = { employee_ids: [], department_ids: ['d1'] }
  return {
    journey_id: 'j1',
    revision,
    observers: [
      {
        observer_employee_id: 'e5',
        is_active: applied,
        active: applied ? scope : { employee_ids: [], department_ids: [] },
        pending: scope,
      },
    ],
  }
}
let observerConfig: { revision: number; observers: unknown[] } = { revision: 0, observers: [] }
/** More sidebar journeys after j1, for the sidebar search tests. */
let otherJourneys: Record<string, unknown>[] = []

const sent = (method: string, suffix: string) =>
  calls.filter((call) => call.method === method && call.path.endsWith(suffix))

beforeEach(() => {
  calls = []
  detail = draftDetail
  preview = {}
  observerConfig = { revision: 0, observers: [] }
  otherJourneys = []
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
        return json({
          enabled: true,
          journeys: [{ ...summary, status: detail.status }, ...otherJourneys],
        })
      }
      if (path.endsWith('/course-options')) return json(courseOptions)
      if (path.endsWith('/preview'))
        return json({
          match_count: 12,
          preview_employees: [{ employee_id: 'e1', name: 'Asha Verma', department: 'Sales' }],
          ...preview,
        })
      if (path.endsWith('/observers/apply')) {
        observerConfig = observerReply(observerConfig.revision + 1, true)
        return json(observerConfig)
      }
      if (path.endsWith('/observers')) {
        if (method === 'PUT') observerConfig = observerReply(observerConfig.revision + 1, false)
        return json(observerConfig)
      }
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

  it('saves and then applies Observers on their own, as in the Assign tab', async () => {
    const user = userEvent.setup()
    detail = liveDetail
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    const observers = await screen.findByRole('region', { name: 'Journey observers' })
    await user.click(await within(observers).findByRole('button', { name: 'Add observer' }))
    await user.click(within(observers).getByRole('button', { name: 'Departments (0)' }))
    await user.click(await screen.findByRole('checkbox', { name: 'Sales' }))
    await user.click(screen.getByRole('button', { name: 'Done' }))
    // Unsaved Observer edits must be saved before Apply, and never mark the journey unsaved.
    expect(within(observers).getByRole('button', { name: 'Apply Observers' })).toBeDisabled()
    expect(screen.queryByText('Unsaved changes')).toBeNull()

    await user.click(within(observers).getByRole('button', { name: 'Save Observers' }))
    await waitFor(() => expect(sent('PUT', '/j1/observers')).toHaveLength(1))
    expect(sent('PUT', '/j1/observers')[0]?.body).toEqual({
      revision: 0,
      observers: [{ observer_employee_id: 'e5', employee_ids: [], department_ids: ['d1'] }],
    })
    expect(await within(observers).findByText(/additions need Apply Observers/)).toBeInTheDocument()
    expect(within(observers).getByText('Access not active')).toBeInTheDocument()

    await user.click(within(observers).getByRole('button', { name: 'Apply Observers' }))
    await waitFor(() => expect(sent('POST', '/j1/observers/apply')).toHaveLength(1))
    expect(sent('POST', '/j1/observers/apply')[0]?.body).toEqual({ revision: 1 })
    expect(
      await within(observers).findByText('Active access: 1 departments, 0 selected employees'),
    ).toBeInTheDocument()
    // The journey itself was never saved for this.
    expect(sent('PUT', '/api/learning-journeys/j1')).toHaveLength(0)
  })

  it('cannot apply Observers until the journey is published', async () => {
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    const observers = await screen.findByRole('region', { name: 'Journey observers' })
    expect(
      await within(observers).findByText('Publish the journey before applying observers.'),
    ).toBeInTheDocument()
    expect(within(observers).getByRole('button', { name: 'Apply Observers' })).toBeDisabled()
  })

  it('warns when matching employees are also Observers', async () => {
    preview = { blocked_employee_count: 2 }
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    expect(
      await screen.findByText(
        '2 matching employees are also Observers. Resolve these conflicts before saving.',
      ),
    ).toBeInTheDocument()
  })

  it('sends trainers to Performance for learner progress', async () => {
    const user = userEvent.setup()
    detail = liveDetail
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    const progress = await screen.findByRole('region', { name: 'Learner progress' })
    expect(screen.queryByRole('region', { name: 'Progress' })).toBeNull()
    await user.click(within(progress).getByRole('button', { name: 'View in Performance' }))
    expect(takePendingLinkedReport()).toEqual({
      courseId: null,
      status: null,
      journeyId: 'j1',
      courseStatus: 'active',
    })
  })

  it('filters the Course to add list and never adds a course the filter hides', async () => {
    const user = userEvent.setup()
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    const courses = await screen.findByRole('region', { name: 'Courses' })
    await user.click(within(courses).getByRole('button', { name: 'Add existing course' }))
    const picker = within(courses).getByRole('combobox', { name: 'Course to add' })
    const filter = within(courses).getByRole('searchbox', { name: 'Filter courses' })

    await user.type(filter, 'draft')
    expect(within(picker).queryByRole('option', { name: /Equity Basics/ })).toBeNull()
    expect(within(picker).getByRole('option', { name: /Draft course/ })).toBeDisabled()

    await user.clear(filter)
    await user.type(filter, 'equity')
    await user.selectOptions(picker, 'c2')
    const add = within(courses).getByRole('button', { name: 'Add' })
    expect(add).toBeEnabled()
    // A filter that hides the picked course clears the pick, so Add cannot add it unseen.
    await user.type(filter, ' zzz')
    expect(within(picker).getByRole('option', { name: 'No courses match the filter' })).toBeTruthy()
    expect(add).toBeDisabled()

    await user.clear(filter)
    await user.type(filter, 'equity')
    await user.selectOptions(picker, 'c2')
    await user.click(add)
    expect(within(courses).getByText('Equity Basics')).toBeInTheDocument()
    // The filter starts empty the next time the picker opens.
    await user.click(within(courses).getByRole('button', { name: 'Add existing course' }))
    expect(within(courses).getByRole('searchbox', { name: 'Filter courses' })).toHaveValue('')
  })

  it('searches the journey list without closing the open journey', async () => {
    const user = userEvent.setup()
    otherJourneys = [
      { ...summary, journey_id: 'j7', title: 'Wealth Management Track', status: 'published' },
      { ...summary, journey_id: 'j8', title: 'Compliance Refresher', status: 'draft' },
    ]
    renderCourses(JourneysTab, { url: '/?tab=journeys&journey=j1' })
    const list = await screen.findByRole('list', { name: 'Learning journeys' })
    expect(within(list).getAllByRole('button')).toHaveLength(3)
    const search = screen.getByRole('searchbox', { name: 'Search learning journeys' })

    await user.type(search, 'wealth track')
    expect(within(list).getAllByRole('button')).toHaveLength(1)
    expect(within(list).getByRole('button', { name: /Wealth Management Track/ })).toBeTruthy()
    // The open journey stays open on the right, with no unsaved-changes prompt.
    expect(await screen.findByRole('region', { name: 'Courses' })).toBeInTheDocument()

    await user.clear(search)
    await user.type(search, 'nothing like this')
    expect(screen.queryByRole('list', { name: 'Learning journeys' })).toBeNull()
    expect(screen.getByText('No matching journeys. Try a different search.')).toBeInTheDocument()

    await user.clear(search)
    expect(
      within(screen.getByRole('list', { name: 'Learning journeys' })).getAllByRole('button'),
    ).toHaveLength(3)
  })
})
