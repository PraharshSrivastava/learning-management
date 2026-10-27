import { apiRequest } from '@lms/shared/api/client'
import { parseCourse, parseGenerationJob, type Course } from '@lms/shared/models'
import { useToast } from '@lms/shared/ui/Toast'
import { useIsMutating, useMutation, useMutationState, useQueryClient } from '@tanstack/react-query'
import { useBlockingOverlay } from '../../shell/overlay'
import { trainerKeys } from '../../shell/queryKeys'
import { useUpdateTrainerSearch, type TrainerTab } from '../../shell/search'
import { generationErrorMessage } from '../training/trainingData'
import { moduleVideoProgress, useVideoGenerationMode } from '../training/videoMode'
import { isCourseFullyGenerated } from './courseLogic'
import { useCourseDetail, useStoreCourse } from './courseQueries'

const FULL_GENERATION_KEY = ['full-course-generation'] as const
const POLL_INTERVAL_MS = 4000

/** A failure that already has its user text. `tab` is where the user goes after it. */
class GenerationFailure extends Error {
  constructor(
    message: string,
    readonly tab: TrainerTab | null,
  ) {
    super(message)
  }
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Full course generation (FullCourseGenerationNotifier). A new run starts a backend job and polls
 * it every 4 s. A resume from a later checkpoint does the same, so a long video stage never holds
 * one HTTP request open; a blueprint checkpoint resumes in one request, because it re-extracts the
 * document. The overlay stays up while either runs, also when the user opens another tab; see
 * useFullCourseGenerationOverlay.
 */
export function useFullCourseGeneration() {
  const queryClient = useQueryClient()
  const storeCourse = useStoreCourse()
  const updateSearch = useUpdateTrainerSearch()
  const toast = useToast()

  const refreshCourse = async (courseId: string): Promise<boolean> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: trainerKeys.courses }),
      queryClient.invalidateQueries({ queryKey: trainerKeys.assignableCourses }),
    ])
    return queryClient.getQueryState(trainerKeys.course(courseId))?.status === 'success'
  }

  const runJob = async (courseId: string, resuming = false): Promise<TrainerTab> => {
    let jobId: string
    try {
      const job = parseGenerationJob(
        await apiRequest(
          `/api/courses/${encodeURIComponent(courseId)}/generation-jobs${resuming ? '/continue' : ''}`,
          { method: 'POST' },
        ),
      )
      jobId = job.id
    } catch (error) {
      const found = await refreshCourse(courseId)
      throw new GenerationFailure(
        generationErrorMessage(
          error,
          resuming ? 'Could not continue generation.' : 'Full course generation failed.',
        ),
        found ? 'blueprint' : null,
      )
    }
    for (;;) {
      await wait(POLL_INTERVAL_MS)
      let job
      try {
        job = parseGenerationJob(
          await apiRequest(`/api/generation-jobs/${encodeURIComponent(jobId)}`),
        )
      } catch (error) {
        await refreshCourse(courseId)
        throw new GenerationFailure(
          generationErrorMessage(error, 'Could not check generation progress.'),
          null,
        )
      }
      await refreshCourse(courseId)
      if (job.status === 'completed') return 'courses'
      if (job.status === 'failed') {
        throw new GenerationFailure(job.error ?? 'Full course generation failed.', 'blueprint')
      }
    }
  }

  const checkpointOf = (courseId: string): string => {
    const course =
      queryClient.getQueryData<Course>(trainerKeys.course(courseId)) ??
      queryClient
        .getQueryData<Course[]>(trainerKeys.courses)
        ?.find((item) => item.courseId === courseId)
    return course?.failedCheckpoint || course?.currentCheckpoint || ''
  }

  const resume = async (courseId: string): Promise<TrainerTab> => {
    const checkpoint = checkpointOf(courseId)
    if (checkpoint && checkpoint !== 'blueprint') return runJob(courseId, true)
    try {
      const course = parseCourse(
        await apiRequest(`/api/courses/${encodeURIComponent(courseId)}/continue-generation`, {
          method: 'POST',
        }),
      )
      storeCourse(course)
      void queryClient.invalidateQueries({ queryKey: trainerKeys.assignableCourses })
      return isCourseFullyGenerated(course) ? 'courses' : 'blueprint'
    } catch (error) {
      const found = await refreshCourse(courseId)
      throw new GenerationFailure(
        generationErrorMessage(error, 'Could not continue generation.'),
        found ? 'blueprint' : null,
      )
    }
  }

  const mutation = useMutation({
    mutationKey: FULL_GENERATION_KEY,
    mutationFn: async ({
      courseId,
      fromCheckpoint,
    }: {
      courseId: string
      fromCheckpoint: boolean
    }) => (fromCheckpoint ? resume(courseId) : runJob(courseId)),
    onSuccess: (tab, { courseId }) => updateSearch({ tab, course: courseId }),
    onError: (error, { courseId }) => {
      // Flutter kept this error in state but never showed it. A toast tells the user why it stopped.
      toast(error.message, { tone: 'error' })
      if (error instanceof GenerationFailure && error.tab) {
        updateSearch({ tab: error.tab, course: courseId })
      }
    },
  })

  const running = useIsMutating({ mutationKey: FULL_GENERATION_KEY }) > 0

  return {
    running,
    start: (courseId: string, fromCheckpoint: boolean) => {
      if (!running) mutation.mutate({ courseId, fromCheckpoint })
    },
  }
}

/**
 * Shows the blocking overlay from shell level, so it stays up across a tab or course change that
 * unmounts BlueprintEditor while the job keeps running (the Flutter root Stack never let go of it).
 */
export function useFullCourseGenerationOverlay(): void {
  const running = useIsMutating({ mutationKey: FULL_GENERATION_KEY }) > 0
  const external = useVideoGenerationMode() === 'external'
  const courseId = useMutationState({
    filters: { mutationKey: FULL_GENERATION_KEY, status: 'pending' },
    select: (mutation) => (mutation.state.variables as { courseId: string } | undefined)?.courseId,
  }).at(-1)
  // The job polling reloads this course, so module video progress updates under the overlay.
  const course = useCourseDetail(external && running ? courseId : undefined).data
  useBlockingOverlay(
    running,
    external ? 'Generating course content with module videos' : 'Generating course content',
    external ? moduleVideoProgress(course) : null,
  )
}
