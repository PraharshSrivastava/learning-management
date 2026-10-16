// Report requests. Dart source: _uri, _get, exportCsv and exportEmployeeCsv in
// frontend/lib/state/trainer/performance_report_providers.dart:98-121 and :263-301.
import { ApiError, apiUrl, authHeaders } from '../api/client'
import type { Params, ReportApp } from './state'

export const reportBase = (app: ReportApp) =>
  app === 'trainer' ? '/api/trainer/performance' : '/api/employee/performance'

/** `_uri`: view and course_status first, then the params (the params can override them). */
export function reportUrl(
  app: ReportApp,
  path: string,
  base: { view: string; courseStatus: string },
  params: Params,
): string {
  const query = new URLSearchParams({
    view: base.view,
    course_status: base.courseStatus,
    ...params,
  })
  return apiUrl(`${reportBase(app)}/${path}?${query.toString()}`)
}

async function send(url: string): Promise<Response> {
  try {
    return await fetch(url, { headers: authHeaders(), credentials: 'same-origin' })
  } catch {
    throw new ApiError('Unable to reach the server. Check your connection and try again.', 0, null)
  }
}

/**
 * `_get`. A non-2xx answer throws "Unable to load performance data (<code>)".
 * A 401 or 403 also calls `onAccessDenied` (lmsAccessProvider.refresh).
 */
export async function reportGet(url: string, onAccessDenied: () => void): Promise<unknown> {
  const response = await send(url)
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) onAccessDenied()
    throw new ApiError(
      `Unable to load performance data (${response.status})`,
      response.status,
      null,
    )
  }
  const text = await response.text()
  return text ? (JSON.parse(text) as unknown) : {}
}

/** CSV export. `failure` is "Unable to export report" or "Unable to export employees". */
export async function reportText(url: string, failure: string): Promise<string> {
  const response = await send(url)
  if (!response.ok) {
    throw new ApiError(`${failure} (${response.status})`, response.status, null)
  }
  return response.text()
}

/** `_downloadCsv`: Blob plus anchor download. The object URL is revoked after 1 s. */
export function downloadCsv(csv: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
