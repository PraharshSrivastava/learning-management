import { useQuery } from '@tanstack/react-query'
import { ApiError, apiRequest, lmsApp } from '../api/client'

export const OPEN_FROM_HUB = 'Open this application from the Hub dashboard.'

export interface HubSession {
  authenticated: boolean
  localDevMode: boolean
  email: string | null
  /** The `trainer` or `employee` record for the signed-in Hub user, if any. */
  person: unknown
}

export const hubSessionKey = () => ['hub-session', lmsApp()] as const

export async function fetchHubSession(): Promise<HubSession> {
  const app = lmsApp()
  let data: unknown
  try {
    data = await apiRequest(`/api/hub/session/${app}`)
  } catch (error) {
    // A 5xx is a server fault, not a missing session. Say so instead of sending the user to the Hub.
    if (error instanceof ApiError && error.status !== 0 && error.status < 500)
      throw new Error(OPEN_FROM_HUB, { cause: error })
    throw new Error('The LMS server is not available. Try again in a moment.', { cause: error })
  }
  const body = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>
  const authenticated = body.authenticated === true
  return {
    authenticated,
    localDevMode: body.local_dev_mode === true,
    email: authenticated && body.email != null ? String(body.email) : null,
    person: authenticated ? (body[app] ?? null) : null,
  }
}

export function useHubSession() {
  return useQuery({
    queryKey: hubSessionKey(),
    queryFn: fetchHubSession,
    retry: false,
    staleTime: Infinity,
  })
}
