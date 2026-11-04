import { apiRequest } from '@lms/shared/api/client'
import {
  isVideoServiceActive,
  parseGenerationConfig,
  type Course,
  type GenerationConfig,
  type VideoGenerationMode,
} from '@lms/shared/models'
import { useQuery } from '@tanstack/react-query'

const CONFIG_KEY = ['generation-config'] as const

/** An older backend without the config endpoint, or a failed request: local, no toggle. */
const FALLBACK_CONFIG: GenerationConfig = {
  defaultMode: 'local',
  toggleEnabled: false,
  videoEngineAvailable: false,
}

/** Server-wide generation settings (GET /api/generation/config). */
export function useGenerationConfig(): GenerationConfig {
  const query = useQuery({
    queryKey: CONFIG_KEY,
    queryFn: async () => parseGenerationConfig(await apiRequest('/api/generation/config')),
    staleTime: Infinity,
    retry: false,
  })
  return query.data ?? FALLBACK_CONFIG
}

/**
 * How one course's module videos are made. "external" means the Video Generator service, which
 * burns subtitles into the video and has no slides or narration scripts. The course's own engine
 * (the Blueprint tab's Video Engine toggle) wins. With the toggle switched off on the server, or
 * a course from an older backend, the server-wide default applies, as the backend does.
 */
export function courseVideoMode(
  course: Pick<Course, 'videoEngine'> | null | undefined,
  config: GenerationConfig,
): VideoGenerationMode {
  if (!config.toggleEnabled) return config.defaultMode
  if (course?.videoEngine === true) return 'external'
  if (course?.videoEngine === false) return 'local'
  return config.defaultMode
}

/** Overlay detail for a full-course run: finished videos and each module still in progress. */
export function moduleVideoProgress(course: Course | null | undefined): string | null {
  if (!course || course.modules.length === 0) return null
  const ready = course.modules.filter((module) => module.videoPath).length
  const active = course.modules
    .filter((module) => !module.videoPath && isVideoServiceActive(module.videoService))
    .map((module) => {
      const service = module.videoService!
      const progress = service.progress == null ? '' : ` ${Math.round(service.progress)}%`
      return `Module ${module.moduleNumber}: ${service.stage ?? service.status}${progress}`
    })
  if (ready === 0 && active.length === 0) return null
  return [`Module videos ready: ${ready} of ${course.modules.length}`, ...active].join('\n')
}
