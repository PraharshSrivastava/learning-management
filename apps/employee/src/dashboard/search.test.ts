import { describe, expect, it } from 'vitest'
import { employeeSearchSchema, navigationIndex, openCourseId, viewForIndex } from './search'

describe('employee search', () => {
  it('drops unknown views and coerces numeric ids', () => {
    expect(employeeSearchSchema.parse({ view: 'admin', course_id: 123, status: ' ' })).toEqual({
      view: undefined,
      course_id: '123',
      status: undefined,
    })
  })

  it('maps views to sidebar indexes and back', () => {
    expect(navigationIndex(undefined)).toBe(0)
    expect(navigationIndex('course')).toBe(0)
    expect(navigationIndex('team-performance')).toBe(3)
    expect([0, 1, 2, 3].map(viewForIndex)).toEqual([
      undefined,
      'courses',
      'notifications',
      'performance',
    ])
  })

  it('keeps course_id of a report out of course playback', () => {
    expect(openCourseId({ view: 'course', course_id: 'c1' })).toBe('c1')
    expect(openCourseId({ view: 'team-performance', course_id: 'c1' })).toBeNull()
  })
})
