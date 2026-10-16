import { configureApi } from '@lms/shared/api/client'
import { createQueryClient } from '@lms/shared/api/queryClient'
import { SessionProvider } from '@lms/shared/auth/session'
import { ToastProvider } from '@lms/shared/ui/Toast'
import { TooltipProvider } from '@lms/shared/ui/Tooltip'
import { QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from '@tanstack/react-router'
import { render } from '@testing-library/react'
import { vi } from 'vitest'
import { parseEmployee } from '../auth/employee'
import { EmployeeDashboard } from '../dashboard/EmployeeDashboard'
import { employeeSearchSchema } from '../dashboard/search'

type Handler = (url: URL, init: RequestInit | undefined) => unknown

/** Stubs fetch. The handler returns the JSON body, or a Response for errors. */
export function stubFetch(handler: Handler) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const body: unknown = await handler(new URL(String(input), 'http://localhost'), init)
    if (body instanceof Response) return body
    return new Response(JSON.stringify(body ?? null), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** Fake WebSocket that records each instance. */
export class FakeSocket {
  static instances: FakeSocket[] = []
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null
  closed = false
  constructor(public url: string) {
    FakeSocket.instances.push(this)
  }
  close() {
    this.closed = true
  }
  send(json: unknown) {
    this.onmessage?.({ data: JSON.stringify(json) })
  }
}

export function stubSocket() {
  FakeSocket.instances = []
  vi.stubGlobal('WebSocket', FakeSocket)
}

/** Renders the dashboard for a signed-in employee at the given URL. */
export function renderDashboard(url = '/') {
  configureApi({ app: 'employee', publicMount: '/lms/employee', configuredApiBase: undefined })
  const rootRoute = createRootRoute()
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    validateSearch: employeeSearchSchema,
    component: EmployeeDashboard,
  })
  const router = createRouter({
    routeTree: rootRoute.addChildren([indexRoute]),
    history: createMemoryHistory({ initialEntries: [url] }),
  })
  const client = createQueryClient()
  const view = render(
    <QueryClientProvider client={client}>
      <SessionProvider
        initialPerson={parseEmployee({ employee_id: 'e1', name: 'Priya Nair', department: 'Ops' })}
      >
        <TooltipProvider>
          <ToastProvider>
            <RouterProvider router={router} />
          </ToastProvider>
        </TooltipProvider>
      </SessionProvider>
    </QueryClientProvider>,
  )
  return { ...view, router, client }
}
