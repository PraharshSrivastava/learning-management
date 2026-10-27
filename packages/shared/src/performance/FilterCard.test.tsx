// FilterCard wiring (performance_report_portal.dart:166-329) with the real picker and joined days
// box. Their own behavior is tested in SearchableFilter and JoinedDaysFilter tests.
import { cleanup, fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { useReport } from './context'
import { FilterCard } from './FilterCard'
import { renderReport, stubReportApi, stubResize } from './testUtils'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const options = {
  courses: [{ courseId: 'c1', courseName: 'Safety' }],
  departments: ['Finance'],
  mailingLists: ['Ops list'],
  journeysEnabled: false,
}

function Probe() {
  const { state, dispatch } = useReport()
  return (
    <>
      <output data-testid="filter">{JSON.stringify(state.filter)}</output>
      <output data-testid="reset">{state.employeeResetVersion}</output>
      <button
        type="button"
        onClick={() =>
          dispatch({ type: 'filter', filter: { ...state.filter, courseStatus: 'archived' } })
        }
      >
        Archive
      </button>
    </>
  )
}

const filter = () => JSON.parse(screen.getByTestId('filter').textContent ?? '{}')

async function setup() {
  stubReportApi(['all_courses'], () => ({}))
  renderReport(
    <>
      <FilterCard options={options} />
      <Probe />
    </>,
  )
  await screen.findByText('Filter reports')
}

/** Opens the picker of `field` (its accessible name) and picks `option`. */
async function pick(field: string, option: string | RegExp) {
  await userEvent.click(screen.getByRole('button', { name: field }))
  await userEvent.click(await screen.findByRole('button', { name: option }))
}

it('lists the options, applies each filter and counts the active ones', async () => {
  await setup()
  expect(screen.queryByText(/^\d+ active$/)).not.toBeInTheDocument()
  await pick('Course: All', /^Safety/)
  await pick('Department: All', 'Finance')
  await pick('Mailing list: All', 'Ops list')
  expect(filter()).toMatchObject({ courseId: 'c1', department: 'Finance', mailingList: 'Ops list' })
  expect(screen.getByText('3 active')).toBeInTheDocument()
  await pick('Department: Finance', 'All department options')
  expect(filter().department).toBeNull()
  expect(screen.getByText('2 active')).toBeInTheDocument()
})

it('applies joined days on Enter', async () => {
  await setup()
  const days = screen.getByLabelText('Joined within days')
  await userEvent.type(days, '30{Enter}')
  expect(filter().joinedLessThanDaysAgo).toBe(30)
  expect(screen.getByText('1 active')).toBeInTheDocument()
})

it('course availability has no All option and resets the other filters', async () => {
  await setup()
  await pick('Course: All', /^Safety/)
  await userEvent.click(screen.getByRole('button', { name: 'Course availability: Active' }))
  expect(await screen.findByText('3 matching options')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^All course availability/ })).toBeNull()
  await userEvent.click(screen.getByRole('button', { name: 'Disabled' }))
  expect(filter()).toMatchObject({ courseStatus: 'disabled', courseId: null })
  expect(screen.getByTestId('reset')).toHaveTextContent('1')
  // Archived courses show as Disabled.
  fireEvent.click(screen.getByRole('button', { name: 'Archive' }))
  expect(screen.getByRole('button', { name: 'Course availability: Disabled' })).toBeInTheDocument()
})

it('Clear all clears every filter and the joined days text', async () => {
  await setup()
  await pick('Course: All', /^Safety/)
  const days = screen.getByLabelText('Joined within days')
  await userEvent.type(days, '7{Enter}')
  expect(screen.getByText('2 active')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Clear all' }))
  expect(filter()).toMatchObject({ courseId: null, joinedLessThanDaysAgo: null })
  expect(screen.queryByText(/^\d+ active$/)).not.toBeInTheDocument()
  expect(screen.getByTestId('reset')).toHaveTextContent('1')
  expect(days).toHaveValue('')
})

it('gives the five filters one width from the row', async () => {
  stubResize(1500)
  await setup()
  const fields = [
    'Course availability: Active',
    'Course: All',
    'Department: All',
    'Mailing list: All',
  ].map((name) => screen.getByRole('button', { name }))
  for (const field of fields) expect(field.style.width).toBe('290.4px')
  const days = screen.getByLabelText('Joined within days').closest('[style]')
  expect((days as HTMLElement).style.width).toBe('290.4px')
})
