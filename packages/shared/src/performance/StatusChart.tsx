// Dart: none. The Flutter overview has no status chart (performance_report_portal.dart:331-578).
// The coordinator added it below the KPI cards. Counts come from the overview summary.
import { barX, defineChart } from '@tanstack/charts'
import { Chart } from '@tanstack/charts/react'
import { scaleBand } from '@tanstack/charts/scales/band'
import { scaleLinear } from '@tanstack/charts/scales/linear'
import { tooltip } from '@tanstack/charts/tooltip'
import { useMemo } from 'react'
import type { ReportSummary } from '../models/performance'
import { colors } from './format'
import { Box, Heading } from './primitives'

/** Status palette: segment order is the stack order, left to right. */
const segments = [
  { key: 'pending', label: 'Pending', color: colors.gray },
  { key: 'started', label: 'Started', color: colors.accentBlue },
  { key: 'completed', label: 'Completed', color: colors.accentGreen },
  { key: 'overdue', label: 'Overdue', color: colors.accentRed },
] as const

type StatusCounts = Pick<ReportSummary, 'assigned' | (typeof segments)[number]['key']>

/** One stacked horizontal bar of the assignment statuses, with a text legend. */
export function StatusChart({ summary }: { summary: StatusCounts }) {
  const rows = useMemo(
    () =>
      segments.map((segment) => ({
        group: 'Assignments',
        status: segment.label,
        count: summary[segment.key],
      })),
    [summary],
  )
  const definition = useMemo(() => {
    const total = rows.reduce((sum, row) => sum + row.count, 0)
    return defineChart({
      marks: [
        barX(rows, {
          x: 'count',
          y: 'group',
          color: 'status',
          // A white outline leaves a 2 px surface gap between the segments.
          stroke: '#ffffff',
          strokeWidth: 2,
          radius: 4,
        }),
      ],
      scales: {
        x: { scale: scaleLinear().domain([0, Math.max(total, 1)]), axis: false },
        y: { scale: () => scaleBand().padding(0), axis: false },
      },
      color: {
        domain: segments.map((segment) => segment.label),
        range: segments.map((segment) => segment.color),
      },
      guides: false,
      margin: 0,
      tooltip: {
        use: tooltip,
        format: (point) => `${point.datum.status}: ${point.datum.count}`,
      },
    })
  }, [rows])

  if (summary.assigned === 0) return null
  return (
    <Box>
      <Heading title="Assignment status" subtitle="Assignments in this scope by progress." />
      {/* The legend names every color and gives the exact count, so no value is color only. */}
      <ul className="m-0 mb-2 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-[12px]">
        {segments.map((segment) => (
          <li key={segment.key} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="size-2.5 rounded-[2px]"
              style={{ backgroundColor: segment.color }}
            />
            <span className="text-text-secondary">{segment.label}</span>
            <span className="font-bold">{summary[segment.key]}</span>
          </li>
        ))}
      </ul>
      <Chart definition={definition} height={24} ariaLabel="Assignment status" />
    </Box>
  )
}
