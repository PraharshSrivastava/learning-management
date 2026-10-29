import { useLmsAccess } from '@lms/shared/auth/lmsAccess'
import { useSession } from '@lms/shared/auth/session'
import { isNewAssignment, orderedAssigned, type EmployeeCourse } from '@lms/shared/models'
import { LazyPerformanceReport } from '@lms/shared/performance/LazyPerformanceReport'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Employee } from '../auth/employee'
import { JourneyBar, JourneyStrip, LearningJourneysPage } from '../journeys/JourneyViews'
import { useLearnerJourneys } from '../journeys/useLearnerJourneys'
import { CoursePlayback } from '../learning/CoursePlayback'
import { AppBar } from './AppBar'
import { CourseGrid } from './CourseCard'
import { DashboardBody, type CourseFilter } from './DashboardBody'
import { NotificationsDialog, NotificationsView } from './Notifications'
import { PageFrame } from './PageFrame'
import {
  destinationForView,
  destinationsFor,
  openCourseId,
  useEmployeeSearch,
  useSetEmployeeSearch,
  viewForDestination,
  type Destination,
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
  const learnerJourneys = useLearnerJourneys(courses)
  const search = useEmployeeSearch()
  const setSearch = useSetEmployeeSearch()
  const isCompact = useViewportWidth() < 840

  const [navigationExpanded, setNavigationExpanded] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [filter, setFilter] = useState<CourseFilter>('Assigned')
  const [seenNotifications, setSeenNotifications] = useState<ReadonlySet<string>>(() => new Set())
  const [dialogCourses, setDialogCourses] = useState<EmployeeCourse[] | null>(null)

  // Without report access the Performance views fall back to Dashboard, as in Flutter.
  // Learning Journeys appear only when the backend reports the feature as enabled.
  const destinations = destinationsFor({
    journeys: learnerJourneys.enabled,
    performance: canReport,
  })
  const requested = destinationForView(search.view)
  const active: Destination = destinations.includes(requested) ? requested : 'dashboard'
  const courseId = openCourseId(search)
  const openCourse =
    courseId == null ? null : (courses.find((c) => c.courseId === courseId) ?? null)
  const courseMissing = courseId != null && openCourse == null && courses.length > 0

  // A deep link to a course that is not assigned falls back to the list.
  const listView = search.view === 'course' ? undefined : search.view
  useEffect(() => {
    if (courseMissing)
      setSearch({ view: listView, journey_id: search.journey_id }, { replace: true })
  }, [courseMissing, listView, search.journey_id, setSearch])

  const unreadCourses = courses.filter(
    (course) => isNewAssignment(course) && !seenNotifications.has(course.courseId),
  )

  const handleNavigation = (destination: Destination) => {
    setSearch({ view: viewForDestination(destination) })
    setDrawerOpen(false)
    void refetch()
  }

  const openJourney = (journeyId: string | null) =>
    setSearch({ view: 'journeys', journey_id: journeyId ?? undefined })

  // Opening a course from a journey keeps that journey in the URL, so the course player's back
  // button returns to the journey it came from.
  const openCourseById = (id: string, journeyId?: string) => {
    const course = courses.find((item) => item.courseId === id)
    if (!course) return
    setSearch({
      view: search.view,
      course_id: course.courseId,
      journey_id: journeyId ?? search.journey_id,
    })
  }

  const showNotifications = (list: EmployeeCourse[]) => {
    if (list.length > 0) {
      setSeenNotifications((seen) => new Set([...seen, ...list.map((c) => c.courseId)]))
    }
    setDialogCourses(list)
  }

  const openCourseView = (course: EmployeeCourse) =>
    setSearch({ view: search.view, course_id: course.courseId, journey_id: search.journey_id })

  const closeCourse = () => {
    setSearch({ view: listView, journey_id: search.journey_id })
    void refetch()
  }

  const showPerformance = active === 'performance'
  // A new link object opens the link again, so keep one object per URL link.
  const linkedReport = useMemo(
    () =>
      search.view === 'team-performance'
        ? { courseId: search.course_id ?? null, status: search.status ?? null }
        : null,
    [search.view, search.course_id, search.status],
  )

  let content
  if (showPerformance) {
    // The page frame does not scroll; each page scrolls itself, as the report does here.
    content = (
      <div data-testid="performance-scroll" className="h-full overflow-y-auto">
        <LazyPerformanceReport
          key={`${person?.employeeId}:${token}:${access?.permissions_version}:${access?.report_scope_version}`}
          app="employee"
          linkedReport={linkedReport}
        />
      </div>
    )
  } else if (openCourse) {
    const playback = (
      <FreshCoursePlayback
        key={openCourse.courseId}
        course={openCourse}
        refetch={refetch}
        onBack={closeCourse}
        backLabel={
          search.view === 'journeys' && search.journey_id
            ? 'Back to journey'
            : search.view === 'notifications'
              ? 'Back to notifications'
              : 'Back to dashboard'
        }
      />
    )
    content =
      learnerJourneys.enabled && openCourse.journeys.length > 0 ? (
        <div className="flex h-full flex-col">
          <JourneyBar course={openCourse} journeys={learnerJourneys.journeys} />
          <div className="min-h-0 flex-1">{playback}</div>
        </div>
      ) : (
        playback
      )
  } else if (active === 'journeys') {
    content = (
      <LearningJourneysPage
        journeys={learnerJourneys.journeys}
        isLoading={learnerJourneys.isLoading}
        error={learnerJourneys.error}
        openJourneyId={search.journey_id ?? null}
        onOpenJourney={openJourney}
        onOpenCourse={openCourseById}
      />
    )
  } else if (active === 'courses') {
    content = (
      <PageFrame
        title="My courses"
        subtitle="Pick up where you left off or start your next assigned course."
      >
        <CourseGrid courses={orderedAssigned(courses)} onOpen={openCourseView} />
      </PageFrame>
    )
  } else if (active === 'notifications') {
    const notifications = courses.filter((course) => isNewAssignment(course))
    content = (
      <NotificationsView
        notifications={notifications}
        onOpenCourse={(course) => {
          // Opening a notification reads it, as opening the notification list does.
          setSeenNotifications((seen) => new Set([...seen, course.courseId]))
          openCourseView(course)
        }}
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
        journeys={
          learnerJourneys.enabled ? (
            <JourneyStrip
              journeys={learnerJourneys.journeys}
              onOpenJourney={openJourney}
              onOpenCourse={openCourseById}
              onSeeAll={() => openJourney(null)}
            />
          ) : null
        }
      />
    )
  }

  return (
    <div className="page-gradient flex h-dvh overflow-hidden tracking-normal">
      {!isCompact && (
        <Sidebar
          expanded={navigationExpanded}
          destinations={destinations}
          selected={active}
          onSelect={handleNavigation}
          onToggle={() => setNavigationExpanded((value) => !value)}
        />
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <AppBar
          isCompact={isCompact}
          active={active}
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
            destinations={destinations}
            selected={active}
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
        onOpenCourse={(course) => {
          setDialogCourses(null)
          openCourseView(course)
        }}
      />
    </div>
  )
}

/** Fetch authoritative progress once on entry. Later live updates never reset the chosen module. */
function FreshCoursePlayback({
  course,
  refetch,
  onBack,
  backLabel,
}: {
  course: EmployeeCourse
  refetch: ReturnType<typeof useEmployeeCourses>['refetch']
  onBack: () => void
  backLabel: string
}) {
  const [entry, setEntry] = useState<EmployeeCourse | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let cancelled = false
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      if (!cancelled) setError(true)
    }, 30_000)
    void refetch({ throwOnError: true })
      .then(
        (result) => {
          if (cancelled || timedOut) return
          const fresh = result.data?.find((item) => item.courseId === course.courseId)
          if (!fresh) setError(true)
          else setEntry(fresh)
        },
        () => {
          if (!cancelled && !timedOut) setError(true)
        },
      )
      .finally(() => clearTimeout(timer))
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [course.courseId, refetch, attempt])
  if (entry)
    return (
      <CoursePlayback course={course} initialCourse={entry} onBack={onBack} backLabel={backLabel} />
    )
  return (
    <div className="p-8" role={error ? 'alert' : 'status'}>
      <p>
        {error
          ? 'Could not load your latest progress. Retry before opening the course.'
          : 'Loading your latest progress…'}
      </p>
      {error && (
        <button
          type="button"
          className="mt-4 rounded-lg bg-primary-blue px-4 py-2 text-white"
          onClick={() => {
            setError(false)
            setAttempt((value) => value + 1)
          }}
        >
          Retry course
        </button>
      )}
      <button type="button" className="ml-4 text-primary-blue" onClick={onBack}>
        Back to dashboard
      </button>
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
