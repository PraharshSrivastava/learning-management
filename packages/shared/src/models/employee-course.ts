// Employee app course models (Dart: employee_frontend models.dart Course.fromPublishedJson,
// PublishedCourseModule, EmployeeModuleProgress; course_dashboard_data.dart).
// EmployeeCourse differs from the trainer Course: it has assignment dates, published modules
// and per-module progress, and no lifecycle or generation fields. Course.fromJson and the
// lesson models are unused by the live employee app and are not ported.
import { z } from 'zod'
import { courseImageSchema } from './course'
import {
  bool,
  indexedMap,
  int,
  isRecord,
  list,
  num,
  onlyStr,
  optNum,
  optOnlyStr,
  parseDartDate,
  reparse,
  str,
  unknownList,
  type JsonRecord,
} from './parse'
import { publishedQuizQuestionSchema } from './quiz'

export const publishedCourseModuleSchema = z
  .object({
    module_number: int(),
    title: str(),
    notes: str(),
    video_path: str(),
    quiz: list(publishedQuizQuestionSchema),
    pass_mark: num(2 / 3),
    captions: unknownList(),
  })
  .transform((j) => ({
    moduleNumber: j.module_number,
    title: j.title,
    notes: j.notes,
    videoPath: j.video_path,
    quiz: j.quiz,
    passMark: j.pass_mark,
    captions: j.captions,
  }))
export type PublishedCourseModule = z.output<typeof publishedCourseModuleSchema>
export const parsePublishedCourseModule = (json: unknown): PublishedCourseModule =>
  publishedCourseModuleSchema.parse(json)

export const employeeModuleProgressSchema = z
  .object({
    video_watched: bool(),
    quiz_passed: bool(),
    quiz_score: optNum(),
    selected_answers: z.unknown(),
    attempt_count: int(),
  })
  .transform((j) => ({
    videoWatched: j.video_watched,
    quizPassed: j.quiz_passed,
    quizScore: j.quiz_score,
    // Saved answers load only after a pass, so a failed quiz can be retaken.
    selectedAnswers:
      j.quiz_passed && isRecord(j.selected_answers) ? indexedMap(j.selected_answers, false) : null,
    attemptCount: j.attempt_count,
  }))
export type EmployeeModuleProgress = z.output<typeof employeeModuleProgressSchema>
export const parseEmployeeModuleProgress = (json: unknown): EmployeeModuleProgress =>
  employeeModuleProgressSchema.parse(json)

// Dart EmployeeModuleProgress() defaults.
export const emptyModuleProgress = (): EmployeeModuleProgress => ({
  videoWatched: false,
  quizPassed: false,
  quizScore: null,
  selectedAnswers: null,
  attemptCount: 0,
})

export const employeeCourseSchema = z
  .object({
    course_id: onlyStr(),
    course_name: onlyStr(),
    course_description: onlyStr(),
    images: list(courseImageSchema),
    thumbnail_path: str(),
    created_at: str(),
    assignment_status: optOnlyStr(),
    assigned_at: optOnlyStr(),
    deadline: optOnlyStr(),
    started_at: optOnlyStr(),
    completed_at: optOnlyStr(),
    modules: list(publishedCourseModuleSchema),
    module_progress: z.unknown(),
    quiz_attempts: z.unknown(),
  })
  .transform((j, ctx) => {
    const progress = isRecord(j.module_progress) ? j.module_progress : {}
    const attempts: JsonRecord = isRecord(j.quiz_attempts) ? j.quiz_attempts : {}
    const moduleProgress: Record<string, EmployeeModuleProgress> = {}
    for (const [key, value] of Object.entries(progress)) {
      if (!isRecord(value)) continue
      const merged: JsonRecord = { ...value }
      const attempt = attempts[key]
      if (isRecord(attempt)) merged.attempt_count = attempt.count
      moduleProgress[key] = reparse(employeeModuleProgressSchema, merged, ctx)
    }
    return {
      courseId: j.course_id,
      courseName: j.course_name,
      courseDescription: j.course_description,
      images: j.images,
      thumbnailPath: j.thumbnail_path,
      createdAt: j.created_at,
      assignmentStatus: j.assignment_status,
      assignedAt: j.assigned_at,
      deadline: j.deadline,
      startedAt: j.started_at,
      completedAt: j.completed_at,
      publishedModules: j.modules,
      moduleProgress,
    }
  })
export type EmployeeCourse = z.output<typeof employeeCourseSchema>
export const parseEmployeeCourse = (json: unknown): EmployeeCourse =>
  employeeCourseSchema.parse(json)

// Request bodies for PUT /me/courses/{id}/modules/{n}/progress and the assignment status update.
export const videoWatchedToJson = () => ({ video_watched: true })
export const assignmentStatusToJson = (status: string) => ({ status })

// ---------- Dashboard helpers (Dart CourseDashboardData, LearningMetrics) ----------

export type DashboardCourseStatus = 'pending' | 'inProgress' | 'passed' | 'overdue'

const DAY_MS = 24 * 60 * 60 * 1000
const FAR_FUTURE = Number.MAX_SAFE_INTEGER
const FAR_PAST = Number.MIN_SAFE_INTEGER

const timeOf = (value: string | null): number | null => parseDartDate(value)?.getTime() ?? null

function isModuleDone(course: EmployeeCourse, module: PublishedCourseModule): boolean {
  const progress = course.moduleProgress[String(module.moduleNumber)]
  return (
    progress?.quizPassed === true || (module.quiz.length === 0 && progress?.videoWatched === true)
  )
}

export function statusFor(course: EmployeeCourse, now: Date = new Date()): DashboardCourseStatus {
  const modules = course.publishedModules
  const hasStarted = Object.values(course.moduleProgress).some(
    (p) => p.videoWatched || p.quizPassed,
  )
  const isPassed = modules.length > 0 && modules.every((m) => isModuleDone(course, m))
  if (isPassed) return 'passed'
  const deadline = timeOf(course.deadline)
  if (deadline != null && deadline < now.getTime()) return 'overdue'
  return hasStarted ? 'inProgress' : 'pending'
}

export function progressFor(course: EmployeeCourse): number {
  if (course.publishedModules.length === 0) return 0
  const done = course.publishedModules.filter((m) => isModuleDone(course, m)).length
  return done / course.publishedModules.length
}

export const watchedModulesFor = (course: EmployeeCourse): number =>
  course.publishedModules.filter(
    (m) => course.moduleProgress[String(m.moduleNumber)]?.videoWatched === true,
  ).length

export function isDueSoon(course: EmployeeCourse, now: Date = new Date()): boolean {
  const deadline = timeOf(course.deadline)
  return deadline != null && deadline > now.getTime() && deadline < now.getTime() + 7 * DAY_MS
}

export function isNewAssignment(course: EmployeeCourse, now: Date = new Date()): boolean {
  const assignedAt = timeOf(course.assignedAt)
  return (
    assignedAt != null &&
    assignedAt > now.getTime() - 7 * DAY_MS &&
    statusFor(course, now) === 'pending'
  )
}

const statusRank: Record<DashboardCourseStatus, number> = {
  overdue: 0,
  pending: 1,
  inProgress: 2,
  passed: 3,
}

// Not passed; overdue first, then pending, in progress; then earliest deadline.
export function orderedAssigned(
  courses: EmployeeCourse[],
  now: Date = new Date(),
): EmployeeCourse[] {
  return courses
    .filter((c) => statusFor(c, now) !== 'passed')
    .sort((a, b) => {
      const order = statusRank[statusFor(a, now)] - statusRank[statusFor(b, now)]
      if (order !== 0) return order
      return (timeOf(a.deadline) ?? FAR_FUTURE) - (timeOf(b.deadline) ?? FAR_FUTURE) || 0
    })
}

// Passed or in progress, newest assignment first.
export function orderedAttempted(
  courses: EmployeeCourse[],
  now: Date = new Date(),
): EmployeeCourse[] {
  return courses
    .filter((c) => {
      const status = statusFor(c, now)
      return status === 'passed' || status === 'inProgress'
    })
    .sort((a, b) => (timeOf(b.assignedAt) ?? FAR_PAST) - (timeOf(a.assignedAt) ?? FAR_PAST) || 0)
}

export interface LearningMetrics {
  assigned: number
  attempted: number
  passed: number
  pending: number
  inProgress: number
}

export function learningMetrics(
  courses: EmployeeCourse[],
  now: Date = new Date(),
): LearningMetrics {
  const statuses = courses.map((c) => statusFor(c, now))
  const passed = statuses.filter((s) => s === 'passed').length
  const inProgress = statuses.filter((s) => s === 'inProgress').length
  const pending = statuses.filter((s) => s === 'pending' || s === 'overdue').length
  return {
    assigned: courses.length - passed,
    attempted: passed + inProgress,
    passed,
    pending,
    inProgress,
  }
}
