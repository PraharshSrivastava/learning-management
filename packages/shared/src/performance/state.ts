// Report state. Mirrors PerformanceReportNotifier in
// frontend/lib/state/trainer/performance_report_providers.dart.

export type ReportApp = 'trainer' | 'employee'
// 3 is Journeys. It comes last in the numbering so links to the other tabs keep working.
export type ReportTab = 0 | 1 | 2 | 3

export interface ReportFilter {
  courseStatus: string
  courseId: string | null
  employeeId: string | null
  department: string | null
  mailingList: string | null
  joinedLessThanDaysAgo: number | null
}

export const defaultFilter: ReportFilter = {
  courseStatus: 'active',
  courseId: null,
  employeeId: null,
  department: null,
  mailingList: null,
  joinedLessThanDaysAgo: null,
}

export interface ReportState {
  filter: ReportFilter
  reportView: string
  view: ReportTab
  status: string | null
  search: string
  sort: string
  descending: boolean
  page: number
  employeeSummary: boolean
  employeeResetVersion: number
  /** The journey whose detail is open in the Journeys tab. */
  openJourneyId: string | null
}

export const defaultReportView = (app: ReportApp) =>
  app === 'trainer' ? 'all_courses' : 'combined'

/** Assignment statuses the backend accepts. A deep link with another value is dropped. */
export const assignmentStatuses = [
  'assigned',
  'pending',
  'started',
  'completed',
  'overdue',
  'due_soon',
  'inactive',
  'repeated_failures',
] as const

export function sanitizeStatus(value: unknown): string | null {
  return typeof value === 'string' && (assignmentStatuses as readonly string[]).includes(value)
    ? value
    : null
}

const baseState = (reportView: string, employeeResetVersion: number): ReportState => ({
  filter: defaultFilter,
  reportView,
  view: 0,
  status: null,
  search: '',
  sort: 'deadline',
  descending: false,
  page: 1,
  employeeSummary: true,
  employeeResetVersion,
  openJourneyId: null,
})

export function initialReportState(
  app: ReportApp,
  linked?: { courseId: string | null; status: string | null; journeyId?: string | null } | null,
): ReportState {
  const state = baseState(defaultReportView(app), 0)
  const journeyId = linked?.journeyId?.trim() || null
  // A journey link opens the Journeys tab with that journey's detail.
  if (journeyId != null) return { ...state, view: 3, openJourneyId: journeyId }
  const courseId = linked?.courseId?.trim() || null
  const status = sanitizeStatus(linked?.status)
  // openLinkedReport runs only when the link has a course or a status.
  if (courseId != null || status != null) {
    return {
      ...state,
      filter: { ...state.filter, courseId },
      status,
      view: 2,
      employeeSummary: false,
      page: 1,
    }
  }
  return state
}

export type ReportAction =
  | { type: 'reportView'; view: string }
  | { type: 'courseStatus'; status: string }
  | { type: 'tab'; view: ReportTab }
  | { type: 'filter'; filter: ReportFilter }
  | { type: 'status'; status: string | null }
  | { type: 'search'; search: string }
  | { type: 'sort'; sort: string }
  | { type: 'toggleSort' }
  | { type: 'page'; page: number }
  | { type: 'clearFilters' }
  | { type: 'employeeSummary'; summary: boolean }
  | { type: 'viewEmployeesOf'; courseId: string }
  | {
      type: 'openLinked'
      courseId: string | null
      status: string | null
      journeyId?: string | null
    }
  | { type: 'openJourney'; journeyId: string | null }

export function reportReducer(state: ReportState, action: ReportAction): ReportState {
  switch (action.type) {
    case 'reportView':
      // setReportView starts from a fresh state.
      return baseState(action.view, state.employeeResetVersion + 1)
    case 'courseStatus':
      return {
        ...state,
        filter: { ...defaultFilter, courseStatus: action.status },
        page: 1,
        search: '',
        status: null,
        employeeResetVersion: state.employeeResetVersion + 1,
      }
    case 'tab':
      return { ...state, view: action.view }
    case 'filter':
      return { ...state, filter: action.filter, page: 1 }
    case 'status':
      return { ...state, status: action.status, view: 2, page: 1, employeeSummary: false }
    case 'search':
      return { ...state, search: action.search.trim(), page: 1 }
    case 'sort':
      return { ...state, sort: action.sort, page: 1 }
    case 'toggleSort':
      return { ...state, descending: !state.descending, page: 1 }
    case 'page':
      return { ...state, page: action.page }
    case 'clearFilters':
      return {
        ...state,
        filter: defaultFilter,
        status: null,
        search: '',
        employeeResetVersion: state.employeeResetVersion + 1,
        page: 1,
      }
    case 'employeeSummary':
      return { ...state, employeeSummary: action.summary }
    case 'viewEmployeesOf':
      // Course detail "View employees": setFilter, setEmployeeSummary(false), setView(2).
      return {
        ...state,
        filter: { ...state.filter, courseId: action.courseId },
        page: 1,
        employeeSummary: false,
        view: 2,
      }
    case 'openJourney':
      return { ...state, openJourneyId: action.journeyId }
    case 'openLinked':
      if (action.journeyId) {
        return {
          ...state,
          filter: { ...defaultFilter, courseStatus: state.filter.courseStatus },
          status: null,
          view: 3,
          openJourneyId: action.journeyId,
        }
      }
      // openLinkedReport keeps the course availability and replaces the other filters.
      return {
        ...state,
        filter: {
          ...defaultFilter,
          courseStatus: state.filter.courseStatus,
          courseId: action.courseId,
        },
        status: sanitizeStatus(action.status),
        view: 2,
        employeeSummary: false,
        page: 1,
      }
  }
}

export type Params = Record<string, string>

/** _scope: the report view and the filter values that are set. */
export function scopeParams(state: ReportState): Params {
  const { filter } = state
  const params: Params = { view: state.reportView }
  if (filter.courseId != null) params.course_id = filter.courseId
  if (filter.employeeId != null) params.employee_id = filter.employeeId
  if (filter.department != null) params.department = filter.department
  if (filter.mailingList != null) params.mailing_list = filter.mailingList
  if (filter.joinedLessThanDaysAgo != null) {
    params.joined_less_than_days_ago = String(filter.joinedLessThanDaysAgo)
  }
  return params
}

export const without = (params: Params, key: string): Params => {
  const { [key]: _removed, ...rest } = params
  return rest
}

export function assignmentParams(state: ReportState, withPage = true): Params {
  const params: Params = { ...scopeParams(state) }
  if (state.status != null) params.status = state.status
  if (state.search) params.search = state.search
  params.sort = state.sort
  params.descending = String(state.descending)
  if (withPage) params.page = String(state.page)
  return params
}

/** reportContextProvider: dialogs and pickers compare this key to detect an access change. */
export function reportContext(
  personId: string | null,
  token: string | null,
  permissionsVersion: unknown,
  scopeVersion: unknown,
  state: ReportState,
): string {
  const { filter } = state
  return JSON.stringify([
    personId,
    token,
    permissionsVersion ?? null,
    scopeVersion ?? null,
    state.reportView,
    filter.courseStatus,
    filter.courseId,
    filter.employeeId,
    filter.department,
    filter.mailingList,
  ])
}

export const activeFilterCount = (filter: ReportFilter) =>
  [
    filter.courseId,
    filter.employeeId,
    filter.department,
    filter.mailingList,
    filter.joinedLessThanDaysAgo,
  ].filter((value) => value != null).length
