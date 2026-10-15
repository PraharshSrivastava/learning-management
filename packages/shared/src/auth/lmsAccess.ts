import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import { apiRequest, lmsApp, setMediaTicket } from '../api/client'
import { useSession } from './session'

const flag = z.boolean().catch(false)

const lmsAccessSchema = z.object({
  employee_id: z.coerce.string().catch(''),
  trainer_id: z.string().nullish().catch(null),
  name: z.string().catch(''),
  roles: z.array(z.string()).catch([]),
  permissions_version: z.number().catch(0),
  report_scope_version: z.coerce.string().catch(''),
  capabilities: z
    .object({
      can_learn: flag,
      can_author_courses: flag,
      can_view_all_performance: flag,
      can_view_other_trainers_courses: flag,
      can_manage_other_trainers_courses: flag,
      can_view_department_performance: flag,
      can_view_observed_performance: flag,
    })
    .catch({
      can_learn: false,
      can_author_courses: false,
      can_view_all_performance: false,
      can_view_other_trainers_courses: false,
      can_manage_other_trainers_courses: false,
      can_view_department_performance: false,
      can_view_observed_performance: false,
    }),
  performance_views: z.array(z.coerce.string()).catch([]),
})

export type LmsAccess = z.output<typeof lmsAccessSchema>

/** Fetches capabilities and a fresh media ticket. Any failure means "no access", as in the Flutter apps. */
async function fetchLmsAccess(): Promise<LmsAccess | null> {
  const app = lmsApp()
  try {
    const access = lmsAccessSchema.parse(await apiRequest(`/api/lms/me?app=${app}`))
    try {
      const media = (await apiRequest(`/api/media-ticket?app=${app}`)) as {
        ticket?: unknown
      } | null
      setMediaTicket(media?.ticket != null ? String(media.ticket) : null)
    } catch {
      setMediaTicket(null)
    }
    return access
  } catch {
    setMediaTicket(null)
    return null
  }
}

/**
 * Polls `/api/lms/me` every 30 s and when the window regains focus.
 * Polling pauses while the tab is hidden. Returns null when access is unknown or denied.
 */
export function useLmsAccess() {
  const { person, token } = useSession<unknown>()
  const query = useQuery({
    queryKey: ['lms-access', lmsApp(), person, token],
    queryFn: fetchLmsAccess,
    enabled: person != null,
    refetchInterval: 30_000,
    refetchOnWindowFocus: 'always',
    staleTime: 0,
    retry: false,
  })
  return {
    access: query.data ?? null,
    isLoading: query.isPending && person != null,
    refetch: query.refetch,
  }
}
