import { describe, expect, it } from 'vitest'
import { employeeCourse, moduleJson } from '../test/fixtures'
import {
  isQuizUnlocked,
  isVideoUnlocked,
  moduleStatus,
  optionKey,
  passedModuleCount,
  resumeModuleIndex,
  type LocalProgress,
} from './moduleRules'

const none: LocalProgress = { watched: new Set(), passed: new Set() }

describe('module rules', () => {
  it('resumes at the pending quiz and does not skip it for a watched video', () => {
    const course = employeeCourse({
      modules: [moduleJson(1), moduleJson(2), moduleJson(3)],
      module_progress: {
        '1': { video_watched: true, quiz_passed: true },
        '2': { video_watched: true, quiz_passed: false },
      },
    })
    expect(resumeModuleIndex(course)).toBe(1)
  })
  it('resumes after video-only completion and opens final module when complete', () => {
    const course = employeeCourse({
      modules: [moduleJson(1, { quiz: [] }), moduleJson(2)],
      module_progress: {
        '1': { video_watched: true },
        '2': { video_watched: true, quiz_passed: true },
      },
    })
    expect(resumeModuleIndex(course)).toBe(1)
    expect(passedModuleCount(course)).toBe(2)
  })
  it('opens the first module and locks the next until the quiz passes', () => {
    const course = employeeCourse()
    expect(isVideoUnlocked(course, 0, none)).toBe(true)
    expect(isVideoUnlocked(course, 1, none)).toBe(false)
    expect(isQuizUnlocked(course, 0, none)).toBe(false)
    const watched: LocalProgress = { watched: new Set([1]), passed: new Set() }
    expect(isQuizUnlocked(course, 0, watched)).toBe(true)
    expect(isVideoUnlocked(course, 1, watched)).toBe(false)
    expect(isVideoUnlocked(course, 1, { watched: new Set([1]), passed: new Set([1]) })).toBe(true)
  })

  it('uses server progress', () => {
    const course = employeeCourse({
      module_progress: { '1': { video_watched: true, quiz_passed: true, quiz_score: 1 } },
    })
    expect(isVideoUnlocked(course, 1, none)).toBe(true)
    expect(passedModuleCount(course)).toBe(1)
  })

  it('treats a module without a quiz as complete after the video', () => {
    const course = employeeCourse({ modules: [moduleJson(1, { quiz: [] }), moduleJson(2)] })
    expect(isVideoUnlocked(course, 1, none)).toBe(false)
    expect(isVideoUnlocked(course, 1, { watched: new Set([1]), passed: new Set() })).toBe(true)
  })

  it('keeps a module without a quiz open while its video save failed', () => {
    const course = employeeCourse({ modules: [moduleJson(1, { quiz: [] }), moduleJson(2)] })
    const unsaved: LocalProgress = {
      watched: new Set([1]),
      passed: new Set(),
      unsaved: new Set([1]),
    }
    expect(isQuizUnlocked(course, 0, unsaved)).toBe(true)
    expect(isVideoUnlocked(course, 1, unsaved)).toBe(false)
  })

  it('gives each state its label', () => {
    const course = employeeCourse()
    const first = course.publishedModules[0]!
    expect(moduleStatus(course, first, false, none).label).toBe('Locked')
    expect(moduleStatus(course, first, true, none).label).toBe('In progress')
    expect(
      moduleStatus(course, first, true, { watched: new Set([1]), passed: new Set() }).label,
    ).toBe('Quiz ready')
    expect(
      moduleStatus(course, first, true, { watched: new Set([1]), passed: new Set([1]) }).label,
    ).toBe('Completed')
  })

  it('maps option indexes to letters', () => {
    expect([0, 1, 2, 3].map(optionKey)).toEqual(['A', 'B', 'C', 'D'])
  })
})
