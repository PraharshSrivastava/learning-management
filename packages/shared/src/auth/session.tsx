import { useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  use,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { identifyPerson, resetAnalytics } from '../analytics/posthog'
import { setAuthToken, setMediaTicket } from '../api/client'

/** The analytics distinct id and non-identifying traits of a person. Names and emails stay out. */
export interface AnalyticsPerson {
  id: string
  traits?: Record<string, string>
}

export interface Session<P> {
  person: P | null
  /** Bearer token from local dev login. Hub-session users have none. */
  token: string | null
  signIn: (person: P, token: string | null) => void
}

const SessionContext = createContext<Session<unknown> | null>(null)

export function SessionProvider<P>({
  initialPerson,
  analyticsPerson,
  children,
}: {
  initialPerson: P | null
  /** Keep it stable, such as a module function, so identify runs once per person. */
  analyticsPerson?: (person: P) => AnalyticsPerson
  children: ReactNode
}) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<{ person: P | null; token: string | null }>({
    person: initialPerson,
    token: null,
  })
  const signIn = useCallback(
    (person: P, token: string | null) => {
      setAuthToken(token)
      setMediaTicket(null)
      resetAnalytics()
      // Data from a previous identity must not show for the new one.
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== 'hub-session' })
      setState({ person, token })
    },
    [queryClient],
  )
  const identity = useMemo(
    () => (state.person && analyticsPerson ? analyticsPerson(state.person) : null),
    [state.person, analyticsPerson],
  )
  useEffect(() => {
    if (identity?.id) identifyPerson(identity.id, identity.traits)
  }, [identity])
  const value = useMemo(() => ({ ...state, signIn }), [state, signIn])
  return <SessionContext value={value as Session<unknown>}>{children}</SessionContext>
}

export function useSession<P>(): Session<P> {
  const session = use(SessionContext)
  if (!session) throw new Error('useSession must be used inside SessionProvider')
  return session as Session<P>
}
