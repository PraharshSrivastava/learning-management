import type { ReactNode } from 'react'
import { IconButton } from '../ui/Button'
import { Spinner } from '../ui/Spinner'
import { type HubSession, useHubSession } from './hubSession'

interface HubGateProps {
  title: string
  /** Rendered when the Hub session is valid or the backend runs in local dev mode. */
  children: (session: HubSession) => ReactNode
}

/** Blocks the app until the Hub session check passes. Matches `_HubGateScaffold` in both Flutter apps. */
export function HubGate({ title, children }: HubGateProps) {
  const session = useHubSession()
  if (session.data && (session.data.authenticated || session.data.localDevMode)) {
    return children(session.data)
  }
  const checking = session.isPending || session.isFetching
  const message = checking
    ? 'Checking Hub session...'
    : (session.error?.message ?? 'Open this application from the Hub dashboard.')
  return (
    <main className="page-gradient flex min-h-full items-center justify-center">
      <div className="flex w-full max-w-[520px] flex-col items-center p-6 text-center">
        <div className="flex size-11 items-center justify-center rounded-lg bg-[#102c77] font-bold text-white">
          PC
        </div>
        <h1 className="mt-5 font-manrope text-2xl font-extrabold leading-tight text-text-black">
          {title}
        </h1>
        <p className="mt-2 text-sm text-[#667085]" role={checking ? undefined : 'alert'}>
          {message}
        </p>
        {checking ? (
          <Spinner className="mt-6" />
        ) : (
          <IconButton
            className="mt-6"
            icon="refresh"
            label="Check again"
            tonal
            onClick={() => void session.refetch()}
          />
        )}
      </div>
    </main>
  )
}
