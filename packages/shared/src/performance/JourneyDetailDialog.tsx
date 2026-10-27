// The journey detail dialog: the course detail dialog's layout, with the journey's course path
// in place of module outcomes and every learner below it.
import * as RadixDialog from '@radix-ui/react-dialog'
import { useRef, useState } from 'react'
import { errorMessage } from '../api/client'
import {
  parseJourneyDetailReport,
  type JourneyLearnerReport,
  type JourneyReport,
  type JourneyStepReport,
} from '../models/performance'
import { Button, IconButton } from '../ui/Button'
import { Icon, type IconName } from '../ui/icons/Icon'
import { ProgressBar } from '../ui/ProgressBar'
import { Spinner } from '../ui/Spinner'
import { TextField } from '../ui/TextField'
import { useToast } from '../ui/Toast'
import { AccessGuard } from './AccessGuard'
import { downloadBlob, downloadCsv, reportBlob, reportUrl } from './api'
import { StatusFilterChip } from './AssignmentsBox'
import { useReport, useReportQuery } from './context'
import { Ring } from './CourseDetailDialog'
import { colors, dMonY, initials, listStatusColor, matchesWords, mix } from './format'
import { scopeParams, without } from './state'
import { useElementWidth } from './useElementWidth'
import { OVERLAY_LAYER, WINDOW_LAYER } from '../ui/layers'

/** The learner's status, worded as on the course rows. Deadline flags win over progress. */
export function journeyStatusLabel(row: JourneyLearnerReport): string {
  if (row.status === 'overdue') return 'Overdue'
  if (row.status === 'completed') return 'Completed'
  if (row.status === 'removed') return 'Removed'
  if (row.status === 'waiting') return 'Waiting'
  if (row.dueSoon) return 'Due soon'
  if (row.inactive) return 'Inactive'
  return row.status === 'started' ? 'Started' : 'Pending'
}

const FILTERS: [string, (row: JourneyLearnerReport) => boolean][] = [
  ['All', () => true],
  ['Pending', (row) => row.status === 'pending'],
  ['Started', (row) => row.status === 'started'],
  ['Overdue', (row) => row.status === 'overdue'],
  ['Due soon', (row) => row.dueSoon],
  ['Completed', (row) => row.status === 'completed'],
  ['Waiting', (row) => row.status === 'waiting'],
  ['Removed', (row) => row.status === 'removed'],
]

const csvCell = (value: string | number | null) => {
  const text = value == null ? '' : String(value)
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

/** The learner rows as CSV, in the order and columns the table shows. */
export function journeyLearnersCsv(rows: JourneyLearnerReport[]): string {
  const header = [
    'Employee ID',
    'Name',
    'Department',
    'Status',
    'Required courses passed',
    'Required courses',
    'Current course',
    'Assigned on',
    'Deadline',
    'Last activity',
    'Completed on',
    'Certificate number',
  ]
  const lines = rows.map((row) =>
    [
      row.employeeId,
      row.employeeName,
      row.department ?? '',
      journeyStatusLabel(row),
      row.passedCount,
      row.requiredCount,
      row.currentCourseName ?? '',
      dMonY(row.assignedAt, ''),
      dMonY(row.deadline, ''),
      dMonY(row.lastLearnerActivityAt, ''),
      dMonY(row.completedAt, ''),
      row.certificateNumber ?? '',
    ]
      .map(csvCell)
      .join(','),
  )
  // A byte-order mark so Excel reads names with non-ASCII letters correctly.
  return '﻿' + [header.join(','), ...lines].join('\r\n')
}

export function JourneyDetailDialog({
  journeyId,
  onClose,
}: {
  journeyId: string | null
  onClose: () => void
}) {
  return (
    <RadixDialog.Root open={journeyId != null} onOpenChange={(open) => !open && onClose()}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={`fixed inset-0 ${OVERLAY_LAYER} bg-black/54`} />
        {journeyId != null && (
          <GuardedJourney key={journeyId} journeyId={journeyId} onClose={onClose} />
        )}
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}

function GuardedJourney({ journeyId, onClose }: { journeyId: string; onClose: () => void }) {
  const { contextKey } = useReport()
  const [expected] = useState(contextKey)
  return (
    <AccessGuard expected={expected} onClose={onClose}>
      <JourneyDialogContent journeyId={journeyId} onClose={onClose} />
    </AccessGuard>
  )
}

function JourneyDialogContent({ journeyId, onClose }: { journeyId: string; onClose: () => void }) {
  const { state } = useReport()
  // The course filter picks which journeys are listed; inside one journey every course shows.
  const detail = useReportQuery(
    'journeys/' + encodeURIComponent(journeyId),
    without(scopeParams(state), 'course_id'),
    parseJourneyDetailReport,
  )
  const opener = useRef<HTMLElement | null>(null)

  let body
  if (detail.error) {
    body = <StateMessage detail={errorMessage(detail.error)} onClose={onClose} />
  } else if (!detail.data) {
    body = (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    )
  } else {
    body = (
      <JourneyContent
        journey={detail.data.journey}
        steps={detail.data.steps}
        learners={detail.data.learners}
        onClose={onClose}
      />
    )
  }
  return (
    <RadixDialog.Content
      onOpenAutoFocus={() => {
        opener.current =
          document.activeElement instanceof HTMLElement ? document.activeElement : null
      }}
      onCloseAutoFocus={(event) => {
        const target = opener.current
        opener.current = null
        if (target?.isConnected) {
          event.preventDefault()
          target.focus()
        }
      }}
      aria-describedby={undefined}
      className={`fixed top-1/2 left-1/2 ${WINDOW_LAYER} flex h-[min(860px,calc(100%-32px))] w-[min(1120px,calc(100%-32px))] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-3xl bg-white focus:outline-none`}
    >
      {(detail.error || !detail.data) && (
        <RadixDialog.Title className="sr-only">Journey detail</RadixDialog.Title>
      )}
      {body}
    </RadixDialog.Content>
  )
}

function JourneyContent({
  journey,
  steps,
  learners,
  onClose,
}: {
  journey: JourneyReport
  steps: JourneyStepReport[]
  learners: JourneyLearnerReport[]
  onClose: () => void
}) {
  const bodyRef = useRef<HTMLDivElement>(null)
  const width = useElementWidth(bodyRef)
  const stacked = width < 690
  const summary = <JourneySummary journey={journey} compact={stacked && width >= 290} />
  return (
    <>
      <div className="flex shrink-0 items-start bg-linear-to-br from-[#eaf4fc] to-white pt-[22px] pr-[18px] pb-[22px] pl-7">
        <div className="min-w-0 flex-1">
          <p className="m-0 text-[11px] font-extrabold tracking-[1.4px] text-brand-blue-700">
            JOURNEY DETAIL
          </p>
          <RadixDialog.Title className="m-0 mt-2 text-[27px] font-extrabold text-text-black">
            {journey.title || 'Learning journey'}
          </RadixDialog.Title>
          {journey.journeyStatus === 'disabled' && (
            <p className="m-0 mt-1 text-xs text-text-secondary">
              This journey is disabled. Its learners were removed from it.
            </p>
          )}
        </div>
        <IconButton
          icon="close"
          label="Close journey detail"
          className="text-[#44474e]!"
          onClick={onClose}
        />
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-6">
        <div ref={bodyRef}>
          {stacked ? (
            <div className="flex flex-col items-start">
              <div className="w-full">{summary}</div>
              <div className="h-[22px]" />
              <CoursePath steps={steps} />
            </div>
          ) : (
            <div className="flex items-start">
              <div className="w-[215px] shrink-0">{summary}</div>
              <div className="w-[26px] shrink-0" />
              <div className="min-w-0 flex-1">
                <CoursePath steps={steps} />
              </div>
            </div>
          )}
          <div className="h-6" />
          <Learners journey={journey} learners={learners} />
        </div>
      </div>
    </>
  )
}

function JourneySummary({ journey, compact }: { journey: JourneyReport; compact: boolean }) {
  const rate = Math.min(100, Math.max(0, journey.completionRate))
  const ring = <Ring rate={rate} size={compact ? 94 : 126} label="Journey completion" />
  const stats = [
    { label: 'Assigned', value: journey.assigned, color: colors.primaryBlue },
    { label: 'Completed', value: journey.completed, color: colors.accentGreen },
    { label: 'Overdue', value: journey.overdue, color: colors.accentRed },
  ]
  return (
    <div className="flex flex-col items-start rounded-[15px] border border-[#dde6f1] bg-[#f8fbfe] p-[18px]">
      {compact ? (
        <div className="flex w-full items-center">
          {ring}
          <div className="w-[18px] shrink-0" />
          <div className="min-w-0 flex-1">
            {stats.map((stat) => (
              <p key={stat.label} className="m-0 py-[3px] font-bold" style={{ color: stat.color }}>
                {stat.value} {stat.label.toLowerCase()}
              </p>
            ))}
          </div>
        </div>
      ) : (
        <>
          <div className="flex w-full justify-center">{ring}</div>
          <div className="h-5" />
          {stats.map((stat) => (
            <div key={stat.label} className="py-[7px]">
              <p className="m-0 text-[22px] font-extrabold" style={{ color: stat.color }}>
                {stat.value}
              </p>
              <p className="m-0 text-text-secondary">{stat.label.toLowerCase()}</p>
            </div>
          ))}
        </>
      )}
      <div className="mt-3 w-full border-t border-[#dde6f1] pt-3 text-xs text-text-secondary">
        <p className="m-0">Average progress {journey.averageProgress}%</p>
        {journey.certificateEnabled && (
          <p className="m-0 mt-1">
            {journey.certificates} {journey.certificates === 1 ? 'certificate' : 'certificates'}{' '}
            earned
          </p>
        )}
      </div>
    </div>
  )
}

function CoursePath({ steps }: { steps: JourneyStepReport[] }) {
  return (
    <div className="flex w-full flex-col items-start">
      <h3 className="m-0 text-xl font-extrabold text-text-black">Course outcomes</h3>
      <p className="m-0 mt-1 text-xs text-text-secondary">
        {steps.length} {steps.length === 1 ? 'course' : 'courses'} in this journey
      </p>
      <div className="h-4" />
      {steps.map((step, index) => (
        <CourseStep key={step.courseId} step={step} isLast={index === steps.length - 1} />
      ))}
    </div>
  )
}

function CourseStep({ step, isLast }: { step: JourneyStepReport; isLast: boolean }) {
  const rate = step.learners === 0 ? 0 : Math.min(1, Math.max(0, step.passed / step.learners))
  const tags = [
    step.stageTitle,
    step.isRequired ? null : 'Optional',
    step.unlockRule === 'open' ? 'Opens anytime' : null,
  ].filter((tag): tag is string => tag != null)
  return (
    <div className="flex w-full items-stretch">
      <div className="flex w-[34px] shrink-0 flex-col items-center">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-blue text-base font-extrabold text-white">
          {step.stepNumber}
        </span>
        {!isLast && <span className="w-0.5 flex-1 bg-brand-blue-100" />}
      </div>
      <div className="w-3 shrink-0" />
      <div className="mb-3 min-w-0 flex-1 rounded-[13px] border border-[#dde6f1] bg-white p-4">
        <p className="m-0 text-base font-extrabold text-text-black">
          {step.courseName || 'Course'}
        </p>
        {tags.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span
                key={tag}
                className="rounded-md bg-[#f3f7fc] px-1.5 py-0.5 text-[10px] font-bold text-text-secondary"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
        <div className="mt-2.5 flex items-center">
          <Icon name="check_circle_outline" size={17} color={colors.accentGreen} />
          <span className="ml-[5px] text-xs text-text-secondary">
            {step.passed}/{step.learners} completed
          </span>
        </div>
        <ProgressBar
          value={rate}
          height={6}
          radius={6}
          color={colors.accentBlue}
          trackColor={colors.brandBlue100}
          className="mt-1.5"
          label={`${step.courseName || 'Course'} completed`}
        />
        <div className="mt-3 flex flex-wrap gap-x-2.5 gap-y-2">
          <StepMeta icon="play_circle_outline" label={`${step.inProgress} in progress`} />
          <StepMeta icon="radio_button_unchecked" label={`${step.available} not started`} />
          <StepMeta icon="lock_outline" label={`${step.locked} locked`} />
          {step.unavailable > 0 && (
            <StepMeta icon="remove_circle_outline" label={`${step.unavailable} not available`} />
          )}
        </div>
      </div>
    </div>
  )
}

function StepMeta({ icon, label }: { icon: IconName; label: string }) {
  return (
    <span className="inline-flex items-center">
      <Icon name={icon} size={15} color={colors.textSecondary} />
      <span className="ml-1 text-[11px]" style={{ color: colors.textSecondary }}>
        {label}
      </span>
    </span>
  )
}

function Learners({
  journey,
  learners,
}: {
  journey: JourneyReport
  learners: JourneyLearnerReport[]
}) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('All')
  const ref = useRef<HTMLDivElement>(null)
  const table = useElementWidth(ref) >= 900
  // A filter with nobody in it is hidden, except the ones every journey has.
  const filters = FILTERS.filter(
    ([label, test]) =>
      ['All', 'Pending', 'Started', 'Completed'].includes(label) || learners.some(test),
  )
  const test = FILTERS.find(([label]) => label === filter)?.[1] ?? (() => true)
  const shown = learners.filter(
    (row) =>
      test(row) &&
      matchesWords(search, `${row.employeeName} ${row.employeeId} ${row.department ?? ''}`),
  )
  return (
    <div ref={ref}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="m-0 text-xl font-extrabold text-text-black">Learners</h3>
          <p className="m-0 mt-1 text-xs text-text-secondary">
            Everyone in this journey within your report view and filters.
          </p>
        </div>
        <Button
          variant="secondary"
          icon="download_outlined"
          disabled={shown.length === 0}
          onClick={() =>
            downloadCsv(journeyLearnersCsv(shown), `${slug(journey.title)}-learners.csv`)
          }
        >
          Export learners CSV
        </Button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <TextField
          dense
          aria-label="Search learners"
          placeholder="Search learners"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="w-[280px] max-w-full"
        />
        {filters.map(([label]) => (
          <StatusFilterChip
            key={label}
            label={label}
            selected={filter === label}
            onClick={() => setFilter(label)}
          />
        ))}
      </div>
      <p className="m-0 mt-2.5 mb-2 text-text-secondary">
        {shown.length} of {learners.length} learners
      </p>
      {shown.length === 0 ? (
        <p className="m-0 p-6">No learners match your search and selected status.</p>
      ) : (
        <>
          {table && <TableHeader />}
          {shown.map((row) => (
            <LearnerRow
              key={row.employeeId}
              row={row}
              table={table}
              journeyId={journey.journeyId}
            />
          ))}
        </>
      )}
    </div>
  )
}

const slug = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'journey'

const COLUMNS = [
  ['EMPLOYEE', 24],
  ['PROGRESS', 14],
  ['CURRENT COURSE', 22],
  ['DUE DATE', 12],
  ['LAST ACTIVE', 12],
  ['STATUS', 11],
  ['CERTIFICATE', 9],
] as const

function TableHeader() {
  return (
    <div className="flex items-center rounded-lg bg-[#f3f7fc] px-3.5 py-3">
      {COLUMNS.map(([label, flex]) => (
        <span
          key={label}
          className="min-w-0 truncate text-[10px] font-extrabold tracking-[0.5px] text-text-secondary"
          style={{ flex }}
        >
          {label}
        </span>
      ))}
    </div>
  )
}

function LearnerRow({
  row,
  table,
  journeyId,
}: {
  row: JourneyLearnerReport
  table: boolean
  journeyId: string
}) {
  const label = journeyStatusLabel(row)
  const color = listStatusColor(label)
  const name = row.employeeName || 'Employee'
  const dueColor =
    color === colors.accentRed || color === colors.accentOrange ? color : colors.textBlack
  const current =
    row.currentCourseName != null
      ? `Step ${row.currentStep ?? ''} · ${row.currentCourseName}`
      : row.status === 'completed'
        ? `Finished ${dMonY(row.completedAt)}`
        : '-'
  const certificate = <CertificateButton journeyId={journeyId} row={row} />
  if (!table) {
    return (
      <div className="flex w-full flex-col border-b border-[#e6edf5] bg-white px-1 py-3.5">
        <span className="flex w-full items-center">
          <Avatar name={name} />
          <span className="ml-2.5 block min-w-0 flex-1">
            <span className="block truncate font-extrabold">{name}</span>
            <span className="block truncate text-[12px] text-text-secondary">{current}</span>
          </span>
          <Pill label={label} color={color} />
        </span>
        <span className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-text-secondary">
          <span>
            {row.passedCount}/{row.requiredCount} courses
          </span>
          <span>Due {dMonY(row.deadline)}</span>
          <span>Active {dMonY(row.lastLearnerActivityAt)}</span>
          {certificate}
        </span>
      </div>
    )
  }
  return (
    <div className="flex w-full items-center border-b border-[#e6edf5] bg-white px-3.5 py-3">
      <span className="flex min-w-0 items-center gap-2.5" style={{ flex: 24 }}>
        <Avatar name={name} />
        <span className="block min-w-0 flex-1">
          <span className="block truncate font-extrabold">{name}</span>
          {row.department && (
            <span className="block truncate text-[11px] text-text-secondary">{row.department}</span>
          )}
        </span>
      </span>
      <span className="block min-w-0" style={{ flex: 14 }}>
        <span className="block text-[11px] font-bold">
          {row.passedCount}/{row.requiredCount} courses
        </span>
        <ProgressBar
          className="mt-1.5 w-[82px]!"
          value={row.completionPercent / 100}
          height={5}
          radius={5}
          color={colors.accentBlue}
          trackColor={colors.brandBlue100}
        />
      </span>
      <span className="line-clamp-2 min-w-0 pr-2" style={{ flex: 22 }}>
        {current}
      </span>
      <span className="block min-w-0 truncate font-semibold" style={{ flex: 12, color: dueColor }}>
        {dMonY(row.deadline)}
      </span>
      <span className="block min-w-0 truncate text-text-secondary" style={{ flex: 12 }}>
        {dMonY(row.lastLearnerActivityAt)}
      </span>
      <span className="block min-w-0" style={{ flex: 11 }}>
        <Pill label={label} color={color} />
      </span>
      <span className="block min-w-0" style={{ flex: 9 }}>
        {certificate}
      </span>
    </div>
  )
}

function CertificateButton({ journeyId, row }: { journeyId: string; row: JourneyLearnerReport }) {
  const { app, state } = useReport()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const number = row.certificateNumber
  if (number == null) return <span className="text-text-secondary">-</span>
  const download = async () => {
    setBusy(true)
    try {
      const url = reportUrl(
        app,
        `journeys/${encodeURIComponent(journeyId)}/certificates/${encodeURIComponent(row.employeeId)}`,
        { view: state.reportView, courseStatus: state.filter.courseStatus },
        {},
      )
      downloadBlob(await reportBlob(url, 'Unable to download the certificate'), `${number}.pdf`)
    } catch (error) {
      toast(errorMessage(error), { tone: 'error' })
    } finally {
      setBusy(false)
    }
  }
  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => void download()}
      aria-label={`Download certificate for ${row.employeeName}`}
      title={number}
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-extrabold text-primary-blue hover:bg-black/4 focus-visible:outline-2 focus-visible:outline-brand-blue-light disabled:opacity-60"
    >
      <Icon name="download_outlined" size={15} />
      PDF
    </button>
  )
}

function Avatar({ name }: { name: string }) {
  return (
    <span className="inline-flex size-[38px] shrink-0 items-center justify-center rounded-full bg-brand-blue-100 text-[12px] font-extrabold text-primary-blue">
      {initials(name)}
    </span>
  )
}

function Pill({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="inline-block max-w-full truncate rounded-[20px] px-[9px] py-[5px] text-[11px] font-extrabold"
      style={{ color, backgroundColor: mix(color, 0.1) }}
    >
      {label}
    </span>
  )
}

function StateMessage({ detail, onClose }: { detail: string; onClose: () => void }) {
  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="flex flex-col items-center p-6">
        <Icon name="error_outline" size={36} color={colors.accentRed} />
        <p className="m-0 mt-3 font-extrabold">Could not load journey detail</p>
        <p className="m-0 mt-1.5 text-center">{detail}</p>
        <Button variant="text" onClick={onClose}>
          Close
        </Button>
      </div>
    </div>
  )
}
