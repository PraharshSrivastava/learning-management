// Dart: frontend/lib/features/performance/report_access_guard.dart:1-18 and the empty access
// text in performance_report_portal.dart:139 (employee_frontend :139).
import * as RadixDialog from '@radix-ui/react-dialog'
import type { ReactNode } from 'react'
import { Button } from '../ui/Button'
import { useReport } from './context'
import type { ReportApp } from './state'
import { WINDOW_LAYER } from '../ui/layers'

/**
 * ReportAccessGuard. In Flutter the guard replaces the whole dialog route with an AlertDialog.
 * Here the caller owns the Radix Root, Portal and Overlay, and passes its RadixDialog.Content as
 * `children`. When the report context changed since the dialog opened, the guard renders an M3
 * AlertDialog content in its place, so the dialog or drawer shows the guard text.
 */
export function AccessGuard({
  expected,
  onClose,
  children,
}: {
  expected: string
  onClose: () => void
  children: ReactNode
}) {
  const { contextKey } = useReport()
  if (contextKey === expected) return children
  return (
    <RadixDialog.Content
      aria-describedby={undefined}
      className={`fixed top-1/2 left-1/2 ${WINDOW_LAYER} flex w-[calc(100%-80px)] max-w-[560px] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[28px] bg-[#e8e7ef] p-6 focus:outline-none`}
    >
      <RadixDialog.Title className="m-0 font-manrope text-2xl leading-[30px] font-extrabold tracking-normal text-text-black">
        Performance access changed
      </RadixDialog.Title>
      <p className="m-0 mt-4 text-sm text-[#44474e]">
        Close this detail and refresh your current view.
      </p>
      <div className="mt-6 flex justify-end">
        <Button variant="text" onClick={onClose}>
          Close
        </Button>
      </div>
    </RadixDialog.Content>
  )
}

/** The view row text when the person has no report view. */
export function NoAccess({ app }: { app: ReportApp }) {
  return (
    <p className="m-0">
      {app === 'trainer' ? 'Performance access unavailable' : 'Performance access is unavailable.'}
    </p>
  )
}
