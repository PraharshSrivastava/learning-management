import { apiRequest } from '@lms/shared/api/client'
import { parseCourse, type Course } from '@lms/shared/models'
import { useToast } from '@lms/shared/ui/Toast'
import { useIsMutating, useMutation } from '@tanstack/react-query'
import { useBlockingOverlay } from '../../shell/overlay'
import { useRefreshCourses, useStoreCourse } from '../courses/courseQueries'
import { generationErrorMessage } from './trainingData'

const VIDEO_KEY = ['module-generation', 'video'] as const
const QUIZ_KEY = ['module-generation', 'quiz'] as const

/**
 * Compile a module video and generate the course quiz. Both endpoints run synchronously on the
 * backend, so there is no job to poll. The returned course is stored at once, as Flutter did, so a
 * failed reload does not show old content. The overlay stays up until the course data is reloaded.
 */
export function useModuleGeneration(courseId: string) {
  const toast = useToast()

  const storeCourse = useStoreCourse()
  const refreshCourses = useRefreshCourses()
  const onSuccess = async (course: Course) => {
    storeCourse(course)
    await refreshCourses()
  }

  const video = useMutation({
    mutationKey: VIDEO_KEY,
    mutationFn: async (moduleNumber: number) =>
      parseCourse(
        await apiRequest(
          `/api/courses/${encodeURIComponent(courseId)}/modules/${moduleNumber}/generate-video`,
          {
            method: 'POST',
          },
        ),
      ),
    onSuccess,
    onError: (error) =>
      toast(generationErrorMessage(error, 'Video generation failed.'), { tone: 'error' }),
  })

  const quiz = useMutation({
    mutationKey: QUIZ_KEY,
    mutationFn: async () =>
      parseCourse(
        await apiRequest(`/api/courses/${encodeURIComponent(courseId)}/generate-quiz`, {
          method: 'POST',
        }),
      ),
    onSuccess,
    onError: (error) =>
      toast(generationErrorMessage(error, 'Quiz generation failed.'), { tone: 'error' }),
  })

  // Count mutations of every mounted view, so a second view cannot start a parallel request.
  const videoRunning = useIsMutating({ mutationKey: VIDEO_KEY }) > 0
  const quizRunning = useIsMutating({ mutationKey: QUIZ_KEY }) > 0
  useBlockingOverlay(videoRunning, 'Generating video')
  useBlockingOverlay(quizRunning, 'Generating quizzes')
  const busy = videoRunning || quizRunning

  return {
    busy,
    compileVideo: (moduleNumber: number) => {
      if (!busy) video.mutate(moduleNumber)
    },
    generateQuiz: () => {
      if (!busy) quiz.mutate()
    },
  }
}
