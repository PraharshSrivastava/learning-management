// Every modal window must sit above its own overlay, or the overlay dims it and takes its clicks.
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { CourseDetailDialog } from '../performance/CourseDetailDialog'
import { EmployeeDrawer } from '../performance/EmployeeDrawer'
import { renderReport, stubReportApi, stubResize } from '../performance/testUtils'
import { Dialog } from './Dialog'
import { OVERLAY_LAYER, WINDOW_LAYER } from './layers'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const layer = (name: string) => Number(name.replace('z-', ''))

function expectWindowAboveOverlay(window: HTMLElement) {
  const overlay = document.querySelector<HTMLElement>('.fixed.inset-0')
  expect(overlay).not.toBeNull()
  expect(overlay).toHaveClass(OVERLAY_LAYER)
  expect(window).toHaveClass(WINDOW_LAYER)
}

it('keeps the window layer above the overlay layer', () => {
  expect(layer(WINDOW_LAYER)).toBeGreaterThan(layer(OVERLAY_LAYER))
})

it('puts the shared dialog above its overlay', () => {
  render(
    <Dialog open onOpenChange={() => {}} title="Confirm">
      Body
    </Dialog>,
  )
  expectWindowAboveOverlay(screen.getByRole('dialog', { name: 'Confirm' }))
})

it('puts the Performance course detail and employee drawer above their overlays', async () => {
  stubResize()
  stubReportApi(['all_courses'], () => ({}))
  const { unmount } = renderReport(<CourseDetailDialog courseId="c1" onClose={() => {}} />)
  expectWindowAboveOverlay(await screen.findByRole('dialog'))
  unmount()

  renderReport(<EmployeeDrawer employeeId="e1" onClose={() => {}} onOpenAssignment={() => {}} />)
  expectWindowAboveOverlay(await screen.findByRole('dialog'))
})
