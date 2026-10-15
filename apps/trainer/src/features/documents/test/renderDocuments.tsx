import { configureApi } from '@lms/shared/api/client'
import { createQueryClient } from '@lms/shared/api/queryClient'
import { ToastProvider } from '@lms/shared/ui/Toast'
import { TooltipProvider } from '@lms/shared/ui/Tooltip'
import { QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { render } from '@testing-library/react'
import { vi } from 'vitest'
import { OverlayProvider } from '../../../shell/overlay'
import { trainerSearchSchema } from '../../../shell/search'
import { DocumentsTab } from '../DocumentsTab'

type Handler = (url: URL, init: RequestInit | undefined) => unknown

/** Stubs fetch. The handler returns the JSON body, or a Response for errors and binary data. */
export function stubFetch(handler: Handler) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const body = await handler(new URL(String(input), 'http://localhost'), init)
    if (body instanceof Response) return body
    return new Response(JSON.stringify(body ?? null), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** The JSON body of the first fetch call to `path`. */
export function requestBody(fetchMock: ReturnType<typeof stubFetch>, path: string): unknown {
  const call = fetchMock.mock.calls.find(([input]) => String(input).includes(path))
  return call ? JSON.parse(String(call[1]?.body)) : undefined
}

export const fileJson = (name: string, overrides: Record<string, unknown> = {}) => ({
  document_id: `doc-${name}`,
  file_name: `trainer_0001__${name}`,
  display_name: name,
  size: 1536,
  created_at: '2026-01-01T09:05:00',
  ...overrides,
})

/** XMLHttpRequest fake for uploadWithProgress. */
export class FakeXhr {
  static last: FakeXhr | null = null
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  status = 0
  responseText = ''
  url = ''
  body: unknown = null
  constructor() {
    FakeXhr.last = this
  }
  open(_method: string, url: string) {
    this.url = url
  }
  setRequestHeader() {}
  send(body: unknown) {
    this.body = body
  }
  abort() {
    this.onabort?.()
  }
  progress(loaded: number, total: number) {
    this.upload.onprogress?.({ lengthComputable: true, loaded, total } as ProgressEvent)
  }
  respond(status: number, body: unknown) {
    this.status = status
    this.responseText = JSON.stringify(body)
    this.onload?.()
  }
}

/** jsdom has no matchMedia, ResizeObserver, or object URLs. */
export function stubBrowser({ mobile = false } = {}) {
  vi.stubGlobal(
    'matchMedia',
    (query: string) =>
      ({
        matches: mobile && query.includes('max-width'),
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  )
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
  FakeXhr.last = null
  vi.stubGlobal('XMLHttpRequest', FakeXhr)
  let next = 0
  URL.createObjectURL = vi.fn(() => `blob:pdf-${++next}`)
  URL.revokeObjectURL = vi.fn()
}

/** Renders the Documents tab under a memory router at `url`. */
export function renderDocuments(url = '/?tab=documents') {
  configureApi({ app: 'trainer', publicMount: '/lms/trainer', configuredApiBase: undefined })
  const rootRoute = createRootRoute({ component: Outlet })
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    validateSearch: trainerSearchSchema,
    component: DocumentsTab,
  })
  const router = createRouter({
    routeTree: rootRoute.addChildren([indexRoute]),
    history: createMemoryHistory({ initialEntries: [url] }),
  })
  const client = createQueryClient()
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  const view = render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <ToastProvider>
          <OverlayProvider>
            <RouterProvider router={router} />
          </OverlayProvider>
        </ToastProvider>
      </TooltipProvider>
    </QueryClientProvider>,
  )
  const search = () => router.state.location.search as Record<string, unknown>
  return { ...view, router, client, invalidate, search }
}
