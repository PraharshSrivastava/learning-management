// Port of employee_frontend/test/quiz_submission_result_test.dart.
import { parsePublishedCourseModule, parseQuizSubmissionResult } from '@lms/shared/models'
import { describe, expect, it } from 'vitest'

describe('quiz submission result', () => {
  it('module pass mark defaults to exact two thirds', () => {
    const module = parsePublishedCourseModule({
      module_number: 1,
      video_path: 'module.mp4',
      quiz: [],
    })
    expect(module.passMark).toBeCloseTo(2 / 3, 9)
  })

  it('parses the authoritative backend grading response', () => {
    const result = parseQuizSubmissionResult({
      quiz_passed: true,
      quiz_score: 2 / 3,
      correct_count: 2,
      total_questions: 3,
      pass_mark: 2 / 3,
      correct_answers: { '0': 'A', '1': 'B', '2': 'C' },
      explanations: { '0': 'First explanation' },
    })
    expect(result.passed).toBe(true)
    expect(result.correctCount).toBe(2)
    expect(result.totalQuestions).toBe(3)
    expect(result.correctAnswers).toEqual({ 0: 'A', 1: 'B', 2: 'C' })
    expect(result.explanations).toEqual({ 0: 'First explanation' })
  })
})
