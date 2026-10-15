// Ports of frontend/test/observer_refresh_test.dart.
import { configureApi } from '@lms/shared/api/client'
import { parseCourse, parseEmployee, type Employee } from '@lms/shared/models'
import { TooltipProvider } from '@lms/shared/ui/Tooltip'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { Reply, Requester } from './api'
import { ObserverPanel } from './ObserverPanel'

const course = parseCourse({ course_id: 'course', course_name: 'Test', status: 'published' })

const employee = (id: string, status = 'active'): Employee =>
  parseEmployee({ employee_id: id, name: id, status })

function config(revision: number, active: boolean) {
  return {
    course_id: 'course',
    revision,
    observers: [
      {
        observer_employee_id: 'observer',
        is_active: active,
        active: { employee_ids: active ? ['a'] : [], department_ids: [] },
        pending: { employee_ids: ['a'], department_ids: [] },
      },
    ],
  }
}

function panel(request: Requester, employees: Employee[], refreshGeneration = 0) {
  return (
    <TooltipProvider>
      <ObserverPanel
        course={course}
        employees={employees}
        refreshGeneration={refreshGeneration}
        isAssignmentActive
        request={request}
        onDraftObservers={() => {}}
      />
    </TooltipProvider>
  )
}

beforeEach(() => {
  configureApi({ app: 'trainer', publicMount: '/lms/trainer', configuredApiBase: undefined })
})

afterEach(cleanup)

describe('ObserverPanel', () => {
  it('Select all and Clear all update the employee scope; a searched Observer saves by id', async () => {
    const user = userEvent.setup()
    let savedPayload: { observers: Record<string, unknown>[] } | null = null
    const request: Requester = async (path, init = {}) => {
      if (path.endsWith('/options')) return { status: 200, body: { departments: [] } }
      if (init.method === 'PUT') savedPayload = init.json as typeof savedPayload
      return { status: 200, body: config(1, false) }
    }
    render(
      panel(
        request,
        ['observer', 'a', 'b', 'inactive'].map((id) =>
          employee(id, id === 'inactive' ? 'inactive' : 'active'),
        ),
      ),
    )

    await user.click(await screen.findByRole('button', { name: 'Employees (1)' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Select all' }))
    expect(within(dialog).getByText('3 selected')).toBeTruthy()
    expect(within(dialog).queryByText(/^inactive/)).toBeNull()
    await user.click(within(dialog).getByRole('button', { name: 'Clear all' }))
    expect(within(dialog).getByText('0 selected')).toBeTruthy()
    await user.click(within(dialog).getByRole('button', { name: 'Select all' }))
    await user.click(within(dialog).getByRole('button', { name: 'Done' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(screen.getByRole('button', { name: 'Employees (3)' })).toBeTruthy()

    await user.click(screen.getByRole('button', { name: 'Observer: observer' }))
    const picker = await screen.findByRole('dialog')
    expect(within(picker).queryByText('All observer options')).toBeNull()
    await user.type(within(picker).getByRole('searchbox'), 'b')
    await user.click(within(picker).getByRole('button', { name: 'b' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    await user.click(screen.getByRole('button', { name: 'Save Observers' }))
    await waitFor(() => expect(savedPayload).not.toBeNull())
    const rows = savedPayload!.observers
    expect(rows).toHaveLength(1)
    expect(rows[0]?.observer_employee_id).toBe('b')
    expect([...(rows[0]?.employee_ids as string[])].sort()).toEqual(['a', 'b', 'observer'])
  })

  it('a header refresh updates the Observer status and keeps the unsaved employee scope', async () => {
    const user = userEvent.setup()
    let revision = 1
    let active = false
    let reads = 0
    const request: Requester = async (path): Promise<Reply> => {
      if (path.endsWith('/options')) return { status: 200, body: { departments: [] } }
      reads++
      return { status: 200, body: config(revision, active) }
    }
    const employees = ['observer', 'a', 'b'].map((id) => employee(id))
    const view = render(panel(request, employees, 0))

    await user.click(await screen.findByRole('button', { name: 'Employees (1)' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('checkbox', { name: 'b ()' }))
    await user.click(within(dialog).getByRole('button', { name: 'Done' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(screen.getByRole('button', { name: 'Employees (2)' })).toBeTruthy()

    active = true
    revision = 2
    view.rerender(panel(request, employees, 1))
    await waitFor(() => expect(screen.getByText(/Your edits are preserved/)).toBeTruthy())
    expect(reads).toBe(2)
    expect(screen.getByRole('button', { name: 'Employees (2)' })).toBeTruthy()
    expect(screen.getByText(/Active access:/)).toBeTruthy()
  })
})
