// RTL tests for the rule editor and group editing.
import { configureApi } from '@lms/shared/api/client'
import { parseCourse } from '@lms/shared/models'
import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { Reply, RequestInit, Requester } from './api'
import { deadlineRange } from './dates'
import { renderCourses } from '../courses/test/renderCourses'
import { RuleView } from './RuleView'
import { AssignmentWorkspace } from './workspace'

const course = parseCourse({
  course_id: 'c1',
  course_name: 'Compliance',
  status: 'published',
  lifecycle_state: 'active',
})

const employees = [
  { employee_id: 'e1', name: 'Dev Patel', department: 'Finance', status: 'active' },
  { employee_id: 'e2', name: 'Meera Iyer', department: 'Finance', status: 'active' },
  { employee_id: 'e3', name: 'Arjun Mehta', department: 'Operations', status: 'active' },
]

interface Call {
  path: string
  init: RequestInit
}

function setup(rule: Record<string, unknown>) {
  const calls: Call[] = []
  const request: Requester = async (path, init = {}): Promise<Reply> => {
    calls.push({ path, init })
    const route = path.split('?')[0] ?? path
    if (route.endsWith('/assignment/options')) {
      return { status: 200, body: { employees, departments: ['Finance', 'Operations'] } }
    }
    if (route.endsWith('/saved-groups')) return { status: 200, body: [] }
    if (route.endsWith('/employee-preview')) {
      return { status: 200, body: { total: 2, total_assigned_count: 1, employees: [] } }
    }
    if (route.endsWith('/observer/options')) return { status: 200, body: { departments: [] } }
    if (route.endsWith('/observers')) {
      return { status: 200, body: { course_id: 'c1', revision: 1, observers: [] } }
    }
    if (route.endsWith('/assignment')) {
      return {
        status: 200,
        body: {
          rule: { course_id: 'c1', updated_at: 'v1', is_active: true, ...rule },
          match_count: 2,
          total_assigned_count: 1,
        },
      }
    }
    return { status: 404, body: null }
  }
  const workspace = new AssignmentWorkspace({
    request,
    refreshCourses: async () => true,
    refreshPerformance: async () => {},
    debounceMs: 0,
  })
  const view = renderCourses(
    () => (
      <RuleView
        course={course}
        workspace={workspace}
        request={request}
        onCourseChanged={async () => {}}
      />
    ),
    { person: null },
  )
  return { ...view, calls, workspace }
}

const mutations = (calls: Call[]) =>
  calls.filter((c) => (c.init.method ?? 'GET') !== 'GET' && !c.path.includes('employee-preview'))

beforeEach(() => {
  configureApi({ app: 'trainer', publicMount: '/lms/trainer', configuredApiBase: undefined })
})

afterEach(cleanup)

describe('RuleView', () => {
  it('the switch hides and shows individual employee selection', async () => {
    const user = userEvent.setup()
    const { workspace } = setup({ include_all: true, deadline_days: 7 })
    await workspace.loadForCourse('c1')
    const toggle = await screen.findByRole('switch', { name: 'All active employees' })
    expect(toggle.getAttribute('aria-checked')).toBe('true')
    const target = screen.getByRole('region', { name: 'Target employees' })
    expect(within(target).queryByRole('button', { name: 'Add employees' })).toBeNull()

    await user.click(toggle)
    expect(toggle.getAttribute('aria-checked')).toBe('false')
    expect(workspace.getState().rule.includeAll).toBe(false)
    expect(workspace.getState().dirty).toBe(true)
    expect(within(target).getByRole('button', { name: 'Add employees' })).toBeTruthy()
    // No group has to be created before an individual employee can be chosen.
    expect(within(target).queryByRole('button', { name: 'Add group' })).toBeNull()
  })

  it('adds several employees at once without creating a group, then removes them', async () => {
    const user = userEvent.setup()
    const { workspace } = setup({ include_all: false, deadline_days: 7 })
    await workspace.loadForCourse('c1')
    const target = await screen.findByRole('region', { name: 'Target employees' })
    await user.click(within(target).getByRole('button', { name: 'Add employees' }))
    const dialog = await screen.findByRole('dialog', { name: 'Add employees' })
    await user.type(within(dialog).getByRole('searchbox'), 'a')
    await user.click(within(dialog).getByRole('checkbox', { name: 'Meera Iyer (e2)' }))
    await user.click(within(dialog).getByRole('checkbox', { name: 'Arjun Mehta (e3)' }))
    await user.click(within(dialog).getByRole('button', { name: 'Add 2 employees' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(workspace.getState().rule.includeGroups).toEqual([
      expect.objectContaining({ name: 'Selected employees', employeeIds: ['e2', 'e3'] }),
    ])
    expect(within(target).getByText('Meera Iyer (e2)')).toBeTruthy()

    await user.click(within(target).getByRole('button', { name: /Remove Meera Iyer/ }))
    expect(workspace.getState().rule.includeGroups[0]?.employeeIds).toEqual(['e3'])
    await user.click(within(target).getByRole('button', { name: /Remove Arjun Mehta/ }))
    expect(workspace.getState().rule.includeGroups).toEqual([])
  })

  it('keeps department filters as a supplementary group beside picked employees', async () => {
    const user = userEvent.setup()
    const { workspace } = setup({ include_all: false, deadline_days: 7 })
    await workspace.loadForCourse('c1')
    const target = await screen.findByRole('region', { name: 'Target employees' })
    await user.click(
      within(target).getByRole('button', { name: 'Departments, mailing lists and saved groups' }),
    )
    await user.click(within(target).getByRole('button', { name: 'Add filter group' }))
    const group = within(target).getByRole('region', { name: 'Include group 1' })
    expect(within(group).getByText('Departments')).toBeTruthy()
    // Individual employees are chosen with Add employees, not inside a filter group.
    expect(within(group).queryByRole('button', { name: 'Add employee' })).toBeNull()
  })

  it('excludes individual employees through the same picker', async () => {
    const user = userEvent.setup()
    const { workspace } = setup({ include_all: true, deadline_days: 7 })
    await workspace.loadForCourse('c1')
    const exclusions = await screen.findByRole('group', { name: 'Exclusions' })
    await user.click(within(exclusions).getByRole('button', { name: 'Exclude employees' }))
    const dialog = await screen.findByRole('dialog', { name: 'Exclude employees' })
    await user.click(within(dialog).getByRole('checkbox', { name: 'Dev Patel (e1)' }))
    await user.click(within(dialog).getByRole('button', { name: 'Exclude 1 employee' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(workspace.getState().rule.excludeGroups).toEqual([
      expect.objectContaining({ employeeIds: ['e1'] }),
    ])
    expect(workspace.getState().rule.includeGroups).toEqual([])
  })

  it('chips follow the directory order and keep unknown ids removable', async () => {
    const { workspace } = setup({
      include_all: false,
      deadline_days: 7,
      include_groups: [{ group_id: 'g', name: 'Mixed order', employee_ids: ['gone', 'e3', 'e1'] }],
    })
    await workspace.loadForCourse('c1')
    const target = await screen.findByRole('region', { name: 'Target employees' })
    await within(target).findByText('Dev Patel (e1)')
    const labels = within(target)
      .getAllByRole('button', { name: /^Remove / })
      .map((b) => b.getAttribute('aria-label'))
    expect(labels).toEqual([
      expect.stringContaining('Dev Patel (e1)'),
      expect.stringContaining('Arjun Mehta (e3)'),
      expect.stringContaining('Unavailable employee (gone)'),
    ])
  })

  it('a mixed saved group shows a warning and blocks Save Rule', async () => {
    const user = userEvent.setup()
    const { workspace, calls } = setup({
      include_all: false,
      deadline_days: 7,
      include_groups: [
        { group_id: 'g', name: 'Mixed', employee_ids: ['e1'], departments: ['Finance'] },
      ],
    })
    await workspace.loadForCourse('c1')
    const group = await screen.findByRole('region', { name: 'Include group 1' })
    expect(
      within(group).getByText(
        'This saved group mixes specific employees with filters. Clear one side before saving.',
      ),
    ).toBeTruthy()

    await user.click(screen.getByRole('button', { name: 'Save Rule' }))
    expect(
      await screen.findByText(
        'Include group 1 mixes specific employees with filters. Clear one side before saving.',
      ),
    ).toBeTruthy()
    expect(mutations(calls)).toEqual([])
  })

  it('switches the deadline mode and edits the due days', async () => {
    const user = userEvent.setup()
    const { workspace } = setup({
      include_all: true,
      deadline_mode: 'fixed',
      deadline_date: '2099-10-31',
      deadline_days: 7,
    })
    await workspace.loadForCourse('c1')
    const section = await screen.findByRole('region', { name: 'Completion deadline' })
    const date = within(section).getByLabelText('Completion date') as HTMLInputElement
    expect(date.value).toBe('2099-10-31')
    expect(within(section).getByText('Due by the end of this date (Asia/Kolkata).')).toBeTruthy()

    // Only a complete date inside today .. 1 January ten years on reaches the rule.
    const { min, max } = deadlineRange()
    expect(date.min).toBe(min)
    expect(date.max).toBe(max)
    fireEvent.change(date, { target: { value: max } })
    expect(workspace.getState().rule.deadlineDate).toBe(max)
    fireEvent.change(date, { target: { value: '2000-01-01' } })
    expect(workspace.getState().rule.deadlineDate).toBe(max)
    expect(date.getAttribute('aria-invalid')).toBe('true')
    fireEvent.blur(date)
    expect(date.value).toBe(max)
    expect(date.getAttribute('aria-invalid')).toBeNull()

    await user.click(within(section).getByRole('button', { name: 'Days after assignment' }))
    const field = within(section).getByRole('textbox', { name: 'Due days after assignment' })
    expect((field as HTMLInputElement).value).toBe('7')
    // As in Flutter, an empty field falls back to 1 day at once.
    await user.clear(field)
    expect((field as HTMLInputElement).value).toBe('1')
    await user.tripleClick(field)
    await user.keyboard('1a4')
    expect((field as HTMLInputElement).value).toBe('14')
    expect(workspace.getState().rule.deadlineMode).toBe('relative')
    expect(workspace.getState().rule.deadlineDays).toBe(14)
    expect(within(section).queryByText('Due by the end of this date (Asia/Kolkata).')).toBeNull()
  })

  it('Save Rule sends the edited rule once the preview is fresh', async () => {
    const user = userEvent.setup()
    const { workspace, calls } = setup({ include_all: true, deadline_days: 7 })
    await workspace.loadForCourse('c1')
    await user.click(await screen.findByRole('switch', { name: 'All active employees' }))
    await user.click(screen.getByRole('button', { name: 'Save Rule' }))
    await waitFor(() => expect(mutations(calls)).toHaveLength(1))
    const put = mutations(calls)[0]!
    expect(put.init.method).toBe('PUT')
    expect(put.init.json).toMatchObject({ include_all: false, expected_updated_at: 'v1' })
    expect(await screen.findByText('Assignment rule saved.')).toBeTruthy()
  })
  it('the form is inert while a save runs, so the keyboard cannot edit it', async () => {
    const { workspace, container } = setup({ include_all: true, deadline_days: 7 })
    await workspace.loadForCourse('c1')
    await screen.findByRole('switch', { name: 'All active employees' })
    const card = container.querySelector('[aria-busy]')!
    expect(card.hasAttribute('inert')).toBe(false)
    act(() => workspace['set']({ isSaving: true }))
    expect(card.hasAttribute('inert')).toBe(true)
    expect(card.getAttribute('aria-busy')).toBe('true')
  })
})
