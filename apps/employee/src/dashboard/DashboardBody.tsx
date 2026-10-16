import {
  learningMetrics,
  orderedAssigned,
  orderedAttempted,
  statusFor,
  type EmployeeCourse,
  type LearningMetrics,
} from '@lms/shared/models'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import { Spinner } from '@lms/shared/ui/Spinner'
import clsx from 'clsx'
import { useRef, type ReactNode } from 'react'
import { CourseGrid, useElementWidth } from './CourseCard'
import { PageTitle } from './PageFrame'

export const FILTERS = ['Assigned', 'Attempted', 'Passed', 'Pending', 'In progress'] as const
export type CourseFilter = (typeof FILTERS)[number]

const metricItems: {
  label: CourseFilter
  key: keyof LearningMetrics
  icon: IconName
  color: string
}[] = [
  { label: 'Assigned', key: 'assigned', icon: 'assignment_outlined', color: '#00317a' },
  { label: 'Attempted', key: 'attempted', icon: 'play_circle_outline', color: '#2878d7' },
  { label: 'Passed', key: 'passed', icon: 'verified_outlined', color: '#00a878' },
  { label: 'Pending', key: 'pending', icon: 'schedule_outlined', color: '#d59a00' },
  { label: 'In progress', key: 'inProgress', icon: 'trending_up_outlined', color: '#6750a4' },
]

const sectionTitles: Record<CourseFilter, string> = {
  Assigned: 'Assigned to you',
  Attempted: 'Attempted courses',
  Passed: 'Passed courses',
  Pending: 'Pending courses',
  'In progress': 'Courses in progress',
}

/** Flutter `_coursesForSelectedMetric`. */
export function coursesForFilter(
  courses: EmployeeCourse[],
  filter: CourseFilter,
  now: Date = new Date(),
): EmployeeCourse[] {
  switch (filter) {
    case 'Attempted':
      return orderedAttempted(courses, now)
    case 'Passed':
      return courses.filter((course) => statusFor(course, now) === 'passed')
    case 'Pending':
      return orderedAssigned(courses, now).filter((course) => {
        const status = statusFor(course, now)
        return status === 'pending' || status === 'overdue'
      })
    case 'In progress':
      return orderedAssigned(courses, now).filter(
        (course) => statusFor(course, now) === 'inProgress',
      )
    default:
      return orderedAssigned(courses, now)
  }
}

interface DashboardBodyProps {
  courses: EmployeeCourse[]
  isLoading: boolean
  error: string | null
  filter: CourseFilter
  onFilterChange: (filter: CourseFilter) => void
  onOpenCourse: (course: EmployeeCourse) => void
}

/** Flutter `_DashboardBody`. */
export function DashboardBody({
  courses,
  isLoading,
  error,
  filter,
  onFilterChange,
  onOpenCourse,
}: DashboardBodyProps) {
  const metrics = learningMetrics(courses)
  return (
    <div className="h-full overflow-y-auto p-7 [scrollbar-width:none]">
      <div className="mx-auto max-w-[1480px]">
        <PageTitle
          title="My learning"
          subtitle={
            metrics.pending > 0
              ? `You have ${metrics.pending} course${metrics.pending === 1 ? '' : 's'} ready for your attention.`
              : 'Your learning activity is up to date.'
          }
        />
        <MetricsGrid metrics={metrics} selected={filter} onSelect={onFilterChange} />
        <div className="h-8" />
        {error != null && courses.length > 0 && (
          <div className="mb-5 flex items-center gap-2.5 rounded-lg border border-[#f3d19c] bg-[#fff7e8] p-3">
            <Icon name="wifi_off_outlined" color="#8a5a00" />
            <p className="m-0 flex-1 text-[13px] text-[#704a00]">
              Showing the latest available learning data. {error}
            </p>
          </div>
        )}
        {isLoading && courses.length === 0 ? (
          <div className="flex flex-col items-center gap-4 py-[72px]">
            <Spinner />
            <p className="m-0">Loading your learning dashboard...</p>
          </div>
        ) : error != null && courses.length === 0 ? (
          <DashboardMessage icon="cloud_off_outlined" title="Unable to load your learning">
            {error}
          </DashboardMessage>
        ) : courses.length === 0 ? (
          <DashboardMessage icon="school_outlined" title="No courses assigned yet">
            New assigned courses will appear here when they are ready.
          </DashboardMessage>
        ) : (
          <CourseContent courses={courses} filter={filter} onOpenCourse={onOpenCourse} />
        )}
      </div>
    </div>
  )
}

function MetricsGrid({
  metrics,
  selected,
  onSelect,
}: {
  metrics: LearningMetrics
  selected: CourseFilter
  onSelect: (filter: CourseFilter) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const width = useElementWidth(ref)
  const columns = width >= 1040 ? 5 : width >= 620 ? 3 : 2
  return (
    <div
      ref={ref}
      role="group"
      aria-label="Learning metrics"
      className="grid gap-3"
      style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
    >
      {metricItems.map((item) => {
        const isSelected = item.label === selected
        return (
          <button
            key={item.label}
            type="button"
            aria-label={`Show ${item.label} courses`}
            aria-pressed={isSelected}
            onClick={() => onSelect(item.label)}
            className={clsx(
              'flex items-center gap-3 rounded-2xl border p-4 text-left transition-shadow focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light',
              !isSelected &&
                'border-light-gray bg-white shadow-[0_3px_10px_rgb(16_24_40/0.04)] hover:bg-[#fafbfc]',
            )}
            style={{
              aspectRatio: columns >= 3 ? 2.2 : 1.9,
              ...(isSelected
                ? {
                    backgroundColor: item.color,
                    borderColor: item.color,
                    boxShadow: `0 7px 16px ${item.color}3d`,
                  }
                : {}),
            }}
          >
            <span
              className="flex size-10 shrink-0 items-center justify-center rounded-xl"
              style={{
                backgroundColor: isSelected ? 'rgb(255 255 255 / 0.18)' : `${item.color}1f`,
                color: isSelected ? '#fff' : item.color,
              }}
            >
              <Icon name={item.icon} size={21} />
            </span>
            <span className="flex min-w-0 flex-col">
              <span
                className={clsx(
                  'text-[26px] leading-none font-bold',
                  isSelected ? 'text-white' : 'text-text-black',
                )}
              >
                {metrics[item.key]}
              </span>
              <span
                className={clsx(
                  'mt-[5px] truncate text-[13px] font-medium',
                  isSelected ? 'text-white/82' : 'text-text-secondary',
                )}
              >
                {item.label}
              </span>
            </span>
          </button>
        )
      })}
    </div>
  )
}

function CourseContent({
  courses,
  filter,
  onOpenCourse,
}: {
  courses: EmployeeCourse[]
  filter: CourseFilter
  onOpenCourse: (course: EmployeeCourse) => void
}) {
  const filtered = coursesForFilter(courses, filter)
  const attempted = orderedAttempted(courses)
  return (
    <>
      <SectionHeader>{sectionTitles[filter]}</SectionHeader>
      {filtered.length === 0 ? (
        <InlineEmpty>No {filter.toLowerCase()} courses to show.</InlineEmpty>
      ) : (
        <CourseGrid courses={filtered} onOpen={onOpenCourse} />
      )}
      {filter === 'Assigned' && (
        <>
          <div className="h-9" />
          <SectionHeader>Already attempted</SectionHeader>
          {attempted.length === 0 ? (
            <InlineEmpty>Courses you start or complete will appear here.</InlineEmpty>
          ) : (
            <CourseGrid courses={attempted.slice(0, 4)} onOpen={onOpenCourse} />
          )}
        </>
      )}
    </>
  )
}

function SectionHeader({ children }: { children: ReactNode }) {
  return <h2 className="m-0 mb-4 text-[21px] font-bold text-[#101828]">{children}</h2>
}

function InlineEmpty({ children }: { children: ReactNode }) {
  return (
    <p className="m-0 rounded-lg border border-[#e6e9ef] bg-white p-6 text-[#667085]">{children}</p>
  )
}

function DashboardMessage({
  icon,
  title,
  children,
}: {
  icon: IconName
  title: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-[#e6e9ef] bg-white p-12">
      <Icon name={icon} size={44} color="#00317a" />
      <p className="m-0 mt-3.5 text-[18px] font-bold">{title}</p>
      <p className="m-0 mt-1.5 text-center text-[#667085]">{children}</p>
    </div>
  )
}
