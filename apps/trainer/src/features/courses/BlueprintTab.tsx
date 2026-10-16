import { CourseDetailsView } from './CourseDetailsView'
import { CourseLibraryAccess } from './CourseLibraryAccess'
import { CoursesSidebar } from './CoursesSidebar'
import { EmptyCourseView } from './EmptyCourseView'
import { useSelectedCourse } from './courseQueries'

/** Blueprint tab: own course list and the blueprint editor of the selected course. */
export function BlueprintTab() {
  const { course, detailError } = useSelectedCourse()
  return (
    <CourseLibraryAccess>
      <div className="flex h-full">
        <div className="w-[380px] shrink-0 p-5">
          <CoursesSidebar selectedId={course?.courseId ?? null} />
        </div>
        <div className="min-w-0 flex-1 pt-5 pr-6 pb-6 pl-6">
          {course ? (
            <CourseDetailsView course={course} detailError={detailError} />
          ) : (
            <EmptyCourseView />
          )}
        </div>
      </div>
    </CourseLibraryAccess>
  )
}
