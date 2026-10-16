// Dart: frontend/test/report_filter_row_test.dart:7-38. jsdom has no layout, so the test checks
// the width the row gives each filter and the horizontal scroll container.
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ReportFilterRow } from './ReportFilterRow'
import { stubResize } from './testUtils'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const filters = (width: number) =>
  [0, 1, 2, 3, 4].map((index) => (
    <div key={index} data-testid={`filter-${index}`} style={{ width }}>
      Filter {index}
    </div>
  ))

it('five filters fill a wide row in one line', () => {
  stubResize(1500)
  const { container } = render(<ReportFilterRow>{filters}</ReportFilterRow>)
  // (1500 - 48) / 5: five filters and four 12 px gaps fill the row.
  for (let index = 0; index < 5; index++) {
    expect(screen.getByTestId(`filter-${index}`).style.width).toBe('290.4px')
  }
  const row = screen.getByTestId('filter-0').parentElement
  expect(row).toHaveClass('flex', 'w-max', 'items-start', 'gap-3')
  expect(container.firstElementChild).toHaveClass('overflow-x-auto', 'pb-2')
})

it('keeps the 210 px minimum and scrolls on narrow screens', () => {
  stubResize(500)
  const { container } = render(<ReportFilterRow>{filters}</ReportFilterRow>)
  for (let index = 0; index < 5; index++) {
    expect(screen.getByTestId(`filter-${index}`).style.width).toBe('210px')
  }
  expect(container.firstElementChild).toHaveClass('overflow-x-auto')
})
