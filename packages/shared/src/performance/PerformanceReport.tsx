// Dart: frontend/lib/features/performance/performance_report_portal.dart:31-165 (shell, header,
// _reportScope), :757-834 (_showAssignment, _showEmployee, _showCourse, _export), :944-986 (_ViewTabs).
import clsx from 'clsx'
import { useEffect, useState } from 'react'
import { Button } from '../ui/Button'
import { ProgressBar } from '../ui/ProgressBar'
import { Select } from '../ui/TextField'
import { AssignmentDetailDialog } from './AssignmentDetailDialog'
import { NoAccess } from './AccessGuard'
import { CoursesView } from './CourseBrowser'
import { CourseDetailDialog } from './CourseDetailDialog'
import { ReportProvider, useMainReport, useReport, type LinkedReportInput } from './context'
import { EmployeeDrawer } from './EmployeeDrawer'
import { EmployeesView } from './EmployeesView'
import { FilterCard } from './FilterCard'
import { dmyHm } from './format'
import { JourneysView } from './JourneyBrowser'
import { JourneyDetailDialog } from './JourneyDetailDialog'
import { Overview } from './Overview'
import { Box } from './primitives'
import type { ReportApp, ReportTab } from './state'
import { useCsvExport } from './useCsvExport'

const VIEW_LABELS: Record<string, string> = {
  all_courses: 'All Courses',
  my_courses: 'My Courses',
  my_departments: 'My Department(s)',
  observed: 'Observed Employees',
  combined: 'Combined',
}

const TABS: { view: ReportTab; label: string }[] = [
  { view: 0, label: 'Overview' },
  { view: 1, label: 'Courses' },
  { view: 3, label: 'Journeys' },
  { view: 2, label: 'Employees' },
]

/** PerformanceReportPortal. A linked report opens the Employees tab with its course and status. */
export function PerformanceReport({
  app,
  linkedReport,
}: {
  app: ReportApp
  linkedReport?: LinkedReportInput | null
}) {
  return (
    <ReportProvider app={app} linkedReport={linkedReport}>
      <Portal />
    </ReportProvider>
  )
}

function Portal() {
  const { state, dispatch } = useReport()
  const report = useMainReport()
  const { exportAssignments, exportEmployees } = useCsvExport()
  const [assignmentId, setAssignmentId] = useState<string | null>(null)
  const [courseId, setCourseId] = useState<string | null>(null)
  const [employeeId, setEmployeeId] = useState<string | null>(null)
  const generatedAt = report.overview?.generatedAt
  const journeysEnabled = report.options?.journeysEnabled === true
  // A journey link falls back to Overview when Learning Journeys are switched off.
  const journeysOff = report.options != null && !journeysEnabled
  useEffect(() => {
    if (journeysOff && state.view === 3) dispatch({ type: 'tab', view: 0 })
  }, [journeysOff, state.view, dispatch])

  return (
    <div className="min-h-full bg-[#f5f8fc] p-6">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2.5">
        <div>
          <h2 className="m-0 text-[27px] font-extrabold">Performance</h2>
          <p className="m-0 text-text-secondary">
            Learning outcomes and assignments that need attention.
          </p>
          {generatedAt && (
            <p className="m-0 text-xs text-text-secondary">Updated {dmyHm(generatedAt)}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            icon="refresh"
            disabled={report.isLoading}
            onClick={() => void report.refresh()}
          >
            Refresh
          </Button>
          {(state.view !== 2 || !state.employeeSummary) && (
            <Button
              variant="secondary"
              icon="download_outlined"
              onClick={() => void exportAssignments()}
            >
              Export assignments CSV
            </Button>
          )}
        </div>
      </div>
      <div className="h-4" />
      <ReportScope />
      <div className="h-4" />
      <ViewTabs
        selected={state.view}
        tabs={journeysEnabled ? TABS : TABS.filter((tab) => tab.view !== 3)}
        onSelect={(view) => dispatch({ type: 'tab', view })}
      />
      <div className="h-4" />
      <FilterCard options={report.options} />
      {report.isLoading && <ProgressBar className="mt-3" label="Loading performance report" />}
      {report.error != null && (
        <Box className="mt-3">
          <p className="m-0 text-accent-red">{report.error}</p>
        </Box>
      )}
      <div className="h-4" />
      {state.view === 0 && (
        <Overview
          overview={report.overview}
          isLoading={report.isLoading}
          onOpenAssignment={setAssignmentId}
        />
      )}
      {state.view === 1 && (
        <CoursesView
          courses={report.courses?.courses ?? []}
          isLoading={report.isLoading}
          onOpenCourse={setCourseId}
        />
      )}
      {state.view === 3 && journeysEnabled && (
        <JourneysView
          journeys={report.journeys?.journeys ?? []}
          isLoading={report.isLoading}
          onOpenJourney={(journeyId) => dispatch({ type: 'openJourney', journeyId })}
        />
      )}
      {state.view === 2 && (
        <EmployeesView
          assignments={report.assignments}
          onOpenAssignment={setAssignmentId}
          onOpenEmployee={setEmployeeId}
          onExportEmployees={exportEmployees}
        />
      )}
      <AssignmentDetailDialog assignmentId={assignmentId} onClose={() => setAssignmentId(null)} />
      <CourseDetailDialog courseId={courseId} onClose={() => setCourseId(null)} />
      <JourneyDetailDialog
        journeyId={journeysEnabled ? state.openJourneyId : null}
        onClose={() => dispatch({ type: 'openJourney', journeyId: null })}
      />
      <EmployeeDrawer
        employeeId={employeeId}
        onClose={() => setEmployeeId(null)}
        onOpenAssignment={(id) => {
          setEmployeeId(null)
          setAssignmentId(id)
        }}
      />
    </div>
  )
}

/** `_reportScope`: the view picker. The provider moves a view that is no longer allowed. */
function ReportScope() {
  const { app, views, state, dispatch } = useReport()
  if (views.length === 0) return <NoAccess app={app} />
  const value = views.includes(state.reportView) ? state.reportView : (views[0] ?? '')
  return (
    <div className="flex items-center gap-3">
      <span>View</span>
      <Select
        dense
        aria-label="Report view"
        className="w-[220px]"
        value={value}
        options={views.map((view) => ({ value: view, label: VIEW_LABELS[view] ?? view }))}
        onChange={(view) => dispatch({ type: 'reportView', view })}
      />
    </div>
  )
}

/** `_ViewTabs`: 106 px tabs with a 3 px primary blue underline on the selected one. */
function ViewTabs({
  selected,
  tabs,
  onSelect,
}: {
  selected: ReportTab
  tabs: { view: ReportTab; label: string }[]
  onSelect: (view: ReportTab) => void
}) {
  return (
    // Flutter centers the 44 px unselected tabs next to the 46 px selected one.
    <div role="tablist" aria-label="Report sections" className="flex items-center">
      {tabs.map(({ view, label }) => {
        const active = view === selected
        return (
          <button
            key={view}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onSelect(view)}
            className={clsx(
              'w-[106px] py-[11px] text-center hover:bg-black/4 focus-visible:outline-2 focus-visible:outline-brand-blue-light',
              active
                ? 'border-b-3 border-primary-blue font-extrabold text-primary-blue'
                : 'border-b border-light-gray font-semibold text-text-secondary',
            )}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
