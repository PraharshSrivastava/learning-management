import type { EmployeeCourse, PublishedCourseModule } from '@lms/shared/models'
import type { IconName } from '@lms/shared/ui/icons/Icon'

/** Progress the learner made in this session, before the server confirms it. */
export interface LocalProgress {
  watched: ReadonlySet<number>
  passed: ReadonlySet<number>
  /** Watched videos whose completion save failed. */
  unsaved?: ReadonlySet<number>
}

const progressOf = (course: EmployeeCourse, module: PublishedCourseModule) =>
  course.moduleProgress[String(module.moduleNumber)]

export function isVideoWatched(
  course: EmployeeCourse,
  module: PublishedCourseModule,
  local: LocalProgress,
): boolean {
  return progressOf(course, module)?.videoWatched === true || local.watched.has(module.moduleNumber)
}

/** A module without a quiz is complete when its video is watched. */
export function isModuleComplete(
  course: EmployeeCourse,
  module: PublishedCourseModule,
  local: LocalProgress,
): boolean {
  // Without a quiz, nothing else saves the completion, so a failed save keeps the module open.
  if (module.quiz.length === 0) {
    return (
      progressOf(course, module)?.videoWatched === true ||
      (local.watched.has(module.moduleNumber) && !local.unsaved?.has(module.moduleNumber))
    )
  }
  return (
    (progressOf(course, module)?.quizPassed === true && isVideoWatched(course, module, local)) ||
    local.passed.has(module.moduleNumber)
  )
}

/** Flutter `_isVideoUnlocked`: the first module is open, the others need the previous one complete. */
export function isVideoUnlocked(
  course: EmployeeCourse,
  index: number,
  local: LocalProgress,
): boolean {
  if (index === 0) return true
  const previous = course.publishedModules[index - 1]
  return previous != null && isModuleComplete(course, previous, local)
}

/** Flutter `_isQuizUnlocked`: the quiz opens after the module video is watched. */
export function isQuizUnlocked(
  course: EmployeeCourse,
  index: number,
  local: LocalProgress,
): boolean {
  const module = course.publishedModules[index]
  return module != null && isVideoWatched(course, module, local)
}

export interface ModuleStatus {
  icon: IconName
  color: string
  background: string
  label: 'Locked' | 'Completed' | 'Quiz ready' | 'In progress'
}

export function moduleStatus(
  course: EmployeeCourse,
  module: PublishedCourseModule,
  unlocked: boolean,
  local: LocalProgress,
): ModuleStatus {
  if (!unlocked)
    return {
      icon: 'lock_outline_rounded',
      color: '#667085',
      background: '#f2f4f7',
      label: 'Locked',
    }
  if (isModuleComplete(course, module, local))
    return { icon: 'verified_rounded', color: '#087e5b', background: '#e7f7f0', label: 'Completed' }
  if (isVideoWatched(course, module, local))
    return {
      icon: 'assignment_turned_in_rounded',
      color: '#087e5b',
      background: '#e7f7f0',
      label: 'Quiz ready',
    }
  return {
    icon: 'play_circle_outline_rounded',
    color: '#00317a',
    background: '#e7efff',
    label: 'In progress',
  }
}

/** Resume first incomplete module; a completed course opens its final module. */
export function resumeModuleIndex(course: EmployeeCourse): number {
  const none: LocalProgress = { watched: new Set(), passed: new Set() }
  const first = course.publishedModules.findIndex(
    (module) => !isModuleComplete(course, module, none),
  )
  return first < 0 ? Math.max(0, course.publishedModules.length - 1) : first
}

/** Header count includes completed video-only modules. */
export function passedModuleCount(course: EmployeeCourse): number {
  return course.publishedModules.filter((module) =>
    isModuleComplete(course, module, { watched: new Set(), passed: new Set() }),
  ).length
}

/** Option key for an index: A, B, C, D. */
export const optionKey = (index: number): string => String.fromCharCode(65 + index)
