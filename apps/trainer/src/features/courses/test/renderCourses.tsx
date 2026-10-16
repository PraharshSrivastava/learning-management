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
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { render } from '@testing-library/react'
import type { FunctionComponent } from 'react'
import { vi } from 'vitest'
import type { Trainer } from '../../../auth/trainer'
import { OverlayProvider } from '../../../shell/overlay'
import { trainerSearchSchema } from '../../../shell/search'

export const owner: Trainer = { trainerId: 'owner', name: 'Kiran Rao', status: 'active' }

/** GET /api/lms/me body. `library` grants the All Courses view. */
export const accessJson = ({ library = false } = {}) => ({
  employee_id: 'e1',
  trainer_id: 'owner',
  name: 'Kiran Rao',
  roles: ['trainer'],
  permissions_version: 1,
  capabilities: { can_author_courses: true, can_view_other_trainers_courses: library },
})

export const courseJson = (overrides: Record<string, unknown> = {}) => ({
  course_id: 'c1',
  trainer_id: 'owner',
  course_name: 'Compliance Essentials',
  course_description: 'Policies and duties.',
  course_objective: 'Report risks.',
  course_difficulty: 'Intermediate',
  language: 'English',
  target_audience: 'All staff',
  lifecycle_state: 'active',
  lifecycle_revision: 3,
  modules: [
    { module_number: 1, title: 'Basics', source_text: 'Basics text', num_questions: 2 },
    { module_number: 2, title: 'Reporting', source_text: 'Reporting text', num_questions: 3 },
  ],
  module_count: 2,
  images: [],
  ...overrides,
})

/** Renders `component` under a memory router at `url`, with a signed-in owner. */
export function renderCourses(
  component: FunctionComponent,
  { url = '/?tab=blueprint', person = owner }: { url?: string; person?: Trainer | null } = {},
) {
  configureApi({ app: 'trainer', publicMount: '/lms/trainer', configuredApiBase: undefined })
  const rootRoute = createRootRoute({ component: Outlet })
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    validateSearch: trainerSearchSchema,
    component,
  })
  const router = createRouter({
    routeTree: rootRoute.addChildren([indexRoute]),
    history: createMemoryHistory({ initialEntries: [url] }),
  })
  const client = createQueryClient()
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  const view = render(
    <QueryClientProvider client={client}>
      <SessionProvider initialPerson={person}>
        <TooltipProvider>
          <ToastProvider>
            <OverlayProvider>
              <RouterProvider router={router} />
            </OverlayProvider>
          </ToastProvider>
        </TooltipProvider>
      </SessionProvider>
    </QueryClientProvider>,
  )
  const search = () => router.state.location.search as Record<string, unknown>
  return { ...view, router, client, invalidate, search }
}
