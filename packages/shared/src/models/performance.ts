// Performance report models. Source: backend/app/schemas/performance_reporting.py.
// The live Flutter report screens read raw maps with lenient helpers, so these schemas follow
// the backend contract with the same fallbacks (_int, _number, num? checks).
// The unused Dart Performance* classes in frontend models.dart are not ported.
import { z } from 'zod'
import {
  bool,
  int,
  isRecord,
  lenient,
  list,
  looseInt,
  optBool,
  optNum,
  optStr,
  str,
  strList,
} from './parse'

export const reportCourseOptionSchema = z
  .object({ course_id: str(), course_name: str() })
  .transform((j) => ({ courseId: j.course_id, courseName: j.course_name }))
export type ReportCourseOption = z.output<typeof reportCourseOptionSchema>

export const performanceReportOptionsSchema = z
  .object({
    courses: list(reportCourseOptionSchema),
    departments: strList(),
    mailing_lists: strList(),
    journeys_enabled: bool(),
  })
  .transform((j) => ({
    courses: j.courses,
    departments: j.departments,
    mailingLists: j.mailing_lists,
    journeysEnabled: j.journeys_enabled,
  }))
export type PerformanceReportOptions = z.output<typeof performanceReportOptionsSchema>
export const parsePerformanceReportOptions = (json: unknown) =>
  performanceReportOptionsSchema.parse(json)

export const assignmentReportRowSchema = z
  .object({
    assignment_id: str(),
    employee_id: str(),
    employee_name: str(),
    employee_status: str(),
    department: optStr(),
    mailing_lists: strList(),
    course_id: str(),
    course_name: str(),
    status: str(),
    due_soon: bool(),
    inactive: bool(),
    repeated_failures: bool(),
    failed_attempts: looseInt(),
    assigned_at: optStr(),
    started_at: optStr(),
    completed_at: optStr(),
    deadline: optStr(),
    last_learner_activity_at: optStr(),
    total_modules: looseInt(),
    completed_modules: looseInt(),
    completion_percent: looseInt(),
    total_attempts: looseInt(),
    average_score: optNum(),
    scored_modules: looseInt(),
    course_status: str('active'),
    // Dart: row['access_available'] == false hides access, so only an explicit false counts.
    access_available: lenient((v) => v !== false),
    access_reason: optStr(),
    on_time: bool(),
  })
  .transform((j) => ({
    assignmentId: j.assignment_id,
    employeeId: j.employee_id,
    employeeName: j.employee_name,
    employeeStatus: j.employee_status,
    department: j.department,
    mailingLists: j.mailing_lists,
    courseId: j.course_id,
    courseName: j.course_name,
    status: j.status,
    dueSoon: j.due_soon,
    inactive: j.inactive,
    repeatedFailures: j.repeated_failures,
    failedAttempts: j.failed_attempts,
    assignedAt: j.assigned_at,
    startedAt: j.started_at,
    completedAt: j.completed_at,
    deadline: j.deadline,
    lastLearnerActivityAt: j.last_learner_activity_at,
    totalModules: j.total_modules,
    completedModules: j.completed_modules,
    completionPercent: j.completion_percent,
    totalAttempts: j.total_attempts,
    averageScore: j.average_score,
    scoredModules: j.scored_modules,
    courseStatus: j.course_status,
    accessAvailable: j.access_available,
    accessReason: j.access_reason,
    onTime: j.on_time,
  }))
export type AssignmentReportRow = z.output<typeof assignmentReportRowSchema>
export const parseAssignmentReportRow = (json: unknown) => assignmentReportRowSchema.parse(json)

const summaryShape = {
  current_assignments: looseInt(),
  historical_assignments: looseInt(),
  assigned: looseInt(),
  unique_learners: looseInt(),
  pending: looseInt(),
  started: looseInt(),
  completed: looseInt(),
  overdue: looseInt(),
  due_soon: looseInt(),
  inactive: looseInt(),
  repeated_failures: looseInt(),
  completion_rate: looseInt(),
  on_time_compliance: optNum(),
  on_time_denominator: looseInt(),
  average_score: optNum(),
  scored_modules: looseInt(),
}
type SummaryRaw = z.output<z.ZodObject<typeof summaryShape>>
const mapSummary = (j: SummaryRaw) => ({
  currentAssignments: j.current_assignments,
  historicalAssignments: j.historical_assignments,
  assigned: j.assigned,
  uniqueLearners: j.unique_learners,
  pending: j.pending,
  started: j.started,
  completed: j.completed,
  overdue: j.overdue,
  dueSoon: j.due_soon,
  inactive: j.inactive,
  repeatedFailures: j.repeated_failures,
  completionRate: j.completion_rate,
  onTimeCompliance: j.on_time_compliance,
  onTimeDenominator: j.on_time_denominator,
  averageScore: j.average_score,
  scoredModules: j.scored_modules,
})

export const reportSummarySchema = z.object(summaryShape).transform(mapSummary)
export type ReportSummary = z.output<typeof reportSummarySchema>

export const courseReportSchema = z
  .object({ ...summaryShape, course_id: str(), course_name: str() })
  .transform((j) => ({ ...mapSummary(j), courseId: j.course_id, courseName: j.course_name }))
export type CourseReport = z.output<typeof courseReportSchema>

export const reportBreakdownSchema = z
  .object({
    label: str(),
    course_id: optStr(),
    assigned: looseInt(),
    completed: looseInt(),
    overdue: looseInt(),
    completion_rate: looseInt(),
  })
  .transform((j) => ({
    label: j.label,
    courseId: j.course_id,
    assigned: j.assigned,
    completed: j.completed,
    overdue: j.overdue,
    completionRate: j.completion_rate,
  }))
export type ReportBreakdown = z.output<typeof reportBreakdownSchema>

const nestedRecord = <T extends z.ZodType>(schema: T) =>
  z.preprocess((v) => (isRecord(v) ? v : {}), schema)

export const performanceOverviewSchema = z
  .object({
    summary: nestedRecord(reportSummarySchema),
    breakdowns: nestedRecord(
      z
        .object({
          courses: list(reportBreakdownSchema),
          departments: list(reportBreakdownSchema),
          mailing_lists: list(reportBreakdownSchema),
        })
        .transform((b) => ({
          courses: b.courses,
          departments: b.departments,
          mailingLists: b.mailing_lists,
        })),
    ),
    completion_trend: list(
      z
        .object({ date: str(), completed: looseInt() })
        .transform((p) => ({ date: p.date, completed: p.completed })),
    ),
    watchlist: list(assignmentReportRowSchema),
    generated_at: str(),
    due_soon_days: looseInt(),
    inactive_days: looseInt(),
  })
  .transform((j) => ({
    summary: j.summary,
    breakdowns: j.breakdowns,
    completionTrend: j.completion_trend,
    watchlist: j.watchlist,
    generatedAt: j.generated_at,
    dueSoonDays: j.due_soon_days,
    inactiveDays: j.inactive_days,
  }))
export type PerformanceOverview = z.output<typeof performanceOverviewSchema>
export const parsePerformanceOverview = (json: unknown) => performanceOverviewSchema.parse(json)

export const courseListReportSchema = z
  .object({ courses: list(courseReportSchema), generated_at: str() })
  .transform((j) => ({ courses: j.courses, generatedAt: j.generated_at }))
export type CourseListReport = z.output<typeof courseListReportSchema>
export const parseCourseListReport = (json: unknown) => courseListReportSchema.parse(json)

export const courseModuleReportSchema = z
  .object({
    module_id: str(),
    module_number: looseInt(),
    title: str(),
    num_questions: looseInt(),
    assigned: looseInt(),
    watched: looseInt(),
    passed: looseInt(),
    attempts: looseInt(),
    average_score: optNum(),
  })
  .transform((j) => ({
    moduleId: j.module_id,
    moduleNumber: j.module_number,
    title: j.title,
    numQuestions: j.num_questions,
    assigned: j.assigned,
    watched: j.watched,
    passed: j.passed,
    attempts: j.attempts,
    averageScore: j.average_score,
  }))
export type CourseModuleReport = z.output<typeof courseModuleReportSchema>

export const courseDetailReportSchema = z
  .object({
    course: nestedRecord(courseReportSchema),
    modules: list(courseModuleReportSchema),
    generated_at: str(),
  })
  .transform((j) => ({ course: j.course, modules: j.modules, generatedAt: j.generated_at }))
export type CourseDetailReport = z.output<typeof courseDetailReportSchema>
export const parseCourseDetailReport = (json: unknown) => courseDetailReportSchema.parse(json)

export const assignmentListReportSchema = z
  .object({
    rows: list(assignmentReportRowSchema),
    total: looseInt(),
    page: int(1),
    page_size: int(),
    generated_at: str(),
  })
  .transform((j) => ({
    rows: j.rows,
    total: j.total,
    page: j.page,
    pageSize: j.page_size,
    generatedAt: j.generated_at,
  }))
export type AssignmentListReport = z.output<typeof assignmentListReportSchema>
export const parseAssignmentListReport = (json: unknown) => assignmentListReportSchema.parse(json)

export const assignmentModuleReportSchema = z
  .object({
    module_id: str(),
    module_number: looseInt(),
    title: str(),
    num_questions: looseInt(),
    video_watched: bool(),
    quiz_passed: bool(),
    latest_score: optNum(),
    attempt_count: looseInt(),
    last_attempt_at: optStr(),
  })
  .transform((j) => ({
    moduleId: j.module_id,
    moduleNumber: j.module_number,
    title: j.title,
    numQuestions: j.num_questions,
    videoWatched: j.video_watched,
    quizPassed: j.quiz_passed,
    latestScore: j.latest_score,
    attemptCount: j.attempt_count,
    lastAttemptAt: j.last_attempt_at,
  }))
export type AssignmentModuleReport = z.output<typeof assignmentModuleReportSchema>

export const quizAttemptReportSchema = z
  .object({ module_id: optStr(), occurred_at: str(), score: optNum(), passed: optBool() })
  .transform((j) => ({
    moduleId: j.module_id,
    occurredAt: j.occurred_at,
    score: j.score,
    passed: j.passed,
  }))
export type QuizAttemptReport = z.output<typeof quizAttemptReportSchema>

export const assignmentDetailReportSchema = z
  .object({
    assignment: nestedRecord(assignmentReportRowSchema),
    modules: list(assignmentModuleReportSchema),
    attempts: list(quizAttemptReportSchema),
    generated_at: str(),
  })
  .transform((j) => ({
    assignment: j.assignment,
    modules: j.modules,
    attempts: j.attempts,
    generatedAt: j.generated_at,
  }))
export type AssignmentDetailReport = z.output<typeof assignmentDetailReportSchema>
export const parseAssignmentDetailReport = (json: unknown) =>
  assignmentDetailReportSchema.parse(json)

export const employeeReportRowSchema = z
  .object({
    employee_id: str(),
    employee_name: str(),
    employee_status: str(),
    department: optStr(),
    assigned: looseInt(),
    completed: looseInt(),
    in_progress: looseInt(),
    not_started: looseInt(),
    completion_rate: optNum(),
    overdue: looseInt(),
    due_soon: looseInt(),
    inactive: looseInt(),
    repeated_failures: looseInt(),
    average_score: optNum(),
    scored_modules: looseInt(),
    last_learner_activity_at: optStr(),
    needs_attention: bool(),
  })
  .transform((j) => ({
    employeeId: j.employee_id,
    employeeName: j.employee_name,
    employeeStatus: j.employee_status,
    department: j.department,
    assigned: j.assigned,
    completed: j.completed,
    inProgress: j.in_progress,
    notStarted: j.not_started,
    completionRate: j.completion_rate,
    overdue: j.overdue,
    dueSoon: j.due_soon,
    inactive: j.inactive,
    repeatedFailures: j.repeated_failures,
    averageScore: j.average_score,
    scoredModules: j.scored_modules,
    lastLearnerActivityAt: j.last_learner_activity_at,
    needsAttention: j.needs_attention,
  }))
export type EmployeeReportRow = z.output<typeof employeeReportRowSchema>

// summary is dict[str, int]; non-numbers count as 0 (_number in Dart).
const countMap = lenient((v) => {
  const out: Record<string, number> = {}
  if (isRecord(v)) {
    for (const [key, value] of Object.entries(v)) {
      out[key] = typeof value === 'number' && Number.isFinite(value) ? Math.trunc(value) : 0
    }
  }
  return out
})

export const employeeListReportSchema = z
  .object({
    rows: list(employeeReportRowSchema),
    total: looseInt(),
    page: int(1),
    page_size: int(),
    summary: countMap,
    generated_at: str(),
  })
  .transform((j) => ({
    rows: j.rows,
    total: j.total,
    page: j.page,
    pageSize: j.page_size,
    summary: j.summary,
    generatedAt: j.generated_at,
  }))
export type EmployeeListReport = z.output<typeof employeeListReportSchema>
export const parseEmployeeListReport = (json: unknown) => employeeListReportSchema.parse(json)

export const employeeDetailReportSchema = z
  .object({
    employee: nestedRecord(employeeReportRowSchema),
    assignments: list(assignmentReportRowSchema),
    generated_at: str(),
  })
  .transform((j) => ({
    employee: j.employee,
    assignments: j.assignments,
    generatedAt: j.generated_at,
  }))
export type EmployeeDetailReport = z.output<typeof employeeDetailReportSchema>
export const parseEmployeeDetailReport = (json: unknown) => employeeDetailReportSchema.parse(json)

// Report display helpers (Dart _score, _percent). Placeholder is "-" instead of the em dash.
export const formatScore = (value: unknown): string =>
  typeof value === 'number' ? `${value.toFixed(1)}%` : '-'

export const formatPercent = (value: unknown): string =>
  typeof value === 'number' ? `${value.toFixed(Number.isInteger(value) ? 0 : 1)}%` : '-'

// Learning Journey results. Source: backend/app/services/journey_reporting.py.
export const journeyReportSchema = z
  .object({
    journey_id: str(),
    title: str(),
    journey_status: str(),
    step_count: looseInt(),
    required_count: looseInt(),
    certificate_enabled: bool(),
    assigned: looseInt(),
    unique_learners: looseInt(),
    completed: looseInt(),
    started: looseInt(),
    pending: looseInt(),
    waiting: looseInt(),
    overdue: looseInt(),
    removed: looseInt(),
    due_soon: looseInt(),
    inactive: looseInt(),
    completion_rate: looseInt(),
    average_progress: looseInt(),
    certificates: looseInt(),
  })
  .transform((j) => ({
    journeyId: j.journey_id,
    title: j.title,
    journeyStatus: j.journey_status,
    stepCount: j.step_count,
    requiredCount: j.required_count,
    certificateEnabled: j.certificate_enabled,
    assigned: j.assigned,
    uniqueLearners: j.unique_learners,
    completed: j.completed,
    started: j.started,
    pending: j.pending,
    waiting: j.waiting,
    overdue: j.overdue,
    removed: j.removed,
    dueSoon: j.due_soon,
    inactive: j.inactive,
    completionRate: j.completion_rate,
    averageProgress: j.average_progress,
    certificates: j.certificates,
  }))
export type JourneyReport = z.output<typeof journeyReportSchema>

export const journeyListReportSchema = z
  .object({ enabled: bool(), journeys: list(journeyReportSchema), generated_at: str() })
  .transform((j) => ({ enabled: j.enabled, journeys: j.journeys, generatedAt: j.generated_at }))
export type JourneyListReport = z.output<typeof journeyListReportSchema>
export const parseJourneyListReport = (json: unknown) => journeyListReportSchema.parse(json)

export const journeyStepReportSchema = z
  .object({
    course_id: str(),
    course_name: str(),
    step_number: looseInt(),
    stage_title: optStr(),
    is_required: bool(),
    unlock_rule: str(),
    learners: looseInt(),
    passed: looseInt(),
    in_progress: looseInt(),
    available: looseInt(),
    locked: looseInt(),
    unavailable: looseInt(),
  })
  .transform((j) => ({
    courseId: j.course_id,
    courseName: j.course_name,
    stepNumber: j.step_number,
    stageTitle: j.stage_title,
    isRequired: j.is_required,
    unlockRule: j.unlock_rule,
    learners: j.learners,
    passed: j.passed,
    inProgress: j.in_progress,
    available: j.available,
    locked: j.locked,
    unavailable: j.unavailable,
  }))
export type JourneyStepReport = z.output<typeof journeyStepReportSchema>

export const journeyLearnerReportSchema = z
  .object({
    journey_id: str(),
    employee_id: str(),
    employee_name: str(),
    employee_status: str(),
    department: optStr(),
    status: str(),
    assigned_at: optStr(),
    available_at: optStr(),
    started_at: optStr(),
    completed_at: optStr(),
    deadline: optStr(),
    last_learner_activity_at: optStr(),
    passed_count: looseInt(),
    required_count: looseInt(),
    completion_percent: looseInt(),
    current_step: optNum(),
    current_course_id: optStr(),
    current_course_name: optStr(),
    certificate_number: optStr(),
    due_soon: bool(),
    inactive: bool(),
  })
  .transform((j) => ({
    journeyId: j.journey_id,
    employeeId: j.employee_id,
    employeeName: j.employee_name,
    employeeStatus: j.employee_status,
    department: j.department,
    status: j.status,
    assignedAt: j.assigned_at,
    availableAt: j.available_at,
    startedAt: j.started_at,
    completedAt: j.completed_at,
    deadline: j.deadline,
    lastLearnerActivityAt: j.last_learner_activity_at,
    passedCount: j.passed_count,
    requiredCount: j.required_count,
    completionPercent: j.completion_percent,
    currentStep: j.current_step,
    currentCourseId: j.current_course_id,
    currentCourseName: j.current_course_name,
    certificateNumber: j.certificate_number,
    dueSoon: j.due_soon,
    inactive: j.inactive,
  }))
export type JourneyLearnerReport = z.output<typeof journeyLearnerReportSchema>

export const journeyDetailReportSchema = z
  .object({
    journey: nestedRecord(journeyReportSchema),
    steps: list(journeyStepReportSchema),
    learners: list(journeyLearnerReportSchema),
    generated_at: str(),
  })
  .transform((j) => ({
    journey: j.journey,
    steps: j.steps,
    learners: j.learners,
    generatedAt: j.generated_at,
  }))
export type JourneyDetailReport = z.output<typeof journeyDetailReportSchema>
export const parseJourneyDetailReport = (json: unknown) => journeyDetailReportSchema.parse(json)
