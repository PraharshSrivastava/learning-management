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

export interface GenerationConfig {
  /** Engine for courses with no stored choice. */
  defaultMode: VideoGenerationMode
  /** Trainers can choose the engine per course on the Blueprint tab. */
  toggleEnabled: boolean
  /** The Video Generator is configured on the server. */
  videoEngineAvailable: boolean
}

/** GET /api/generation/config. An older backend without the toggle fields reads as toggle off. */
export const parseGenerationConfig = (json: unknown): GenerationConfig => {
  const value = typeof json === 'object' && json !== null ? (json as Record<string, unknown>) : {}
  return {
    defaultMode: parseVideoGenerationMode(json),
    toggleEnabled: value.video_engine_toggle_enabled === true,
    videoEngineAvailable: value.video_engine_available === true,
  }
}

export const isGenerationComplete = (job: GenerationJob) =>
  job.status === 'completed' || job.status === 'failed'
