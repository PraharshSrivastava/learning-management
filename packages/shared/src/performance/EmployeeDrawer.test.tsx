// Dart: frontend/test/employee_summary_panel_test.dart:146-223 (the drawer tests).
import { fireEvent, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useReport } from './context'
import { EmployeeDrawer } from './EmployeeDrawer'
import { colors } from './format'
import { renderReport, stubReportApi, stubResize } from './testUtils'

const employee = {
  employee_id: 'e1',
  employee_name: 'Kavya Nair',
  department: 'Sales',
  assigned: 8,
  completed: 5,
  in_progress: 2,
  not_started: 1,
  completion_rate: 62.5,
  overdue: 1,
  due_soon: 2,
  average_score: 78.0,
  needs_attention: true,
  repeated_failures: 1,
}

const assignment = {
  assignment_id: 'a1',
  course_name: 'Client Conversations',
  status: 'completed',
  completed_modules: 3,
  total_modules: 3,
  completion_percent: 100,
  average_score: 85.0,
  deadline: '2026-09-22T12:00:00',
}

/** Opens the drawer after the access loads, as the portal does from a row click. */
function Host({
  onClose,
  onOpenAssignment,
}: {
  onClose: () => void
  onOpenAssignment: (id: string) => void
}) {
  const { accessLoading, dispatch } = useReport()
  const [employeeId, setEmployeeId] = useState<string | null>(null)
  return (
    <>
      {!accessLoading && (
        <button type="button" onClick={() => setEmployeeId('e 1')}>
          Open employee
        </button>
      )}
      <button type="button" onClick={() => dispatch({ type: 'search', search: 'other' })}>
        Change search
      </button>
      <button type="button" onClick={() => dispatch({ type: 'courseStatus', status: 'disabled' })}>
        Change course status
      </button>
      <EmployeeDrawer
        employeeId={employeeId}
        onClose={() => {
          onClose()
          setEmployeeId(null)
        }}
        onOpenAssignment={onOpenAssignment}
      />
    </>
  )
}

async function renderDrawer(detail: unknown, onOpenAssignment = vi.fn(), onClose = vi.fn()) {
  const fetchMock = stubReportApi(['all_courses'], (url) =>
    url.pathname.endsWith('/employees/e%201') ? detail : {},
  )
  renderReport(<Host onClose={onClose} onOpenAssignment={onOpenAssignment} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Open employee' }))
  return { fetchMock, onOpenAssignment, onClose }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('EmployeeDrawer', () => {
  it.each([1000, 375])(
    'shows the course breakdown and opens an assignment at %i px',
    async (width) => {
      stubResize(width - 48)
      const { fetchMock, onOpenAssignment } = await renderDrawer({
        employee,
        assignments: [assignment],
      })
      expect(await screen.findByText('Course breakdown')).toBeInTheDocument()
      expect(screen.getByRole('dialog', { name: 'Employee performance' })).toBeInTheDocument()
      expect(screen.getByText('Learning snapshot')).toBeInTheDocument()
      expect(screen.getByText('Repeated quiz failures · 1 course')).toBeInTheDocument()
      expect(screen.queryByText(/Quiz support needed/)).toBeNull()
      expect(screen.getByText('62.5%')).toBeInTheDocument()
      expect(screen.getByText('Employee ID: e1')).toBeInTheDocument()
      expect(
        screen.getByText(
          '1 courses within your current reporting scope. Select a course for module results.',
        ),
      ).toBeInTheDocument()
      // The table header shows only at 700 px and wider.
      expect(screen.queryByText('COURSE') != null).toBe(width - 48 >= 700)
      fireEvent.click(screen.getByText('Client Conversations'))
      expect(onOpenAssignment).toHaveBeenCalledWith('a1')
      const url = fetchMock.mock.calls
        .map(([input]) => new URL(String(input), 'http://localhost'))
        .find((item) => item.pathname.includes('/employees/'))!
      expect(url.pathname).toBe('/api/trainer/performance/employees/e%201')
      expect(url.searchParams.get('view')).toBe('all_courses')
      expect(url.searchParams.has('employee_id')).toBe(false)
    },
  )

  it('uses neutral zero signals and one missing score for a healthy empty drawer', async () => {
    stubResize()
    await renderDrawer({
      employee: {
        ...employee,
        assigned: 0,
        completed: 0,
        completion_rate: 0,
        overdue: 0,
        due_soon: 0,
        repeated_failures: 0,
        average_score: null,
      },
      assignments: [],
    })
    expect(await screen.findByText('Course breakdown')).toBeInTheDocument()
    for (const label of [
      '0 overdue',
      '0 due soon',
      '0 inactive courses',
      'Repeated quiz failures · 0 courses',
    ]) {
      expect(screen.getByText(label)).toHaveStyle({ color: colors.textSecondary })
    }
    expect(screen.getAllByText('-')).toHaveLength(1)
    expect(screen.getByText('Last activity: Not recorded')).toBeInTheDocument()
    expect(screen.getByText('No courses in the current reporting scope.')).toBeInTheDocument()
  })

  it('colors the signals that need attention', async () => {
    stubResize()
    await renderDrawer({ employee: { ...employee, inactive: 3 }, assignments: [] })
    expect(await screen.findByText('1 overdue')).toHaveStyle({ color: colors.red })
    expect(screen.getByText('2 due soon')).toHaveStyle({ color: colors.amber })
    expect(screen.getByText('3 inactive courses')).toHaveStyle({ color: colors.amber })
    expect(screen.getByText('Repeated quiz failures · 1 course')).toHaveStyle({
      color: colors.amber,
    })
  })

  it('shows the load error', async () => {
    stubResize()
    await renderDrawer(new Response('', { status: 404 }))
    expect(
      await screen.findByText(
        'Could not load employee detail. Unable to load performance data (404)',
      ),
    ).toBeInTheDocument()
  })

  it('closes from the close button and shows the guard after a context change', async () => {
    stubResize()
    const { onClose } = await renderDrawer({ employee, assignments: [] })
    await screen.findByText('Course breakdown')
    fireEvent.click(screen.getByRole('button', { name: 'Close employee detail' }))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Employee performance')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Open employee' }))
    await screen.findByText('Course breakdown')
    fireEvent.click(screen.getByText('Change search'))
    expect(screen.getByText('Course breakdown')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Change course status'))
    expect(screen.getByRole('dialog', { name: 'Performance access changed' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
