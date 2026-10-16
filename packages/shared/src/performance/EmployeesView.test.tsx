// The Flutter tests have no _employees case. These cover the contract in performance-contracts.md (d).
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { parseAssignmentListReport } from '../models/performance'
import { useReport } from './context'
import { EmployeesView } from './EmployeesView'
import { renderReport, stubReportApi, stubResize } from './testUtils'

// The panel has its own tests. Here it only shows that it got the callbacks.
vi.mock('./EmployeeSummaryPanel', () => ({
  EmployeeSummaryPanel: ({
    onOpenEmployee,
    onExport,
  }: {
    onOpenEmployee: (employeeId: string) => void
    onExport: (params: Record<string, string>) => Promise<void>
  }) => (
    <div>
      <p>Summary panel</p>
      <button onClick={() => onOpenEmployee('e7')}>open employee</button>
      <button onClick={() => void onExport({ sort: 'employee' })}>export employees</button>
    </div>
  ),
}))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function Summary() {
  const { state } = useReport()
  return <output aria-label="summary">{String(state.employeeSummary)}</output>
}

const assignments = parseAssignmentListReport({
  rows: [{ assignment_id: 'a1', employee_name: 'Kavya Nair', status: 'started' }],
  total: 1,
})

it('switches between the employee summary and the course assignments', async () => {
  stubResize()
  stubReportApi(['all_courses'], () => ({}))
  const onOpenEmployee = vi.fn()
  const onExport = vi.fn(async () => {})
  const onOpenAssignment = vi.fn()
  renderReport(
    <>
      <Summary />
      <EmployeesView
        assignments={assignments}
        onOpenAssignment={onOpenAssignment}
        onOpenEmployee={onOpenEmployee}
        onExportEmployees={onExport}
      />
    </>,
  )
  const summaryChip = screen.getByRole('button', { name: 'Employee summary' })
  const assignmentsChip = screen.getByRole('button', { name: 'Course assignments' })
  expect(summaryChip).toHaveAttribute('aria-pressed', 'true')
  expect(assignmentsChip).toHaveAttribute('aria-pressed', 'false')
  await userEvent.click(screen.getByRole('button', { name: 'open employee' }))
  expect(onOpenEmployee).toHaveBeenCalledWith('e7')
  await userEvent.click(screen.getByRole('button', { name: 'export employees' }))
  expect(onExport).toHaveBeenCalledWith({ sort: 'employee' })

  await userEvent.click(assignmentsChip)
  expect(screen.getByLabelText('summary')).toHaveTextContent('false')
  expect(screen.queryByText('Summary panel')).not.toBeInTheDocument()
  expect(screen.getByText('Employee assignments')).toBeInTheDocument()
  await userEvent.click(screen.getByText('Kavya Nair'))
  expect(onOpenAssignment).toHaveBeenCalledWith('a1')

  await userEvent.click(summaryChip)
  expect(screen.getByLabelText('summary')).toHaveTextContent('true')
  expect(screen.getByText('Summary panel')).toBeInTheDocument()
})
