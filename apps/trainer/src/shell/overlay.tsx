import { LoadingOverlay } from '@lms/shared/ui/LoadingOverlay'
import { createContext, use, useEffect, useId, useState, type ReactNode } from 'react'

interface OverlayEntry {
  id: string
  message: string
  detail?: string | null
}

type Register = (entry: OverlayEntry | { id: string; message: null }) => void

const OverlayContext = createContext<Register | null>(null)

/**
 * Shows the blocking progress overlay for long backend jobs. The newest active job is on top.
 * The app behind it is inert, so keyboard and screen readers cannot reach it (Flutter ModalBarrier).
 */
export function OverlayProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<OverlayEntry[]>([])
  const [register] = useState<Register>(
    () => (entry: OverlayEntry | { id: string; message: null }) =>
      setEntries((current) => {
        const rest = current.filter((item) => item.id !== entry.id)
        return entry.message === null ? rest : [...rest, entry]
      }),
  )
  const top = entries.at(-1)
  return (
    <OverlayContext value={register}>
      <div inert={top != null} className="contents">
        {children}
      </div>
      {top && <LoadingOverlay message={top.message} detail={top.detail} />}
    </OverlayContext>
  )
}

/**
 * Blocks the app with the progress overlay while `active` is true. `detail` is live progress text
 * shown under the time expectation.
 */
export function useBlockingOverlay(
  active: boolean,
  message: string,
  detail: string | null = null,
): void {
  const register = use(OverlayContext)
  if (!register) throw new Error('useBlockingOverlay must be used inside OverlayProvider')
  const id = useId()
  useEffect(() => {
    register(active ? { id, message, detail } : { id, message: null })
  }, [register, id, active, message, detail])
  useEffect(() => () => register({ id, message: null }), [register, id])
}
