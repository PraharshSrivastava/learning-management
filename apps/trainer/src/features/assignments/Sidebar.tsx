// Assignable courses list (Flutter _AssignableCoursesSidebar), styled like the Blueprint desk.
import type { Course } from '@lms/shared/models'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { Spinner } from '@lms/shared/ui/Spinner'
import clsx from 'clsx'
import { useState } from 'react'
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
  const [search, setSearch] = useState('')
  const needle = search.trim().toLocaleLowerCase()
  const shown = courses.filter((course) => course.courseName.toLocaleLowerCase().includes(needle))
  return (
    <div className="assign-course-list">
      <div className="assign-course-head">
        <h2>Assignable courses</h2>
        <span className="assign-count">{courses.length}</span>
      </div>
      <label className="assign-course-search">
        <Icon name="search" size={17} />
        <input
          type="search"
          aria-label="Search assignable courses"
          placeholder="Search courses…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <div className="assign-course-scroll">
        {isLoading ? (
          <div className="flex h-full items-center justify-center p-8">
            <Spinner label="Loading courses" />
          </div>
        ) : error != null ? (
          <div className="flex flex-col items-center justify-center p-6 text-center">
            <Icon name="error_outline_rounded" size={32} className="text-accent-red" />
            <p className="mt-2 font-medium text-[#19273e]">Error loading courses</p>
            <p className="mt-1 text-xs text-[#5b6980]">{error}</p>
          </div>
        ) : courses.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-6 text-center">
            <Icon name="assignment_turned_in_outlined" size={40} className="text-gray/50" />
            <p className="mt-3 font-medium text-[#5b6980]">No courses ready to assign</p>
            <p className="mt-2 text-xs text-[#5b6980]">
              Generate all videos and quizzes before assigning a course.
            </p>
          </div>
        ) : shown.length === 0 ? (
          <p className="p-6 text-center text-sm text-[#5b6980]">No matching courses.</p>
        ) : (
          <ul aria-label="Assignable courses">
            {shown.map((course) => {
              const selected = course.courseId === selectedId
              const modules = course.moduleCount
              return (
                <li key={course.courseId}>
                  <button
                    type="button"
                    title={course.courseName}
                    aria-current={selected ? 'true' : undefined}
                    onClick={() => onSelect(course)}
                    className={clsx('assign-course-row', selected && 'assign-course-selected')}
                  >
                    <span className="assign-course-icon">
                      <Icon name="menu_book" size={18} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="assign-course-title">{course.courseName}</span>
                      <span className="assign-course-meta">
                        <span
                          className="font-semibold"
                          style={{ color: difficultyColor(course.courseDifficulty) }}
                        >
                          {course.courseDifficulty}
                        </span>
                        <LifecycleBadge course={course} />
                        <span className="ml-auto">
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
