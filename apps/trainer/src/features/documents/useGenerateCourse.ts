import { ApiError, apiRequest, errorDetail, errorMessage } from '@lms/shared/api/client'
import { parseCourse } from '@lms/shared/models'
import { useToast } from '@lms/shared/ui/Toast'
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import { useBlockingOverlay } from '../../shell/overlay'
import { trainerKeys } from '../../shell/queryKeys'
import { useUpdateTrainerSearch } from '../../shell/search'
import { useRefreshCourses, useStoreCourse } from '../courses/courseQueries'

/** Flutter `_responseErrorDetail`: server detail, else the fallback with the status code. */
export function generationError(error: unknown): string {
  if (error instanceof ApiError && error.status > 0) {
    return (
      errorDetail(error.body) ??
      `Course outline extraction failed. Server returned ${error.status}.`
    )
  }
  return errorMessage(error)
}

/**
 * Create Course (CourseGenerationNotifier.generateCourse): opens the Blueprint tab with no course,
 * blocks the app while the outline is made, then stores and selects the new course. The course
 * is stored at once, so an old or failed list reload cannot hide it.
 */
export function useGenerateCourse() {
  const queryClient = useQueryClient()
  const storeCourse = useStoreCourse()
  const refreshCourses = useRefreshCourses()
  const updateSearch = useUpdateTrainerSearch()
  const toast = useToast()
  const [running, setRunning] = useState(false)
  useBlockingOverlay(running, 'Creating your course outline')

  return useCallback(
    async (fileName: string) => {
      if (running) return
      setRunning(true)
      updateSearch({ tab: 'blueprint', course: undefined })
      try {
        const data = await apiRequest('/api/courses/generate', { json: { file_name: fileName } })
        const course = parseCourse(data)
        // A list request that started before the course existed would return the list without
        // it. Drop that request and reload, then store the response, as Flutter did.
        await queryClient.cancelQueries({ queryKey: trainerKeys.courses })
        await refreshCourses()
        storeCourse(course)
        updateSearch({ course: course.courseId }, { replace: true })
      } catch (error) {
        // Flutter stored the error but never showed it. A toast tells the user why nothing opened.
        toast(generationError(error), { tone: 'error' })
      } finally {
        setRunning(false)
      }
    },
    [queryClient, refreshCourses, running, storeCourse, toast, updateSearch],
  )
}
