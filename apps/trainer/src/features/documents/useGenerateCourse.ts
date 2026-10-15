import { ApiError, apiRequest, errorDetail, errorMessage } from '@lms/shared/api/client'
import { parseCourse } from '@lms/shared/models'
import { useToast } from '@lms/shared/ui/Toast'
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import { useBlockingOverlay } from '../../shell/overlay'
import { trainerKeys } from '../../shell/queryKeys'
import { useUpdateTrainerSearch } from '../../shell/search'

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
 * blocks the app while the outline is made, then selects the new course.
 */
export function useGenerateCourse() {
  const queryClient = useQueryClient()
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
        await queryClient.invalidateQueries({ queryKey: trainerKeys.courses })
        updateSearch({ course: course.courseId }, { replace: true })
      } catch (error) {
        // Flutter stored the error but never showed it. A toast tells the user why nothing opened.
        toast(generationError(error), { tone: 'error' })
      } finally {
        setRunning(false)
      }
    },
    [queryClient, running, toast, updateSearch],
  )
}
