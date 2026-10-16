// Dart: frontend/lib/features/performance/report_filter_row.dart:15-53 (employee_frontend is the same).
import { useRef, type ReactNode } from 'react'
import { useElementWidth } from './useElementWidth'

/** Minimum width of one filter. Flutter also scales it up with large text. */
const minimumFilterWidth = 210

/**
 * Five filters stay together; narrow views scroll rather than wrapping. `children` gets the
 * width of one filter: max(210, (row width - 48) / 5), so five filters and four 12 px gaps fill
 * the row.
 */
export function ReportFilterRow({ children }: { children: (width: number) => ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const maxWidth = useElementWidth(ref)
  const width = Math.max(minimumFilterWidth, (maxWidth - 48) / 5)
  return (
    <div ref={ref} className="overflow-x-auto pb-2">
      <div className="flex w-max items-start gap-3">{children(width)}</div>
    </div>
  )
}
