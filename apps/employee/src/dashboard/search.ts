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

/** Sidebar index for a view. `view=course` is the Flutter deep link and opens from Dashboard. */
export function navigationIndex(view: EmployeeView | undefined): number {
  switch (view) {
    case 'courses':
      return 1
    case 'notifications':
      return 2
    case 'performance':
    case 'team-performance':
      return 3
    default:
      return 0
  }
}

export const viewForIndex = (index: number): EmployeeView | undefined =>
  index === 1 ? 'courses' : index === 2 ? 'notifications' : index === 3 ? 'performance' : undefined

/** The open course. On the performance views `course_id` is the report course instead. */
export function openCourseId(search: EmployeeSearch): string | null {
  if (search.view === 'performance' || search.view === 'team-performance') return null
  return search.course_id ?? null
}
