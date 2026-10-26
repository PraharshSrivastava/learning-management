import { describe, expect, it } from 'vitest'
import {
  destinationForView,
  destinationsFor,
  employeeSearchSchema,
  openCourseId,
  viewForDestination,
} from './search'

describe('employee search', () => {
  it('drops unknown views and coerces numeric ids', () => {
    expect(employeeSearchSchema.parse({ view: 'admin', course_id: 123, status: ' ' })).toEqual({
      view: undefined,
      course_id: '123',
      status: undefined,
      journey_id: undefined,
    })
  })

  it('maps views to sidebar entries and back', () => {
    expect(destinationForView(undefined)).toBe('dashboard')
    expect(destinationForView('course')).toBe('dashboard')
    expect(destinationForView('team-performance')).toBe('performance')
    expect(destinationForView('journeys')).toBe('journeys')
    expect(destinationsFor({ journeys: false, performance: true }).map(viewForDestination)).toEqual(
      [undefined, 'courses', 'notifications', 'performance'],
    )
  })

  it('places Learning Journeys after My Courses only when enabled', () => {
    expect(destinationsFor({ journeys: true, performance: false })).toEqual([
      'dashboard',
      'courses',
      'journeys',
      'notifications',
    ])
    expect(destinationsFor({ journeys: false, performance: false })).toEqual([
      'dashboard',
      'courses',
      'notifications',
    ])
  })

  it('keeps course_id of a report out of course playback', () => {
    expect(openCourseId({ view: 'course', course_id: 'c1' })).toBe('c1')
    expect(openCourseId({ view: 'team-performance', course_id: 'c1' })).toBeNull()
  })
})
