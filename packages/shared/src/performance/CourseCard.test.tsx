// The Flutter tests have no course card case. These cover the contract in
// performance-contracts.md (c) and performance_report_portal.dart:836-942.
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { parseCourseListReport } from '../models/performance'
import { CourseCard } from './CourseCard'

afterEach(cleanup)

const course = (fields: Record<string, unknown>) =>
  parseCourseListReport({ courses: [{ course_id: 'c1', ...fields }] }).courses[0]!

it('shows the name, the truncated rate and the counts, and opens on click', async () => {
  const onClick = vi.fn()
  render(
    <CourseCard
      course={course({
        course_name: 'Risk Basics',
        completion_rate: 66.9,
        assigned: 9,
        completed: 6,
        overdue: 2,
      })}
      onClick={onClick}
    />,
  )
  expect(screen.getByText('Risk Basics')).toBeInTheDocument()
  expect(screen.getByText('66%')).toBeInTheDocument()
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '66')
  expect(screen.getByText('9')).toBeInTheDocument()
  expect(screen.getByText('assigned')).toBeInTheDocument()
  expect(screen.getByText('6')).toBeInTheDocument()
  expect(screen.getByText('2')).toHaveStyle({ color: '#d92d20' })
  await userEvent.click(screen.getByText('Risk Basics'))
  expect(onClick).toHaveBeenCalledOnce()
})

it("clamps the rate to 0..100 and names a course without a name 'Course'", () => {
  render(<CourseCard course={course({ completion_rate: 140 })} onClick={vi.fn()} />)
  expect(screen.getByText('Course')).toBeInTheDocument()
  expect(screen.getByText('100%')).toBeInTheDocument()
})
