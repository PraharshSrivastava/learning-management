import { parseEmployee } from '@lms/shared/models'
import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderCourses } from '../courses/test/renderCourses'
import { JourneyObservers } from './JourneyObservers'

const employees = [
  { employee_id: 'e1', name: 'Meera Iyer', department: 'Compliance', status: 'active' },
  { employee_id: 'e2', name: 'Dev Patel', department: 'Sales', status: 'active' },
].map(parseEmployee)

const puts: unknown[] = []

beforeEach(() => {
  puts.length = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), 'http://localhost').pathname
      const json = (body: unknown) => new Response(JSON.stringify(body))
      if (path.endsWith('/api/observer/options'))
        return json({ departments: [{ department_id: 'd1', name: 'Sales' }] })
      if (path.endsWith('/api/learning-journeys/j1/observers')) {
        if (init?.method === 'PUT') {
          puts.push(JSON.parse(String(init.body)))
          return json({ observers: [] })
        }
        return json({
          observers: [{ observer_employee_id: 'e1', employee_ids: ['e2'], department_ids: [] }],
        })
      }
      return new Response('{}', { status: 404 })
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('JourneyObservers', () => {
  it('lets an observer watch a department and saves the selection', async () => {
    const user = userEvent.setup()
    renderCourses(() => <JourneyObservers journeyId="j1" employees={employees} />)
    const observer = await screen.findByRole('region', { name: 'Observer Meera Iyer' })
    expect(within(observer).getByText('Dev Patel')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save observers' })).toBeDisabled()

    await user.click(within(observer).getByRole('button', { name: 'Departments' }))
    await user.click(await screen.findByRole('checkbox', { name: 'Sales' }))
    await user.click(screen.getByRole('button', { name: 'Apply' }))
    expect(within(observer).getByText('Sales')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Save observers' }))
    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0]).toEqual({
      observers: [{ observer_employee_id: 'e1', employee_ids: ['e2'], department_ids: ['d1'] }],
    })
  })
})
