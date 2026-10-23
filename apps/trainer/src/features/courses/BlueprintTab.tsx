import { CourseDetailsView } from './CourseDetailsView'
import { CourseLibraryAccess } from './CourseLibraryAccess'
import { CoursesSidebar } from './CoursesSidebar'
import { EmptyCourseView } from './EmptyCourseView'
import { useSelectedCourse } from './courseQueries'
import './BlueprintStyles.css'

/** Blueprint tab: own course list and the blueprint editor of the selected course. */
export function BlueprintTab() {
  const { course, detailError } = useSelectedCourse()
  return (
    <div className="blueprint-frame">
      <CourseLibraryAccess>
        <div className="blueprint-desk">
          <div className="bp-layout">
            <aside className="bp-sidebar" aria-label="Course navigation">
              <CoursesSidebar selectedId={course?.courseId ?? null} searchable />
            </aside>
            <main className="bp-main" aria-label="Course blueprint workspace">
              {course ? (
                <CourseDetailsView course={course} detailError={detailError} />
              ) : (
                <EmptyCourseView />
              )}
            </main>
          </div>
        </div>
      </CourseLibraryAccess>
    </div>
  )
}
