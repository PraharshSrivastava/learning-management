// RTL tests for the Assign tab course actions menu.
import { createQueryClient } from '@lms/shared/api/queryClient'
import { SessionProvider } from '@lms/shared/auth/session'
import { parseCourse } from '@lms/shared/models'
import { ToastProvider } from '@lms/shared/ui/Toast'
import { TooltipProvider } from '@lms/shared/ui/Tooltip'
import { QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Trainer } from '../../auth/trainer'
import type { Reply, RequestInit, Requester } from './api'
import { CourseActionsMenu } from './CourseActionsMenu'

const trainer: Trainer = { trainerId: 't1', name: 'Kiran Rao', status: 'active' }

function setup(overrides: Record<string, unknown>) {
  const course = parseCourse({
    course_id: 'c1',
    course_name: 'Compliance',
    status: 'published',
    trainer_id: 't1',
    lifecycle_revision: 3,
    ...overrides,
  })
  const calls: { path: string; init: RequestInit }[] = []
  const request: Requester = async (path, init = {}): Promise<Reply> => {
    calls.push({ path, init })
    if (path.endsWith('/assignment')) {
      return { status: 200, body: { lifecycle_revision: 3, total_assigned_count: 9 } }
    }
    if (path.endsWith('/observers')) {
      return { status: 200, body: { observers: [{ is_active: true }, { is_active: false }] } }
    }
    return { status: 200, body: {} }
  }
  const onChanged = vi.fn(async () => {})
  const onEnable = vi.fn(async () => {})
  render(
    <QueryClientProvider client={createQueryClient()}>
      <SessionProvider initialPerson={trainer}>
        <TooltipProvider>
          <ToastProvider>
            <CourseActionsMenu
              course={course}
              request={request}
              onEnable={onEnable}
              onChanged={onChanged}
            />
          </ToastProvider>
        </TooltipProvider>
      </SessionProvider>
    </QueryClientProvider>,
  )
  return { calls, onChanged, onEnable }
}

const choose = async (action: string) => {
  await userEvent.click(screen.getByRole('button', { name: 'Course actions' }))
  await userEvent.click(within(await screen.findByRole('menu')).getByRole('menuitem', { name: action }))
}

afterEach(cleanup)

describe('CourseActionsMenu', () => {
  it('opens and disables with the impact numbers and the expected revision', async () => {
    const { calls, onChanged } = setup({ lifecycle_state: 'active' })
    await choose('Disable')
    const dialog = await screen.findByRole('dialog')
    expect(
      within(dialog).getByText(/9 current employee assignments; 1 Observer selections/),
    ).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Disable' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith('Disable'))
    const post = calls.find((call) => call.init.method === 'POST')
    expect(post?.path).toBe('/api/courses/c1/lifecycle')
    expect(post?.init.json).toEqual({ action: 'disable', expected_revision: 3 })
  })

  it('deletes only after DELETE is typed', async () => {
    const { calls, onChanged } = setup({ lifecycle_state: 'draft', can_delete: true })
    await choose('Delete')
    const dialog = await screen.findByRole('dialog')
    const confirm = within(dialog).getByRole('button', { name: 'Delete' })
    expect(confirm).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText('Type DELETE'), 'DELETE')
    await userEvent.click(confirm)
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith('Delete'))
    expect(calls.some((call) => call.init.method === 'DELETE')).toBe(true)
  })

  it('Enable hands over to the Assign flow', async () => {
    const { onEnable } = setup({ lifecycle_state: 'disabled' })
    await choose('Enable')
    await waitFor(() => expect(onEnable).toHaveBeenCalled())
  })
})
