import { useSyncExternalStore } from 'react'
import { hasMediaTicket, subscribeMediaTicket } from './client'

/** Re-renders when a media ticket appears or disappears, so protected URLs are rebuilt. */
export function useHasMediaTicket(): boolean {
  return useSyncExternalStore(subscribeMediaTicket, hasMediaTicket, () => false)
}
