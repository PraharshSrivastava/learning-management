import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { downloadCsv } from './api'
import { useReport } from './context'
import { renderReport, stubReportApi } from './testUtils'
import { useCsvExport } from './useCsvExport'

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  downloadCsv: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

function Exports({ employeeParams = {} }: { employeeParams?: Record<string, string> }) {
  const { exportAssignments, exportEmployees } = useCsvExport()
  const { dispatch, state, views } = useReport()
  if (views.length === 0) return null
  return (
    <>
      <button type="button" onClick={() => void exportAssignments()}>
        Export assignments
      </button>
      <button type="button" onClick={() => void exportEmployees(employeeParams)}>
        Export employees
      </button>
      <button
        type="button"
        onClick={() => dispatch({ type: 'filter', filter: { ...state.filter, courseId: 'c2' } })}
      >
        Change course
      </button>
      <button type="button" onClick={() => dispatch({ type: 'status', status: 'overdue' })}>
        Overdue
      </button>
      <button type="button" onClick={() => dispatch({ type: 'search', search: ' Kavya ' })}>
        Search
      </button>
    </>
  )
}

const linked = { courseId: 'c1', status: null }

it('exports the assignment list without the page', async () => {
  const requests: URL[] = []
  stubReportApi(['all_courses'], (url) => {
    requests.push(url)
    return 'id,name\n1,Kavya'
  })
  renderReport(<Exports />, { linkedReport: linked })
  await userEvent.click(await screen.findByRole('button', { name: 'Overdue' }))
  await userEvent.click(screen.getByRole('button', { name: 'Search' }))
  await userEvent.click(screen.getByRole('button', { name: 'Export assignments' }))

  await waitFor(() => expect(downloadCsv).toHaveBeenCalledTimes(1))
  expect(downloadCsv).toHaveBeenCalledWith('id,name\n1,Kavya', 'performance-assignments.csv')
  const url = requests.at(-1)!
  expect(url.pathname).toBe('/api/trainer/performance/export')
  expect(Object.fromEntries(url.searchParams)).toEqual({
    view: 'all_courses',
    course_status: 'active',
    course_id: 'c1',
    status: 'overdue',
    search: 'Kavya',
    sort: 'deadline',
    descending: 'false',
  })
})

it('exports employees with the scope minus the employee and the panel params', async () => {
  const requests: URL[] = []
  stubReportApi(['combined'], (url) => {
    requests.push(url)
    return 'employee\nKavya'
  })
  renderReport(
    <Exports employeeParams={{ search: 'Kavya Nair', attention: 'needs_attention', page: '3' }} />,
    { app: 'employee', linkedReport: linked },
  )
  await userEvent.click(await screen.findByRole('button', { name: 'Export employees' }))

  await waitFor(() => expect(downloadCsv).toHaveBeenCalledTimes(1))
  expect(downloadCsv).toHaveBeenCalledWith('employee\nKavya', 'performance-employees.csv')
  const url = requests.at(-1)!
  expect(url.pathname).toBe('/api/employee/performance/employees/export')
  expect(Object.fromEntries(url.searchParams)).toEqual({
    view: 'combined',
    course_status: 'active',
    course_id: 'c1',
    search: 'Kavya Nair',
    attention: 'needs_attention',
    sort: 'employee',
    descending: 'false',
  })
})

it('drops the file and asks for a new export when the report context changed', async () => {
  let answer: (csv: string) => void = () => {}
  stubReportApi(['all_courses'], () => new Promise<string>((resolve) => (answer = resolve)))
  renderReport(<Exports />)
  await userEvent.click(await screen.findByRole('button', { name: 'Export assignments' }))
  await userEvent.click(screen.getByRole('button', { name: 'Change course' }))
  answer('id\n1')

  expect(await screen.findByText('Report access changed. Export again.')).toBeInTheDocument()
  expect(downloadCsv).not.toHaveBeenCalled()
})

it('shows the export failure with the status code', async () => {
  stubReportApi(['all_courses'], () => new Response('', { status: 500 }))
  renderReport(<Exports />)
  await userEvent.click(await screen.findByRole('button', { name: 'Export employees' }))
  expect(await screen.findByText('Unable to export employees (500)')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Export assignments' }))
  expect(await screen.findByText('Unable to export report (500)')).toBeInTheDocument()
  expect(downloadCsv).not.toHaveBeenCalled()
})
