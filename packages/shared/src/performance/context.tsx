// Report state and server data. Mirrors PerformanceReportNotifier, reportContextProvider and
// reportViewsProvider in frontend/lib/state/trainer/performance_report_providers.dart and
// frontend/lib/state/trainer/lms_access_providers.dart:41-43.
import { useQuery, type QueryKey } from '@tanstack/react-query'
import {
  createContext,
  use,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
} from 'react'
import { errorMessage } from '../api/client'
import { useLmsAccess } from '../auth/lmsAccess'
import { useSession } from '../auth/session'
import {
  parseAssignmentListReport,
  parseCourseListReport,
  parseJourneyListReport,
  parsePerformanceOverview,
  parsePerformanceReportOptions,
} from '../models/performance'
import { reportGet, reportText, reportUrl } from './api'
import {
  assignmentParams,
  initialReportState,
  reportContext,
  reportReducer,
  scopeParams,
  type Params,
  type ReportAction,
  type ReportApp,
  type ReportState,
} from './state'

export interface LinkedReportInput {
  courseId: string | null
  status: string | null
  /** Opens the Journeys tab with this journey's detail. */
  journeyId?: string | null
  /** Course availability to open with; a disabled journey is only in the history choices. */
  courseStatus?: string | null
}

export interface ReportContextValue {
  app: ReportApp
  state: ReportState
  dispatch: Dispatch<ReportAction>
  /** reportContextProvider. Dialogs keep the value from open time and compare it later. */
  contextKey: string
  /** True when the context key is still `expected` (Dart `isCurrent`). Stable. */
  isCurrent: (expected: string) => boolean
  /** performance_views from /api/lms/me. Empty means no access. */
  views: string[]
  accessLoading: boolean
  /** Root of every report query key: ['performance', app, contextKey]. */
  baseKey: readonly ['performance', ReportApp, string]
  /** GET <base>/<path>. 401 and 403 also refresh the access. */
  get: (path: string, params: Params) => Promise<unknown>
  /** GET <base>/<path> as text (CSV). `failure` is the error prefix. */
  getText: (path: string, params: Params, failure: string) => Promise<string>
}

const ReportContext = createContext<ReportContextValue | null>(null)

interface PersonIds {
  trainerId?: string
  employeeId?: string
}

export function ReportProvider({
  app,
  linkedReport,
  children,
}: {
  app: ReportApp
  linkedReport?: LinkedReportInput | null
  children: ReactNode
}) {
  const [state, dispatch] = useReducer(reportReducer, undefined, () =>
    initialReportState(app, linkedReport),
  )
  // openLinkedReport: a later link changes the open report and keeps its view and course status.
  // A new object is a new link, so callers keep the same object while the link does not change.
  const [appliedLink, setAppliedLink] = useState(linkedReport)
  if (linkedReport !== appliedLink) {
    setAppliedLink(linkedReport)
    if (linkedReport) {
      dispatch({
        type: 'openLinked',
        courseId: linkedReport.courseId,
        status: linkedReport.status,
        journeyId: linkedReport.journeyId ?? null,
        courseStatus: linkedReport.courseStatus ?? null,
      })
    }
  }
  const { person, token } = useSession<PersonIds>()
  const { access, isLoading: accessLoading, refetch } = useLmsAccess()
  const personId = (app === 'trainer' ? person?.trainerId : person?.employeeId) ?? null
  const contextKey = reportContext(
    personId,
    token,
    access?.permissions_version,
    access?.report_scope_version,
    state,
  )
  const views = useMemo(() => access?.performance_views ?? [], [access])

  const latest = useRef(contextKey)
  useLayoutEffect(() => {
    latest.current = contextKey
  }, [contextKey])
  const isCurrent = useCallback((expected: string) => latest.current === expected, [])

  // _reportScope: a view that is no longer allowed falls back to the first allowed view.
  const firstView = views[0]
  useEffect(() => {
    if (firstView != null && !views.includes(state.reportView)) {
      dispatch({ type: 'reportView', view: firstView })
    }
  }, [firstView, views, state.reportView])

  const { reportView } = state
  const { courseStatus } = state.filter
  const get = useCallback(
    (path: string, params: Params) =>
      reportGet(reportUrl(app, path, { view: reportView, courseStatus }, params), () => {
        void refetch()
      }),
    [app, reportView, courseStatus, refetch],
  )
  const getText = useCallback(
    (path: string, params: Params, failure: string) =>
      reportText(reportUrl(app, path, { view: reportView, courseStatus }, params), failure),
    [app, reportView, courseStatus],
  )

  const value = useMemo<ReportContextValue>(
    () => ({
      app,
      state,
      dispatch,
      contextKey,
      isCurrent,
      views,
      accessLoading,
      baseKey: ['performance', app, contextKey] as const,
      get,
      getText,
    }),
    [app, state, contextKey, isCurrent, views, accessLoading, get, getText],
  )
  return <ReportContext value={value}>{children}</ReportContext>
}

export function useReport(): ReportContextValue {
  const value = use(ReportContext)
  if (!value) throw new Error('useReport must be used inside ReportProvider')
  return value
}

/** True when the selected report view is allowed, so requests can run. */
export function useViewAllowed(): boolean {
  const { views, state } = useReport()
  return views.includes(state.reportView)
}

/**
 * One report request, keyed under ['performance', app, contextKey, path, params].
 * The previous answer stays on screen while a new one loads, but only inside the same context.
 */
export function useReportQuery<T>(
  path: string,
  params: Params,
  parse: (json: unknown) => T,
  enabled = true,
) {
  const { baseKey, get, contextKey } = useReport()
  const allowed = useViewAllowed()
  return useQuery({
    queryKey: [...baseKey, path, params] as QueryKey,
    queryFn: async () => parse(await get(path, params)),
    enabled: enabled && allowed,
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[2] === contextKey ? previous : undefined,
  })
}

/** The four requests of `refresh()`: options, overview, courses and assignments. */
export function useMainReport() {
  const { state } = useReport()
  const scope = scopeParams(state)
  const options = useReportQuery('options', {}, parsePerformanceReportOptions)
  const overview = useReportQuery('overview', scope, parsePerformanceOverview)
  const courses = useReportQuery('courses', scope, parseCourseListReport)
  const assignments = useReportQuery(
    'assignments',
    assignmentParams(state),
    parseAssignmentListReport,
  )
  // Journeys load only while their tab is open, because each learner's steps are worked out.
  const journeysShown = options.data?.journeysEnabled === true && state.view === 3
  const journeys = useReportQuery('journeys', scope, parseJourneyListReport, journeysShown)
  const all = [options, overview, courses, assignments, ...(journeysShown ? [journeys] : [])]
  const failed = all.find((query) => query.error != null)
  const refetchAll = all.map((query) => query.refetch)
  return {
    options: options.data,
    overview: overview.data,
    courses: courses.data,
    assignments: assignments.data,
    journeys: journeys.data,
    isLoading: all.some((query) => query.isFetching),
    error: failed ? errorMessage(failed.error) : null,
    refresh: () => Promise.all(refetchAll.map((refetch) => refetch())),
  }
}
