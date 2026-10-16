import { useLmsAccess } from '@lms/shared/auth/lmsAccess'
import { useSession } from '@lms/shared/auth/session'
import { isNewAssignment, orderedAssigned, type EmployeeCourse } from '@lms/shared/models'
import { PerformanceReport } from '@lms/shared/performance/PerformanceReport'
import { useEffect, useState, type ReactNode } from 'react'
import type { Employee } from '../auth/employee'
import { CoursePlayback } from '../learning/CoursePlayback'
import { AppBar } from './AppBar'
import { CourseGrid } from './CourseCard'
import { DashboardBody, type CourseFilter } from './DashboardBody'
import { NotificationsDialog, NotificationsView } from './Notifications'
import { PageFrame } from './PageFrame'
import {
  navigationIndex,
  openCourseId,
  useEmployeeSearch,
  useSetEmployeeSearch,
  viewForIndex,
} from './search'
import { Sidebar } from './Sidebar'
import { useEmployeeCourses } from './useEmployeeCourses'
import { useViewportWidth } from './useViewportWidth'

/** Flutter `EmployeeDashboardPage`: navigation rail, app bar and the active view. */
export function EmployeeDashboard() {
  const { person, token } = useSession<Employee>()
  const { access } = useLmsAccess()
  const canReport = (access?.performance_views.length ?? 0) > 0
  const { courses, isLoading, error, refetch } = useEmployeeCourses()
  const search = useEmployeeSearch()
  const setSearch = useSetEmployeeSearch()
  const isCompact = useViewportWidth() < 840

  const [navigationExpanded, setNavigationExpanded] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [filter, setFilter] = useState<CourseFilter>('Assigned')
  const [seenNotifications, setSeenNotifications] = useState<ReadonlySet<string>>(() => new Set())
  const [dialogCourses, setDialogCourses] = useState<EmployeeCourse[] | null>(null)

  // Without report access the Performance views fall back to Dashboard, as in Flutter.
  const requestedIndex = navigationIndex(search.view)
  const activeIndex = requestedIndex === 3 && !canReport ? 0 : requestedIndex
  const courseId = openCourseId(search)
  const openCourse =
    courseId == null ? null : (courses.find((c) => c.courseId === courseId) ?? null)
  const courseMissing = courseId != null && openCourse == null && courses.length > 0

  // A deep link to a course that is not assigned falls back to the list.
  const listView = search.view === 'course' ? undefined : search.view
  useEffect(() => {
    if (courseMissing) setSearch({ view: listView }, { replace: true })
  }, [courseMissing, listView, setSearch])

  const unreadCourses = courses.filter(
    (course) => isNewAssignment(course) && !seenNotifications.has(course.courseId),
  )

  const handleNavigation = (index: number) => {
    setSearch({ view: viewForIndex(index) })
    setDrawerOpen(false)
    void refetch()
  }

  const showNotifications = (list: EmployeeCourse[]) => {
    if (list.length > 0) {
      setSeenNotifications((seen) => new Set([...seen, ...list.map((c) => c.courseId)]))
    }
    setDialogCourses(list)
  }

  const openCourseView = (course: EmployeeCourse) =>
    setSearch({ view: search.view, course_id: course.courseId })

  const closeCourse = () => {
    setSearch({ view: listView })
    void refetch()
  }

  const showPerformance = activeIndex === 3

  let content
  if (showPerformance) {
    const linked =
      search.view === 'team-performance'
        ? { courseId: search.course_id ?? null, status: search.status ?? null }
        : null
    content = (
      <PerformanceReport
        key={`${person?.employeeId}:${token}:${access?.permissions_version}:${access?.report_scope_version}`}
        app="employee"
        linkedReport={linked}
      />
    )
  } else if (openCourse) {
    content = <CoursePlayback key={openCourse.courseId} course={openCourse} onBack={closeCourse} />
  } else if (activeIndex === 1) {
    content = (
      <PageFrame
        title="My courses"
        subtitle="Pick up where you left off or start your next assigned course."
      >
        <CourseGrid courses={orderedAssigned(courses)} onOpen={openCourseView} />
      </PageFrame>
    )
  } else if (activeIndex === 2) {
    const notifications = courses.filter((course) => isNewAssignment(course))
    content = (
      <NotificationsView
        notifications={notifications}
        onOpenNotifications={() => showNotifications(notifications)}
      />
    )
  } else {
    content = (
      <DashboardBody
        courses={courses}
        isLoading={isLoading}
        error={error}
        filter={filter}
        onFilterChange={setFilter}
        onOpenCourse={openCourseView}
      />
    )
  }

  return (
    <div className="page-gradient flex h-dvh overflow-hidden tracking-normal">
      {!isCompact && (
        <Sidebar
          expanded={navigationExpanded}
          canReport={canReport}
          selectedIndex={activeIndex}
          onSelect={handleNavigation}
          onToggle={() => setNavigationExpanded((value) => !value)}
        />
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <AppBar
          isCompact={isCompact}
          activeIndex={activeIndex}
          unreadCount={unreadCourses.length}
          employee={person}
          onMenu={() => setDrawerOpen(true)}
          onNotifications={() => showNotifications(unreadCourses)}
        />
        <main className="min-h-0 flex-1">{content}</main>
      </div>
      {isCompact && drawerOpen && (
        <NavigationDrawer onClose={() => setDrawerOpen(false)}>
          <Sidebar
            expanded
            canReport={canReport}
            selectedIndex={activeIndex}
            onSelect={handleNavigation}
            onToggle={() => setDrawerOpen(false)}
            className="h-[calc(100%-24px)]"
          />
        </NavigationDrawer>
      )}
      <NotificationsDialog
        courses={dialogCourses ?? []}
        open={dialogCourses != null}
        onOpenChange={(open) => !open && setDialogCourses(null)}
      />
    </div>
  )
}

/** Flutter Drawer: 304 px panel over a scrim. Esc and a scrim click close it. */
function NavigationDrawer({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-30">
      <div aria-hidden className="absolute inset-0 bg-black/54" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        className="absolute inset-y-0 left-0 flex w-[304px] max-w-[calc(100%-56px)] rounded-r-2xl bg-[#f9f9ff] shadow-[0_8px_24px_rgb(0_0_0/0.2)]"
      >
        {children}
      </div>
    </div>
  )
}
