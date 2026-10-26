// Assignment editor state for one trainer session (Flutter AssignmentNotifier).
// It is a small external store so request ordering and debounce stay outside React renders.
import {
  assignmentRuleToJson,
  defaultAssignmentRule,
  hasMixedSelection,
  parseAssignmentOptions,
  parseSavedAssignmentGroup,
  ruleForEditor,
  savedGroupPayload,
  type AssignmentGroup,
  type AssignmentOptions,
  type AssignmentRule,
  type Employee,
  type SavedAssignmentGroup,
  type SavedGroupType,
} from '@lms/shared/models'
import {
  detailOr,
  isOk,
  paths,
  parseAssignmentReply,
  parsePreviewReply,
  publishCounts,
  type AssignmentReply,
  type Requester,
} from './api'
import { directGroupIndex } from './directEmployees'

export type PreviewView = 'matching' | 'assigned'

export interface AssignmentState {
  options: AssignmentOptions
  savedGroups: SavedAssignmentGroup[]
  rule: AssignmentRule
  previewEmployees: Employee[]
  matchCount: number
  totalAssignedCount: number
  previewTotal: number
  previewPage: number
  previewView: PreviewView
  previewSearch: string
  isPreviewLoading: boolean
  previewStale: boolean
  dirty: boolean
  refreshGeneration: number
  blockedEmployeeCount: number
  draftObserverIds: string[]
  conflictingObserverIds: string[]
  isLoading: boolean
  isSaving: boolean
  isPublishing: boolean
  assignedCount: number | null
  error: string | null
  message: string | null
  loadedCourseId: string | null
}

export const SESSION_ERROR =
  'Your session or course access changed. Sign in again to reload assignment data.'

export function initialAssignmentState(patch: Partial<AssignmentState> = {}): AssignmentState {
  return {
    options: { employees: [], departments: [], mailingLists: [], jobTitles: [] },
    savedGroups: [],
    rule: defaultAssignmentRule(),
    previewEmployees: [],
    matchCount: 0,
    totalAssignedCount: 0,
    previewTotal: 0,
    previewPage: 1,
    previewView: 'matching',
    previewSearch: '',
    isPreviewLoading: false,
    previewStale: false,
    dirty: false,
    refreshGeneration: 0,
    blockedEmployeeCount: 0,
    draftObserverIds: [],
    conflictingObserverIds: [],
    isLoading: false,
    isSaving: false,
    isPublishing: false,
    assignedCount: null,
    error: null,
    message: null,
    loadedCourseId: null,
    ...patch,
  }
}

class SessionExpired extends Error {
  constructor() {
    super(SESSION_ERROR)
  }
}

const errorText = (error: unknown) => (error instanceof Error ? error.message : String(error))

/** Rule validation run before save and publish. */
export function groupValidationError(rule: AssignmentRule): string | null {
  const validate = (groups: AssignmentGroup[], label: string) => {
    for (const [index, group] of groups.entries()) {
      if (hasMixedSelection(group)) {
        return `${label} group ${index + 1} mixes specific employees with filters. Clear one side before saving.`
      }
      if (group.joinedLessThanDaysAgo === 0) {
        return `${label} group ${index + 1} joined-days filter must be at least 1.`
      }
    }
    return null
  }
  return validate(rule.includeGroups, 'Include') ?? validate(rule.excludeGroups, 'Exclude')
}

export interface WorkspaceDeps {
  request: Requester
  /** Reloads the course lists. Returns false when the assignable list failed. */
  refreshCourses: () => Promise<boolean>
  /** Reloads performance report data. */
  refreshPerformance: () => Promise<void>
  /** Preview debounce in ms. */
  debounceMs?: number
}

export class AssignmentWorkspace {
  private state = initialAssignmentState()
  private listeners = new Set<() => void>()
  private request = 0
  private previewRequest = 0
  private timer: ReturnType<typeof setTimeout> | null = null
  private baseline: string | null = null
  private expectedUpdatedAt: string | null = null
  private expectedLifecycleRevision: number | null = null

  constructor(private readonly deps: WorkspaceDeps) {}

  subscribe = (listener: () => void) => {
    this.listeners.add(listener)
    return () => void this.listeners.delete(listener)
  }

  getState = () => this.state

  private replace(next: AssignmentState) {
    this.state = next
    for (const listener of this.listeners) listener()
  }

  /** Flutter copyWith: error and message clear unless they are passed. */
  private set(patch: Partial<AssignmentState>) {
    this.replace({ ...this.state, error: null, message: null, ...patch })
  }

  /** Same as set, but keeps the current error and message. */
  private patch(patch: Partial<AssignmentState>) {
    this.set({ error: this.state.error, message: this.state.message, ...patch })
  }

  private cancelTimer() {
    if (this.timer != null) clearTimeout(this.timer)
    this.timer = null
  }

  dismissMessage() {
    this.set({ error: this.state.error })
  }

  clearForAuthChange() {
    ++this.request
    ++this.previewRequest
    this.cancelTimer()
    this.baseline = null
    this.expectedUpdatedAt = null
    this.expectedLifecycleRevision = null
    this.replace(initialAssignmentState())
  }

  /** Stops a pending preview. Safe to call twice (StrictMode remounts reuse the store). */
  dispose() {
    this.cancelTimer()
  }

  private async read(path: string): Promise<unknown> {
    const reply = await this.deps.request(path)
    if (reply.status === 401 || reply.status === 403) throw new SessionExpired()
    if (reply.status !== 200) {
      throw new Error(`Refresh failed (${reply.status}). Sign in again if your session expired.`)
    }
    return reply.body
  }

  async refreshOptionsAndGroups() {
    const courseId = this.state.loadedCourseId
    if (courseId != null) await this.refreshAssignmentWorkspace(courseId)
  }

  async refreshAssignmentWorkspace(courseId: string, initial = false) {
    const serial = ++this.request
    ++this.previewRequest
    this.cancelTimer()
    if (initial) {
      this.baseline = null
      this.expectedUpdatedAt = null
      this.expectedLifecycleRevision = null
      this.replace(initialAssignmentState({ loadedCourseId: courseId, isLoading: true }))
    } else {
      this.set({ isLoading: true })
    }
    const errors: string[] = []
    let sessionExpired = false
    let saved: AssignmentReply | null = null
    let options: AssignmentOptions | undefined
    let groups: SavedAssignmentGroup[] | undefined
    await Promise.all([
      (async () => {
        try {
          options = parseAssignmentOptions(await this.read(paths.options))
        } catch (error) {
          sessionExpired ||= error instanceof SessionExpired
          errors.push('Employee options could not be refreshed.')
        }
      })(),
      (async () => {
        try {
          saved = parseAssignmentReply(await this.read(paths.assignment(courseId)))
        } catch (error) {
          sessionExpired ||= error instanceof SessionExpired
          errors.push('Saved rule and assignment totals could not be refreshed.')
        }
      })(),
      (async () => {
        try {
          const reply = await this.deps.request(paths.savedGroups)
          if (reply.status === 401 || reply.status === 403) sessionExpired = true
          if (reply.status !== 200 || !Array.isArray(reply.body)) throw new Error()
          groups = reply.body.map(parseSavedAssignmentGroup)
        } catch {
          errors.push('Saved groups could not be refreshed.')
        }
      })(),
      (async () => {
        try {
          if (!(await this.deps.refreshCourses())) {
            errors.push('Course status could not be refreshed.')
          }
        } catch {
          errors.push('Course status could not be refreshed.')
        }
      })(),
    ])
    if (serial !== this.request || this.state.loadedCourseId !== courseId) return
    if (sessionExpired) {
      this.replace(initialAssignmentState({ error: SESSION_ERROR }))
      return
    }
    let warning: string | null = null
    let freshRule: AssignmentRule | undefined
    const reply = saved as AssignmentReply | null
    if (reply) {
      const baseline = JSON.stringify(reply.rawRule)
      if (this.state.dirty && this.baseline != null && baseline !== this.baseline) {
        warning =
          'The saved rule changed in another session. Your edits are preserved; review the saved version before saving.'
      }
      if (!this.state.dirty) {
        freshRule = ruleForEditor(reply.rawRule)
        this.baseline = baseline
        this.expectedUpdatedAt = reply.updatedAt
        this.expectedLifecycleRevision = reply.lifecycleRevision
      }
    }
    const all = warning ? [...errors, warning] : errors
    const s = this.state
    this.set({
      options: options ?? s.options,
      savedGroups: groups ?? s.savedGroups,
      rule: freshRule ?? s.rule,
      totalAssignedCount: reply?.totalAssignedCount ?? s.totalAssignedCount,
      matchCount: s.dirty ? s.matchCount : (reply?.matchCount ?? s.matchCount),
      refreshGeneration: s.refreshGeneration + 1,
      isLoading: false,
      error: all.length > 0 ? all.join(' ') : null,
    })
    await this.fetchEmployeePreview()
  }

  async fetchSavedGroups() {
    const serial = this.request
    try {
      const reply = await this.deps.request(paths.savedGroups)
      if (serial !== this.request) return
      if (reply.status === 200) {
        const list = Array.isArray(reply.body) ? reply.body : []
        this.patch({ savedGroups: list.map(parseSavedAssignmentGroup) })
      } else {
        this.set({ error: 'Saved groups could not be refreshed.', message: this.state.message })
      }
    } catch {
      if (serial !== this.request) return
      this.set({ error: 'Saved groups could not be refreshed.', message: this.state.message })
    }
  }

  async reloadSavedRule(courseId: string) {
    const serial = this.request
    this.set({ isLoading: true, error: this.state.error })
    try {
      const body = await this.read(paths.assignment(courseId))
      if (serial !== this.request || this.state.loadedCourseId !== courseId) return
      this.applyAssignmentResponse(body, { isLoading: false })
      await this.fetchEmployeePreview()
    } catch (error) {
      if (serial === this.request && this.state.loadedCourseId === courseId) {
        this.set({ isLoading: false, error: errorText(error) })
      }
    }
  }

  async loadForCourse(courseId: string) {
    if (this.state.loadedCourseId === courseId) return
    await this.refreshAssignmentWorkspace(courseId, true)
  }

  private schedulePreview(page?: number) {
    this.cancelTimer()
    this.timer = setTimeout(() => {
      this.timer = null
      void this.fetchEmployeePreview(page == null ? {} : { page })
    }, this.deps.debounceMs ?? 350)
  }

  updateDraftObservers(ids: string[]) {
    if (JSON.stringify(ids) === JSON.stringify(this.state.draftObserverIds)) return
    this.patch({ draftObserverIds: ids, previewStale: true })
    ++this.previewRequest
    this.schedulePreview()
  }

  updateRule(rule: AssignmentRule) {
    this.set({ rule, dirty: true, previewStale: true, assignedCount: null })
    ++this.previewRequest
    this.schedulePreview(1)
  }

  async fetchEmployeePreview(args: { view?: PreviewView; search?: string; page?: number } = {}) {
    const courseId = this.state.loadedCourseId
    if (courseId == null) return
    const serial = ++this.previewRequest
    const draft = JSON.stringify(assignmentRuleToJson(this.state.rule))
    const observers = JSON.stringify(this.state.draftObserverIds)
    this.patch({
      previewView: args.view ?? this.state.previewView,
      previewSearch: args.search ?? this.state.previewSearch,
      previewPage: args.page ?? this.state.previewPage,
      isPreviewLoading: true,
    })
    const { previewView, previewSearch, previewPage } = this.state
    try {
      const reply = await this.deps.request(
        paths.preview(courseId, previewView, previewSearch, previewPage),
        {
          method: 'POST',
          json: {
            ...(JSON.parse(draft) as object),
            observer_employee_ids: this.state.draftObserverIds,
          },
        },
      )
      if (reply.status === 401 || reply.status === 403) throw new SessionExpired()
      if (reply.status !== 200) {
        throw new Error(`Employee preview could not be refreshed (${reply.status}).`)
      }
      const data = parsePreviewReply(reply.body)
      // Apply only when nothing changed while the request ran.
      if (
        serial !== this.previewRequest ||
        this.state.loadedCourseId !== courseId ||
        draft !== JSON.stringify(assignmentRuleToJson(this.state.rule)) ||
        observers !== JSON.stringify(this.state.draftObserverIds)
      ) {
        return
      }
      const s = this.state
      this.patch({
        previewEmployees: data.employees,
        previewTotal: data.total,
        blockedEmployeeCount: data.blockedEmployeeCount,
        conflictingObserverIds: data.conflictingObserverIds,
        totalAssignedCount: data.totalAssignedCount,
        matchCount:
          s.previewView === 'matching' && s.previewSearch === '' ? data.total : s.matchCount,
        previewStale: false,
        isPreviewLoading: false,
      })
    } catch (error) {
      if (serial !== this.previewRequest || this.state.loadedCourseId !== courseId) return
      if (error instanceof SessionExpired) {
        this.clearForAuthChange()
        this.set({ error: SESSION_ERROR })
      } else {
        this.set({
          isPreviewLoading: false,
          previewStale: true,
          error: errorText(error),
          message: this.state.message,
        })
      }
    }
  }

  /** Shared checks before save and publish. Returns false when the operation must stop. */
  private async preflight(courseId: string, operationRequest: number): Promise<boolean> {
    const s = this.state
    if (s.loadedCourseId !== courseId || s.isSaving || s.isPublishing || s.isLoading) return false
    await this.fetchEmployeePreview()
    if (this.state.loadedCourseId !== courseId || operationRequest !== this.request) return false
    if (this.state.previewStale) {
      this.set({ error: 'Refresh the employee preview before saving or publishing.' })
      return false
    }
    const conflicts = this.state.conflictingObserverIds
    if (conflicts.length > 0) {
      const names = this.state.options.employees
        .filter((e) => conflicts.includes(e.employeeId))
        .map((e) => e.name)
        .join(', ')
      this.set({
        error: `${names || 'Selected employees'} are selected as both employees and Observers for this course. Remove the conflicting selection before continuing.`,
      })
      return false
    }
    const validation = groupValidationError(this.state.rule)
    if (validation) {
      this.set({ error: validation })
      return false
    }
    const now = this.state
    return !(now.isSaving || now.isPublishing || now.isLoading || now.loadedCourseId !== courseId)
  }

  private current(courseId: string, operationRequest: number) {
    return this.state.loadedCourseId === courseId && operationRequest === this.request
  }

  private expectedFields(expectedRevision?: number | null) {
    const revision = expectedRevision ?? this.expectedLifecycleRevision
    return {
      ...(revision != null ? { expected_lifecycle_revision: revision } : {}),
      ...(this.expectedUpdatedAt != null ? { expected_updated_at: this.expectedUpdatedAt } : {}),
    }
  }

  async save(courseId: string) {
    const operationRequest = this.request
    if (!(await this.preflight(courseId, operationRequest))) return
    this.set({ isSaving: true })
    try {
      const rule = await this.persistReusableGroups(this.state.rule)
      if (!this.current(courseId, operationRequest)) return
      const reply = await this.deps.request(paths.assignment(courseId), {
        method: 'PUT',
        json: { ...assignmentRuleToJson(rule), ...this.expectedFields() },
      })
      if (!this.current(courseId, operationRequest)) return
      if (reply.status === 200) {
        this.applyAssignmentResponse(reply.body, {
          isSaving: false,
          message: 'Assignment rule saved.',
        })
        await this.fetchSavedGroups()
        await this.fetchEmployeePreview()
      } else {
        this.set({ isSaving: false, error: detailOr(reply, 'Failed to save assignment rule') })
      }
    } catch (error) {
      if (this.current(courseId, operationRequest)) {
        this.set({ isSaving: false, error: errorText(error), message: this.state.message })
      }
    }
  }

  async publish(courseId: string, expectedRevision?: number | null) {
    const operationRequest = this.request
    if (!(await this.preflight(courseId, operationRequest))) return
    this.set({ isPublishing: true })
    try {
      const rule = await this.persistReusableGroups(this.state.rule)
      if (!this.current(courseId, operationRequest)) return
      const reply = await this.deps.request(paths.publish(courseId), {
        method: 'POST',
        json: { ...assignmentRuleToJson(rule), ...this.expectedFields(expectedRevision) },
      })
      if (!this.current(courseId, operationRequest)) return
      if (reply.status === 200) {
        const c = publishCounts(reply.body)
        this.applyAssignmentResponse(reply.body, {
          isPublishing: false,
          message:
            `Course published and assigned successfully. ${c.total} employees currently assigned. ` +
            `${c.assigned} new assignments created, ${c.reactivated} restored, ${c.removed} removed, ` +
            `${c.deadlines} deadlines updated.`,
          assignedCount: c.assignedCount,
        })
        try {
          if (!(await this.deps.refreshCourses())) throw new Error()
          await this.deps.refreshPerformance()
        } catch {
          this.set({
            error:
              'The operation succeeded, but course/report data could not be refreshed. Click Refresh.',
            message: this.state.message,
          })
        }
        await this.fetchSavedGroups()
        await this.fetchEmployeePreview()
      } else {
        this.set({ isPublishing: false, error: detailOr(reply, 'Failed to publish assignment') })
      }
    } catch (error) {
      if (this.current(courseId, operationRequest)) {
        this.set({ isPublishing: false, error: errorText(error), message: this.state.message })
      }
    }
  }

  /**
   * Saves each non-empty group as a reusable saved group, in order. Individually picked employees
   * (Add employees) stay in the course rule only: saved groups are keyed by name, so one shared
   * "Selected employees" group would be overwritten by every course.
   */
  private async persistReusableGroups(rule: AssignmentRule): Promise<AssignmentRule> {
    const courseId = this.state.loadedCourseId
    const operationRequest = this.request
    const directInclude = directGroupIndex(rule.includeGroups)
    const directExclude = directGroupIndex(rule.excludeGroups)
    const persist = async (group: AssignmentGroup, type: SavedGroupType, index: number) => {
      if (index === (type === 'include' ? directInclude : directExclude)) {
        return { ...group, savedGroupId: null }
      }
      if (
        group.employeeIds.length === 0 &&
        group.departments.length === 0 &&
        group.mailingLists.length === 0 &&
        group.jobTitles.length === 0 &&
        group.joinedLessThanDaysAgo == null
      ) {
        return group
      }
      const json = savedGroupPayload(group, type, index)
      const reply =
        group.savedGroupId == null
          ? await this.deps.request(paths.savedGroups, { method: 'POST', json })
          : await this.deps.request(paths.savedGroup(group.savedGroupId), { method: 'PUT', json })
      if (!isOk(reply)) throw new Error(detailOr(reply, 'Failed to save reusable group'))
      return parseSavedAssignmentGroup(reply.body).group
    }
    const includeGroups: AssignmentGroup[] = []
    for (const [index, group] of rule.includeGroups.entries()) {
      includeGroups.push(await persist(group, 'include', index))
    }
    const excludeGroups: AssignmentGroup[] = []
    for (const [index, group] of rule.excludeGroups.entries()) {
      excludeGroups.push(await persist(group, 'exclude', index))
    }
    const updated = { ...rule, includeGroups, excludeGroups }
    if (this.state.loadedCourseId === courseId && operationRequest === this.request) {
      this.set({ rule: updated })
    }
    return updated
  }

  private applyAssignmentResponse(
    body: unknown,
    flags: Partial<Pick<AssignmentState, 'isLoading' | 'isSaving' | 'isPublishing'>> & {
      message?: string
      assignedCount?: number | null
    },
  ) {
    const reply = parseAssignmentReply(body)
    this.baseline = JSON.stringify(reply.rawRule)
    this.expectedUpdatedAt = reply.updatedAt
    this.expectedLifecycleRevision = reply.lifecycleRevision
    const s = this.state
    this.set({
      rule: ruleForEditor(reply.rawRule),
      dirty: false,
      totalAssignedCount: reply.totalAssignedCount ?? s.totalAssignedCount,
      refreshGeneration: s.refreshGeneration + 1,
      matchCount: reply.matchCount ?? 0,
      assignedCount: flags.assignedCount ?? s.assignedCount,
      previewStale: true,
      isLoading: flags.isLoading ?? s.isLoading,
      isSaving: flags.isSaving ?? s.isSaving,
      isPublishing: flags.isPublishing ?? s.isPublishing,
      message: flags.message ?? null,
    })
  }
}
