// Ports of frontend/test/assignment_refresh_test.dart.
import { describe, expect, it, vi } from 'vitest'
import type { Reply, RequestInit, Requester } from './api'
import { AssignmentWorkspace, groupValidationError } from './workspace'
import { defaultAssignmentRule, type AssignmentGroup } from '@lms/shared/models'

type Handler = (path: string, init: RequestInit) => Reply | Promise<Reply>

interface Call {
  path: string
  method: string
  json: unknown
}

const ok = (body: unknown, status = 200): Reply => ({ status, body })

const saved = (id: string, days = 7) => ({
  rule: { course_id: id, include_all: true, deadline_days: days, updated_at: 'v1' } as Record<
    string,
    unknown
  >,
  match_count: 3,
  total_assigned_count: 2,
  preview_employees: [],
})

/** Path without the query string. */
const route = (path: string) => path.split('?')[0] ?? path

function setup(handler: Handler) {
  const calls: Call[] = []
  const request: Requester = async (path, init = {}) => {
    calls.push({ path, method: init.method ?? 'GET', json: init.json })
    return handler(path, init)
  }
  const refreshCourses = vi.fn(async () => true)
  const refreshPerformance = vi.fn(async () => {})
  const workspace = new AssignmentWorkspace({
    request,
    refreshCourses,
    refreshPerformance,
    debounceMs: 0,
  })
  return { workspace, calls, refreshCourses, refreshPerformance }
}

/** Default replies for the four reads. */
function reads(path: string): Reply | null {
  const r = route(path)
  if (r.endsWith('/options')) return ok({})
  if (r.endsWith('/saved-groups')) return ok([])
  if (r.endsWith('/employee-preview'))
    return ok({ total: 0, total_assigned_count: 0, employees: [] })
  return null
}

describe('AssignmentWorkspace', () => {
  it('new rules default to Specific date but saved relative deadlines are preserved', async () => {
    const { workspace } = setup((path) => {
      const read = reads(path)
      if (read) return read
      const data = saved('course')
      data.rule.deadline_mode = 'relative'
      if (path.includes('/new/')) data.rule.updated_at = null
      return ok(data)
    })
    await workspace.loadForCourse('new')
    expect(workspace.getState().rule.deadlineMode).toBe('fixed')
    expect(workspace.getState().rule.deadlineDate).toBeNull()
    await workspace.reloadSavedRule('new')
    expect(workspace.getState().rule.deadlineMode).toBe('fixed')
    await workspace.loadForCourse('saved')
    expect(workspace.getState().rule.deadlineMode).toBe('relative')
    expect(workspace.getState().rule.deadlineDays).toBe(7)
  })

  it('same-course Refresh reloads rule, options, groups and counts and keeps the edited deadline', async () => {
    let version = 1
    const { workspace, calls, refreshCourses } = setup((path) => {
      const r = route(path)
      if (r.endsWith('/options'))
        return ok({ departments: [`Department ${version}`], employees: [] })
      if (r.endsWith('/saved-groups')) return ok([])
      if (r.endsWith('/employee-preview')) {
        return ok({ total: 3, total_assigned_count: version + 1, employees: [] })
      }
      return ok(saved('one'))
    })
    await workspace.loadForCourse('one')
    workspace.updateRule({ ...workspace.getState().rule, deadlineDays: 15 })
    version = 2
    await workspace.refreshOptionsAndGroups()
    const state = workspace.getState()
    expect(state.rule.deadlineDays).toBe(15)
    expect(state.dirty).toBe(true)
    expect(state.options.departments).toEqual(['Department 2'])
    expect(state.totalAssignedCount).toBe(3)
    expect(state.refreshGeneration).toBe(2)
    expect(calls.filter((c) => route(c.path).endsWith('/assignment'))).toHaveLength(2)
    expect(calls.filter((c) => route(c.path).endsWith('/saved-groups'))).toHaveLength(2)
    const previews = calls.filter((c) => route(c.path).endsWith('/employee-preview'))
    expect(JSON.stringify(previews.at(-1)?.json)).toContain('15')
    expect(calls.filter((c) => c.method === 'PUT')).toHaveLength(0)
    expect(refreshCourses).toHaveBeenCalledTimes(2)
  })

  it('a partial refresh failure is visible and does not erase the last employee options', async () => {
    let fail = false
    const { workspace } = setup((path) => {
      const r = route(path)
      if (r.endsWith('/options')) return fail ? ok({}, 503) : ok({ departments: ['Risk'] })
      if (r.endsWith('/saved-groups')) return ok([])
      if (r.endsWith('/employee-preview')) {
        return ok({ total: 3, total_assigned_count: 2, employees: [] })
      }
      return ok(saved('one'))
    })
    await workspace.loadForCourse('one')
    fail = true
    await workspace.refreshOptionsAndGroups()
    expect(workspace.getState().options.departments).toEqual(['Risk'])
    expect(workspace.getState().error).toContain('Employee options')
    expect(workspace.getState().isLoading).toBe(false)
  })

  it('an earlier course response cannot replace the newly selected course', async () => {
    let release: (reply: Reply) => void = () => {}
    const gate = new Promise<Reply>((resolve) => {
      release = resolve
    })
    const { workspace } = setup((path) => {
      const read = reads(path)
      if (read) return read
      if (path.includes('/one/')) return gate
      return ok(saved('two', 12))
    })
    const old = workspace.loadForCourse('one')
    await Promise.resolve()
    await workspace.loadForCourse('two')
    release(ok(saved('one', 3)))
    await old
    expect(workspace.getState().loadedCourseId).toBe('two')
    expect(workspace.getState().rule.deadlineDays).toBe(12)
  })

  it('expired course access clears cached employee data', async () => {
    let expired = false
    const { workspace } = setup((path) => {
      if (expired) return ok({}, 401)
      const r = route(path)
      if (r.endsWith('/options')) return ok({ departments: ['Risk'] })
      if (r.endsWith('/saved-groups')) return ok([])
      if (r.endsWith('/employee-preview')) {
        return ok({ total: 3, total_assigned_count: 2, employees: [] })
      }
      return ok(saved('one'))
    })
    await workspace.loadForCourse('one')
    expired = true
    await workspace.refreshOptionsAndGroups()
    expect(workspace.getState().options.departments).toEqual([])
    expect(workspace.getState().totalAssignedCount).toBe(0)
    expect(workspace.getState().error).toContain('Sign in again')
  })

  it('unsaved Observer conflicts block publication before any assignment mutation', async () => {
    let mutations = 0
    const { workspace } = setup((path, init) => {
      const r = route(path)
      if (r.endsWith('/options')) {
        return ok({ employees: [{ employee_id: 'observer', name: 'Aditya' }] })
      }
      if (r.endsWith('/saved-groups')) return ok([])
      if (r.endsWith('/employee-preview')) {
        const payload = init.json as { observer_employee_ids: string[] }
        return ok({
          total: 3,
          total_assigned_count: 2,
          employees: [],
          conflicting_observer_ids: payload.observer_employee_ids.length === 0 ? [] : ['observer'],
        })
      }
      if ((init.method ?? 'GET') !== 'GET') mutations++
      return ok(saved('one'))
    })
    await workspace.loadForCourse('one')
    workspace.updateDraftObservers(['observer'])
    await workspace.publish('one')
    expect(mutations).toBe(0)
    expect(workspace.getState().error).toContain('Aditya')
    expect(workspace.getState().error).toContain('Observers')
  })

  it('a mixed group blocks save before any mutation', async () => {
    let mutations = 0
    const { workspace } = setup((path, init) => {
      const read = reads(path)
      if (read) return read
      if ((init.method ?? 'GET') !== 'GET') mutations++
      return ok(saved('one'))
    })
    await workspace.loadForCourse('one')
    const group: AssignmentGroup = {
      ...emptyGroup(),
      employeeIds: ['e2e-dev'],
      departments: ['Finance'],
    }
    workspace.updateRule({
      ...workspace.getState().rule,
      includeAll: false,
      includeGroups: [group],
    })
    await workspace.save('one')
    expect(mutations).toBe(0)
    expect(workspace.getState().error).toBe(
      'Include group 1 mixes specific employees with filters. Clear one side before saving.',
    )
  })

  it('a stale preview reply is ignored after a newer edit', async () => {
    const releases: ((reply: Reply) => void)[] = []
    const { workspace } = setup((path, init) => {
      const r = route(path)
      if (r.endsWith('/employee-preview') && releases.length < 5) {
        const days = (init.json as { deadline_days: number }).deadline_days
        if (days === 20) {
          return new Promise<Reply>((resolve) => releases.push(resolve))
        }
      }
      const read = reads(path)
      if (read) return read
      return ok(saved('one'))
    })
    await workspace.loadForCourse('one')
    workspace.updateRule({ ...workspace.getState().rule, deadlineDays: 20 })
    const slow = workspace.fetchEmployeePreview()
    workspace.updateRule({ ...workspace.getState().rule, deadlineDays: 21 })
    await workspace.fetchEmployeePreview()
    expect(releases.length).toBeGreaterThan(0)
    for (const release of releases) {
      release(ok({ total: 99, total_assigned_count: 0, employees: [] }))
    }
    await slow
    expect(workspace.getState().previewTotal).toBe(0)
    expect(workspace.getState().previewStale).toBe(false)
  })
})

function emptyGroup(): AssignmentGroup {
  return {
    savedGroupId: null,
    name: 'Group 1',
    employeeIds: [],
    departments: [],
    mailingLists: [],
    jobTitles: [],
    joinedLessThanDaysAgo: null,
  }
}

describe('AssignmentWorkspace mutations', () => {
  it('Publish sends the rule and shows the assignment counters', async () => {
    const { workspace, calls, refreshCourses, refreshPerformance } = setup((path) => {
      const read = reads(path)
      if (read) return read
      if (route(path).endsWith('/publish-assignment')) {
        return ok({
          ...saved('one', 9),
          total_assigned_count: 5,
          assigned_count: 3,
          reactivated_count: 1,
          removed_count: 2,
          deadline_update_count: 4,
        })
      }
      return ok(saved('one'))
    })
    await workspace.loadForCourse('one')
    await workspace.publish('one', 3)
    const publish = calls.find((c) => route(c.path).endsWith('/publish-assignment'))
    expect(publish?.method).toBe('POST')
    expect(publish?.json).toMatchObject({
      expected_lifecycle_revision: 3,
      expected_updated_at: 'v1',
    })
    const state = workspace.getState()
    expect(state.isPublishing).toBe(false)
    expect(state.message).toBe(
      'Course published and assigned successfully. 5 employees currently assigned. ' +
        '3 new assignments created, 1 restored, 2 removed, 4 deadlines updated.',
    )
    expect(state.assignedCount).toBe(3)
    expect(state.rule.deadlineDays).toBe(9)
    expect(refreshCourses).toHaveBeenCalled()
    expect(refreshPerformance).toHaveBeenCalled()
  })

  it('a failed report refresh after Publish keeps the success message and shows an error', async () => {
    const { workspace, refreshCourses } = setup((path) => reads(path) ?? ok(saved('one')))
    await workspace.loadForCourse('one')
    refreshCourses.mockResolvedValueOnce(false)
    await workspace.publish('one')
    expect(workspace.getState().message).toContain('Course published')
    expect(workspace.getState().error).toContain('could not be refreshed')
  })

  it('preview paging and search request the chosen page', async () => {
    const { workspace, calls } = setup((path) => {
      if (route(path).endsWith('/employee-preview')) {
        return ok({ total: 60, total_assigned_count: 0, employees: [] })
      }
      return reads(path) ?? ok(saved('one'))
    })
    await workspace.loadForCourse('one')
    await workspace.fetchEmployeePreview({ page: 3 })
    await workspace.fetchEmployeePreview({ view: 'assigned', search: 'kiran', page: 1 })
    const pages = calls
      .filter((c) => route(c.path).endsWith('/employee-preview'))
      .map((c) => new URLSearchParams(c.path.split('?')[1]))
    expect(pages.at(-2)?.get('page')).toBe('3')
    expect(pages.at(-1)?.get('view')).toBe('assigned')
    expect(pages.at(-1)?.get('search')).toBe('kiran')
    expect(pages.at(-1)?.get('page')).toBe('1')
    expect(workspace.getState().previewPage).toBe(1)
  })

  it('reloading the saved rule drops a dirty draft, as after Disable', async () => {
    let active = true
    const { workspace } = setup((path) => {
      const read = reads(path)
      if (read) return read
      const data = saved('one')
      data.rule.is_active = active
      return ok(data)
    })
    await workspace.loadForCourse('one')
    workspace.updateRule({ ...workspace.getState().rule, deadlineDays: 30 })
    expect(workspace.getState().dirty).toBe(true)
    active = false
    await workspace.reloadSavedRule('one')
    expect(workspace.getState().dirty).toBe(false)
    expect(workspace.getState().rule.isActive).toBe(false)
    expect(workspace.getState().rule.deadlineDays).toBe(7)
  })
})

describe('groupValidationError', () => {
  it('accepts an empty rule', () => {
    expect(groupValidationError(defaultAssignmentRule())).toBeNull()
  })

  it('rejects a zero joined-days filter in an exclusion group', () => {
    const rule = {
      ...defaultAssignmentRule(),
      excludeGroups: [{ ...emptyGroup(), joinedLessThanDaysAgo: 0 }],
    }
    expect(groupValidationError(rule)).toBe(
      'Exclude group 1 joined-days filter must be at least 1.',
    )
  })
})
