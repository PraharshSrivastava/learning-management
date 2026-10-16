import { render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { OverlayProvider, useBlockingOverlay } from './overlay'

function Job() {
  const [active, setActive] = useState(false)
  useBlockingOverlay(active, 'Generating video')
  return (
    <button type="button" onClick={() => setActive(true)}>
      Start
    </button>
  )
}

describe('OverlayProvider', () => {
  it('makes the app behind the overlay inert while a job runs', async () => {
    render(
      <OverlayProvider>
        <Job />
      </OverlayProvider>,
    )
    const button = screen.getByRole('button', { name: 'Start' })
    expect(button.closest('[inert]')).toBeNull()
    button.click()
    expect(await screen.findByText('Generating video')).toBeInTheDocument()
    expect(button.closest('[inert]')).not.toBeNull()
    expect(screen.getByRole('alertdialog').closest('[inert]')).toBeNull()
  })
})
