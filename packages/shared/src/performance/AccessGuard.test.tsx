import * as RadixDialog from '@radix-ui/react-dialog'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { AccessGuard, NoAccess } from './AccessGuard'
import { useReport } from './context'
import { renderReport, stubReportApi } from './testUtils'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function Detail({ onClose }: { onClose: () => void }) {
  const { contextKey, dispatch, state } = useReport()
  const [expected] = useState(contextKey)
  return (
    <>
      <button
        type="button"
        onClick={() => dispatch({ type: 'filter', filter: { ...state.filter, courseId: 'c2' } })}
      >
        Change filter
      </button>
      <RadixDialog.Root open modal={false}>
        <RadixDialog.Portal>
          <AccessGuard expected={expected} onClose={onClose}>
            <RadixDialog.Content aria-describedby={undefined}>
              <RadixDialog.Title>Assignment detail</RadixDialog.Title>
            </RadixDialog.Content>
          </AccessGuard>
        </RadixDialog.Portal>
      </RadixDialog.Root>
    </>
  )
}

it('shows the detail, then the guard text when the report context changes', async () => {
  stubReportApi(['all_courses'], () => ({}))
  const onClose = vi.fn()
  renderReport(<Detail onClose={onClose} />)
  expect(await screen.findByRole('dialog', { name: 'Assignment detail' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Change filter' }))
  expect(screen.getByRole('dialog', { name: 'Performance access changed' })).toBeInTheDocument()
  expect(screen.getByText('Close this detail and refresh your current view.')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(onClose).toHaveBeenCalledTimes(1)
})

it('uses the app text for no access', () => {
  const { rerender } = render(<NoAccess app="trainer" />)
  expect(screen.getByText('Performance access unavailable')).toBeInTheDocument()
  rerender(<NoAccess app="employee" />)
  expect(screen.getByText('Performance access is unavailable.')).toBeInTheDocument()
})
