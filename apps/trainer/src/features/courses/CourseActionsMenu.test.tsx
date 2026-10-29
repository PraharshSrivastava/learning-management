// Port of frontend/test/course_actions_menu_test.dart, plus the confirm flows.
import { parseCourse } from '@lms/shared/models'
import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ComponentProps } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { stubBrowser, stubFetch } from '../documents/test/renderDocuments'
import { CourseActionsMenu } from './CourseActionsMenu'
import { courseJson, owner, renderCourses } from './test/renderCourses'

beforeEach(() => stubBrowser())
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const menuFor = (
  overrides: Record<string, unknown>,
  props: Omit<ComponentProps<typeof CourseActionsMenu>, 'course'> = {},
) => {
  const course = parseCourse(courseJson(overrides))
  return function Menu() {
    return (
      <>
        <p>Mounted</p>
        <CourseActionsMenu course={course} {...props} />
      </>
    )
  }
}

const openMenu = async () => {
  await userEvent.click(await screen.findByRole('button', { name: 'Course actions' }))
  return screen.findByRole('menu')
}

describe('CourseActionsMenu', () => {
  describe('Assign excludes Enable, which its publish button already offers', () => {
    it('shows nothing for a disabled course with no other action', async () => {
      stubFetch(() => null)
      renderCourses(
        menuFor({ lifecycle_state: 'disabled' }, { directSingle: true, exclude: ['Enable'] }),
      )
      await screen.findByText('Mounted')
      expect(screen.queryByRole('button', { name: 'Enable' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Course actions' })).not.toBeInTheDocument()
    })
    it('still offers Disable directly for an active course', async () => {
      stubFetch(() => null)
      renderCourses(
        menuFor({ lifecycle_state: 'active' }, { directSingle: true, exclude: ['Enable'] }),
      )
      expect(await screen.findByRole('button', { name: 'Disable' })).toBeInTheDocument()
    })
  })
  describe('Blueprint direct single action', () => {
    it('shows Delete directly and keeps typed confirmation and cancellation intact', async () => {
      const fetchMock = stubFetch(() => null)
      renderCourses(menuFor({ lifecycle_state: 'draft', can_delete: true }, { directSingle: true }))
      await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
      expect(screen.queryByRole('button', { name: 'Course actions' })).not.toBeInTheDocument()
      const dialog = await screen.findByRole('dialog')
      expect(within(dialog).getByRole('button', { name: 'Delete' })).toBeDisabled()
      await userEvent.type(within(dialog).getByLabelText('Type DELETE'), 'DELETE')
      expect(within(dialog).getByRole('button', { name: 'Delete' })).toBeEnabled()
      await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
    })
    it('shows Disable directly with its current assignment impact', async () => {
      stubFetch((url) =>
        url.pathname.endsWith('/assignment')
          ? { lifecycle_revision: 3, total_assigned_count: 9 }
          : { observers: [] },
      )
      renderCourses(
        menuFor({ lifecycle_state: 'active', can_delete: false }, { directSingle: true }),
      )
      await userEvent.click(await screen.findByRole('button', { name: 'Disable' }))
      expect(await screen.findByText(/9 current employee assignments/)).toBeInTheDocument()
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })
    it('shows Enable directly and retains Assign navigation', async () => {
      stubFetch(() => null)
      const { search } = renderCourses(
        menuFor({ lifecycle_state: 'disabled', can_delete: false }, { directSingle: true }),
      )
      await userEvent.click(await screen.findByRole('button', { name: 'Enable' }))
      await waitFor(() => expect(search()).toMatchObject({ tab: 'assign', course: 'c1' }))
    })
    it('hides the control when no action is permitted', async () => {
      stubFetch(() => null)
      renderCourses(
        menuFor({ lifecycle_state: 'draft', can_delete: false }, { directSingle: true }),
      )
      await screen.findByText('Mounted')
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })
    it('retains the menu for multiple permitted actions', async () => {
      stubFetch(() => null)
      renderCourses(
        menuFor({ lifecycle_state: 'active', can_delete: true }, { directSingle: true }),
      )
      const menu = await openMenu()
      expect(within(menu).getByRole('menuitem', { name: 'Disable' })).toBeInTheDocument()
      expect(within(menu).getByRole('menuitem', { name: 'Delete' })).toBeInTheDocument()
    })
    it('hides direct controls from another trainer', async () => {
      stubFetch(() => null)
      renderCourses(menuFor({ lifecycle_state: 'active' }, { directSingle: true }), {
        person: { ...owner, trainerId: 'other' },
      })
      await screen.findByText('Mounted')
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })
    it('blocks the direct action while generation runs', async () => {
      stubFetch(() => null)
      renderCourses(
        menuFor(
          { lifecycle_state: 'active', generation: { status: 'running' } },
          { directSingle: true },
        ),
      )
      expect(await screen.findByRole('button', { name: 'Disable' })).toBeDisabled()
    })
  })
  const cases = {
    active: ['Disable'],
    disabled: ['Enable'],
    draft: ['Delete'],
  } as const
  for (const [state, expected] of Object.entries(cases)) {
    it(`${state} offers only eligible lifecycle actions`, async () => {
      stubFetch(() => null)
      renderCourses(menuFor({ lifecycle_state: state, can_delete: state === 'draft' }))
      const menu = await openMenu()
      for (const action of ['Disable', 'Enable', 'Archive', 'Restore', 'Delete']) {
        const item = within(menu).queryByRole('menuitem', { name: action })
        if ((expected as readonly string[]).includes(action)) expect(item).toBeInTheDocument()
        else expect(item).not.toBeInTheDocument()
      }
    })
  }

  it('keeps Delete disabled until DELETE is typed, and Cancel closes the dialog', async () => {
    const fetchMock = stubFetch(() => null)
    renderCourses(menuFor({ lifecycle_state: 'draft', can_delete: true }))
    await userEvent.click(within(await openMenu()).getByRole('menuitem', { name: 'Delete' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Delete Compliance Essentials?')).toBeInTheDocument()
    const confirm = within(dialog).getByRole('button', { name: 'Delete' })
    expect(confirm).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText('Type DELETE'), 'DELET')
    expect(confirm).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText('Type DELETE'), 'E')
    expect(confirm).toBeEnabled()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
  })

  it('deletes with the expected revision and clears the selection', async () => {
    const fetchMock = stubFetch(() => null)
    const { search } = renderCourses(menuFor({ lifecycle_state: 'draft', can_delete: true }), {
      url: '/?tab=blueprint&course=c1',
    })
    await userEvent.click(within(await openMenu()).getByRole('menuitem', { name: 'Delete' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('Type DELETE'), 'DELETE')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('Delete completed.')).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'DELETE')
    expect(String(call?.[0])).toContain('/api/courses/c1?expected_revision=3')
    expect(search().course).toBeUndefined()
  })

  it('deletes with Enter once DELETE is typed, and not before', async () => {
    const fetchMock = stubFetch(() => null)
    renderCourses(menuFor({ lifecycle_state: 'draft', can_delete: true }))
    await userEvent.click(within(await openMenu()).getByRole('menuitem', { name: 'Delete' }))
    const dialog = await screen.findByRole('dialog')
    const field = within(dialog).getByLabelText('Type DELETE')
    await userEvent.type(field, 'DELET{Enter}')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
    await userEvent.type(field, 'E{Enter}')
    expect(await screen.findByText('Delete completed.')).toBeInTheDocument()
    const calls = fetchMock.mock.calls.filter(([, init]) => init?.method === 'DELETE')
    expect(calls).toHaveLength(1)
    expect(String(calls[0]?.[0])).toContain('/api/courses/c1?expected_revision=3')
  })

  it('shows the Disable impact and posts the lifecycle action', async () => {
    const fetchMock = stubFetch((url) => {
      if (url.pathname.endsWith('/assignment')) {
        return { lifecycle_revision: 3, total_assigned_count: 9 }
      }
      if (url.pathname.endsWith('/observers')) {
        return { observers: [{ is_active: true }, { is_active: false }] }
      }
      return null
    })
    renderCourses(menuFor({ lifecycle_state: 'active' }))
    await userEvent.click(within(await openMenu()).getByRole('menuitem', { name: 'Disable' }))
    const dialog = await screen.findByRole('dialog')
    expect(
      within(dialog).getByText(
        /9 current employee assignments; 1 Observer selections are applied\./,
      ),
    ).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Disable' }))
    expect(await screen.findByText('Disable completed.')).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/lifecycle'))
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ action: 'disable', expected_revision: 3 })
  })

  it('stops when the revision changed since the list loaded', async () => {
    stubFetch((url) => (url.pathname.endsWith('/assignment') ? { lifecycle_revision: 4 } : {}))
    renderCourses(menuFor({ lifecycle_state: 'active' }))
    await userEvent.click(within(await openMenu()).getByRole('menuitem', { name: 'Disable' }))
    expect(
      await screen.findByText('Course availability changed. Refresh before continuing.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('Enable opens the Assign tab for the course', async () => {
    stubFetch(() => null)
    const { search } = renderCourses(menuFor({ lifecycle_state: 'disabled' }))
    await userEvent.click(within(await openMenu()).getByRole('menuitem', { name: 'Enable' }))
    await waitFor(() => expect(search()).toMatchObject({ tab: 'assign', course: 'c1' }))
  })

  it('Enable runs the Assign tab publish step when given', async () => {
    stubFetch(() => null)
    const onEnable = vi.fn(async () => {})
    const { search } = renderCourses(menuFor({ lifecycle_state: 'disabled' }, { onEnable }))
    await userEvent.click(within(await openMenu()).getByRole('menuitem', { name: 'Enable' }))
    await waitFor(() => expect(onEnable).toHaveBeenCalledOnce())
    expect(search().tab).not.toBe('assign')
  })

  it('tells the Assign tab about a change before the report refresh', async () => {
    stubFetch(() => null)
    const onChanged = vi.fn(async () => {})
    renderCourses(menuFor({ lifecycle_state: 'draft', can_delete: true }, { onChanged }))
    await userEvent.click(within(await openMenu()).getByRole('menuitem', { name: 'Delete' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('Type DELETE'), 'DELETE')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('Delete completed.')).toBeInTheDocument()
    expect(onChanged).toHaveBeenCalledWith('Delete')
  })

  it('another trainer has no mutation menu', async () => {
    stubFetch(() => null)
    renderCourses(menuFor({ lifecycle_state: 'active' }), {
      person: { ...owner, trainerId: 'other' },
    })
    await screen.findByText('Mounted')
    expect(screen.queryByRole('button', { name: 'Course actions' })).not.toBeInTheDocument()
  })

  it('is disabled while generation runs', async () => {
    stubFetch(() => null)
    renderCourses(menuFor({ lifecycle_state: 'active', generation: { status: 'running' } }))
    expect(await screen.findByRole('button', { name: 'Course actions' })).toBeDisabled()
  })
})
