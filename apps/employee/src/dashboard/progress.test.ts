import { describe, expect, it } from 'vitest'
import { employeeCourse, moduleJson } from '../test/fixtures'
import { applyModuleProgress, assignedDateLabel, dueDateLabel, percentLabel } from './progress'

describe('applyModuleProgress', () => {
  it('starts a pending course and keeps other courses', () => {
    const other = employeeCourse({ course_id: 'c2' })
    const [course, untouched] = applyModuleProgress([employeeCourse(), other], 'c1', 1, {
      videoWatched: true,
    })
    expect(course!.assignmentStatus).toBe('started')
    expect(course!.moduleProgress['1']).toMatchObject({ videoWatched: true, attemptCount: 0 })
    expect(untouched).toBe(other)
  })

  it('counts quiz attempts and completes the course when all modules pass', () => {
    const start = employeeCourse({
      modules: [moduleJson(1)],
      module_progress: { '1': { video_watched: true } },
      assignment_status: 'started',
    })
    const [course] = applyModuleProgress([start], 'c1', 1, {
      quizPassed: true,
      quizScore: 1,
      selectedAnswers: { 0: 'A' },
    })
    expect(course!.assignmentStatus).toBe('completed')
    expect(course!.moduleProgress['1']).toMatchObject({
      quizPassed: true,
      attemptCount: 1,
      selectedAnswers: { 0: 'A' },
    })
  })

  it('a failed quiz resets the video and clears the answers', () => {
    const start = employeeCourse({ module_progress: { '1': { video_watched: true } } })
    const [course] = applyModuleProgress([start], 'c1', 1, {
      quizPassed: false,
      quizScore: 0,
      selectedAnswers: null,
      videoWatched: false,
    })
    expect(course!.moduleProgress['1']).toMatchObject({
      videoWatched: false,
      selectedAnswers: null,
      attemptCount: 1,
    })
  })
})

describe('labels', () => {
  it('formats dates as Dart does', () => {
    expect(dueDateLabel('2026-03-05T10:00:00')).toBe('5/3/2026')
    expect(dueDateLabel('not a dateTlater')).toBe('not a date')
    expect(assignedDateLabel(null)).toBe('Recently assigned')
    expect(assignedDateLabel('2026-12-01')).toBe('Assigned 1/12/2026')
    expect(percentLabel(2 / 3)).toBe('66.7')
  })
})
