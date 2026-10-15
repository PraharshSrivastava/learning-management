import type { Course } from '@lms/shared/models'
import { lifecycleBadge } from './courseLogic'

/** Availability pill: Active, Disabled, Draft, Ready, Published, or Archived. */
export function CourseLifecycleBadge({
  course,
}: {
  course: Pick<Course, 'lifecycleState' | 'status'>
}) {
  const badge = lifecycleBadge(course)
  if (!badge) return null
  return (
    <span
      className="inline-block rounded-[20px] px-2 py-[3px] font-dm text-[11px] leading-[16.5px] font-bold"
      style={{
        color: badge.color,
        backgroundColor: `color-mix(in srgb, ${badge.color} 10%, transparent)`,
      }}
    >
      {badge.label}
    </span>
  )
}
