import { describe, expect, it } from 'vitest'
import { deadlineRange, isDeadlineInRange, todayInKolkata } from './dates'

describe('deadline dates', () => {
  it('uses the Asia/Kolkata day', () => {
    // 2026-10-15 19:00 UTC is already 16 October in Kolkata.
    expect(todayInKolkata(Date.UTC(2026, 9, 15, 19, 0))).toBe('2026-10-16')
    expect(todayInKolkata(Date.UTC(2026, 9, 15, 18, 0))).toBe('2026-10-15')
  })

  it('accepts only complete dates from today to 1 January ten years on', () => {
    const now = Date.UTC(2026, 9, 16, 6, 0)
    expect(deadlineRange(now)).toEqual({ min: '2026-10-16', max: '2036-01-01' })
    expect(isDeadlineInRange('2026-10-16', now)).toBe(true)
    expect(isDeadlineInRange('2036-01-01', now)).toBe(true)
    expect(isDeadlineInRange('2026-10-15', now)).toBe(false)
    expect(isDeadlineInRange('2036-01-02', now)).toBe(false)
    expect(isDeadlineInRange('', now)).toBe(false)
  })
})
