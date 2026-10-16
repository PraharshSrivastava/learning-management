import '@lms/shared/theme.css'
import { configureApi, runtimeUrls } from '@lms/shared/api/client'
import { createQueryClient } from '@lms/shared/api/queryClient'
import { QueryClientProvider } from '@tanstack/react-query'
import {
  createRootRoute,
  createRoute,
  createRouter,
  Navigate,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { employeeSearchSchema } from './dashboard/search'

configureApi({
  app: 'employee',
  publicMount: __LMS_PUBLIC_MOUNT__,
  configuredApiBase: import.meta.env.VITE_API_BASE_URL,
})

const rootRoute = createRootRoute({ component: Outlet })
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  validateSearch: employeeSearchSchema,
  component: App,
})

const router = createRouter({
  routeTree: rootRoute.addChildren([indexRoute]),
  basepath: runtimeUrls().activeMount || '/',
  defaultNotFoundComponent: () => <Navigate to="/" replace />,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

const queryClient = createQueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
