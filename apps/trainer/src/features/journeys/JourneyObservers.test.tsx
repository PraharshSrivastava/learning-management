import { parseEmployee } from '@lms/shared/models'
import { cleanup, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderCourses } from '../courses/test/renderCourses'
import type { JourneyObserver } from './api'
import { JourneyObservers, observersIncomplete } from './JourneyObservers'

const employees = [
  { employee_id: 'e1', name: 'Meera Iyer', department: 'Compliance', status: 'active' },
  { employee_id: 'e2', name: 'Dev Patel', department: 'Sales', status: 'active' },
].map(parseEmployee)

const changes: JourneyObserver[][] = []

function Harness() {
  const [value, setValue] = useState<JourneyObserver[]>([
    { observerEmployeeId: 'e1', employeeIds: ['e2'], departmentIds: [] },
  ])
  return (
    <JourneyObservers
      value={value}
      employees={employees}
      onChange={(next) => {
        changes.push(next)
        setValue(next)
      }}
    />
  )
}

beforeEach(() => {
  changes.length = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://localhost').pathname
      if (path.endsWith('/api/observer/options'))
        return new Response(
          JSON.stringify({ departments: [{ department_id: 'd1', name: 'Sales' }] }),
        )
      return new Response('{}', { status: 404 })
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('JourneyObservers', () => {
  it('edits an observer in place; the journey saves it', async () => {
    const user = userEvent.setup()
    renderCourses(Harness)
    const observer = await screen.findByRole('region', { name: 'Observer Meera Iyer' })
    expect(within(observer).getByText('Dev Patel')).toBeInTheDocument()
    // No separate save: Observers are saved with the journey.
    expect(screen.queryByRole('button', { name: 'Save observers' })).not.toBeInTheDocument()

    await user.click(within(observer).getByRole('button', { name: 'Departments' }))
    await user.click(await screen.findByRole('checkbox', { name: 'Sales' }))
    await user.click(screen.getByRole('button', { name: 'Apply' }))
    expect(within(observer).getByText('Sales')).toBeInTheDocument()
    expect(changes.at(-1)).toEqual([
      { observerEmployeeId: 'e1', employeeIds: ['e2'], departmentIds: ['d1'] },
    ])
  })

  it('flags an observer who watches no one', () => {
    expect(
      observersIncomplete([{ observerEmployeeId: 'e1', employeeIds: [], departmentIds: [] }]),
    ).toBe(true)
    expect(
      observersIncomplete([{ observerEmployeeId: 'e1', employeeIds: ['e2'], departmentIds: [] }]),
    ).toBe(false)
  })
})
