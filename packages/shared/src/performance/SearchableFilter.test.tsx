// Dart: frontend/test/performance_search_test.dart:11-48 (pickers) and :113-131 (stale pick).
import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { useReport } from './context'
import { SearchableFilter } from './SearchableFilter'
import { renderReport, stubReportApi } from './testUtils'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const options = (label: string) =>
  Array.from({ length: 200 }, (_, i) => [`id${i}`, `${label} option ${i}`] as const)

for (const label of ['Course', 'Department', 'Mailing list']) {
  it(`${label} picker searches beyond the visible rows and clears only on selection`, async () => {
    stubReportApi(['all_courses'], () => ({}))
    const onChange = vi.fn()
    renderReport(
      <SearchableFilter
        label={label}
        value="id0"
        width={300}
        icon="search"
        items={options(label)}
        onChange={onChange}
      />,
    )
    const lower = label.toLowerCase()
    await userEvent.click(
      await screen.findByRole('button', { name: `${label}: ${label} option 0` }),
    )
    const dialog = screen.getByRole('dialog', { name: `Select ${lower}` })
    await userEvent.type(within(dialog).getByRole('searchbox'), `${label} option 199`)
    expect(
      within(dialog).getAllByRole('button', { name: new RegExp(`${label} option`) }),
    ).toHaveLength(1)
    expect(within(dialog).getByText('1 matching options')).toBeInTheDocument()
    expect(onChange).not.toHaveBeenCalled()
    await userEvent.click(within(dialog).getByRole('button', { name: new RegExp('option 199') }))
    expect(onChange).toHaveBeenLastCalledWith('id199')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: `${label}: ${label} option 0` }))
    const again = screen.getByRole('dialog', { name: `Select ${lower}` })
    expect(within(again).getByText('200 matching options')).toBeInTheDocument()
    await userEvent.type(within(again).getByRole('searchbox'), 'no such item')
    expect(within(again).getByText('No matching options.')).toBeInTheDocument()
    await userEvent.click(within(again).getByRole('button', { name: `All ${lower} options` }))
    expect(onChange).toHaveBeenLastCalledWith(null)
  })
}

it('shows the selected label, the course id subtitle and the check mark', async () => {
  stubReportApi(['all_courses'], () => ({}))
  renderReport(
    <SearchableFilter
      label="Course"
      value="c2"
      width={210}
      icon="menu_book_outlined"
      items={[
        ['c1', 'Course 1'],
        ['c2', 'Course 2'],
      ]}
      onChange={() => {}}
    />,
  )
  await userEvent.click(await screen.findByRole('button', { name: 'Course: Course 2' }))
  const row = screen.getByRole('button', { name: /Course 2/ })
  expect(within(row).getByText('c2')).toBeInTheDocument()
  expect(row.querySelector('svg')).not.toBeNull()
  expect(screen.getByRole('button', { name: /Course 1/ }).querySelector('svg')).toBeNull()
  await userEvent.type(screen.getByRole('searchbox'), 'c1')
  await userEvent.click(screen.getByRole('button', { name: 'Clear search' }))
  expect(screen.getByRole('searchbox')).toHaveValue('')
  await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('uses the empty texts for All and Choose', async () => {
  stubReportApi(['all_courses'], () => ({}))
  const items = [['all', 'All courses']] as const
  renderReport(
    <>
      <SearchableFilter
        label="Department"
        value={null}
        width={210}
        icon="search"
        items={items}
        onChange={() => {}}
      />
      <SearchableFilter
        label="Course availability"
        value={null}
        width={210}
        icon="search"
        items={items}
        allowAll={false}
        onChange={() => {}}
      />
      <SearchableFilter
        label="Course"
        value="gone"
        width={210}
        icon="search"
        items={items}
        onChange={() => {}}
      />
    </>,
  )
  expect(await screen.findByRole('button', { name: 'Department: All' })).toBeInTheDocument()
  await userEvent.click(
    screen.getByRole('button', { name: 'Course availability: Choose course availability' }),
  )
  expect(screen.queryByRole('button', { name: /All course availability options/ })).toBeNull()
  await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.getByRole('button', { name: 'Course: Selected Course' })).toBeInTheDocument()
})

function ChangeScope() {
  const { dispatch, state } = useReport()
  return (
    <button
      type="button"
      onClick={() => dispatch({ type: 'filter', filter: { ...state.filter, department: 'Ops' } })}
    >
      Change scope
    </button>
  )
}

it('picker ignores a selection after its report scope changes', async () => {
  stubReportApi(['all_courses'], () => ({}))
  const onChange = vi.fn()
  renderReport(
    <>
      <ChangeScope />
      <SearchableFilter
        label="Course"
        value={null}
        width={300}
        icon="search"
        items={[['c1', 'Course 1']]}
        onChange={onChange}
      />
    </>,
  )
  await userEvent.click(await screen.findByRole('button', { name: 'Course: All' }))
  expect(screen.getByRole('dialog', { name: 'Select course' })).toBeInTheDocument()
  // The open dialog makes the page inert, so the scope changes from outside the dialog.
  fireEvent.click(screen.getByText('Change scope'))
  expect(screen.getByRole('dialog', { name: 'Performance access changed' })).toBeInTheDocument()
  expect(screen.queryByText('Course 1')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(onChange).not.toHaveBeenCalled()
})
