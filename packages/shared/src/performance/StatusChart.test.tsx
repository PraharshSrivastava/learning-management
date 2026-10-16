import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { StatusChart } from './StatusChart'
import { stubResize } from './testUtils'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const summary = { assigned: 20, pending: 6, started: 5, completed: 5, overdue: 4 }

it('names every status with its count', () => {
  stubResize(800)
  render(<StatusChart summary={summary} />)
  const legend = screen.getByRole('list')
  const items = within(legend).getAllByRole('listitem')
  expect(items.map((item) => item.textContent)).toEqual([
    'Pending6',
    'Started5',
    'Completed5',
    'Overdue4',
  ])
  expect(screen.getByLabelText('Assignment status')).toBeInTheDocument()
})

it('is hidden when nothing is assigned', () => {
  stubResize(800)
  const { container } = render(
    <StatusChart summary={{ assigned: 0, pending: 0, started: 0, completed: 0, overdue: 0 }} />,
  )
  expect(container).toBeEmptyDOMElement()
})
