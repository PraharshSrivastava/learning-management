// Endpoints and local parsers for the Assign tab.
// The shared models have no parsers for the observer and preview payloads, so they live here.
import { apiUrl, authHeaders, errorDetail } from '@lms/shared/api/client'
import { isRecord, parseEmployee, type Employee, type JsonRecord } from '@lms/shared/models'

export interface Reply {
  status: number
  body: unknown
}

export interface RequestInit {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  json?: unknown
}

/** Sends a request and returns the status and decoded body. It does not throw on non-2xx. */
export type Requester = (path: string, init?: RequestInit) => Promise<Reply>

export const fetchRequester: Requester = async (path, init = {}) => {
  const headers: Record<string, string> = { ...authHeaders() }
  if (init.json !== undefined) headers['Content-Type'] = 'application/json'
  let response: Response
  try {
    response = await fetch(apiUrl(path), {
      method: init.method ?? 'GET',
      headers,
      body: init.json === undefined ? undefined : JSON.stringify(init.json),
      credentials: 'same-origin',
    })
  } catch {
    throw new Error('Unable to reach the server. Check your connection and try again.')
  }
  const text = await response.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }
  return { status: response.status, body }
}

export const isOk = (reply: Reply) => reply.status >= 200 && reply.status < 300

export const detailOr = (reply: Reply, fallback: string) => errorDetail(reply.body) ?? fallback

/** Preview rows per page. The footer pager uses the same value. */
export const PREVIEW_PAGE_SIZE = 25

export const paths = {
  assignableCourses: '/api/assignment/courses',
  options: '/api/assignment/options',
  savedGroups: '/api/assignment/saved-groups',
  savedGroup: (id: string) => `/api/assignment/saved-groups/${encodeURIComponent(id)}`,
  assignment: (courseId: string) => `/api/courses/${encodeURIComponent(courseId)}/assignment`,
  publish: (courseId: string) => `/api/courses/${encodeURIComponent(courseId)}/publish-assignment`,
  preview: (courseId: string, view: string, search: string, page: number) =>
    `/api/courses/${encodeURIComponent(courseId)}/assignment/employee-preview?${new URLSearchParams(
      { view, search, page: String(page), page_size: String(PREVIEW_PAGE_SIZE) },
    ).toString()}`,
  observers: (courseId: string) => `/api/courses/${encodeURIComponent(courseId)}/observers`,
  applyObservers: (courseId: string) =>
    `/api/courses/${encodeURIComponent(courseId)}/observers/apply`,
  observerOptions: '/api/observer/options',
  lifecycle: (courseId: string) => `/api/courses/${encodeURIComponent(courseId)}/lifecycle`,
  deleteCourse: (courseId: string, revision: number) =>
    `/api/courses/${encodeURIComponent(courseId)}?expected_revision=${revision}`,
}

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.map((item) => String(item)) : []

const intOr = (value: unknown, fallback: number): number =>
  typeof value === 'number' && Number.isFinite(value) ? Math.trunc(value) : fallback

const optInt = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? Math.trunc(value) : null

export const asRecord = (value: unknown): JsonRecord => (isRecord(value) ? value : {})

/** GET /api/courses/{id}/assignment and the save/publish replies. */
export interface AssignmentReply {
  rawRule: JsonRecord
  updatedAt: string | null
  lifecycleRevision: number | null
  totalAssignedCount: number | null
  matchCount: number | null
}

export function parseAssignmentReply(body: unknown): AssignmentReply {
  const data = asRecord(body)
  const rawRule = asRecord(data.rule)
  return {
    rawRule,
    updatedAt: rawRule.updated_at == null ? null : String(rawRule.updated_at),
    lifecycleRevision: optInt(data.lifecycle_revision),
    totalAssignedCount: optInt(data.total_assigned_count),
    matchCount: optInt(data.match_count),
  }
}

/** POST .../employee-preview reply. */
export interface PreviewReply {
  employees: Employee[]
  total: number
  totalAssignedCount: number
  blockedEmployeeCount: number
  conflictingObserverIds: string[]
}

export function parsePreviewReply(body: unknown): PreviewReply {
  const data = asRecord(body)
  return {
    employees: Array.isArray(data.employees) ? data.employees.map(parseEmployee) : [],
    total: intOr(data.total, 0),
    totalAssignedCount: intOr(data.total_assigned_count, 0),
    blockedEmployeeCount: intOr(data.blocked_employee_count, 0),
    conflictingObserverIds: strings(data.conflicting_observer_ids),
  }
}

/** Publish counters for the success message. */
export function publishCounts(body: unknown) {
  const data = asRecord(body)
  return {
    total: intOr(data.total_assigned_count, 0),
    assigned: intOr(data.assigned_count, 0),
    removed: intOr(data.removed_count, 0),
    reactivated: intOr(data.reactivated_count, 0),
    deadlines: intOr(data.deadline_update_count, 0),
    assignedCount: optInt(data.assigned_count),
  }
}

export interface ObserverSelection {
  observerEmployeeId: string | null
  employeeIds: string[]
  departmentIds: string[]
}

export interface ObserverAccess {
  isActive: boolean
  activeEmployeeIds: string[]
  activeDepartmentIds: string[]
}

export interface ObserverConfig {
  revision: number
  selections: ObserverSelection[]
  effective: Record<string, ObserverAccess>
}

/** GET /api/courses/{id}/observers. The editable draft is the `pending` side. */
export function parseObserverConfig(body: unknown): ObserverConfig {
  const data = asRecord(body)
  const rows = Array.isArray(data.observers) ? data.observers.map(asRecord) : []
  const effective: Record<string, ObserverAccess> = {}
  for (const row of rows) {
    const active = asRecord(row.active)
    effective[String(row.observer_employee_id)] = {
      isActive: row.is_active === true,
      activeEmployeeIds: strings(active.employee_ids),
      activeDepartmentIds: strings(active.department_ids),
    }
  }
  return {
    revision: intOr(data.revision, 0),
    effective,
    selections: rows.map((row) => {
      const pending = asRecord(row.pending)
      return {
        observerEmployeeId:
          row.observer_employee_id == null ? null : String(row.observer_employee_id),
        employeeIds: strings(pending.employee_ids),
        departmentIds: strings(pending.department_ids),
      }
    }),
  }
}

export interface ObserverDepartment {
  id: string
  name: string
}

/** GET /api/observer/options. */
export function parseObserverDepartments(body: unknown): ObserverDepartment[] {
  const data = asRecord(body)
  return (Array.isArray(data.departments) ? data.departments.map(asRecord) : []).map((d) => ({
    id: String(d.department_id),
    name: String(d.name ?? ''),
  }))
}

export const observerSelectionToJson = (s: ObserverSelection) => ({
  observer_employee_id: s.observerEmployeeId,
  employee_ids: s.employeeIds,
  department_ids: s.departmentIds,
})
