import { apiGet, apiRequest, errorMessage, websocketUrl } from '@lms/shared/api/client'
import { useSession } from '@lms/shared/auth/session'
import {
  parseEmployeeCourse,
  parseQuizSubmissionResult,
  quizSubmitToJson,
  videoWatchedToJson,
  type EmployeeCourse,
  type QuizSubmissionResult,
} from '@lms/shared/models'
import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { Employee } from '../auth/employee'
import { applyModuleProgress, type ModuleProgressPatch } from './progress'

export const employeeKeys = {
  courses: (employeeId: string | undefined) => ['employee', 'courses', employeeId ?? ''] as const,
}

const parseCourses = (json: unknown): EmployeeCourse[] =>
  Array.isArray(json) ? json.map(parseEmployeeCourse) : []

const modulePath = (courseId: string, moduleNumber: number) =>
  `/api/me/courses/${encodeURIComponent(courseId)}/modules/${moduleNumber}`

/** Flutter waits 5 s. The delay doubles after each failed connect, up to one minute. */
export const RECONNECT_BASE_MS = 5_000
export const RECONNECT_MAX_MS = 60_000

/**
 * Live course list: GET /api/me/courses, then the WebSocket replaces the list on each message.
 * The socket reconnects after close or error and closes on unmount or identity change.
 */
export function useEmployeeCourses() {
  const { person, token } = useSession<Employee>()
  const queryClient = useQueryClient()
  const employeeId = person?.employeeId
  // Counts socket lists. A GET that started before the latest list must not replace it.
  const socketLists = useRef(0)
  const query = useQuery({
    queryKey: employeeKeys.courses(employeeId),
    queryFn: async ({ queryKey }) => {
      const before = socketLists.current
      const courses = await apiGet('/api/me/courses', parseCourses)
      if (socketLists.current === before) return courses
      return queryClient.getQueryData<EmployeeCourse[]>(queryKey) ?? courses
    },
  })
  const [socketError, setSocketError] = useState<string | null>(null)

  useEffect(() => {
    const key = employeeKeys.courses(employeeId)
    let socket: WebSocket | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    let failures = 0
    let disposed = false

    const connect = () => {
      if (disposed) return
      socket = new WebSocket(websocketUrl('/api/me/courses/ws', { token: token ?? '' }))
      socket.onmessage = (event) => {
        failures = 0
        try {
          const courses = parseCourses(JSON.parse(String(event.data)))
          socketLists.current += 1
          queryClient.setQueryData(key, courses)
          setSocketError(null)
        } catch {
          setSocketError('Failed to parse learning data')
        }
      }
      socket.onerror = () => setSocketError('Live updates are unavailable. Retrying.')
      socket.onclose = () => {
        if (disposed) return
        const delay = Math.min(RECONNECT_BASE_MS * 2 ** failures, RECONNECT_MAX_MS)
        failures += 1
        timer = setTimeout(connect, delay)
      }
    }
    connect()
    return () => {
      disposed = true
      clearTimeout(timer)
      if (socket) {
        socket.onclose = null
        socket.close()
      }
    }
  }, [queryClient, employeeId, token])

  const courses = query.data ?? []
  const fetchError = query.error ? errorMessage(query.error) : null
  return {
    courses,
    isLoading: query.isPending,
    error: fetchError ?? socketError,
    refetch: query.refetch,
  }
}

function patchCourses(
  queryClient: QueryClient,
  key: readonly unknown[],
  courseId: string,
  moduleNumber: number,
  patch: ModuleProgressPatch,
) {
  queryClient.setQueryData<EmployeeCourse[]>(key, (courses) =>
    courses ? applyModuleProgress(courses, courseId, moduleNumber, patch) : courses,
  )
}

/** Progress writes for one course. Each write updates the cache first, then refetches. */
export function useModuleProgress() {
  const { person } = useSession<Employee>()
  const queryClient = useQueryClient()
  const employeeId = person?.employeeId

  const markVideoWatched = useCallback(
    async (courseId: string, moduleNumber: number, isCurrent: () => boolean = () => true) => {
      const key = employeeKeys.courses(employeeId)
      patchCourses(queryClient, key, courseId, moduleNumber, { videoWatched: true })
      try {
        await apiRequest(modulePath(courseId, moduleNumber), {
          method: 'PUT',
          json: videoWatchedToJson(),
        })
      } catch (error) {
        // Callers only save an unwatched video, so the cache goes back to unwatched. The quiz
        // submit then sends the save again.
        if (isCurrent())
          patchCourses(queryClient, key, courseId, moduleNumber, { videoWatched: false })
        throw error
      } finally {
        void queryClient.invalidateQueries({ queryKey: key })
      }
    },
    [queryClient, employeeId],
  )

  const submitQuiz = useCallback(
    async (
      courseId: string,
      moduleNumber: number,
      selectedAnswers: Record<number, string>,
      isCurrent: () => boolean = () => true,
    ): Promise<QuizSubmissionResult> => {
      const key = employeeKeys.courses(employeeId)
      const json = await apiRequest(modulePath(courseId, moduleNumber), {
        method: 'PUT',
        json: quizSubmitToJson(selectedAnswers),
      })
      let result: QuizSubmissionResult
      try {
        result = parseQuizSubmissionResult(json)
      } catch {
        throw new Error('Failed to submit quiz')
      }
      if (isCurrent())
        patchCourses(queryClient, key, courseId, moduleNumber, {
          quizPassed: result.passed,
          quizScore: result.score,
          selectedAnswers: result.passed ? { ...selectedAnswers } : null,
          ...(result.passed ? {} : { videoWatched: false }),
        })
      void queryClient.invalidateQueries({ queryKey: key })
      return result
    },
    [queryClient, employeeId],
  )

  return { markVideoWatched, submitQuiz }
}
