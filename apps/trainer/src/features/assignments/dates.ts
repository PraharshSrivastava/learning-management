// Deadline dates are plain `YYYY-MM-DD` strings so time zones never shift them.

const pad = (n: number) => String(n).padStart(2, '0')

/** Today in Asia/Kolkata (UTC+5:30), as Flutter computes it. */
export function todayInKolkata(now = Date.now()): string {
  const d = new Date(now + 330 * 60 * 1000)
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`
}

/** Flutter showDatePicker range: today to 1 January ten years on. */
export function deadlineRange(now = Date.now()): { min: string; max: string } {
  const min = todayInKolkata(now)
  return { min, max: `${Number(min.slice(0, 4)) + 10}-01-01` }
}

/** A complete `YYYY-MM-DD` value inside the range. Typed values can skip the native min/max. */
export function isDeadlineInRange(value: string, now = Date.now()): boolean {
  const { min, max } = deadlineRange(now)
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && value >= min && value <= max
}
