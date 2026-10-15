import { useSyncExternalStore } from 'react'

const QUERY = '(max-width: 899.98px)'

/** Flutter picks the mobile layout when the window is narrower than 900 px. */
export function useIsMobile(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const list = window.matchMedia(QUERY)
      list.addEventListener('change', notify)
      return () => list.removeEventListener('change', notify)
    },
    () => window.matchMedia(QUERY).matches,
    () => false,
  )
}
