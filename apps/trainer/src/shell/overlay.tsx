import { LoadingOverlay } from '@lms/shared/ui/LoadingOverlay'
import { createContext, use, useEffect, useId, useState, type ReactNode } from 'react'

interface OverlayEntry {
  id: string
  message: string
}

type Register = (entry: OverlayEntry | { id: string; message: null }) => void

const OverlayContext = createContext<Register | null>(null)

/** Shows the blocking progress overlay for long backend jobs. The newest active job is on top. */
export function OverlayProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<OverlayEntry[]>([])
  const [register] = useState<Register>(
    () => (entry: OverlayEntry | { id: string; message: null }) =>
      setEntries((current) => {
        const rest = current.filter((item) => item.id !== entry.id)
        return entry.message === null ? rest : [...rest, { id: entry.id, message: entry.message }]
      }),
  )
  const top = entries.at(-1)
  return (
    <OverlayContext value={register}>
      {children}
      {top && <LoadingOverlay message={top.message} />}
    </OverlayContext>
  )
}

/** Blocks the app with the progress overlay while `active` is true. */
export function useBlockingOverlay(active: boolean, message: string): void {
  const register = use(OverlayContext)
  if (!register) throw new Error('useBlockingOverlay must be used inside OverlayProvider')
  const id = useId()
  useEffect(() => {
    register({ id, message: active ? message : null })
    return () => register({ id, message: null })
  }, [register, id, active, message])
}
