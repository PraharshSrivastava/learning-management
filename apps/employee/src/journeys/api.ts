// GET /api/me/learning-journeys and its parser.
import { apiRequest } from '@lms/shared/api/client'
import { isRecord, type JsonRecord } from '@lms/shared/models'

export type StepState = 'passed' | 'in_progress' | 'available' | 'locked' | 'unavailable'
export type LearnerJourneyStatus = 'waiting' | 'pending' | 'started' | 'overdue' | 'completed'

export interface LearnerStep {
  courseId: string
  courseName: string
  moduleCount: number
  stepNumber: number
  isRequired: boolean
  unlockRule: 'open' | 'after_previous'
  state: StepState
  lockedByCourseName: string | null
}

export interface LearnerJourney {
  journeyId: string
  title: string
  description: string
  certificateEnabled: boolean
  status: LearnerJourneyStatus
  deadline: string | null
  completedAt: string | null
  stepCount: number
  passedCount: number
  requiredCount: number
  nextCourseId: string | null
  prerequisite: { journeyId: string; title: string; met: boolean } | null
  stages: { title: string; steps: LearnerStep[] }[]
}

const STEP_STATES: readonly StepState[] = [
  'passed',
  'in_progress',
  'available',
  'locked',
  'unavailable',
]
const STATUSES: readonly LearnerJourneyStatus[] = [
  'waiting',
  'pending',
  'started',
  'overdue',
  'completed',
]

const text = (value: unknown): string => (typeof value === 'string' ? value : '')
const optText = (value: unknown): string | null => (typeof value === 'string' ? value : null)
const num = (value: unknown): number =>
  typeof value === 'number' && Number.isFinite(value) ? Math.trunc(value) : 0
const records = (value: unknown): JsonRecord[] =>
  Array.isArray(value) ? value.filter(isRecord) : []

function parseStep(j: JsonRecord): LearnerStep {
  const state = STEP_STATES.find((item) => item === j.state) ?? 'locked'
  return {
    courseId: text(j.course_id),
    courseName: text(j.course_name),
    moduleCount: num(j.module_count),
    stepNumber: num(j.step_number),
    isRequired: j.is_required !== false,
    unlockRule: j.unlock_rule === 'open' ? 'open' : 'after_previous',
    state,
    lockedByCourseName: optText(j.locked_by_course_name),
  }
}

export function parseLearnerJourney(json: unknown): LearnerJourney {
  const j = isRecord(json) ? json : {}
  const prerequisite = isRecord(j.prerequisite) ? j.prerequisite : null
  return {
    journeyId: text(j.journey_id),
    title: text(j.title),
    description: text(j.description),
    certificateEnabled: j.certificate_enabled !== false,
    status: STATUSES.find((item) => item === j.status) ?? 'pending',
    deadline: optText(j.deadline),
    completedAt: optText(j.completed_at),
    stepCount: num(j.step_count),
    passedCount: num(j.passed_count),
    requiredCount: num(j.required_count),
    nextCourseId: optText(j.next_course_id),
    prerequisite: prerequisite
      ? {
          journeyId: text(prerequisite.journey_id),
          title: text(prerequisite.title),
          met: prerequisite.met === true,
        }
      : null,
    stages: records(j.stages).map((stage) => ({
      title: text(stage.title),
      steps: records(stage.steps).map(parseStep),
    })),
  }
}

export function parseLearnerJourneys(json: unknown): {
  enabled: boolean
  journeys: LearnerJourney[]
} {
  const data = isRecord(json) ? json : {}
  return {
    enabled: data.enabled === true,
    journeys: records(data.journeys).map(parseLearnerJourney),
  }
}

export const fetchMyJourneys = async () =>
  parseLearnerJourneys(await apiRequest('/api/me/learning-journeys'))

/** Share of required, available steps already passed, from 0 to 1. */
export const journeyProgress = (journey: LearnerJourney): number =>
  journey.requiredCount > 0 ? journey.passedCount / journey.requiredCount : 0
