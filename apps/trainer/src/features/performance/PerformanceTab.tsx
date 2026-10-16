// Dart: frontend/lib/features/dashboard_page.dart:45-60 and :193 (portal mount and e-mail link),
// frontend/lib/features/performance/performance_report_portal.dart:31-45 (initState openLinkedReport),
// frontend/lib/features/courses/course_library_access.dart:101 (View Performance).
import { LazyPerformanceReport } from '@lms/shared/performance/LazyPerformanceReport'
import { useLayoutEffect, useState } from 'react'
import { takePendingLinkedReport } from '../../shell/linkedReport'
import { useTrainerSearch } from '../../shell/search'

/**
 * Trainer Performance tab. An e-mail link or "View Performance" leaves a pending link. The tab
 * takes it when it mounts (a useState initializer, so StrictMode does not lose it) and each time
 * the tab opens again, because TrainerShell keeps a visited tab mounted. The report then opens the
 * assignment list with the course and status filter.
 */
export function PerformanceTab() {
  const { tab } = useTrainerSearch()
  const [linked, setLinked] = useState(takePendingLinkedReport)

  // A layout effect, so the old report does not paint before the linked one.
  useLayoutEffect(() => {
    if (tab !== 'performance') return
    const next = takePendingLinkedReport()
    // The pending link is a module value, not React state, so the tab reads it after the switch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (next) setLinked(next)
  }, [tab])

  return <LazyPerformanceReport app="trainer" linkedReport={linked} />
}
