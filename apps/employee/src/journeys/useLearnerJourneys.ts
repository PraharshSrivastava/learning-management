import { errorMessage } from '@lms/shared/api/client'
import { useSession } from '@lms/shared/auth/session'
import type { EmployeeCourse } from '@lms/shared/models'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import type { Employee } from '../auth/employee'
import { fetchMyJourneys } from './api'

/**
 * The learner's journeys. The query key follows the course list, so a passed course (which can
 * unlock the next journey step) refreshes the roadmap without a reload.
 */
export function useLearnerJourneys(courses: EmployeeCourse[]) {
  const { person } = useSession<Employee>()
  const signature = courses
    .map(
      (course) => `${course.courseId}:${course.assignmentStatus ?? ''}:${course.completedAt ?? ''}`,
    )
    .join('|')
  const query = useQuery({
    queryKey: ['employee', 'journeys', person?.employeeId ?? '', signature],
    queryFn: fetchMyJourneys,
    placeholderData: keepPreviousData,
  })
  return {
    enabled: query.data?.enabled === true,
    journeys: query.data?.journeys ?? [],
    isLoading: query.isPending,
    error: query.error ? errorMessage(query.error) : null,
  }
}
