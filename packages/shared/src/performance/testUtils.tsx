// Test helpers for the report. Not imported by app code.
import { render } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { vi } from 'vitest'
import { configureApi } from '../api/client'
import { createQueryClient } from '../api/queryClient'
import { SessionProvider } from '../auth/session'
import { ToastProvider } from '../ui/Toast'
import { TooltipProvider } from '../ui/Tooltip'
import { ReportProvider, type LinkedReportInput } from './context'
import type { ReportApp } from './state'

type Handler = (url: URL, init: RequestInit | undefined) => unknown

/** Stubs fetch. The handler returns the JSON body, a string (CSV), or a Response. */
export function stubFetch(handler: Handler) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const body: unknown = await handler(new URL(String(input), 'http://localhost'), init)
    if (body instanceof Response) return body
    if (typeof body === 'string') return new Response(body, { status: 200 })
    return new Response(JSON.stringify(body ?? null), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** jsdom has no ResizeObserver. `width` is the width every observed element reports. */
export function stubResize(width = 1392) {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(private callback: ResizeObserverCallback) {}
      observe(target: Element) {
        this.callback(
          [{ target, contentRect: { width } as DOMRectReadOnly } as ResizeObserverEntry],
          this as unknown as ResizeObserver,
        )
      }
      unobserve() {}
      disconnect() {}
    },
  )
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
    width,
    height: 0,
    top: 0,
    left: 0,
    right: width,
    bottom: 0,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  } as DOMRect)
}

/** The /api/lms/me answer. `views` is performance_views. */
export const lmsMe = (views: string[], version = 1) => ({
  employee_id: 'e1',
  trainer_id: 't1',
  name: 'Kiran',
  roles: [],
  permissions_version: version,
  report_scope_version: 'v1',
  capabilities: {},
  performance_views: views,
})

/** Answers /api/lms/me and /api/media-ticket, then calls `handler` for the rest. */
export function stubReportApi(views: string[], handler: Handler) {
  return stubFetch((url, init) => {
    if (url.pathname.endsWith('/api/lms/me')) return lmsMe(views)
    if (url.pathname.endsWith('/api/media-ticket')) return { ticket: 'ticket' }
    return handler(url, init)
  })
}

/** Renders `ui` with the app providers and a signed-in person. */
export function renderReport(
  ui: ReactNode,
  {
    app = 'trainer',
    linkedReport,
    withReport = true,
  }: { app?: ReportApp; linkedReport?: LinkedReportInput | null; withReport?: boolean } = {},
) {
  configureApi({
    app,
    publicMount: app === 'trainer' ? '/lms/trainer' : '/lms/employee',
    configuredApiBase: undefined,
  })
  const person =
    app === 'trainer'
      ? { trainerId: 't1', name: 'Kiran', status: 'active' }
      : { employeeId: 'e1', name: 'Priya Nair', department: 'Ops' }
  const client = createQueryClient()
  const content = withReport ? (
    <ReportProvider app={app} linkedReport={linkedReport}>
      {ui}
    </ReportProvider>
  ) : (
    ui
  )
  const view = render(
    <QueryClientProvider client={client}>
      <SessionProvider initialPerson={person}>
        <TooltipProvider>
          <ToastProvider>{content}</ToastProvider>
        </TooltipProvider>
      </SessionProvider>
    </QueryClientProvider>,
  )
  return { ...view, client }
}
