// Material 3 date picker dialog (Flutter showDatePicker), calendar mode only.
// Dates are plain `YYYY-MM-DD` strings so time zones never shift them.
import { Icon } from '@lms/shared/ui/icons/Icon'
import { Dialog } from '@lms/shared/ui/Dialog'
import clsx from 'clsx'
import { useState } from 'react'
import { ActionButton } from './controls'

export interface Ymd {
  year: number
  month: number // 1 to 12
  day: number
}

const pad = (n: number) => String(n).padStart(2, '0')
export const formatYmd = (d: Ymd) => `${d.year}-${pad(d.month)}-${pad(d.day)}`
const key = (d: Ymd) => d.year * 10000 + d.month * 100 + d.day

export function parseYmd(text: string | null | undefined): Ymd | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(text ?? '')
  if (!match) return null
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])]
  if (month < 1 || month > 12 || day < 1 || day > daysIn(year, month)) return null
  return { year, month, day }
}

/** Today in Asia/Kolkata (UTC+5:30), as Flutter computes it. */
export function todayInKolkata(now = Date.now()): Ymd {
  const d = new Date(now + 330 * 60 * 1000)
  return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() }
}

const daysIn = (year: number, month: number) => new Date(Date.UTC(year, month, 0)).getUTCDate()
const weekdayOfFirst = (year: number, month: number) =>
  new Date(Date.UTC(year, month - 1, 1)).getUTCDay()

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]
const SHORT_DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

interface DatePickerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  initial: Ymd
  first: Ymd
  last: Ymd
  onPick: (date: Ymd) => void
}

export function DatePickerDialog(props: DatePickerDialogProps) {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange} title="Select date" width={360}>
      {props.open && <Calendar {...props} />}
    </Dialog>
  )
}

function Calendar({ initial, first, last, onPick, onOpenChange }: DatePickerDialogProps) {
  const [selected, setSelected] = useState(initial)
  const [view, setView] = useState({ year: initial.year, month: initial.month })
  const headline = new Date(Date.UTC(selected.year, selected.month - 1, selected.day))
  const headlineText = `${SHORT_DAYS[headline.getUTCDay()]}, ${MONTHS[selected.month - 1]?.slice(0, 3)} ${selected.day}`
  const canPrev = view.year * 12 + view.month > first.year * 12 + first.month
  const canNext = view.year * 12 + view.month < last.year * 12 + last.month
  const shift = (delta: number) => {
    const index = view.year * 12 + (view.month - 1) + delta
    setView({ year: Math.floor(index / 12), month: (index % 12) + 1 })
  }
  const blanks = weekdayOfFirst(view.year, view.month)
  const days = daysIn(view.year, view.month)
  return (
    <div>
      <p className="-mx-6 border-b border-[#c4c6d0] px-6 pb-3 text-[32px] leading-10 text-[#191c20]">
        {headlineText}
      </p>
      <div className="-mr-3 flex h-14 items-center justify-between">
        <span className="text-sm font-medium text-[#44474e]">
          {MONTHS[view.month - 1]} {view.year}
        </span>
        <div className="flex">
          <button
            type="button"
            aria-label="Previous month"
            disabled={!canPrev}
            onClick={() => shift(-1)}
            className="inline-flex size-10 items-center justify-center rounded-full text-[#44474e] hover:bg-black/6 disabled:opacity-40"
          >
            <Icon name="chevron_left" size={24} />
          </button>
          <button
            type="button"
            aria-label="Next month"
            disabled={!canNext}
            onClick={() => shift(1)}
            className="inline-flex size-10 items-center justify-center rounded-full text-[#44474e] hover:bg-black/6 disabled:opacity-40"
          >
            <Icon name="chevron_right" size={24} />
          </button>
        </div>
      </div>
      <div className="-mx-3 grid grid-cols-7 text-center">
        {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
          <span key={i} className="flex h-10 items-center justify-center text-sm text-[#191c20]">
            {d}
          </span>
        ))}
        {Array.from({ length: blanks }, (_, i) => (
          <span key={`b${i}`} />
        ))}
        {Array.from({ length: days }, (_, i) => {
          const date = { year: view.year, month: view.month, day: i + 1 }
          const disabled = key(date) < key(first) || key(date) > key(last)
          const isSelected = key(date) === key(selected)
          const isToday = key(date) === key(first)
          return (
            <span key={i} className="flex h-12 items-center justify-center">
              <button
                type="button"
                disabled={disabled}
                aria-label={formatYmd(date)}
                aria-pressed={isSelected}
                onClick={() => setSelected(date)}
                className={clsx(
                  'size-10 rounded-full text-sm',
                  isSelected
                    ? 'bg-primary-blue text-white'
                    : isToday
                      ? 'border border-primary-blue text-primary-blue'
                      : 'text-[#191c20] hover:bg-black/6',
                  'disabled:border-transparent disabled:text-[#191c20]/38 disabled:hover:bg-transparent',
                )}
              >
                {i + 1}
              </button>
            </span>
          )
        })}
      </div>
      <div className="-mb-3 flex justify-end gap-2 pt-2">
        <ActionButton variant="text" onClick={() => onOpenChange(false)}>
          Cancel
        </ActionButton>
        <ActionButton
          variant="text"
          onClick={() => {
            onPick(selected)
            onOpenChange(false)
          }}
        >
          OK
        </ActionButton>
      </div>
    </div>
  )
}
