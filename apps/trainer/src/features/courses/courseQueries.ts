import { ApiError, apiRequest, errorMessage } from '@lms/shared/api/client'
import { parseCourse, type Course } from '@lms/shared/models'
import { useIsMutating, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSyncExternalStore } from 'react'
import { useBlockingOverlay } from '../../shell/overlay'
import { trainerKeys } from '../../shell/queryKeys'
import { useTrainerSearch } from '../../shell/search'
import type { CourseFilter } from './courseLogic'

const coursePath = (courseId: string) => `/api/courses/${encodeURIComponent(courseId)}`

async function fetchCourses(): Promise<Course[]> {
  const data = await apiRequest('/api/courses')
  return Array.isArray(data) ? data.map((item) => parseCourse(item)) : []
}

/** Sidebar error text. Flutter showed "Server returned N" for any HTTP error. */
export function courseListError(error: unknown): string {
  if (error instanceof ApiError && error.status > 0) return `Server returned ${error.status}`
  return errorMessage(error)
}

/** The trainer's own courses (GET /api/courses). */
export function useCourseList() {
  return useQuery({ queryKey: trainerKeys.courses, queryFn: fetchCourses })
}

/** Full course with modules and images (GET /api/courses/{id}). */
export function useCourseDetail(courseId: string | undefined) {
  return useQuery({
    queryKey: trainerKeys.course(courseId ?? ''),
    queryFn: async () => parseCourse(await apiRequest(coursePath(courseId ?? ''))),
    enabled: courseId != null,
  })
}

/**
 * The selected course. It must be in the own list, so a deleted or foreign id selects nothing.
 * The detail adds modules and images. The newer copy wins for the summary fields, as
 * `_preserveLoadedDetail` did.
 */
export function useSelectedCourse() {
  const { course: selectedId } = useTrainerSearch()
  const list = useCourseList()
  const summary = selectedId ? list.data?.find((item) => item.courseId === selectedId) : undefined
  const detail = useCourseDetail(summary ? selectedId : undefined)
  let course: Course | null = summary ?? null
  if (summary && detail.data) {
    course =
      list.dataUpdatedAt > detail.dataUpdatedAt
        ? { ...detail.data, ...summaryFields(summary) }
        : { ...detail.data, moduleCount: summary.moduleCount }
  }
  return {
    course,
    detailError: summary && detail.isError ? courseListError(detail.error) : null,
  }
}

/** Fields that the list summary carries. Modules and images stay from the detail. */
function summaryFields(summary: Course): Partial<Course> {
  const { modules: _modules, images: _images, creatorName: _creator, ...fields } = summary
  return fields
}

// Availability filter. It is shared by the Blueprint and Courses tabs, as the Riverpod provider was.
let filter: CourseFilter = 'all'
const filterListeners = new Set<() => void>()

export function setCourseFilter(next: CourseFilter): void {
  filter = next
  for (const listener of filterListeners) listener()
}

export function useCourseFilter(): CourseFilter {
  return useSyncExternalStore(
    (listener) => {
      filterListeners.add(listener)
      return () => filterListeners.delete(listener)
    },
    () => filter,
  )
}

/** Puts a course from the server into the list and detail caches. */
export function useStoreCourse() {
  const queryClient = useQueryClient()
  return (course: Course) => {
    queryClient.setQueryData(trainerKeys.course(course.courseId), course)
    queryClient.setQueryData<Course[]>(trainerKeys.courses, (current) => {
      if (!current) return current
      const stored = { ...course, moduleCount: course.modules.length }
      const index = current.findIndex((item) => item.courseId === course.courseId)
      if (index < 0) return [stored, ...current]
      return current.map((item, position) => (position === index ? stored : item))
    })
  }
}

/** Reloads the own list, the open detail, and the Assign tab course list. */
export function useRefreshCourses() {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: trainerKeys.courses }),
      queryClient.invalidateQueries({ queryKey: trainerKeys.assignableCourses }),
    ])
}

const UPDATE_KEY = ['course-update'] as const

/** Flutter `_responseErrorDetail` for the blueprint update. */
export function updateErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status > 0) {
    return error.message.startsWith('Server returned ')
      ? `Failed to update course blueprint. Server returned ${error.status}.`
      : error.message
  }
  return errorMessage(error)
}

/** PUT /api/courses/{id}. Blocks the app with the save overlay while it runs. */
export function useUpdateCourse() {
  const storeCourse = useStoreCourse()
  const refreshCourses = useRefreshCourses()
  const mutation = useMutation({
    mutationKey: UPDATE_KEY,
    mutationFn: async ({ courseId, payload }: { courseId: string; payload: unknown }) =>
      parseCourse(await apiRequest(coursePath(courseId), { method: 'PUT', json: payload })),
    onSuccess: async (course) => {
      storeCourse(course)
      await refreshCourses()
    },
  })
  const saving = useIsMutating({ mutationKey: UPDATE_KEY }) > 0
  useBlockingOverlay(saving, 'Saving course blueprint modifications...')
  return mutation
}
