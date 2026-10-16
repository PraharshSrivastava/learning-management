import { parseEmployeeCourse, type EmployeeCourse } from '@lms/shared/models'

/**
 * A learner quiz question as the backend sends it. The correct answer and the explanation are
 * only sent after the employee passed the quiz (backend/app/services/learning.py).
 */
export const quizQuestion = (text: string, correct = 'A', revealed = false) => ({
  question_id: `${text}-id`,
  question: `${text} question`,
  options: [`${text} first`, `${text} second`],
  ...(revealed ? { correct, explanation: `Why ${text}` } : {}),
})

export const moduleJson = (number: number, overrides: Record<string, unknown> = {}) => ({
  module_number: number,
  title: `Module title ${number}`,
  notes: `Notes ${number}`,
  video_path: `assets/videos/c/m${number}.mp4`,
  quiz: [quizQuestion(`Q${number}`)],
  ...overrides,
})

/** Employee course JSON as GET /api/me/courses returns it. */
export function courseJson(overrides: Record<string, unknown> = {}) {
  return {
    course_id: 'c1',
    course_name: 'Course one',
    course_description: 'About course one',
    images: [],
    thumbnail_path: '',
    assignment_status: 'pending',
    assigned_at: null,
    deadline: null,
    modules: [moduleJson(1), moduleJson(2)],
    module_progress: {},
    ...overrides,
  }
}

export const employeeCourse = (overrides?: Record<string, unknown>): EmployeeCourse =>
  parseEmployeeCourse(courseJson(overrides))
