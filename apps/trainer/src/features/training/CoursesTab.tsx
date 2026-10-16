import { CourseDetailPending, isDetailPending } from '../courses/CourseDetailsView'
import { CourseLibraryAccess } from '../courses/CourseLibraryAccess'
import { CoursesSidebar } from '../courses/CoursesSidebar'
import { EmptyCourseView } from '../courses/EmptyCourseView'
import { useSelectedCourse } from '../courses/courseQueries'
import { TrainingView } from './TrainingView'

/** Courses tab: own course list and the training view of the selected course. */
export function CoursesTab() {
  const { course, detailError } = useSelectedCourse()
  return (
    <CourseLibraryAccess>
      <div className="flex h-full">
        <div className="w-[380px] shrink-0 p-5">
          <CoursesSidebar selectedId={course?.courseId ?? null} />
        </div>
        <div className="min-w-0 flex-1 pt-5 pr-6 pb-6 pl-6">
          {!course ? (
            <EmptyCourseView />
          ) : isDetailPending(course) ? (
            <CourseDetailPending detailError={detailError} />
          ) : (
            <TrainingView course={course} />
          )}
        </div>
      </div>
    </CourseLibraryAccess>
  )
}
