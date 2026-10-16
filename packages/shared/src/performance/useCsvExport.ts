// Dart: frontend/lib/state/trainer/performance_report_providers.dart:263-301 (exportCsv,
// exportEmployeeCsv) and frontend/lib/features/performance/performance_report_portal.dart:620-621
// and :813-834 (onExport, _export, _downloadCsv).
import { useCallback } from 'react'
import { errorMessage } from '../api/client'
import { useToast } from '../ui/Toast'
import { downloadCsv } from './api'
import { useReport } from './context'
import { assignmentParams, scopeParams, without, type Params } from './state'

/**
 * The two CSV downloads of the report. A request that ends after the report context changed
 * gives no file, as the `serial != _request` check does in Dart. Errors show as a toast.
 */
export function useCsvExport() {
  const { state, contextKey, isCurrent, getText } = useReport()
  const toast = useToast()

  const download = useCallback(
    async (path: string, params: Params, failure: string, filename: string) => {
      const expected = contextKey
      try {
        const csv = await getText(path, params, failure)
        if (!isCurrent(expected)) throw new Error('Report access changed. Export again.')
        downloadCsv(csv, filename)
      } catch (error) {
        toast(errorMessage(error), { tone: 'error' })
      }
    },
    [contextKey, isCurrent, getText, toast],
  )

  const exportAssignments = useCallback(
    () =>
      download(
        'export',
        assignmentParams(state, false),
        'Unable to export report',
        'performance-assignments.csv',
      ),
    [download, state],
  )

  // `params` comes from the employee summary panel: search, attention, sort and descending.
  const exportEmployees = useCallback(
    (params: Params) => {
      const query: Params = { ...without(scopeParams(state), 'employee_id') }
      if (params.search !== undefined) query.search = params.search
      if (params.attention !== undefined) query.attention = params.attention
      query.sort = params.sort ?? 'employee'
      query.descending = params.descending ?? 'false'
      return download(
        'employees/export',
        query,
        'Unable to export employees',
        'performance-employees.csv',
      )
    },
    [download, state],
  )

  return { exportAssignments, exportEmployees }
}
