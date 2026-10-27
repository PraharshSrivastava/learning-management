import { ApiError, apiRequest } from '@lms/shared/api/client'
import { parseCourse, parseGenerationJob, type Course } from '@lms/shared/models'
import { useToast } from '@lms/shared/ui/Toast'
import { useIsMutating, useMutation, useMutationState, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useBlockingOverlay } from '../../shell/overlay'
import { trainerKeys } from '../../shell/queryKeys'
import { useRefreshCourses, useStoreCourse } from '../courses/courseQueries'
import { generationErrorMessage } from './trainingData'

const VIDEO_KEY = ['module-generation', 'video'] as const
const QUIZ_KEY = ['module-generation', 'quiz'] as const
const POLL_INTERVAL_MS = 5000
/** Slower refresh while a video started elsewhere (another tab, a reload) is still running. */
const BACKGROUND_REFRESH_MS = 10000

interface VideoRequest {
  courseId: string
  moduleNumber: number
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Module video and course quiz generation.
 *
 * A module video runs as a background job (the Video Generator can take many minutes), so the
 * page stays usable: the job is polled and the course reloaded, which shows the module's progress.
 * The quiz endpoint is synchronous and keeps the blocking overlay. Its returned course is stored at
 * once, as Flutter did, so a failed reload does not show old content.
 *
 * `videoActive` is true when the server reports a module video in progress, so a run started in
 * another tab or before a reload keeps refreshing and blocks a second start.
 */
export function useModuleGeneration(courseId: string, { videoActive = false } = {}) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const storeCourse = useStoreCourse()
  const refreshCourses = useRefreshCourses()

  const moduleError = (moduleNumber: number): string | null =>
    queryClient
      .getQueryData<Course>(trainerKeys.course(courseId))
      ?.modules.find((module) => module.moduleNumber === moduleNumber)?.videoService?.error ?? null

  const video = useMutation({
    mutationKey: VIDEO_KEY,
    mutationFn: async ({ courseId: id, moduleNumber }: VideoRequest) => {
      const job = parseGenerationJob(
        await apiRequest(
          `/api/courses/${encodeURIComponent(id)}/modules/${moduleNumber}/video-jobs`,
          { method: 'POST' },
        ),
      )
      for (;;) {
        await wait(POLL_INTERVAL_MS)
        const current = parseGenerationJob(
          await apiRequest(`/api/generation-jobs/${encodeURIComponent(job.id)}`),
        )
        await refreshCourses()
        if (current.status === 'completed') return
        if (current.status === 'failed') {
          // The worker reports only its exit code; the module keeps the real cause.
          throw new Error(moduleError(moduleNumber) ?? current.error ?? 'Video generation failed.')
        }
      }
    },
    onError: async (error) => {
      toast(
        error instanceof ApiError
          ? generationErrorMessage(error, 'Video generation failed.')
          : error.message,
        { tone: 'error' },
      )
      await refreshCourses()
    },
  })

  const quiz = useMutation({
    mutationKey: QUIZ_KEY,
    mutationFn: async () =>
      parseCourse(
        await apiRequest(`/api/courses/${encodeURIComponent(courseId)}/generate-quiz`, {
          method: 'POST',
        }),
      ),
    onSuccess: async (course: Course) => {
      storeCourse(course)
      await refreshCourses()
    },
    onError: (error) =>
      toast(generationErrorMessage(error, 'Quiz generation failed.'), { tone: 'error' }),
  })

  // Read mutations of every mounted view, so a second view cannot start a parallel request.
  const videoModules = useMutationState({
    filters: { mutationKey: VIDEO_KEY, status: 'pending' },
    select: (mutation) => mutation.state.variables as VideoRequest | undefined,
  })
    .filter((request): request is VideoRequest => request?.courseId === courseId)
    .map((request) => request.moduleNumber)
  const quizRunning = useIsMutating({ mutationKey: QUIZ_KEY }) > 0
  useBlockingOverlay(quizRunning, 'Generating quizzes')

  const polling = videoModules.length > 0
  useEffect(() => {
    if (!videoActive || polling) return
    const timer = setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: trainerKeys.courses })
    }, BACKGROUND_REFRESH_MS)
    return () => clearInterval(timer)
  }, [videoActive, polling, queryClient])

  const videoBusy = polling || videoActive
  return {
    /** Quiz generation is running. */
    busy: quizRunning,
    /** A video for this course is being generated, so another must not start. */
    videoBusy,
    /** Module numbers whose video job this browser is polling. */
    videoModules,
    compileVideo: (moduleNumber: number) => {
      if (!videoBusy && !quizRunning) video.mutate({ courseId, moduleNumber })
    },
    generateQuiz: () => {
      if (!quizRunning) quiz.mutate()
    },
  }
}
