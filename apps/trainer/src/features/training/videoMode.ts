import { apiRequest } from '@lms/shared/api/client'
import {
  isVideoServiceActive,
  parseVideoGenerationMode,
  type Course,
  type VideoGenerationMode,
} from '@lms/shared/models'
import { useQuery } from '@tanstack/react-query'

const CONFIG_KEY = ['generation-config'] as const

/**
 * How the backend produces module videos. "external" means the Video Generator service, which
 * burns subtitles into the video and has no slides or narration scripts. An older backend without
 * the config endpoint, or a failed request, means local rendering.
 */
export function useVideoGenerationMode(): VideoGenerationMode {
  const query = useQuery({
    queryKey: CONFIG_KEY,
    queryFn: async () => parseVideoGenerationMode(await apiRequest('/api/generation/config')),
    staleTime: Infinity,
    retry: false,
  })
  return query.data ?? 'local'
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
