// Display helpers shared by the report views. Dart sources: _date, _dateTime, _score, _percent and
// _statusLabel in frontend/lib/features/performance/*.dart. The em dash placeholder is "-".
import type { IconName } from '../ui/icons/Icon'

const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const ZONE = /(Z|[+-]\d{2}(:?\d{2})?)$/i
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/

interface Parts {
  year: number
  month: number
  day: number
  hour: number
  minute: number
}

/**
 * Dart DateTime.tryParse: a value with a zone is UTC, a value without a zone is local time.
 * With `toLocal`, a UTC value is shown in local time (Dart `.toLocal()`).
 */
function dartParts(value: unknown, toLocal = false): Parts | null {
  if (value == null) return null
  const text = String(value).trim()
  if (!text) return null
  if (DATE_ONLY.test(text)) {
    const [year, month, day] = text.split('-').map(Number)
    return { year: year!, month: month!, day: day!, hour: 0, minute: 0 }
  }
  const utc = ZONE.test(text)
  const date = new Date(text.replace(/^(\d{4}-\d{2}-\d{2}) /, '$1T'))
  if (Number.isNaN(date.getTime())) return null
  if (utc && !toLocal) {
    return {
      year: date.getUTCFullYear(),
      month: date.getUTCMonth() + 1,
      day: date.getUTCDate(),
      hour: date.getUTCHours(),
      minute: date.getUTCMinutes(),
    }
  }
  return {
    year: date.getFullYear(),
    month: date.getMonth() + 1,
    day: date.getDate(),
    hour: date.getHours(),
    minute: date.getMinutes(),
  }
}

const pad = (value: number) => String(value).padStart(2, '0')

/** `d/m/yyyy`, or "-". */
export function dmy(value: unknown): string {
  const p = dartParts(value)
  return p ? `${p.day}/${p.month}/${p.year}` : '-'
}

/** `d/m/yyyy hh:mm`, or "-". */
export function dmyHm(value: unknown): string {
  const p = dartParts(value)
  return p ? `${p.day}/${p.month}/${p.year} ${pad(p.hour)}:${pad(p.minute)}` : '-'
}

/** `d Mon yyyy`, or the fallback. The employee panel converts to local time first. */
export function dMonY(value: unknown, fallback = '-', toLocal = false): string {
  const p = dartParts(value, toLocal)
  return p ? `${p.day} ${months[p.month - 1]} ${p.year}` : fallback
}

/** Dart `_score`: one decimal place. */
export const score = (value: unknown): string =>
  typeof value === 'number' ? `${value.toFixed(1)}%` : '-'

/** Dart `_percent`: no decimal places for a whole number. */
export const percent = (value: unknown): string =>
  typeof value === 'number' ? `${value.toFixed(Number.isInteger(value) ? 0 : 1)}%` : '-'

/** Color.lerp(white, color, t) for a #rrggbb color. */
export function mix(color: string, t: number): string {
  const hex = color.replace('#', '')
  const channel = (index: number) => {
    const value = parseInt(hex.slice(index * 2, index * 2 + 2), 16)
    return Math.round(255 + (value - 255) * t)
  }
  return `rgb(${channel(0)} ${channel(1)} ${channel(2)})`
}

/** `color.withOpacity(alpha)` for a #rrggbb color. */
export function alpha(color: string, value: number): string {
  const hex = color.replace('#', '')
  const channel = (index: number) => parseInt(hex.slice(index * 2, index * 2 + 2), 16)
  return `rgb(${channel(0)} ${channel(1)} ${channel(2)} / ${value})`
}

export const colors = {
  primaryBlue: '#00317a',
  brandBlue700: '#0b4e9b',
  brandBlue100: '#eaf3fc',
  textBlack: '#172033',
  textSecondary: '#5f6878',
  gray: '#8b94a3',
  lightGray: '#ebeff4',
  surfaceSecondary: '#f7f9fc',
  accentBlue: '#2878d7',
  accentOrange: '#d59a00',
  accentLightOrange: '#fff6d8',
  accentGreen: '#00a878',
  accentRed: '#d92d20',
  purple: '#7047eb',
  completedGreen: '#087f68',
  green: '#008b73',
  red: '#ce3546',
  amber: '#aa7000',
  barBlue: '#3076d9',
} as const

interface StatusRow {
  status: string
  dueSoon: boolean
  repeatedFailures: boolean
  inactive: boolean
}

/** Portal `_statusLabel`: deadline flags win over progress. */
export function statusLabel(row: StatusRow): string {
  if (row.status === 'overdue') return 'Overdue'
  if (row.dueSoon) return 'Due soon'
  if (row.status === 'completed') return 'Completed'
  if (row.repeatedFailures) return 'Quiz difficulty'
  if (row.inactive) return 'Inactive'
  return row.status === 'started' ? 'Started' : 'Pending'
}

/** Watchlist `_StatusBadge` color. */
export function badgeColor(label: string): string {
  if (label === 'Overdue') return colors.accentRed
  if (label === 'Due soon') return colors.accentOrange
  if (label === 'Completed') return colors.accentGreen
  return colors.accentBlue
}

/** EmployeeAssignmentList `_status` color. */
export function listStatusColor(label: string): string {
  switch (label) {
    case 'Overdue':
      return colors.accentRed
    case 'Due soon':
    case 'Quiz difficulty':
    case 'Inactive':
      return colors.accentOrange
    case 'Completed':
      return colors.accentGreen
    case 'Started':
      return colors.accentBlue
    default:
      return colors.textSecondary
  }
}

/** Employee drawer `_statusLabel`. */
export const courseStatusLabel = (status: string): string =>
  ({ completed: 'Completed', started: 'In progress', pending: 'Not started', overdue: 'Overdue' })[
    status
  ] ?? 'Unknown'

export function courseStatusColor(status: string): string {
  if (status === 'completed') return colors.green
  if (status === 'overdue') return colors.red
  if (status === 'pending') return colors.textSecondary
  return colors.primaryBlue
}

/** `_courseIcon`: a keyword in the course name picks the icon. */
export function courseIcon(name: string): IconName {
  const text = name.toLowerCase()
  if (text.includes('risk')) return 'shield_outlined'
  if (text.includes('compliance')) return 'verified_user_outlined'
  if (text.includes('product')) return 'lightbulb_outline'
  if (text.includes('conversation')) return 'forum_outlined'
  return 'menu_book_outlined'
}

/** `_initials`: the first letter of the first two words. */
export function initials(name: string): string {
  const parts = name
    .trim()
    .split(/\s+/)
    .filter((part) => part.length > 0)
  const letters = parts
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join('')
  return letters || '?'
}

/** Word search used by the course browser and the filter picker. */
export function matchesWords(query: string, haystack: string): boolean {
  const words = query.trim().toLowerCase().split(/\s+/)
  const text = haystack.toLowerCase()
  return words.every((word) => text.includes(word))
}

/** Assignment dialog `_status`: completed and overdue win over the due soon flag. */
export function dialogStatusLabel(row: { status: string; dueSoon: boolean }): string {
  if (row.status === 'completed') return 'Completed'
  if (row.status === 'overdue') return 'Overdue'
  if (row.dueSoon) return 'Due soon'
  if (row.status === 'started') return 'In progress'
  return 'Pending'
}

/** Assignment dialog status color. */
export function dialogStatusColor(label: string): string {
  if (label === 'Overdue') return colors.accentRed
  if (label === 'Completed') return colors.completedGreen
  return colors.primaryBlue
}
