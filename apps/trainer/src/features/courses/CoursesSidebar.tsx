import { Icon } from '@lms/shared/ui/icons/Icon'
import { Spinner } from '@lms/shared/ui/Spinner'
import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { trainerKeys } from '../../shell/queryKeys'
import { useUpdateTrainerSearch } from '../../shell/search'
import { CourseLifecycleBadge } from './CourseLifecycleBadge'
import { COURSE_FILTERS, difficultyColor, filterCourses, filterLabel } from './courseLogic'
import { courseListError, setCourseFilter, useCourseFilter, useCourseList } from './courseQueries'
import { UnderlineDropdown } from './UnderlineDropdown'

const FILTER_OPTIONS = COURSE_FILTERS.map((value) => ({ value, label: filterLabel(value) }))

/** "My Courses" card: availability filter and the own course list. */
export function CoursesSidebar({
  selectedId,
  searchable = false,
}: {
  selectedId: string | null
  searchable?: boolean
}) {
  const list = useCourseList()
  const filter = useCourseFilter()
  const updateSearch = useUpdateTrainerSearch()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const available = filterCourses(list.data ?? [], filter)
  const courses = available.filter(
    (course) =>
      !searchable ||
      course.courseName.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()),
  )

  const select = (courseId: string) => {
    updateSearch({ course: courseId })
    // Flutter reloaded the detail on every tap.
    void queryClient.invalidateQueries({ queryKey: trainerKeys.course(courseId) })
  }

  return (
    <div className="bp-course-list card flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between p-4">
        <h2 className="m-0 font-manrope text-lg leading-[24.3px] font-bold tracking-normal text-primary-blue">
          My Courses
        </h2>
        <span className="text-xs leading-[16.8px] text-gray">{courses.length} courses</span>
      </div>
      {searchable && (
        <label className="bp-course-search">
          <Icon name="search" size={17} />
          <input
            type="search"
            aria-label="Search courses"
            placeholder="Search courses…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
      )}
      <UnderlineDropdown
        label="Course availability"
        value={filter}
        options={FILTER_OPTIONS}
        onChange={setCourseFilter}
        expanded
        className="mx-4"
      />
      <div className="h-px shrink-0 bg-light-gray" />
      <div className="min-h-0 flex-1 overflow-y-auto">
        {list.isPending && courses.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <Spinner label="Loading courses" />
          </div>
        ) : list.isError ? (
          <div
            role="alert"
            className="flex h-full flex-col items-center justify-center p-4 text-center"
          >
            <Icon name="error_outline_rounded" size={32} className="text-accent-red" />
            <p className="m-0 mt-2 font-barlow leading-[21px] font-bold">Error loading courses</p>
            <p className="m-0 mt-1 text-xs leading-[16.8px] text-gray">
              {courseListError(list.error)}
            </p>
          </div>
        ) : courses.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center p-8 text-center">
            <Icon name="auto_stories_outlined" size={48} className="text-gray/50" />
            <p className="m-0 mt-3 font-barlow leading-[21px] font-medium text-gray">
              {search.trim() ? 'No matching courses' : 'No courses created yet'}
            </p>
            <p className="m-0 mt-2 text-xs leading-[16.8px] text-gray">
              {search.trim() ? (
                'Try a different search or course availability filter.'
              ) : (
                <>Upload a PDF and click &quot;Create Course&quot; to generate one.</>
              )}
            </p>
          </div>
        ) : (
          <ul className="m-0 list-none p-0" aria-label="My courses">
            {courses.map((course, index) => {
              const isSelected = course.courseId === selectedId
              return (
                <li key={course.courseId}>
                  {index > 0 && <div className="h-px bg-light-gray" />}
                  <button
                    type="button"
                    aria-current={isSelected || undefined}
                    title={course.courseName}
                    onClick={() => select(course.courseId)}
                    className={clsx(
                      'flex h-[62px] w-full items-center gap-3 pr-6 pl-4 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-blue-light',
                      'bp-course-row',
                      isSelected && 'bp-course-selected',
                      'hover:bg-[#1a1b20]/8',
                    )}
                  >
                    <Icon
                      name="menu_book"
                      size={24}
                      className={isSelected ? 'text-primary-blue' : 'text-gray'}
                    />
                    <span className="min-w-0 flex-1">
                      <span
                        className={clsx(
                          'block truncate font-barlow text-[15px] leading-[22.5px]',
                          isSelected
                            ? 'font-bold text-primary-blue'
                            : 'font-medium text-text-black',
                        )}
                      >
                        {course.courseName}
                      </span>
                      <span className="flex items-center justify-between">
                        <span
                          className="text-xs leading-[16.8px] font-bold"
                          style={{ color: difficultyColor(course.courseDifficulty) }}
                        >
                          {course.courseDifficulty}
                        </span>
                        <CourseLifecycleBadge course={course} />
                        {list.isFetching ? (
                          <Spinner size={12} strokeWidth={2} label="Refreshing courses" />
                        ) : (
                          <span className="text-xs leading-[16.8px] text-gray">
                            {course.moduleCount} module{course.moduleCount === 1 ? '' : 's'}
                          </span>
                        )}
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
