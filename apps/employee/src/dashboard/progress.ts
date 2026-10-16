import {
  emptyModuleProgress,
  parseDartDate,
  type EmployeeCourse,
  type EmployeeModuleProgress,
} from '@lms/shared/models'

/** Local progress change. `selectedAnswers: undefined` keeps the saved answers. */
export interface ModuleProgressPatch {
  videoWatched?: boolean
  quizPassed?: boolean
  quizScore?: number
  selectedAnswers?: Record<number, string> | null
}

/** Optimistic update from course_progress_providers.dart `_applyModuleProgress`. */
export function applyModuleProgress(
  courses: EmployeeCourse[],
  courseId: string,
  moduleNumber: number,
  patch: ModuleProgressPatch,
): EmployeeCourse[] {
  const key = String(moduleNumber)
  return courses.map((course) => {
    if (course.courseId !== courseId) return course
    const existing = course.moduleProgress[key] ?? emptyModuleProgress()
    const quizChanged = patch.quizPassed !== undefined || patch.quizScore !== undefined
    const next: EmployeeModuleProgress = {
      videoWatched: patch.videoWatched ?? existing.videoWatched,
      quizPassed: patch.quizPassed ?? existing.quizPassed,
      quizScore: patch.quizScore ?? existing.quizScore,
      selectedAnswers:
        patch.selectedAnswers === undefined ? existing.selectedAnswers : patch.selectedAnswers,
      attemptCount: quizChanged ? existing.attemptCount + 1 : existing.attemptCount,
    }
    const moduleProgress = { ...course.moduleProgress, [key]: next }
    const allComplete =
      course.publishedModules.length > 0 &&
      course.publishedModules.every((module) => {
        const progress = moduleProgress[String(module.moduleNumber)]
        const watched = progress?.videoWatched === true
        const passed = module.quiz.length === 0 ? watched : progress?.quizPassed === true
        return watched && passed
      })
    const assignmentStatus = allComplete
      ? 'completed'
      : course.assignmentStatus === 'pending'
        ? 'started'
        : course.assignmentStatus
    return { ...course, assignmentStatus, moduleProgress }
  })
}

/** Dart `'${d.day}/${d.month}/${d.year}'`, or null when the value does not parse. */
export function shortDate(value: string | null): string | null {
  const date = parseDartDate(value)
  return date ? `${date.getDate()}/${date.getMonth() + 1}/${date.getFullYear()}` : null
}

/** Course card due date. Unparsed values show their date part. */
export const dueDateLabel = (value: string): string => shortDate(value) ?? value.split('T')[0]!

/** Notification subtitle. */
export function assignedDateLabel(value: string | null): string {
  const date = shortDate(value)
  return date ? `Assigned ${date}` : 'Recently assigned'
}

/** Dart `(value * 100).toStringAsFixed(1)`. */
export const percentLabel = (value: number): string => (value * 100).toFixed(1)
