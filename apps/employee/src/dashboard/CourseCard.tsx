import { assetUrl } from '@lms/shared/api/client'
import { useHasMediaTicket } from '@lms/shared/api/useMediaTicket'
import {
  isDueSoon,
  progressFor,
  statusFor,
  watchedModulesFor,
  type DashboardCourseStatus,
  type EmployeeCourse,
} from '@lms/shared/models'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import { ProgressBar } from '@lms/shared/ui/ProgressBar'
import { useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from 'react'
import { dueDateLabel } from './progress'

interface StatusInfo {
  label: string
  icon: IconName
  color: string
}

export function statusInfo(status: DashboardCourseStatus, dueSoon: boolean): StatusInfo {
  if (status === 'passed')
    return { label: 'Completed', icon: 'verified_outlined', color: '#00a878' }
  if (status === 'inProgress')
    return { label: 'Started', icon: 'play_circle_outline', color: '#00317a' }
  if (status === 'overdue') return { label: 'Overdue', icon: 'error_outline', color: '#d92d20' }
  if (dueSoon) return { label: 'Due soon', icon: 'schedule_outlined', color: '#d59a00' }
  return { label: 'Pending', icon: 'pending_actions_outlined', color: '#00317a' }
}

const actions: Record<DashboardCourseStatus, { label: string; color: string }> = {
  passed: { label: 'Review', color: '#596273' },
  inProgress: { label: 'Continue', color: '#087e8b' },
  overdue: { label: 'Start', color: '#00317a' },
  pending: { label: 'Start', color: '#00317a' },
}

/** Flutter `_CourseGrid`: 3, 2 or 1 columns. Card height is the 16:9 image plus 275 px. */
export function CourseGrid({
  courses,
  onOpen,
}: {
  courses: EmployeeCourse[]
  onOpen: (course: EmployeeCourse) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const width = useElementWidth(ref)
  const columns = width >= 820 ? 3 : width >= 520 ? 2 : 1
  const cardWidth = (width - 16 * (columns - 1)) / columns
  const style: CSSProperties = {
    gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
    gridAutoRows: width > 0 ? cardWidth * (9 / 16) + 275 : undefined,
  }
  return (
    <div ref={ref} className="grid gap-4" style={style}>
      {courses.map((course) => (
        <CourseCard key={course.courseId} course={course} onOpen={() => onOpen(course)} />
      ))}
    </div>
  )
}

/** Width of an element, kept in sync with ResizeObserver (LayoutBuilder). */
export function useElementWidth(ref: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    setWidth(element.getBoundingClientRect().width)
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(entry.contentRect.width)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref])
  return width
}

function CourseCard({ course, onOpen }: { course: EmployeeCourse; onOpen: () => void }) {
  const status = statusFor(course)
  const progress = progressFor(course)
  const moduleCount = course.publishedModules.length
  const info = statusInfo(status, isDueSoon(course))
  const action = actions[status]
  return (
    // The whole card opens the course, as the Flutter InkWell does. The button is the keyboard target.
    <article
      onClick={onOpen}
      className="flex min-h-0 cursor-pointer flex-col overflow-hidden rounded-2xl border border-light-gray bg-white transition-colors hover:bg-[#fafbfc]"
    >
      <div className="relative shrink-0">
        <Thumbnail course={course} />
        {course.journeys[0] && (
          <span className="absolute top-2.5 left-2.5 max-w-[calc(100%-20px)] truncate rounded-full bg-white/92 px-2 py-[3px] text-[11px] font-bold text-primary-blue">
            {course.journeys[0].title} · Step {course.journeys[0].step} of{' '}
            {course.journeys[0].stepCount}
          </span>
        )}
      </div>
      <div className="flex min-h-0 flex-1 flex-col px-4 py-3.5">
        <span
          className="inline-flex items-center gap-1 self-start rounded-2xl px-2 py-[5px]"
          style={{ color: info.color, backgroundColor: `${info.color}1c` }}
        >
          <Icon name={info.icon} size={14} />
          <span className="text-[11px] leading-[1.5] font-bold">{info.label}</span>
        </span>
        <h3 className="m-0 mt-2.5 line-clamp-2 h-10 text-[16px] leading-[1.25] font-bold">
          {course.courseName}
        </h3>
        <p className="m-0 mt-1.5 line-clamp-2 h-9 text-[13px] leading-[1.35] text-[#667085]">
          {course.courseDescription || 'Structured learning designed for your job title.'}
        </p>
        <div className="h-3.5 shrink-0" />
        {moduleCount > 0 && (
          <>
            <div className="flex items-center text-[12px]">
              <span className="flex-1 text-[#667085]">
                {watchedModulesFor(course)} of {moduleCount} modules
              </span>
              <span className="font-bold text-primary-blue">{Math.round(progress * 100)}%</span>
            </div>
            <ProgressBar
              value={progress}
              height={5}
              radius={3}
              className="mt-[7px] mb-[13px]"
              label={`${course.courseName} progress`}
            />
          </>
        )}
        <div className="flex-1" />
        {course.deadline != null && (
          <div className="mb-3 flex items-center gap-1.5 text-[12px] text-[#667085]">
            <Icon name="calendar_today_outlined" size={14} />
            <span className="truncate">Due {dueDateLabel(course.deadline)}</span>
          </div>
        )}
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation()
            onOpen()
          }}
          aria-label={`${action.label} ${course.courseName}`}
          className="inline-flex h-9 w-full shrink-0 items-center justify-center gap-2 rounded-full text-[14px] font-bold text-white hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light"
          style={{ backgroundColor: action.color }}
        >
          <Icon name={status === 'passed' ? 'visibility_outlined' : 'arrow_forward'} size={18} />
          {action.label}
        </button>
      </div>
    </article>
  )
}

function Thumbnail({ course }: { course: EmployeeCourse }) {
  // Re-render when the ticket appears, so a protected image retries with it.
  useHasMediaTicket()
  const path = course.thumbnailPath || course.images[0]?.filePath || ''
  const src = path ? assetUrl(path) : ''
  // The image loads at once, as Flutter did, so public images do not need a ticket. Failure is
  // kept per URL and a loaded image stays visible per path, so a ticket renewal does not blank it.
  const [loadedPath, setLoadedPath] = useState<string | null>(null)
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  if (!path || failedSrc === src) return <ThumbnailFallback />
  return (
    <div className="relative aspect-video shrink-0 bg-brand-blue-100">
      <img
        src={src}
        alt=""
        className="absolute inset-0 size-full object-cover"
        style={{ opacity: loadedPath === path ? 1 : 0 }}
        onLoad={() => setLoadedPath(path)}
        onError={() => setFailedSrc(src)}
      />
    </div>
  )
}

function ThumbnailFallback() {
  return (
    <div className="primary-gradient flex aspect-video shrink-0 items-center justify-center text-white">
      <Icon name="image_not_supported_outlined" />
    </div>
  )
}
