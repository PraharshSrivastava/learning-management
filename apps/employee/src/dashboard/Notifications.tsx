import type { EmployeeCourse } from '@lms/shared/models'
import { Dialog, DialogClose } from '@lms/shared/ui/Dialog'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import { PageFrame } from './PageFrame'
import { assignedDateLabel } from './progress'

function SchoolAvatar() {
  return (
    <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-[#e7efff] text-primary-blue">
      <Icon name="school_outlined" />
    </span>
  )
}

/** Flutter `_NotificationsView`: new assignments as a list. */
export function NotificationsView({
  notifications,
  onOpenNotifications,
}: {
  notifications: EmployeeCourse[]
  onOpenNotifications: () => void
}) {
  return (
    <PageFrame
      title="Notifications"
      subtitle="Keep track of new learning assignments and important due dates."
    >
      <ul className="m-0 list-none divide-y divide-light-gray rounded-lg border border-[#e6e9ef] bg-white p-0">
        {notifications.map((course) => (
          <li key={course.courseId} className="flex min-h-[88px] items-center gap-4 px-[18px] py-2">
            <SchoolAvatar />
            <div className="min-w-0 flex-1">
              <p className="m-0 text-[15px] text-text-black">
                New course assigned: {course.courseName}
              </p>
              <p className="m-0 text-[#44474e]">
                Open your notification center to review this assignment.
              </p>
            </div>
            <Tooltip content="Open notification">
              <button
                type="button"
                aria-label="Open notification"
                onClick={onOpenNotifications}
                className="inline-flex size-10 shrink-0 items-center justify-center rounded-full text-[#44474e] hover:bg-primary-blue/8"
              >
                <Icon name="arrow_forward" />
              </button>
            </Tooltip>
          </li>
        ))}
      </ul>
    </PageFrame>
  )
}

/** Flutter `_showNotifications` dialog. */
export function NotificationsDialog({
  courses,
  open,
  onOpenChange,
}: {
  courses: EmployeeCourse[]
  open: boolean
  onOpenChange: (open: boolean) => void
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
          {courses.map((course) => (
            // The Flutter ListTile row renders 60 px high at desktop density.
            <li key={course.courseId} className="flex min-h-[60px] items-center gap-4 py-2">
              <SchoolAvatar />
              <div className="min-w-0 flex-1">
                <p className="m-0 text-[15px] text-text-black">New course: {course.courseName}</p>
                <p className="m-0 text-[#44474e]">{assignedDateLabel(course.assignedAt)}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Dialog>
  )
}
