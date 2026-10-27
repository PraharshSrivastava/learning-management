// Trainer app course models (Dart: frontend models.dart CourseImage, CourseModule, Course).
// Dart toJson of CourseImage/CourseModule/Course is never sent by the app, so it is not ported.
import { z } from 'zod'
import {
  bool,
  raw,
  dartString,
  int,
  isRecord,
  lenient,
  list,
  optRecord,
  optStr,
  reparse,
  str,
  unknownList,
} from './parse'
import { hasQuizQuestions } from './quiz'

export const courseImageSchema = z
  .object({ image_id: str(), caption: str(), file_path: str() })
  .transform((j) => ({ imageId: j.image_id, caption: j.caption, filePath: j.file_path }))
export type CourseImage = z.output<typeof courseImageSchema>
export const parseCourseImage = (json: unknown): CourseImage => courseImageSchema.parse(json)

/** Progress of one module's run on the external Video Generator service. */
export interface ModuleVideoService {
  status: string
  stage: string | null
  /** 0 to 100, or null when the service cannot report it. */
  progress: number | null
  error: string | null
}

const ACTIVE_VIDEO_STATUSES = new Set(['submitting', 'queued', 'processing'])
const FAILED_VIDEO_STATUSES = new Set(['failed', 'needs_attention'])

export const isVideoServiceActive = (service: ModuleVideoService | null): boolean =>
  service != null && ACTIVE_VIDEO_STATUSES.has(service.status)

export const hasVideoServiceFailed = (service: ModuleVideoService | null): boolean =>
  service != null && FAILED_VIDEO_STATUSES.has(service.status)

const videoService = () =>
  lenient((value): ModuleVideoService | null => {
    if (!isRecord(value) || value.status == null || value.status === '') return null
    const progress = value.progress
    return {
      status: dartString(value.status),
      stage: value.stage == null ? null : dartString(value.stage),
      progress: typeof progress === 'number' && Number.isFinite(progress) ? progress : null,
      error: value.error == null ? null : dartString(value.error),
    }
  })

export const courseModuleSchema = z
  .object({
    module_number: int(),
    title: str(),
    source_text: str(),
    start_line: str(),
    end_line: str(),
    num_questions: int(3),
    quiz: optRecord(),
    slides: unknownList(),
    images: list(courseImageSchema),
    video_path: optStr(),
    notes: str(),
    captions: unknownList(),
    video_service: videoService(),
  })
  .transform((j) => ({
    moduleNumber: j.module_number,
    title: j.title,
    sourceText: j.source_text,
    startLine: j.start_line,
    endLine: j.end_line,
    numQuestions: j.num_questions,
    quiz: j.quiz,
    slides: j.slides,
    images: j.images,
    videoPath: j.video_path,
    notes: j.notes,
    captions: j.captions,
    videoService: j.video_service,
  }))
export type CourseModule = z.output<typeof courseModuleSchema>
export const parseCourseModule = (json: unknown): CourseModule => courseModuleSchema.parse(json)

// A non-map item in `modules` becomes a title-only module (Dart fallback).
const moduleOrTitleSchema = z.unknown().transform((item, ctx): CourseModule => {
  if (isRecord(item)) return reparse(courseModuleSchema, item, ctx)
  return {
    moduleNumber: 0,
    title: dartString(item),
    sourceText: '',
    startLine: '',
    endLine: '',
    numQuestions: 3,
    quiz: null,
    slides: [],
    images: [],
    videoPath: null,
    notes: '',
    captions: [],
    videoService: null,
  }
})

// Dart: (json['generation'] as Map?)?[key]?.toString() ?? ''. A non-map value acts as empty here.
const generationField = (key: string) => (generation: unknown) =>
  isRecord(generation) && generation[key] != null ? dartString(generation[key]) : ''

export const courseSchema = z
  .object({
    lifecycle_state: str(),
    lifecycle_revision: int(),
    can_delete: bool(),
    course_id: str(),
    trainer_id: str(),
    document_id: optStr(),
    can_manage: bool(),
    creator_name: optStr(),
    course_name: str(),
    course_description: str(),
    course_objective: str(),
    course_difficulty: str(),
    language: str(),
    target_audience: str(),
    modules: z.preprocess((v) => (Array.isArray(v) ? v : []), z.array(moduleOrTitleSchema)),
    images: list(courseImageSchema),
    thumbnail_path: str(),
    status: str(),
    created_at: str(),
    generation: raw(),
    module_count: raw(),
    is_assignable: bool(),
  })
  .transform((j) => {
    // Course is assignable when ready or published with a thumbnail and fully built modules.
    const inferredAssignable =
      (j.status === 'ready' || j.status === 'published') &&
      j.thumbnail_path.length > 0 &&
      j.modules.length > 0 &&
      j.modules.every((module) => {
        if (module.videoPath == null || module.videoPath.length === 0) return false
        if (module.numQuestions <= 0) return true
        return hasQuizQuestions(module.quiz)
      })
    const moduleCount =
      typeof j.module_count === 'number' && Number.isFinite(j.module_count)
        ? Math.trunc(j.module_count)
        : j.modules.length
    return {
      lifecycleState: j.lifecycle_state,
      lifecycleRevision: j.lifecycle_revision,
      canDelete: j.can_delete,
      courseId: j.course_id,
      trainerId: j.trainer_id,
      documentId: j.document_id,
      canManage: j.can_manage,
      creatorName: j.creator_name,
      courseName: j.course_name,
      courseDescription: j.course_description,
      courseObjective: j.course_objective,
      courseDifficulty: j.course_difficulty,
      language: j.language,
      targetAudience: j.target_audience,
      modules: j.modules,
      images: j.images,
      thumbnailPath: j.thumbnail_path,
      status: j.status,
      createdAt: j.created_at,
      generationStatus: generationField('status')(j.generation),
      failedCheckpoint: generationField('failed_checkpoint')(j.generation),
      currentCheckpoint: generationField('current_checkpoint')(j.generation),
      generationError: generationField('error')(j.generation),
      moduleCount,
      isAssignable: j.is_assignable || inferredAssignable,
    }
  })
export type Course = z.output<typeof courseSchema>
export const parseCourse = (json: unknown): Course => courseSchema.parse(json)
