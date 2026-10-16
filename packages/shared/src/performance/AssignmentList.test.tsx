// Port of frontend/test/employee_assignment_list_test.dart.
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { parseAssignmentReportRow } from '../models/performance'
import { AssignmentList } from './AssignmentList'
import { stubResize } from './testUtils'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const rows = [
  {
    assignment_id: 'assignment-1',
    employee_name: 'Kavya Nair',
    department: 'Sales',
    course_name: 'Client Conversations',
    completed_modules: 2,
    total_modules: 3,
    average_score: 75.0,
    deadline: '2026-09-19T00:00:00',
    last_learner_activity_at: '2026-09-17T00:00:00',
    status: 'overdue',
    due_soon: false,
  },
  {
    assignment_id: 'assignment-2',
    employee_name: 'Neha Bose',
    department: 'Operations',
    course_name: 'Product Knowledge',
    completed_modules: 3,
    total_modules: 3,
    average_score: 80.0,
    deadline: '2026-09-25T00:00:00',
    last_learner_activity_at: '2026-09-22T00:00:00',
    status: 'completed',
    due_soon: false,
  },
].map(parseAssignmentReportRow)

it('shows scannable columns and opens assignment', async () => {
  stubResize(1248)
  const opened = vi.fn()
  render(<AssignmentList rows={rows} onOpenAssignment={opened} />)
  expect(screen.getByText('EMPLOYEE')).toBeInTheDocument()
  expect(screen.getByText('QUIZ SCORE')).toBeInTheDocument()
  expect(screen.getByText('Kavya Nair')).toBeInTheDocument()
  expect(screen.getByText('2/3 modules')).toBeInTheDocument()
  expect(screen.getByText('75.0%')).toBeInTheDocument()
  expect(screen.getByText('19 Sep 2026')).toBeInTheDocument()
  expect(screen.getByText('Overdue')).toBeInTheDocument()
  await userEvent.click(screen.getByText('Kavya Nair'))
  expect(opened).toHaveBeenCalledWith('assignment-1')
})

it('stacks assignment details at narrow width', () => {
  stubResize(388)
  render(<AssignmentList rows={rows} onOpenAssignment={() => {}} />)
  expect(screen.queryByText('QUIZ SCORE')).not.toBeInTheDocument()
  expect(screen.getByText('Client Conversations')).toBeInTheDocument()
  expect(screen.getByText('Score 75.0%')).toBeInTheDocument()
})

it('shows the access line when the course is not available', () => {
  stubResize(1248)
  const [row] = rows
  render(
    <AssignmentList
      rows={[{ ...row!, accessAvailable: false, courseStatus: 'archived' }]}
      onOpenAssignment={() => {}}
    />,
  )
  expect(screen.getByText('Access unavailable · archived')).toBeInTheDocument()
})
