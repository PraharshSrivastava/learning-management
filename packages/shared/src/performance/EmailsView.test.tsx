import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { PerformanceReport } from './PerformanceReport'
import { renderReport, stubReportApi, stubResize } from './testUtils'

beforeEach(() => stubResize())

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const row = (overrides: Record<string, unknown>) => ({
  assignment_id: 'a1',
  notification_id: 'n1',
  employee_id: 'e1',
  employee_name: 'Ananya Mehta',
  email: 'ananya@example.com',
  department: 'Risk',
  state: 'accepted',
  label: 'Sent to mail server',
  detail: 'The mail server accepted this email.',
  note: null,
  attempts: 1,
  max_attempts: 5,
  updated_at: '11 Nov 2026, 10:07 AM IST',
  activity_state: 'not_started',
  activity_label: 'Not started',
  activity_percent: 0,
  can_resend: false,
  resend_needs_confirmation: false,
  technical_detail: null,
  ...overrides,
})

const report = (overrides: Record<string, unknown> = {}) => ({
  generated_at: '11 Nov 2026, 10:42 AM IST',
  course_id: 'c1',
  course_name: 'AML Training',
  can_resend: true,
  total: 3,
  accepted_count: 1,
  failed_count: 1,
  not_started_count: 1,
  tiles: [
    { key: 'all', label: 'All employees', count: 3 },
    { key: 'accepted', label: 'Sent to mail server', count: 1 },
    { key: 'gave_up', label: 'Failed, gave up', count: 1 },
    { key: 'unknown', label: 'Outcome unknown', count: 1 },
  ],
  banners: [],
  last_send_round: '11 Nov 2026, 10:40 AM IST',
  matched: 3,
  page: 1,
  page_size: 50,
  rows: [
    row({
      assignment_id: 'a2',
      notification_id: 'n2',
      employee_name: 'Farhan Qureshi',
      state: 'gave_up',
      label: 'Failed, gave up',
      detail: "The mail server says this mailbox doesn't exist.",
      can_resend: true,
    }),
    row({
      assignment_id: 'a3',
      notification_id: 'n3',
      employee_name: 'Lata Bhatt',
      state: 'unknown',
      label: 'Outcome unknown',
      detail: 'Sending was interrupted. This email may or may not have gone out.',
      can_resend: true,
      resend_needs_confirmation: true,
    }),
    row({}),
  ],
  ...overrides,
})

const requests: { url: URL; init: RequestInit | undefined }[] = []

function stub(answer: () => unknown = () => report()) {
  requests.length = 0
  return stubReportApi(['all_courses', 'my_courses'], (url, init) => {
    requests.push({ url, init })
    if (url.pathname.endsWith('/resend') || url.pathname.endsWith('/resend-failed')) {
      return { resent: 1, skipped: 0 }
    }
    if (url.pathname.endsWith('/performance/emails')) return answer()
    return {}
  })
}

const emailRequests = () =>
  requests.filter(({ url }) => url.pathname.endsWith('/api/trainer/performance/emails'))

const linked = { courseId: 'c1', status: null, view: 'emails' as const }

it('asks for a course before showing anything', async () => {
  stub()
  renderReport(<PerformanceReport app="trainer" />, { withReport: false })
  await userEvent.click(await screen.findByRole('tab', { name: 'Emails' }))
  expect(screen.getByRole('heading', { name: 'Choose a course' })).toBeInTheDocument()
  expect(emailRequests()).toHaveLength(0)
})

it('is not offered in the employee app', async () => {
  stubReportApi(['combined'], () => ({}))
  renderReport(<PerformanceReport app="employee" />, { app: 'employee', withReport: false })
  await screen.findByRole('tab', { name: 'Overview' })
  expect(screen.queryByRole('tab', { name: 'Emails' })).not.toBeInTheDocument()
})

it('shows what the server recorded, without rewording it', async () => {
  stub()
  renderReport(<PerformanceReport app="trainer" linkedReport={linked} />, { withReport: false })
  expect(
    await screen.findByText('1 of 3 assignment emails accepted by the mail server'),
  ).toBeVisible()
  expect(screen.getByRole('tab', { name: 'Emails' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByText("The mail server says this mailbox doesn't exist.")).toBeVisible()
  expect(screen.getByText(/does not confirm the email reached the inbox/)).toBeVisible()
  expect(screen.getByText(/Data as of 11 Nov 2026, 10:42 AM IST/)).toBeVisible()
  expect(emailRequests().at(-1)?.url.searchParams.get('course_id')).toBe('c1')
})

it('shows delivery warnings', async () => {
  stub(() =>
    report({
      banners: [
        { kind: 'log', message: 'Log mode. Emails are written to the server log, not sent.' },
      ],
    }),
  )
  renderReport(<PerformanceReport app="trainer" linkedReport={linked} />, { withReport: false })
  expect(
    await screen.findByText('Log mode. Emails are written to the server log, not sent.'),
  ).toBeVisible()
})

it('filters on the server when a tile is chosen', async () => {
  stub()
  renderReport(<PerformanceReport app="trainer" linkedReport={linked} />, { withReport: false })
  await userEvent.click(await screen.findByRole('button', { name: /Failed, gave up/ }))
  await waitFor(() => expect(emailRequests().at(-1)?.url.searchParams.get('tile')).toBe('gave_up'))
})

it('filters to sent but not started', async () => {
  stub()
  renderReport(<PerformanceReport app="trainer" linkedReport={linked} />, { withReport: false })
  await userEvent.click(await screen.findByRole('button', { name: 'Sent but not started (1)' }))
  await waitFor(() =>
    expect(emailRequests().at(-1)?.url.searchParams.get('not_started')).toBe('true'),
  )
})

it('resends a failed email straight away', async () => {
  stub()
  renderReport(<PerformanceReport app="trainer" linkedReport={linked} />, { withReport: false })
  await userEvent.click(
    await screen.findByRole('button', { name: 'Resend email to Farhan Qureshi' }),
  )
  await waitFor(() => {
    const call = requests.find(({ url }) => url.pathname.endsWith('/n2/resend'))
    expect(JSON.parse(String(call?.init?.body))).toEqual({ confirm_unknown: false })
  })
})

it('warns about a possible duplicate before resending an unknown outcome', async () => {
  stub()
  renderReport(<PerformanceReport app="trainer" linkedReport={linked} />, { withReport: false })
  await userEvent.click(await screen.findByRole('button', { name: 'Resend email to Lata Bhatt' }))
  const dialog = await screen.findByRole('dialog')
  expect(within(dialog).getByText(/could send a second copy/)).toBeVisible()
  expect(requests.some(({ url }) => url.pathname.endsWith('/n3/resend'))).toBe(false)
  await userEvent.click(within(dialog).getByRole('button', { name: 'Resend anyway' }))
  await waitFor(() => {
    const call = requests.find(({ url }) => url.pathname.endsWith('/n3/resend'))
    expect(JSON.parse(String(call?.init?.body))).toEqual({ confirm_unknown: true })
  })
})

it('shows no resend controls to other trainers', async () => {
  stub(() =>
    report({
      can_resend: false,
      rows: [row({ email: 'an***@example.com', state: 'gave_up', label: 'Failed, gave up' })],
    }),
  )
  renderReport(<PerformanceReport app="trainer" linkedReport={linked} />, { withReport: false })
  expect(await screen.findByText('an***@example.com')).toBeVisible()
  expect(screen.queryByRole('button', { name: /Resend/ })).not.toBeInTheDocument()
})

it('keeps old data and says so when a refresh fails', async () => {
  let fail = false
  stub(() => (fail ? new Response('', { status: 500 }) : report()))
  renderReport(<PerformanceReport app="trainer" linkedReport={linked} />, { withReport: false })
  await screen.findByText('1 of 3 assignment emails accepted by the mail server')
  fail = true
  const refresh = screen.getAllByRole('button', { name: 'Refresh' }).at(-1)
  if (refresh) await userEvent.click(refresh)
  expect(
    await screen.findByText("Couldn't refresh. Showing data from 11 Nov 2026, 10:42 AM IST."),
  ).toBeVisible()
  expect(screen.getByText('1 of 3 assignment emails accepted by the mail server')).toBeVisible()
})
