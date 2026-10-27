// Course generation job (Dart: trainer models.dart GenerationJob).
import { z } from 'zod'
import { optStr, str } from './parse'

export const generationJobSchema = z
  .object({ id: str(), course_id: str(), status: str(), error: optStr() })
  .transform((j) => ({ id: j.id, courseId: j.course_id, status: j.status, error: j.error }))
export type GenerationJob = z.output<typeof generationJobSchema>
export const parseGenerationJob = (json: unknown): GenerationJob => generationJobSchema.parse(json)

/** "local" renders slides with narration; "external" uses the Video Generator service. */
export type VideoGenerationMode = 'local' | 'external'

export const parseVideoGenerationMode = (json: unknown): VideoGenerationMode =>
  typeof json === 'object' &&
  json !== null &&
  (json as Record<string, unknown>).video_generation_mode === 'external'
    ? 'external'
    : 'local'

export const isGenerationComplete = (job: GenerationJob) =>
  job.status === 'completed' || job.status === 'failed'
