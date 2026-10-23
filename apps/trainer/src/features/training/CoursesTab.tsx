import { CourseDetailPending, isDetailPending } from '../courses/CourseDetailsView'
import { CourseLibraryAccess } from '../courses/CourseLibraryAccess'
import { CoursesSidebar } from '../courses/CoursesSidebar'
import { EmptyCourseView } from '../courses/EmptyCourseView'
import { useSelectedCourse } from '../courses/courseQueries'
import '../courses/BlueprintStyles.css'
import { TrainingView } from './TrainingView'

/**
 * Courses tab: own course list and the training view of the selected course. It shares the
 * Blueprint desk, so the course list, frame and fonts match between the two tabs.
 */
export function CoursesTab() {
  const { course, detailError } = useSelectedCourse()
  return (
    <CourseLibraryAccess>
      <div className="blueprint-desk">
        <div className="bp-layout">
          <aside className="bp-sidebar" aria-label="Course navigation">
            <CoursesSidebar selectedId={course?.courseId ?? null} searchable />
          </aside>
          <main className="bp-main" aria-label="Course training view">
            {!course ? (
              <EmptyCourseView />
            ) : isDetailPending(course) ? (
              <CourseDetailPending detailError={detailError} />
            ) : (
              <TrainingView course={course} />
            )}
          </main>
        </div>
      </div>
    </CourseLibraryAccess>
  )
}
