// Learning Journeys endpoints and payload parsers for the Trainer app.
import { apiRequest } from '@lms/shared/api/client'
import {
  assignmentGroupToJson,
  isRecord,
  parseAssignmentGroup,
  parseAssignmentOptions,
  parseSavedAssignmentGroup,
  type AssignmentGroup,
  type AssignmentOptions,
  type JsonRecord,
  type SavedAssignmentGroup,
} from '@lms/shared/models'

export type JourneyStatus = 'draft' | 'published' | 'disabled'
export type UnlockRule = 'open' | 'after_previous'

export interface JourneySummary {
  journeyId: string
  title: string
  description: string
  targetAudience: string
  status: JourneyStatus
  prerequisiteJourneyId: string | null
  certificateEnabled: boolean
  publishedAt: string | null
  updatedAt: string
  stageCount: number
  courseCount: number
  assignedCount: number
  completedCount: number
  warnings: string[]
}

export interface OtherJourney {
  journeyId: string
  title: string
}

export interface JourneyStep {
  courseId: string
  courseName: string
  moduleCount: number
  thumbnailPath: string
  unlockRule: UnlockRule
  isRequired: boolean
  eligible: boolean
  reason: string | null
  /** Other journeys this course is in. */
  otherJourneys: OtherJourney[]
  /** This journey's learners who hold the course, and how many of them started or passed it. */
  learnerCount: number
  startedCount: number
}

export interface JourneyStage {
  title: string
  steps: JourneyStep[]
}

export interface JourneyRule {
  includeAll: boolean
  includeGroups: AssignmentGroup[]
  excludeGroups: AssignmentGroup[]
  deadlineMode: 'relative' | 'fixed'
  deadlineDays: number
  deadlineDate: string | null
}

export interface JourneyDetail extends JourneySummary {
  stages: JourneyStage[]
  rule: JourneyRule
}

export interface CourseOption {
  courseId: string
  courseName: string
  status: string
  moduleCount: number
  thumbnailPath: string
  eligible: boolean
  reason: string | null
  journeys: OtherJourney[]
}

export interface PreviewEmployee {
  employeeId: string
  name: string
  department: string
  jobTitle: string
}

const text = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback
const optText = (value: unknown): string | null => (typeof value === 'string' ? value : null)
const count = (value: unknown): number =>
  typeof value === 'number' && Number.isFinite(value) ? Math.trunc(value) : 0
const records = (value: unknown): JsonRecord[] =>
  Array.isArray(value) ? value.filter(isRecord) : []
const otherJourneys = (value: unknown): OtherJourney[] =>
  records(value).map((row) => ({ journeyId: text(row.journey_id), title: text(row.title) }))

export function parseSummary(json: unknown): JourneySummary {
  const j = isRecord(json) ? json : {}
  const status = text(j.status, 'draft')
  return {
    journeyId: text(j.journey_id),
    title: text(j.title),
    description: text(j.description),
    targetAudience: text(j.target_audience),
    status: status === 'published' || status === 'disabled' ? status : 'draft',
    prerequisiteJourneyId: optText(j.prerequisite_journey_id),
    certificateEnabled: j.certificate_enabled !== false,
    publishedAt: optText(j.published_at),
    updatedAt: text(j.updated_at),
    stageCount: count(j.stage_count),
    courseCount: count(j.course_count),
    assignedCount: count(j.assigned_count),
    completedCount: count(j.completed_count),
    warnings: Array.isArray(j.warnings) ? j.warnings.map(String) : [],
  }
}

export function parseRule(json: unknown): JourneyRule {
  const j = isRecord(json) ? json : {}
  return {
    includeAll: j.include_all !== false,
    includeGroups: records(j.include_groups).map(parseAssignmentGroup),
    excludeGroups: records(j.exclude_groups).map(parseAssignmentGroup),
    deadlineMode: j.deadline_mode === 'fixed' ? 'fixed' : 'relative',
    deadlineDays: count(j.deadline_days) || 30,
    deadlineDate: optText(j.deadline_date),
  }
}

export function parseDetail(json: unknown): JourneyDetail {
  const j = isRecord(json) ? json : {}
  return {
    ...parseSummary(j),
    stages: records(j.stages).map((stage) => ({
      title: text(stage.title),
      steps: records(stage.steps).map((step) => ({
        courseId: text(step.course_id),
        courseName: text(step.course_name),
        moduleCount: count(step.module_count),
        thumbnailPath: text(step.thumbnail_path),
        unlockRule: step.unlock_rule === 'open' ? 'open' : 'after_previous',
        isRequired: step.is_required !== false,
        eligible: step.eligible === true,
        reason: optText(step.reason),
        otherJourneys: otherJourneys(step.other_journeys),
        learnerCount: count(step.learner_count),
        startedCount: count(step.started_count),
      })),
    })),
    rule: parseRule(j.rule),
  }
}

export function parseCourseOption(json: unknown): CourseOption {
  const j = isRecord(json) ? json : {}
  return {
    courseId: text(j.course_id),
    courseName: text(j.course_name),
    status: text(j.status),
    moduleCount: count(j.module_count),
    thumbnailPath: text(j.thumbnail_path),
    eligible: j.eligible === true,
    reason: optText(j.reason),
    journeys: otherJourneys(j.journeys),
  }
}

export function rulePayload(rule: JourneyRule): JsonRecord {
  return {
    include_all: rule.includeAll,
    include_groups: rule.includeGroups.map(assignmentGroupToJson),
    exclude_groups: rule.excludeGroups.map(assignmentGroupToJson),
    deadline_mode: rule.deadlineMode,
    deadline_days: rule.deadlineDays,
    deadline_date: rule.deadlineMode === 'fixed' ? rule.deadlineDate : null,
  }
}

/** PUT body for a journey save. */
export function savePayload(journey: JourneyDetail): JsonRecord {
  return {
    expected_updated_at: journey.updatedAt || null,
    title: journey.title.trim() || 'Untitled journey',
    description: journey.description,
    target_audience: journey.targetAudience,
    prerequisite_journey_id: journey.prerequisiteJourneyId,
    certificate_enabled: journey.certificateEnabled,
    stages: journey.stages.map((stage, index) => ({
      title: stage.title.trim() || `Section ${index + 1}`,
      steps: stage.steps.map((step) => ({
        course_id: step.courseId,
        unlock_rule: step.unlockRule,
        is_required: step.isRequired,
      })),
    })),
    rule: rulePayload(journey.rule),
  }
}

const base = '/api/learning-journeys'
const one = (id: string) => `${base}/${encodeURIComponent(id)}`

export async function fetchJourneys(): Promise<{ enabled: boolean; journeys: JourneySummary[] }> {
  const body = await apiRequest(base)
  const data = isRecord(body) ? body : {}
  return {
    enabled: data.enabled === true,
    journeys: records(data.journeys).map(parseSummary),
  }
}

export const fetchJourney = async (id: string) => parseDetail(await apiRequest(one(id)))

export const createJourney = async (title: string) =>
  parseDetail(await apiRequest(base, { method: 'POST', json: { title } }))

export async function saveJourney(
  journey: JourneyDetail,
): Promise<{ detail: JourneyDetail; learnersRechecked: boolean }> {
  const body = await apiRequest(one(journey.journeyId), {
    method: 'PUT',
    json: savePayload(journey),
  })
  return {
    detail: parseDetail(body),
    learnersRechecked: isRecord(body) && body.learners_rechecked === true,
  }
}

export const duplicateJourney = async (id: string) =>
  parseDetail(await apiRequest(`${one(id)}/duplicate`, { method: 'POST' }))

export const publishJourney = async (id: string) => {
  const body = await apiRequest(`${one(id)}/publish`, { method: 'POST' })
  const data = isRecord(body) ? body : {}
  return { detail: parseDetail(body), newlyAssigned: count(data.newly_assigned_count) }
}

export const disableJourney = async (id: string) =>
  parseDetail(await apiRequest(`${one(id)}/disable`, { method: 'POST' }))

export const deleteJourney = async (id: string) => {
  await apiRequest(one(id), { method: 'DELETE' })
}

export async function fetchCourseOptions(): Promise<CourseOption[]> {
  const body = await apiRequest(`${base}/course-options`)
  return Array.isArray(body) ? body.map(parseCourseOption) : []
}

/** Who would get the journey with the unsaved rule and Observers (the first 50 are listed). */
export async function fetchPreview(
  id: string,
  rule: JourneyRule,
  observerEmployeeIds: string[],
): Promise<{ matchCount: number; employees: PreviewEmployee[] }> {
  const body = await apiRequest(`${one(id)}/preview`, {
    method: 'POST',
    json: { rule: rulePayload(rule), observer_employee_ids: observerEmployeeIds },
  })
  const data = isRecord(body) ? body : {}
  return {
    matchCount: count(data.match_count),
    employees: records(data.preview_employees).map((row) => ({
      employeeId: text(row.employee_id),
      name: text(row.name),
      department: text(row.department),
      jobTitle: text(row.job_title),
    })),
  }
}

export interface JourneyObserver {
  observerEmployeeId: string
  employeeIds: string[]
  departmentIds: string[]
}

export interface ObserverDepartment {
  id: string
  name: string
}

const ids = (value: unknown): string[] => (Array.isArray(value) ? value.map(String) : [])

export async function fetchJourneyObservers(id: string): Promise<JourneyObserver[]> {
  const body = await apiRequest(`${one(id)}/observers`)
  const data = isRecord(body) ? body : {}
  return records(data.observers).map((row) => ({
    observerEmployeeId: text(row.observer_employee_id),
    employeeIds: ids(row.employee_ids),
    departmentIds: ids(row.department_ids),
  }))
}

export async function saveJourneyObservers(id: string, observers: JourneyObserver[]) {
  await apiRequest(`${one(id)}/observers`, {
    method: 'PUT',
    json: {
      observers: observers.map((o) => ({
        observer_employee_id: o.observerEmployeeId,
        employee_ids: o.employeeIds,
        department_ids: o.departmentIds,
      })),
    },
  })
}

export async function fetchObserverDepartments(): Promise<ObserverDepartment[]> {
  const body = await apiRequest('/api/observer/options')
  const data = isRecord(body) ? body : {}
  return records(data.departments).map((row) => ({
    id: text(row.department_id),
    name: text(row.name),
  }))
}

export const fetchAssignmentOptions = async (): Promise<AssignmentOptions> =>
  parseAssignmentOptions(await apiRequest('/api/assignment/options'))

export async function fetchSavedGroups(): Promise<SavedAssignmentGroup[]> {
  const body = await apiRequest('/api/assignment/saved-groups')
  return Array.isArray(body) ? body.map(parseSavedAssignmentGroup) : []
}
