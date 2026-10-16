// Trainer Assign tab (Flutter AssignmentPortal).
import { ApiError, apiRequest, errorMessage } from '@lms/shared/api/client'
import { useSession } from '@lms/shared/auth/session'
import { parseCourse, type Course } from '@lms/shared/models'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { Trainer } from '../../auth/trainer'
import { useBlockingOverlay } from '../../shell/overlay'
import { trainerKeys } from '../../shell/queryKeys'
import { useTrainerSearch, useUpdateTrainerSearch } from '../../shell/search'
import { fetchRequester, paths, type Requester } from './api'
import { useMediaQuery } from './controls'
import { RuleView } from './RuleView'
import { Sidebar } from './Sidebar'
import { AssignmentWorkspace } from './workspace'

const PUBLISH_MESSAGE = 'Publishing assignment...\nPublishing may take up to 2 minutes.'

async function fetchAssignableCourses(): Promise<Course[]> {
  const body = await apiRequest(paths.assignableCourses)
  return Array.isArray(body) ? body.map(parseCourse) : []
}

/** Flutter shows the HTTP status for a failed list request. */
const courseListError = (error: unknown) =>
  error instanceof ApiError && error.status > 0
    ? `Server returned ${error.status}`
    : errorMessage(error)

export function AssignTab({ request = fetchRequester }: { request?: Requester }) {
  const queryClient = useQueryClient()
  const { person, token } = useSession<Trainer>()
  const { course: selectedId } = useTrainerSearch()
  const updateSearch = useUpdateTrainerSearch()
  const isMobile = useMediaQuery('(max-width: 899px)')

  const courses = useQuery({
    queryKey: trainerKeys.assignableCourses,
    queryFn: fetchAssignableCourses,
    enabled: person != null,
  })

  const [workspace] = useState(
    () =>
      new AssignmentWorkspace({
        request,
        refreshCourses: async () => {
          void queryClient.invalidateQueries({ queryKey: trainerKeys.courses })
          try {
            await queryClient.fetchQuery({
              queryKey: trainerKeys.assignableCourses,
              queryFn: fetchAssignableCourses,
              staleTime: 0,
            })
            return true
          } catch {
            return false
          }
        },
        refreshPerformance: () =>
          queryClient.invalidateQueries({ queryKey: trainerKeys.performance }),
      }),
  )
  useEffect(() => () => workspace.dispose(), [workspace])

  // A new trainer or token drops all assignment state, as the Flutter auth listener did.
  const authKey = `${person?.trainerId}:${token}`
  const seenAuth = useRef(authKey)
  useEffect(() => {
    if (seenAuth.current === authKey) return
    seenAuth.current = authKey
    workspace.clearForAuthChange()
  }, [workspace, authKey])

  const list = courses.data ?? []
  const course = list.find((c) => c.courseId === selectedId) ?? null
  const courseId = course?.courseId ?? null
  useEffect(() => {
    if (courseId != null) void workspace.loadForCourse(courseId)
  }, [workspace, courseId, authKey])

  const isPublishing = useSyncExternalStore(
    workspace.subscribe,
    () => workspace.getState().isPublishing,
  )
  useBlockingOverlay(isPublishing, PUBLISH_MESSAGE)

  const onCourseChanged = async (deleted: boolean) => {
    await Promise.allSettled([
      queryClient.invalidateQueries({ queryKey: trainerKeys.courses }),
      queryClient.invalidateQueries({ queryKey: trainerKeys.assignableCourses }),
    ])
    // Disable replaces the draft with the saved inactive rule, as Flutter applied the disable reply.
    // Skip it when the user moved to another course.
    if (!deleted && courseId != null && workspace.getState().loadedCourseId === courseId) {
      await workspace.reloadSavedRule(courseId)
    }
    await queryClient.invalidateQueries({ queryKey: trainerKeys.performance })
  }

  const sidebar = (
    <Sidebar
      courses={list}
      isLoading={courses.isPending && person != null}
      error={courses.isError ? courseListError(courses.error) : null}
      selectedId={courseId}
      onSelect={(c) => updateSearch({ course: c.courseId })}
    />
  )
  const rule =
    course == null ? (
      <div className="flex h-full items-center justify-center text-[#667085]">
        Select a course to configure assignment rules.
      </div>
    ) : (
      <RuleView
        key={`${course.courseId}:${authKey}`}
        course={course}
        workspace={workspace}
        request={request}
        onCourseChanged={onCourseChanged}
      />
    )

  if (isMobile) {
    return (
      <div>
        <div className="h-[382px] p-4">{sidebar}</div>
        <div className="px-4">{rule}</div>
      </div>
    )
  }
  return (
    <div className="flex h-full">
      <div className="w-[380px] shrink-0 p-5">{sidebar}</div>
      <div className="flex min-w-0 flex-1 flex-col pt-5 pr-6 pb-6 pl-6 [&>*]:min-h-0 [&>*]:flex-1">
        {rule}
      </div>
    </div>
  )
}
