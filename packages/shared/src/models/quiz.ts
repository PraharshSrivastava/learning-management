// Quiz models (Dart: QuizQuestion/QuizOption in both apps, employee PublishedQuizQuestion,
// employee_frontend course_progress_providers.dart QuizSubmissionResult).
import { z } from 'zod'
import { isRecord, raw, list, str, strList } from './parse'

export const quizOptionSchema = z
  .object({ key: str(), text: str() })
  .transform((j) => ({ key: j.key, text: j.text }))
export type QuizOption = z.output<typeof quizOptionSchema>
export const parseQuizOption = (json: unknown): QuizOption => quizOptionSchema.parse(json)

// Both Flutter apps use the same shape.
export const quizQuestionSchema = z
  .object({
    question_text: str(),
    options: list(quizOptionSchema),
    correct_option: str(),
    explanation: str(),
  })
  .transform((j) => ({
    questionText: j.question_text,
    options: j.options,
    correctOption: j.correct_option,
    explanation: j.explanation,
  }))
export type QuizQuestion = z.output<typeof quizQuestionSchema>
export const parseQuizQuestion = (json: unknown): QuizQuestion => quizQuestionSchema.parse(json)

export const publishedQuizQuestionSchema = z
  .object({
    question_id: str(),
    question: str(),
    options: strList(),
    correct: str(),
    explanation: str(),
    answer_correct: z.boolean().optional(),
  })
  .transform((j) => ({
    questionId: j.question_id,
    question: j.question,
    options: j.options,
    correct: j.correct,
    explanation: j.explanation,
    answerCorrect: j.answer_correct,
  }))
export type PublishedQuizQuestion = z.output<typeof publishedQuizQuestionSchema>
export const parsePublishedQuizQuestion = (json: unknown): PublishedQuizQuestion =>
  publishedQuizQuestionSchema.parse(json)

// Hard casts in Dart: score, counts and pass mark are required numbers.
export const quizSubmissionResultSchema = z
  .object({
    quiz_passed: raw(),
    quiz_score: z.number(),
    correct_count: z.number(),
    total_questions: z.number(),
    pass_mark: z.number(),
    answer_results: raw(),
  })
  .transform((j) => ({
    passed: j.quiz_passed === true,
    score: j.quiz_score,
    correctCount: Math.trunc(j.correct_count),
    totalQuestions: Math.trunc(j.total_questions),
    passMark: j.pass_mark,
    answerResults: Object.fromEntries(
      Object.entries(isRecord(j.answer_results) ? j.answer_results : {}).filter(
        ([key, value]) => /^\d+$/.test(key) && typeof value === 'boolean',
      ),
    ) as Record<number, boolean>,
  }))
export type QuizSubmissionResult = z.output<typeof quizSubmissionResultSchema>
export const parseQuizSubmissionResult = (json: unknown): QuizSubmissionResult =>
  quizSubmissionResultSchema.parse(json)

// PUT body for submitQuiz: {"selected_answers": {"0": "A", ...}}
export function quizSubmitToJson(selectedAnswers: Record<number, string>) {
  const formatted: Record<string, string> = {}
  for (const [key, value] of Object.entries(selectedAnswers)) formatted[String(key)] = value
  return { selected_answers: formatted }
}

// Whether a module quiz payload holds a non-empty questions list.
export const hasQuizQuestions = (quiz: unknown): boolean =>
  isRecord(quiz) && Array.isArray(quiz.questions) && quiz.questions.length > 0
