// Dart: frontend/lib/features/performance/course_report_browser.dart:1-115 and the _courses
// view in performance_report_portal.dart:580-596.
import { useRef, useState } from 'react'
import type { CourseReport } from '../models/performance'
import { IconButton } from '../ui/Button'
import { Icon } from '../ui/icons/Icon'
import { TextField } from '../ui/TextField'
import { useReport } from './context'
import { CourseCard } from './CourseCard'
import { matchesWords } from './format'
import { Heading } from './primitives'
import { useElementWidth } from './useElementWidth'

const pageSize = 12

/** `_courses`: heading plus the course browser. */
export function CoursesView({
  courses,
  isLoading,
  onOpenCourse,
}: {
  courses: CourseReport[]
  isLoading: boolean
  onOpenCourse: (courseId: string) => void
}) {
  const { contextKey, state } = useReport()
  return (
    <div>
      <Heading
        title="Course performance"
        subtitle="Search a course, then open it to inspect module results."
      />
      {/* didUpdateWidget: a new scope or reset version clears the search and the page. */}
      <CourseBrowser
        key={`${contextKey}|${state.employeeResetVersion}`}
        courses={courses}
        isLoading={isLoading}
        onOpenCourse={onOpenCourse}
      />
    </div>
  )
}

/** `CourseReportBrowser`: course search is local to this view, the report scope stays. */
function CourseBrowser({
  courses,
  isLoading,
  onOpenCourse,
}: {
  courses: CourseReport[]
  isLoading: boolean
  onOpenCourse: (courseId: string) => void
}) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const gridRef = useRef<HTMLDivElement>(null)
  const width = useElementWidth(gridRef)
  const matches = courses.filter((course) =>
    matchesWords(search, `${course.courseName} ${course.courseId}`),
  )
  const pages = Math.max(1, Math.ceil(matches.length / pageSize))
  // Flutter clamps the stored page during build, but not while the report loads.
  const clamped = Math.min(Math.max(page, 1), pages)
  if (!isLoading && clamped !== page) setPage(clamped)
  const current = isLoading ? page : clamped
  const shown = matches.slice((current - 1) * pageSize, current * pageSize)
  const columns = width >= 850 ? 2 : 1
  return (
    <div className="flex flex-col items-start">
      <div className="relative w-full">
        <Icon
          name="search"
          size={24}
          className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-primary-blue"
        />
        <TextField
          aria-label="Search courses by name or ID"
          placeholder="Search courses by name or ID"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value)
            setPage(1)
          }}
          className="pl-12 pr-12"
        />
        {search && (
          <IconButton
            icon="close"
            label="Clear course search"
            className="absolute top-1/2 right-1 -translate-y-1/2 text-[#44474e]"
            onClick={() => {
              setSearch('')
              setPage(1)
            }}
          />
        )}
      </div>
      <p className="m-0 mt-2.5 text-text-secondary">
        {isLoading ? 'Loading courses…' : `${matches.length} matching courses`}
      </p>
      <div className="h-3" />
      {matches.length === 0 && !isLoading && (
        <p className="m-0 p-6">No courses match your search and selected filters.</p>
      )}
      <div
        ref={gridRef}
        className="grid w-full items-start gap-3"
        style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
      >
        {shown.map((course) => (
          <CourseCard
            key={course.courseId}
            course={course}
            onClick={() => onOpenCourse(course.courseId)}
          />
        ))}
      </div>
      {matches.length > pageSize && (
        <div className="flex flex-wrap items-center gap-2.5 pt-3">
          <span>
            Showing {(current - 1) * pageSize + 1}–{(current - 1) * pageSize + shown.length} of{' '}
            {matches.length}
          </span>
          <IconButton
            icon="chevron_left"
            label="Previous course page"
            className="text-[#44474e]"
            disabled={current <= 1}
            onClick={() => setPage(current - 1)}
          />
          <span>
            Page {current} of {pages}
          </span>
          <IconButton
            icon="chevron_right"
            label="Next course page"
            className="text-[#44474e]"
            disabled={current >= pages}
            onClick={() => setPage(current + 1)}
          />
        </div>
      )}
    </div>
  )
}
