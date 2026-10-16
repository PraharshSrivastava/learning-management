// Dart: frontend/test/report_filter_row_test.dart:40-80 (day entry) and the joined.clear() calls
// in performance_report_portal.dart:159, :230 and :265.
import { cleanup, fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { useReport } from './context'
import { JoinedDaysFilter } from './JoinedDaysFilter'
import { renderReport, stubReportApi } from './testUtils'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function Probe() {
  const { state, dispatch } = useReport()
  return (
    <>
      <output data-testid="joined">{String(state.filter.joinedLessThanDaysAgo)}</output>
      <button type="button" onClick={() => dispatch({ type: 'clearFilters' })}>
        Clear all
      </button>
    </>
  )
}

it('applies the days on Enter and clears the text on a filter reset', async () => {
  stubReportApi(['all_courses'], () => ({}))
  renderReport(
    <>
      <JoinedDaysFilter width={210} />
      <Probe />
    </>,
  )
  const input = await screen.findByLabelText('Joined within days')
  expect(input).toHaveAttribute('placeholder', 'Enter days')
  expect(input.parentElement?.parentElement).toHaveStyle({ width: '210px' })
  await userEvent.type(input, '3a0')
  expect(input).toHaveValue('30')
  expect(screen.getByTestId('joined')).toHaveTextContent('null')
  await userEvent.type(input, '{Enter}')
  expect(screen.getByTestId('joined')).toHaveTextContent('30')
  expect(input).not.toHaveFocus()

  fireEvent.click(screen.getByRole('button', { name: 'Clear all' }))
  expect(input).toHaveValue('')
  expect(screen.getByTestId('joined')).toHaveTextContent('null')
})

it('clears the filter when Enter is pressed on empty text', async () => {
  stubReportApi(['all_courses'], () => ({}))
  renderReport(
    <>
      <JoinedDaysFilter width={210} />
      <Probe />
    </>,
  )
  const input = await screen.findByLabelText('Joined within days')
  await userEvent.type(input, '7{Enter}')
  expect(screen.getByTestId('joined')).toHaveTextContent('7')
  await userEvent.clear(input)
  await userEvent.type(input, '{Enter}')
  expect(screen.getByTestId('joined')).toHaveTextContent('null')
})
