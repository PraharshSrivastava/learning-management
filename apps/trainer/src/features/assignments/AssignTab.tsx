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
import { RuleView } from './RuleView'
import { Sidebar } from './Sidebar'
import { AssignmentWorkspace } from './workspace'
import './AssignStyles.css'

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

  // The menu refreshes the course lists and reports itself.
  const onCourseChanged = async (deleted: boolean) => {
    // Disable replaces the draft with the saved inactive rule, as Flutter applied the disable reply.
    // Skip it when the user moved to another course.
    if (!deleted && courseId != null && workspace.getState().loadedCourseId === courseId) {
      await workspace.reloadSavedRule(courseId)
    }
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
      <div className="assign-empty">
        <p className="font-medium text-[#19273e]">Select a course to assign</p>
        <p className="mt-1 text-sm text-[#5b6980]">
          Choose a course on the left to set its employees, deadline and observers.
        </p>
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

  return (
    <div className="assign-desk">
      <div className="assign-layout">
        <aside className="assign-sidebar" aria-label="Assignable course navigation">
          {sidebar}
        </aside>
        <main className="min-w-0" aria-label="Course assignment workspace">
          {rule}
        </main>
      </div>
    </div>
  )
}
