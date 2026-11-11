// The employee pickers render at most PICKER_ROW_LIMIT rows; search and counts use the full list.
import { parseEmployee, type Employee } from '@lms/shared/models'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { EmployeeMultiPickerDialog, EmployeePickerDialog } from './pickers'

const directory: Employee[] = Array.from({ length: 150 }, (_, i) =>
  parseEmployee({
    employee_id: `E${i + 1}`,
    name: `Person ${i + 1}`,
    department: 'Ops',
    status: 'active',
  }),
)

afterEach(cleanup)

describe('employee pickers in a big directory', () => {
  it('Add employees shows 100 rows, counts all, and finds a person past row 100', async () => {
    const user = userEvent.setup()
    const onPick = vi.fn()
    render(
      <EmployeeMultiPickerDialog
        open
        onOpenChange={() => {}}
        title="Add employees"
        actionLabel={(count) => `Add ${count}`}
        employees={directory}
        onPick={onPick}
      />,
    )
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getAllByRole('checkbox')).toHaveLength(100)
    expect(within(dialog).getByText('150 of 150 active employees')).toBeTruthy()
    expect(within(dialog).getByText(/Showing the first 100 of 150/)).toBeTruthy()

    await user.type(within(dialog).getByRole('searchbox'), 'E140')
    expect(within(dialog).getAllByRole('checkbox')).toHaveLength(1)
    expect(within(dialog).queryByText(/Showing the first/)).toBeNull()
    await user.click(within(dialog).getByRole('checkbox', { name: 'Person 140 (E140)' }))
    await user.click(within(dialog).getByRole('button', { name: 'Add 1' }))
    expect(onPick).toHaveBeenCalledWith([directory[139]])
  })

  it('the single employee picker caps rows and says when nothing matches', async () => {
    const user = userEvent.setup()
    const onPick = vi.fn()
    render(
      <EmployeePickerDialog
        open
        onOpenChange={() => {}}
        title="Add journey observer"
        employees={directory}
        onPick={onPick}
      />,
    )
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/Showing the first 100 of 150/)).toBeTruthy()
    expect(within(dialog).queryByText('Person 120')).toBeNull()
    await user.type(within(dialog).getByRole('searchbox'), 'E120')
    await user.click(within(dialog).getByText('Person 120'))
    expect(onPick).toHaveBeenCalledWith(directory[119])

    await user.clear(within(dialog).getByRole('searchbox'))
    await user.type(within(dialog).getByRole('searchbox'), 'zzz')
    expect(within(dialog).getByText('No employees match your search.')).toBeTruthy()
  })
})
