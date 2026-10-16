// Dart: frontend/test/performance_search_test.dart:50-83 (course browser). The other cases cover
// the contract in performance-contracts.md (c).
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { parseCourseListReport } from '../models/performance'
import { useReport } from './context'
import { CoursesView } from './CourseBrowser'
import { renderReport, stubReportApi, stubResize } from './testUtils'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const courses = (count: number) =>
  parseCourseListReport({
    courses: Array.from({ length: count }, (_, i) => ({
      course_id: `c${i}`,
      course_name: `Course ${i}`,
    })),
  }).courses

/**
 * Bumps employeeResetVersion the way "Clear filters" does. It shows once the access loaded: the
 * access versions are part of the context key, so the browser resets when they arrive.
 */
function ClearFilters() {
  const { dispatch, views } = useReport()
  if (views.length === 0) return null
  return (
    <button type="button" onClick={() => dispatch({ type: 'clearFilters' })}>
      Clear filters
    </button>
  )
}

function renderCourses(
  count: number,
  { width = 1392, isLoading = false, onOpenCourse = vi.fn() } = {},
) {
  stubResize(width)
  stubReportApi(['all_courses'], () => ({}))
  renderReport(
    <>
      <CoursesView courses={courses(count)} isLoading={isLoading} onOpenCourse={onOpenCourse} />
      <ClearFilters />
    </>,
  )
  return onOpenCourse
}

const accessLoaded = () => screen.findByRole('button', { name: 'Clear filters' })

it('finds every page, clears and opens the correct course at narrow width', async () => {
  const onOpen = renderCourses(30, { width: 375 })
  await accessLoaded()
  expect(screen.queryByText('Course 29')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Next course page' }))
  expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
  await userEvent.type(screen.getByRole('textbox'), 'c29')
  expect(screen.getByText('Course 29')).toBeInTheDocument()
  await userEvent.click(screen.getByText('Course 29'))
  expect(onOpen).toHaveBeenCalledWith('c29')
  await userEvent.click(screen.getByRole('button', { name: 'Clear course search' }))
  expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
})

it('shows the heading, the count and the pager range', async () => {
  renderCourses(30)
  await accessLoaded()
  expect(screen.getByText('Course performance')).toBeInTheDocument()
  expect(
    screen.getByText('Search a course, then open it to inspect module results.'),
  ).toBeInTheDocument()
  expect(screen.getByText('30 matching courses')).toBeInTheDocument()
  expect(screen.getByText('Showing 1–12 of 30')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Previous course page' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Next course page' }))
  await userEvent.click(screen.getByRole('button', { name: 'Next course page' }))
  expect(screen.getByText('Showing 25–30 of 30')).toBeInTheDocument()
  expect(screen.getByText('Page 3 of 3')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Next course page' })).toBeDisabled()
})

it('matches every search word in the name or the ID', async () => {
  renderCourses(30)
  await accessLoaded()
  const search = screen.getByPlaceholderText('Search courses by name or ID')
  await userEvent.type(search, 'course   c1')
  // c1 and c10-c19.
  expect(screen.getByText('11 matching courses')).toBeInTheDocument()
  expect(screen.queryByText('Showing 1–11 of 11')).not.toBeInTheDocument()
  await userEvent.clear(search)
  await userEvent.type(search, 'missing')
  expect(screen.getByText('0 matching courses')).toBeInTheDocument()
  expect(screen.getByText('No courses match your search and selected filters.')).toBeInTheDocument()
})

it('shows the loading text and no empty text while loading', async () => {
  renderCourses(0, { isLoading: true })
  expect(await screen.findByText('Loading courses…')).toBeInTheDocument()
  expect(
    screen.queryByText('No courses match your search and selected filters.'),
  ).not.toBeInTheDocument()
})

it('uses 2 columns at 850 and 1 below', async () => {
  renderCourses(2, { width: 850 })
  const grid = (await screen.findByText('Course 0')).closest('button')?.parentElement
  expect(grid).toHaveStyle({ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' })
  cleanup()
  renderCourses(2, { width: 849 })
  const narrow = (await screen.findByText('Course 0')).closest('button')?.parentElement
  expect(narrow).toHaveStyle({ gridTemplateColumns: 'repeat(1, minmax(0, 1fr))' })
})

it('clears the search and the page when the filters reset', async () => {
  renderCourses(30)
  await accessLoaded()
  const search = screen.getByPlaceholderText('Search courses by name or ID')
  await userEvent.click(screen.getByRole('button', { name: 'Next course page' }))
  await userEvent.type(search, 'course')
  await userEvent.click(screen.getByRole('button', { name: 'Next course page' }))
  expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
  expect(screen.getByPlaceholderText('Search courses by name or ID')).toHaveValue('')
  expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
})
