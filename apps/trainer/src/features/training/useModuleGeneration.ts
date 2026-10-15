import { apiRequest } from '@lms/shared/api/client'
import { parseCourse } from '@lms/shared/models'
import { useToast } from '@lms/shared/ui/Toast'
import { useIsMutating, useMutation, useQueryClient } from '@tanstack/react-query'
import { useBlockingOverlay } from '../../shell/overlay'
import { trainerKeys } from '../../shell/queryKeys'
import { generationErrorMessage } from './trainingData'

const VIDEO_KEY = ['module-generation', 'video'] as const
const QUIZ_KEY = ['module-generation', 'quiz'] as const

/**
 * Compile a module video and generate the course quiz. Both endpoints run synchronously on the
 * backend, so there is no job to poll. The overlay stays up until the course data is reloaded.
 */
export function useModuleGeneration(courseId: string) {
  const queryClient = useQueryClient()
  const toast = useToast()

  const refreshCourses = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: trainerKeys.courses }),
      queryClient.invalidateQueries({ queryKey: trainerKeys.assignableCourses }),
    ])
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
    onSuccess: refreshCourses,
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
    onSuccess: refreshCourses,
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
