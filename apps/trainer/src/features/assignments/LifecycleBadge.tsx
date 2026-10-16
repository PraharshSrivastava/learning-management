import type { Course } from '@lms/shared/models'

/** Flutter CourseLifecycleBadge: lifecycle state, or the status when the state is empty. */
export function LifecycleBadge({ course }: { course: Pick<Course, 'lifecycleState' | 'status'> }) {
  const state = course.lifecycleState || course.status
  if (!state) return null
  const color = state === 'active' ? '#087F68' : state === 'archived' ? '#667085' : '#175CD3'
  return (
    <span
      className="inline-block rounded-[20px] px-2 py-[3px] font-dm text-[11px] leading-[14px] font-medium tracking-normal"
      style={{ color, backgroundColor: `color-mix(in srgb, ${color} 10%, transparent)` }}
    >
      {state.charAt(0).toUpperCase() + state.slice(1)}
    </span>
  )
}
