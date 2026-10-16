// Dart: frontend/lib/features/performance/performance_report_portal.dart:836-942
// (_CourseCard, _CourseStat, _courseIcon).
import type { CourseReport } from '../models/performance'
import { Icon } from '../ui/icons/Icon'
import { ProgressBar } from '../ui/ProgressBar'
import { colors, courseIcon } from './format'

/** `_CourseCard`: white, r14, #DDE6F1 border, InkWell. Opens the course detail. */
export function CourseCard({ course, onClick }: { course: CourseReport; onClick: () => void }) {
  const name = course.courseName || 'Course'
  // Dart `_int(...)` truncates, then clamps to 0..100.
  const rate = Math.min(100, Math.max(0, Math.trunc(course.completionRate)))
  return (
    <button
      type="button"
      onClick={onClick}
      className="block w-full cursor-pointer overflow-hidden rounded-[14px] border border-[#dde6f1] bg-white p-[18px] text-left hover:shadow-[inset_0_0_0_999px_rgb(0_0_0/0.04)] focus-visible:outline-2 focus-visible:outline-brand-blue-light"
    >
      <div className="flex items-center">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-brand-blue-100 text-primary-blue">
          <Icon name={courseIcon(name)} size={22} />
        </span>
        <span className="ml-3 line-clamp-2 min-w-0 flex-1 text-[17px] font-extrabold">{name}</span>
        <Icon name="chevron_right" size={21} className="shrink-0 text-text-secondary" />
      </div>
      <div className="mt-[17px] flex items-center">
        <ProgressBar
          value={rate / 100}
          height={8}
          radius={8}
          color={colors.accentBlue}
          trackColor={colors.brandBlue100}
          className="flex-1"
        />
        <span className="ml-3 font-extrabold text-primary-blue">{rate}%</span>
      </div>
      <div className="mt-[18px] flex">
        <CourseStat value={course.assigned} label="assigned" />
        <CourseStat value={course.completed} label="completed" />
        <CourseStat value={course.overdue} label="overdue" color={colors.accentRed} />
      </div>
    </button>
  )
}

/** `_CourseStat`: 19 w800 value over a 12 secondary label, one third of the row. */
function CourseStat({ value, label, color }: { value: number; label: string; color?: string }) {
  return (
    <span className="flex min-w-0 flex-1 flex-col">
      <span className="text-[19px] font-extrabold" style={{ color: color ?? colors.textBlack }}>
        {Math.trunc(value)}
      </span>
      <span className="text-xs text-text-secondary">{label}</span>
    </span>
  )
}
