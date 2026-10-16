import { ApiError, errorDetail } from '@lms/shared/api/client'
import {
  isRecord,
  parseQuizQuestion,
  type CourseModule,
  type JsonRecord,
  type QuizQuestion,
} from '@lms/shared/models'

/** Quiz questions of a module. Entries that are not objects are skipped. */
export function quizQuestions(module: Pick<CourseModule, 'quiz'>): QuizQuestion[] {
  const questions = module.quiz?.questions
  if (!Array.isArray(questions)) return []
  return questions.filter(isRecord).map((question) => parseQuizQuestion(question))
}

export const hasVideo = (module: Pick<CourseModule, 'videoPath'>): boolean =>
  module.videoPath != null && module.videoPath.length > 0

export interface TranscriptSlide {
  title: string
  script: string
  isCover: boolean
}

const text = (value: unknown): string => (value == null ? '' : String(value))

/** Slides that have a narration script, in deck order. */
export function transcriptSlides(module: Pick<CourseModule, 'slides'>): TranscriptSlide[] {
  return module.slides
    .filter((slide): slide is JsonRecord => isRecord(slide))
    .map((slide) => ({
      title: text(slide.slide_title).trim(),
      script: text(slide.script).trim(),
      isCover: slide.is_cover_slide === true || text(slide.layout_type).toLowerCase() === 'cover',
    }))
    .filter((slide) => slide.script.length > 0)
}

export const slideTitle = (slide: TranscriptSlide, index: number): string =>
  slide.title || (slide.isCover ? 'Module Cover' : `Slide ${index + 1}`)

/** File name for a downloaded module video. */
export function videoDownloadFilename(
  courseId: string,
  moduleNumber: number,
  title: string,
): string {
  const rawTitle = title.trim() || 'module'
  const safeTitle = rawTitle
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return `${courseId}-module-${moduleNumber}-${safeTitle || 'video'}.mp4`
}

/** Text for a failed generation request. Server detail wins. Other failures get a safe sentence. */
export function generationErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback
  if (error.status === 0) return error.message
  const body = error.body
  if (isRecord(body)) {
    const detail = body.detail
    if (isRecord(detail) && text(detail.message).trim()) return text(detail.message)
    const message = errorDetail(body)
    if (typeof detail !== 'object' && message?.trim()) return message
  }
  return `${fallback} Server returned ${error.status}.`
}
