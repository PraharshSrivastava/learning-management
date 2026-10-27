import type { EmployeeCourse } from '@lms/shared/models'
import { Dialog, DialogClose } from '@lms/shared/ui/Dialog'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { PageFrame } from './PageFrame'
import { assignedDateLabel } from './progress'

function SchoolAvatar() {
  return (
    <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-[#e7efff] text-primary-blue">
      <Icon name="school_outlined" />
    </span>
  )
}

/** "Step 2 of 5 in New Joiner Induction" for a course that is part of a learning journey. */
function journeyLine(course: EmployeeCourse): string | null {
  const place = course.journeys[0]
  return place ? `Step ${place.step} of ${place.stepCount} in ${place.title}` : null
}

/** Flutter `_NotificationsView`: new assignments as a list. Each row opens its course. */
export function NotificationsView({
  notifications,
  onOpenCourse,
}: {
  notifications: EmployeeCourse[]
  onOpenCourse: (course: EmployeeCourse) => void
}) {
  return (
    <PageFrame
      title="Notifications"
      subtitle="Keep track of new learning assignments and important due dates."
    >
      <ul className="m-0 list-none divide-y divide-light-gray rounded-lg border border-[#e6e9ef] bg-white p-0">
        {notifications.map((course) => {
          const journey = journeyLine(course)
          return (
            <li key={course.courseId}>
              <button
                type="button"
                aria-label={`Open ${course.courseName}`}
                onClick={() => onOpenCourse(course)}
                className="flex min-h-[88px] w-full items-center gap-4 px-[18px] py-2 text-left hover:bg-primary-blue/4 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-blue-light"
              >
                <SchoolAvatar />
                <span className="min-w-0 flex-1">
                  <span className="block text-[15px] break-words text-text-black">
                    New course assigned: {course.courseName}
                  </span>
                  <span className="block text-[#44474e]">
                    {journey ?? assignedDateLabel(course.assignedAt)}
                  </span>
                </span>
                <Icon name="arrow_forward" className="shrink-0 text-[#44474e]" />
              </button>
            </li>
          )
        })}
      </ul>
    </PageFrame>
  )
}

/** Flutter `_showNotifications` dialog. Each row opens its course. */
export function NotificationsDialog({
  courses,
  open,
  onOpenChange,
  onOpenCourse,
}: {
  courses: EmployeeCourse[]
  open: boolean
  onOpenChange: (open: boolean) => void
  onOpenCourse: (course: EmployeeCourse) => void
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Learning notifications"
      width={408}
      className="tracking-normal"
      actions={
        <DialogClose asChild>
          <button
            type="button"
            className="inline-flex h-9 items-center rounded-full px-3 text-[14px] font-bold text-primary-blue hover:bg-brand-blue-50"
          >
            Close
          </button>
        </DialogClose>
      }
    >
      {courses.length === 0 ? (
        <p className="m-0">You are up to date. New course assignments will appear here.</p>
      ) : (
        <ul className="m-0 list-none divide-y divide-light-gray p-0">
          {courses.map((course) => {
            const journey = journeyLine(course)
            return (
              <li key={course.courseId}>
                {/* The Flutter ListTile row renders 60 px high at desktop density. */}
                <button
                  type="button"
                  aria-label={`Open ${course.courseName}`}
                  onClick={() => onOpenCourse(course)}
                  className="flex min-h-[60px] w-full items-center gap-4 py-2 text-left hover:bg-primary-blue/4 focus-visible:outline-2 focus-visible:outline-brand-blue-light"
                >
                  <SchoolAvatar />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[15px] break-words text-text-black">
                      New course: {course.courseName}
                    </span>
                    {journey && <span className="block text-[#44474e]">{journey}</span>}
                    <span className="block text-[#44474e]">
                      {assignedDateLabel(course.assignedAt)}
                    </span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </Dialog>
  )
}
