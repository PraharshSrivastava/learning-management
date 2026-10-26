import { useNavigate, useSearch } from '@tanstack/react-router'
import { useCallback } from 'react'
import { z } from 'zod'

/**
 * Dashboard state in the URL, so reload and the back button keep the open page.
 * `view=course&course_id=...` and `view=team-performance&course_id=...&status=...` are the
 * Flutter deep links and keep their names.
 */
export const EMPLOYEE_VIEWS = [
  'courses',
  'journeys',
  'notifications',
  'performance',
  'course',
  'team-performance',
] as const
export type EmployeeView = (typeof EMPLOYEE_VIEWS)[number]

// The router parses `?course_id=123` as a number, so values are coerced back to strings.
const optionalText = z
  .preprocess(
    (value) => (value == null ? undefined : String(value)),
    z.string().trim().min(1).optional(),
  )
  .catch(undefined)

export const employeeSearchSchema = z.object({
  view: z.enum(EMPLOYEE_VIEWS).optional().catch(undefined),
  course_id: optionalText,
  status: optionalText,
  /** Learning journey open on the journeys page. */
  journey_id: optionalText,
})

export type EmployeeSearch = z.output<typeof employeeSearchSchema>

export function useEmployeeSearch(): EmployeeSearch {
  return useSearch({ from: '/' })
}

/** Replaces the dashboard search params. */
export function useSetEmployeeSearch() {
  const navigate = useNavigate()
  return useCallback(
    (search: EmployeeSearch, options: { replace?: boolean } = {}) =>
      void navigate({ to: '/', search, replace: options.replace }),
    [navigate],
  )
}

/** Sidebar entries, in order. Learning Journeys and Performance appear only when available. */
export type Destination = 'dashboard' | 'courses' | 'journeys' | 'notifications' | 'performance'

export function destinationsFor(options: {
  journeys: boolean
  performance: boolean
}): Destination[] {
  return [
    'dashboard',
    'courses',
    ...(options.journeys ? (['journeys'] as const) : []),
    'notifications',
    ...(options.performance ? (['performance'] as const) : []),
  ]
}

/** Sidebar entry for a view. `view=course` is the Flutter deep link and opens from Dashboard. */
export function destinationForView(view: EmployeeView | undefined): Destination {
  switch (view) {
    case 'courses':
    case 'journeys':
    case 'notifications':
    case 'performance':
      return view
    case 'team-performance':
      return 'performance'
    default:
      return 'dashboard'
  }
}

export const viewForDestination = (destination: Destination): EmployeeView | undefined =>
  destination === 'dashboard' ? undefined : destination

/** The open course. On the performance views `course_id` is the report course instead. */
export function openCourseId(search: EmployeeSearch): string | null {
  if (search.view === 'performance' || search.view === 'team-performance') return null
  return search.course_id ?? null
}
