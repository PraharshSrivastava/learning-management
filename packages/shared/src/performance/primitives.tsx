// Small shared pieces. Dart sources: _Box, _Heading, _StatusBadge in
// frontend/lib/features/performance/performance_report_portal.dart:1376-1405 and :1352-1374.
import clsx from 'clsx'
import type { ReactNode } from 'react'
import { badgeColor, mix } from './format'

/** `_Box`: AppTheme.cardDecoration(shadow: false) with padding 16. */
export function Box({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx('rounded-2xl border border-light-gray bg-white p-4', className)}>
      {children}
    </div>
  )
}

/** `_Heading`: 16 w800 title and 12 secondary subtitle, 12 below. */
export function Heading({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="mb-3">
      <h3 className="m-0 text-base font-extrabold">{title}</h3>
      <p className="m-0 text-xs text-text-secondary">{subtitle}</p>
    </div>
  )
}

/** Watchlist `_StatusBadge`: tinted pill, 11 w700. */
export function StatusBadge({ label }: { label: string }) {
  const color = badgeColor(label)
  return (
    <span
      className="inline-block max-w-full truncate rounded-xl px-[7px] py-1 text-[11px] font-bold"
      style={{ color, backgroundColor: mix(color, 0.11) }}
    >
      {label}
    </span>
  )
}
