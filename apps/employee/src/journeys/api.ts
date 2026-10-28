// GET /api/me/learning-journeys and its parser.
import { apiRequest, apiUrl, authHeaders } from '@lms/shared/api/client'
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
  /** The next course's state, so its button says Start or Continue. */
  nextCourseState: StepState | null
  /** Set once the journey is completed with a certificate. */
  certificateNumber: string | null
  prerequisite: { journeyId: string; title: string; met: boolean } | null
  /** A finished journey that was disabled, or the learner was removed from: its courses are closed. */
  closed: boolean
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
    nextCourseState: STEP_STATES.find((item) => item === j.next_course_state) ?? null,
    certificateNumber: optText(j.certificate_number),
    prerequisite: prerequisite
      ? {
          journeyId: text(prerequisite.journey_id),
          title: text(prerequisite.title),
          met: prerequisite.met === true,
        }
      : null,
    closed: j.closed === true,
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

/** Saves the learner's completion certificate as a PDF file. */
export async function downloadMyCertificate(journey: LearnerJourney): Promise<void> {
  const response = await fetch(
    apiUrl(`/api/me/learning-journeys/${encodeURIComponent(journey.journeyId)}/certificate`),
    { headers: authHeaders(), credentials: 'same-origin' },
  )
  if (!response.ok) throw new Error('Your certificate could not be downloaded. Try again.')
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${journey.certificateNumber ?? 'certificate'}.pdf`
  anchor.style.display = 'none'
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  // Revoke later: some browsers start the download after the click handler returns.
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
