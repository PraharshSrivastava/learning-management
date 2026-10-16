import { lazy, Suspense, type ComponentProps } from 'react'
import { ProgressBar } from '../ui/ProgressBar'

// The report and its chart library load only when a user opens Performance.
const PerformanceReport = lazy(() =>
  import('./PerformanceReport').then((module) => ({ default: module.PerformanceReport })),
)

export function LazyPerformanceReport(props: ComponentProps<typeof PerformanceReport>) {
  return (
    <Suspense fallback={<ProgressBar label="Loading performance report" />}>
      <PerformanceReport {...props} />
    </Suspense>
  )
}
