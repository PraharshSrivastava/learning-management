// Email status of one course's assignment emails. Trainer app only. The server decides every
// status, label and count; this view only displays them.
import { useQuery, type QueryKey } from '@tanstack/react-query'
import clsx from 'clsx'
import { useDeferredValue, useState } from 'react'
import { apiRequest, errorMessage } from '../api/client'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { TextField } from '../ui/TextField'
import { useToast } from '../ui/Toast'
import { downloadCsv } from './api'
import { useReport, useViewAllowed } from './context'
import { Box } from './primitives'
import { scopeParams, without, type Params } from './state'

interface EmailRow {
  assignment_id: string
  notification_id: string | null
  employee_id: string
  employee_name: string
  email: string | null
  department: string | null
  state: string
  label: string
  detail: string
  note: string | null
  attempts: number | null
  max_attempts: number
  updated_at: string | null
  activity_label: string
  can_resend: boolean
  resend_needs_confirmation: boolean
  technical_detail: string | null
}

interface EmailReport {
  generated_at: string
  course_name: string | null
  can_resend: boolean
  total: number
  accepted_count: number
  failed_count: number
  not_started_count: number
  tiles: { key: string; label: string; count: number }[]
  banners: { kind: string; message: string }[]
  last_send_round: string | null
  matched: number
  page: number
  page_size: number
  rows: EmailRow[]
}

const BADGES: Record<string, string> = {
  accepted: 'bg-[#e6f6f1] text-[#067058]',
  sent_untracked: 'bg-[#e6f6f1] text-[#475467] border border-dashed border-[#067058]',
  logged_only: 'bg-white text-[#7a5200] border border-dashed border-[#7a5200]',
  queued: 'bg-brand-blue-100 text-[#175cd3]',
  in_batch: 'bg-brand-blue-700 text-white',
  retrying: 'bg-accent-light-orange text-[#7a5200]',
  gave_up: 'bg-[#b42318] text-white',
  unknown: 'bg-[#5b3e96] text-white',
  cancelled: 'bg-light-gray text-[#475467]',
  skipped: 'bg-white text-[#475467] border border-gray',
  no_record: 'bg-white text-[#475467] border border-dashed border-gray',
  unrecognised: 'bg-text-black text-white',
}

const BANNERS: Record<string, string> = {
  disabled: 'bg-accent-light-orange text-[#7a5200]',
  log: 'bg-accent-light-orange text-[#7a5200]',
  test: 'bg-brand-blue-100 text-primary-blue',
  worker: 'bg-[#b42318] text-white',
}

const COLUMNS = 'grid grid-cols-[2fr_0.9fr_1.45fr_0.6fr_1fr_2.5fr_1.05fr_0.8fr] gap-3'
const REFRESH_MS = 30_000

/** The Emails tab. It reports on one course at a time, so every number means one rollout. */
export function EmailsView() {
  const { state } = useReport()
  const courseId = state.filter.courseId
  if (courseId == null) {
    return (
      <Box className="py-16 text-center">
        <h3 className="m-0 text-lg font-bold">Choose a course</h3>
        <p className="m-0 mt-1 text-text-secondary">
          Pick a course in the filters above to see the status of its assignment emails.
        </p>
      </Box>
    )
  }
  return <CourseEmails key={courseId} courseId={courseId} />
}

function CourseEmails({ courseId }: { courseId: string }) {
  const { state, baseKey, get, getText, contextKey, isCurrent } = useReport()
  const allowed = useViewAllowed()
  const toast = useToast()
  const [tile, setTile] = useState('all')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search.trim())
  const [notStarted, setNotStarted] = useState(false)
  const [page, setPage] = useState(1)
  const [confirming, setConfirming] = useState<EmailRow | null>(null)
  const [resending, setResending] = useState(false)

  const filters: Params = { ...without(scopeParams(state), 'employee_id') }
  if (tile !== 'all') filters.tile = tile
  if (deferredSearch) filters.search = deferredSearch
  if (notStarted) filters.not_started = 'true'
  const params: Params = { ...filters, page: String(page) }

  const query = useQuery({
    queryKey: [...baseKey, 'emails', params] as QueryKey,
    queryFn: async () => (await get('emails', params)) as EmailReport,
    enabled: allowed,
    refetchInterval: REFRESH_MS,
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[2] === contextKey ? previous : undefined,
  })
  const report = query.data

  const changeFilter = (apply: () => void) => {
    apply()
    setPage(1)
  }

  const resendPath = (suffix: string, extra: Params = {}) => {
    const search = new URLSearchParams({
      view: state.reportView,
      course_status: state.filter.courseStatus,
      ...extra,
    })
    return `/api/trainer/performance/emails/${suffix}?${search.toString()}`
  }

  const run = async (send: () => Promise<unknown>) => {
    setResending(true)
    try {
      const reply = (await send()) as { resent: number; skipped: number }
      const skipped = reply.skipped ? ` ${reply.skipped} could not be resent.` : ''
      toast(
        `${reply.resent} ${reply.resent === 1 ? 'email' : 'emails'} added back to the queue.${skipped}`,
      )
    } catch (error) {
      toast(errorMessage(error), { tone: 'error' })
    } finally {
      setResending(false)
      setConfirming(null)
      void query.refetch()
    }
  }

  const resendOne = (row: EmailRow) =>
    run(() =>
      apiRequest(resendPath(`${encodeURIComponent(row.notification_id ?? '')}/resend`), {
        method: 'POST',
        json: { confirm_unknown: row.resend_needs_confirmation },
      }),
    )

  const resendAll = () =>
    run(() => apiRequest(resendPath('resend-failed', { course_id: courseId }), { method: 'POST' }))

  const exportCsv = async () => {
    const expected = contextKey
    try {
      const csv = await getText('emails/export', filters, 'Unable to export emails')
      if (!isCurrent(expected)) throw new Error('Report access changed. Export again.')
      downloadCsv(csv, 'email-status.csv')
    } catch (error) {
      toast(errorMessage(error), { tone: 'error' })
    }
  }

  if (report == null) {
    return query.error != null ? (
      <Box>
        <p className="m-0 text-accent-red">{errorMessage(query.error)}</p>
      </Box>
    ) : (
      <Box>
        <p className="m-0 text-text-secondary">Loading email status…</p>
      </Box>
    )
  }

  const percent = report.total ? Math.round((report.accepted_count / report.total) * 100) : 0
  const pages = Math.max(1, Math.ceil(report.matched / report.page_size))
  return (
    <div className="flex flex-col gap-4">
      {query.isRefetchError && (
        <div
          role="alert"
          className="rounded-[10px] bg-accent-light-orange p-3 font-semibold text-[#7a5200]"
        >
          Couldn't refresh. Showing data from {report.generated_at}.
        </div>
      )}
      {report.banners.map((banner) => (
        <div
          key={banner.kind}
          role="status"
          className={clsx('rounded-[10px] p-3 font-semibold', BANNERS[banner.kind])}
        >
          {banner.message}
        </div>
      ))}

      <Box>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="m-0 text-base font-bold">
              {report.accepted_count} of {report.total} assignment emails accepted by the mail
              server
            </h3>
            <p className="m-0 text-text-secondary">
              Course assignment email{report.course_name ? ` · ${report.course_name}` : ''}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon="refresh" onClick={() => void query.refetch()}>
              Refresh
            </Button>
            <Button variant="secondary" icon="download_outlined" onClick={() => void exportCsv()}>
              Download CSV
            </Button>
            {report.can_resend && (
              <Button
                disabled={report.failed_count === 0 || resending}
                onClick={() => void resendAll()}
              >
                Resend failed ({report.failed_count})
              </Button>
            )}
          </div>
        </div>
        <div
          role="progressbar"
          aria-label="Emails accepted by the mail server"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          className="mt-3 h-2.5 overflow-hidden rounded-[5px] bg-light-gray"
        >
          <div className="h-2.5 rounded-[5px] bg-primary-blue" style={{ width: `${percent}%` }} />
        </div>
        <div className="mt-2 flex flex-wrap justify-between gap-3 text-[13px] text-text-secondary">
          <span>
            “Sent to mail server” means the company mail server accepted the email. It does not
            confirm the email reached the inbox.
          </span>
          <span>
            {report.last_send_round ? `Last send round: ${report.last_send_round} · ` : ''}Data as
            of {report.generated_at}
          </span>
        </div>
      </Box>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(132px,1fr))] gap-2.5">
        {report.tiles.map((item) => (
          <button
            key={item.key}
            type="button"
            aria-pressed={tile === item.key}
            onClick={() => changeFilter(() => setTile(item.key))}
            className={clsx(
              'min-h-[84px] rounded-[10px] px-3.5 py-3 text-left focus-visible:outline-2 focus-visible:outline-brand-blue-light',
              tile === item.key
                ? 'border-2 border-primary-blue bg-brand-blue-100'
                : 'border border-input-border bg-white hover:bg-brand-blue-50',
            )}
          >
            <span className="block text-2xl font-semibold">{item.count}</span>
            <span className="block text-[13px] leading-[18px]">{item.label}</span>
          </button>
        ))}
      </div>

      <Box className="p-0!">
        <div className="flex flex-wrap items-end justify-between gap-3 border-b border-light-gray p-4">
          <div className="flex flex-1 flex-wrap items-end gap-3">
            <TextField
              dense
              type="search"
              label="Search employees"
              placeholder="Name or email"
              value={search}
              fieldClassName="min-w-[260px] flex-1 max-w-[360px]"
              onChange={(event) => changeFilter(() => setSearch(event.target.value))}
            />
            <Button
              variant="secondary"
              aria-pressed={notStarted}
              className={clsx(notStarted && 'bg-brand-blue-100!')}
              onClick={() => changeFilter(() => setNotStarted(!notStarted))}
            >
              Sent but not started ({report.not_started_count})
            </Button>
          </div>
          <span className="text-text-secondary">
            Showing {report.rows.length} of {report.matched}
          </span>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[1180px]">
            <div
              className={clsx(
                COLUMNS,
                'border-b border-light-gray bg-surface-secondary px-4 py-2.5 text-xs font-semibold text-text-secondary',
              )}
            >
              <div>Employee</div>
              <div>Department</div>
              <div>Email status</div>
              <div>Attempts</div>
              <div>Last update</div>
              <div>Details</div>
              <div>Course activity</div>
              <div />
            </div>
            {report.rows.map((row) => (
              <div
                key={row.assignment_id}
                className={clsx(COLUMNS, 'items-center border-b border-light-gray px-4 py-3')}
              >
                <div className="min-w-0">
                  <div className="font-semibold">{row.employee_name}</div>
                  <div className="text-[13px] wrap-anywhere text-text-secondary">
                    {row.email ?? '—'}
                  </div>
                </div>
                <div>{row.department ?? '—'}</div>
                <div>
                  <span
                    className={clsx(
                      'inline-block rounded-[20px] px-2.5 py-[3px] text-xs font-semibold',
                      BADGES[row.state],
                    )}
                  >
                    {row.label}
                  </span>
                </div>
                <div>{row.attempts != null ? `${row.attempts} of ${row.max_attempts}` : '—'}</div>
                <div className="text-[13px] text-text-secondary">{row.updated_at ?? '—'}</div>
                <div className="text-[13px] wrap-anywhere">
                  <div>{row.detail}</div>
                  {row.note && <div className="mt-[3px] text-[#7a5200]">{row.note}</div>}
                  {row.technical_detail && (
                    <details className="mt-[3px] text-text-secondary">
                      <summary className="cursor-pointer">Technical details</summary>
                      {row.technical_detail}
                    </details>
                  )}
                </div>
                <div className="text-[13px]">{row.activity_label}</div>
                <div>
                  {row.can_resend && (
                    <Button
                      variant="secondary"
                      aria-label={`Resend email to ${row.employee_name}`}
                      disabled={resending}
                      onClick={() =>
                        row.resend_needs_confirmation ? setConfirming(row) : void resendOne(row)
                      }
                    >
                      Resend
                    </Button>
                  )}
                </div>
              </div>
            ))}
            {report.rows.length === 0 && (
              <p className="m-0 px-4 py-10 text-center text-text-secondary">
                No employees match this view.
              </p>
            )}
          </div>
        </div>
        {pages > 1 && (
          <div className="flex items-center justify-end gap-3 p-3">
            <Button variant="text" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <span>
              Page {page} of {pages}
            </span>
            <Button variant="text" disabled={page >= pages} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        )}
      </Box>

      <Dialog
        open={confirming != null}
        onOpenChange={(open) => {
          if (!open) setConfirming(null)
        }}
        title="Resend this email?"
        width={460}
        actions={
          <>
            <Button variant="text" onClick={() => setConfirming(null)}>
              Don't resend
            </Button>
            <Button
              loading={resending}
              onClick={() => {
                if (confirming) void resendOne(confirming)
              }}
            >
              Resend anyway
            </Button>
          </>
        }
      >
        <p className="m-0">
          We can't tell whether the earlier email to {confirming?.employee_name} went out. It may
          already have been delivered, so resending could send a second copy.
        </p>
        <p className="m-0 mt-2 text-[13px] text-text-secondary">
          To be certain first, IT can check the mail server's message trace for this employee.
        </p>
      </Dialog>
    </div>
  )
}
