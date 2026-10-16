// Assignable courses list (Flutter _AssignableCoursesSidebar).
import type { Course } from '@lms/shared/models'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { Spinner } from '@lms/shared/ui/Spinner'
import clsx from 'clsx'
import { LifecycleBadge } from './LifecycleBadge'

interface SidebarProps {
  courses: Course[]
  isLoading: boolean
  error: string | null
  selectedId: string | null
  onSelect: (course: Course) => void
}

export function difficultyColor(difficulty: string): string {
  switch (difficulty.toLowerCase()) {
    case 'easy':
    case 'beginner':
      return 'var(--color-accent-green)'
    case 'medium':
    case 'intermediate':
      return 'var(--color-accent-orange)'
    case 'hard':
    case 'advanced':
      return 'var(--color-accent-red)'
    default:
      return 'var(--color-gray)'
  }
}

export function Sidebar({ courses, isLoading, error, selectedId, onSelect }: SidebarProps) {
  return (
    <div className="card flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between p-4">
        <h2 className="font-manrope text-lg leading-[1.35] font-bold text-primary-blue">
          Assignable Courses
        </h2>
        <span className="text-xs leading-[1.4] tracking-normal text-gray">
          {courses.length} courses
        </span>
      </div>
      <div className="h-px bg-light-gray" />
      <div className="min-h-0 flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <Spinner label="Loading courses" />
          </div>
        ) : error != null ? (
          <div className="flex h-full flex-col items-center justify-center p-4 text-center">
            <Icon name="error_outline_rounded" size={32} className="text-accent-red" />
            <p className="mt-2 font-barlow font-bold text-text-black">Error loading courses</p>
            <p className="mt-1 text-xs leading-[1.4] text-gray">{error}</p>
          </div>
        ) : courses.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center p-8 text-center">
            <Icon name="assignment_turned_in_outlined" size={48} className="text-gray/50" />
            <p className="mt-3 font-barlow font-medium text-gray">No courses ready to assign</p>
            <p className="mt-2 text-xs leading-[1.4] text-gray">
              Generate all videos and quizzes before assigning a course.
            </p>
          </div>
        ) : (
          <ul aria-label="Assignable courses">
            {courses.map((course, index) => {
              const selected = course.courseId === selectedId
              const modules = course.modules.length
              return (
                <li
                  key={course.courseId}
                  className={clsx(index > 0 && 'border-t border-light-gray')}
                >
                  <button
                    type="button"
                    aria-current={selected ? 'true' : undefined}
                    onClick={() => onSelect(course)}
                    className={clsx(
                      'flex min-h-[62px] w-full items-center gap-3 py-2 pr-6 pl-4 text-left transition-colors',
                      'focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-blue-light',
                    )}
                  >
                    <Icon
                      name="menu_book"
                      className={selected ? 'text-primary-blue' : 'text-gray'}
                    />
                    <span className="min-w-0 flex-1 -translate-y-0.5">
                      <span
                        className={clsx(
                          'block truncate font-barlow text-base leading-6 tracking-normal',
                          selected ? 'font-bold text-primary-blue' : 'font-medium text-text-black',
                        )}
                      >
                        {course.courseName}
                      </span>
                      <span className="flex items-center justify-between text-xs leading-[1.4] tracking-normal text-gray">
                        <span
                          className="font-bold"
                          style={{ color: difficultyColor(course.courseDifficulty) }}
                        >
                          {course.courseDifficulty}
                        </span>
                        <LifecycleBadge course={course} />
                        <span>
                          {modules} module{modules === 1 ? '' : 's'}
                        </span>
                      </span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
