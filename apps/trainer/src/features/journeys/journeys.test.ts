import { describe, expect, it } from 'vitest'
import { parseDetail, savePayload, type JourneyStage, type JourneyStep } from './api'
import {
  moveStep,
  moveStepTo,
  orderModeOf,
  publishSummary,
  removedWithLearners,
  withOrderMode,
} from './editing'

const step = (courseId: string, patch: Partial<JourneyStep> = {}): JourneyStep => ({
  courseId,
  courseName: courseId,
  moduleCount: 1,
  thumbnailPath: '',
  unlockRule: 'after_previous',
  isRequired: true,
  eligible: true,
  reason: null,
  otherJourneys: [],
  learnerCount: 0,
  startedCount: 0,
  ...patch,
})

const stages = (): JourneyStage[] => [
  { title: 'One', steps: [step('a'), step('b')] },
  { title: 'Two', steps: [step('c')] },
]

const order = (list: JourneyStage[]) => list.map((stage) => stage.steps.map((s) => s.courseId))

describe('moveStep', () => {
  it('moves within a section', () => {
    expect(order(moveStep(stages(), 0, 1, -1))).toEqual([['b', 'a'], ['c']])
  })

  it('crosses into the neighbouring section at an edge', () => {
    expect(order(moveStep(stages(), 0, 1, 1))).toEqual([['a'], ['b', 'c']])
    expect(order(moveStep(stages(), 1, 0, -1))).toEqual([['a', 'b', 'c'], []])
  })

  it('leaves the first and last courses where they are', () => {
    const original = stages()
    expect(moveStep(original, 0, 0, -1)).toBe(original)
    expect(moveStep(original, 1, 0, 1)).toBe(original)
  })
})

describe('moveStepTo (drag and drop)', () => {
  it('takes the place of the course it is dropped on, up or down', () => {
    expect(order(moveStepTo(stages(), { stage: 0, step: 0 }, { stage: 0, step: 1 }))).toEqual([
      ['b', 'a'],
      ['c'],
    ])
    expect(order(moveStepTo(stages(), { stage: 1, step: 0 }, { stage: 0, step: 0 }))).toEqual([
      ['c', 'a', 'b'],
      [],
    ])
  })

  it('drops at the end of a section and ignores a drop on itself', () => {
    expect(order(moveStepTo(stages(), { stage: 0, step: 0 }, { stage: 1, step: 1 }))).toEqual([
      ['b'],
      ['c', 'a'],
    ])
    const original = stages()
    expect(moveStepTo(original, { stage: 0, step: 1 }, { stage: 0, step: 1 })).toBe(original)
  })
})

describe('course order', () => {
  it('reads and applies the journey-wide order', () => {
    expect(orderModeOf(stages())).toBe('in_order')
    const open = withOrderMode(stages(), 'any_order')
    expect(orderModeOf(open)).toBe('any_order')
    expect(orderModeOf(withOrderMode(open, 'in_order'))).toBe('in_order')
    expect(orderModeOf([{ title: 'One', steps: [] }])).toBe('in_order')
  })

  it('describes what publishing assigns for each order', () => {
    expect(publishSummary(stages())).toMatch(/^Only the first course is assigned now/)
    expect(publishSummary(withOrderMode(stages(), 'any_order'))).toMatch(
      /^All 3 courses are assigned now, and learners can take them in any order/,
    )
    const mixed: JourneyStage[] = [
      { title: 'One', steps: [step('a'), step('b', { unlockRule: 'open' }), step('c')] },
    ]
    expect(publishSummary(mixed)).toMatch(/^2 of 3 courses are assigned now/)
    expect(publishSummary([{ title: 'One', steps: [step('a')] }])).toBe(
      'The course is assigned now.',
    )
  })
})

describe('removedWithLearners', () => {
  it('lists only removed courses that learners already hold', () => {
    const saved: JourneyStage[] = [
      {
        title: 'One',
        steps: [
          step('a', { learnerCount: 4, startedCount: 1 }),
          step('b', { learnerCount: 0 }),
          step('c', { learnerCount: 2, startedCount: 2 }),
        ],
      },
    ]
    const draft: JourneyStage[] = [{ title: 'One', steps: [step('c')] }]
    expect(removedWithLearners(saved, draft)).toEqual([
      { courseId: 'a', courseName: 'a', learnerCount: 4, startedCount: 1 },
    ])
  })
})

describe('journey payloads', () => {
  it('round-trips a saved journey into the PUT body', () => {
    const detail = parseDetail({
      journey_id: 'j1',
      title: ' Foundation ',
      status: 'published',
      updated_at: 'u1',
      prerequisite_journey_id: 'j0',
      stages: [
        {
          title: '',
          steps: [{ course_id: 'c1', unlock_rule: 'open', is_required: false, eligible: true }],
        },
      ],
      rule: {
        include_all: false,
        include_groups: [{ departments: ['Sales'] }],
        deadline_mode: 'relative',
        deadline_days: 45,
        deadline_date: '2026-12-31',
      },
    })
    expect(savePayload(detail)).toEqual({
      expected_updated_at: 'u1',
      title: 'Foundation',
      description: '',
      target_audience: '',
      prerequisite_journey_id: 'j0',
      certificate_enabled: true,
      stages: [
        {
          title: 'Section 1',
          steps: [{ course_id: 'c1', unlock_rule: 'open', is_required: false }],
        },
      ],
      rule: {
        include_all: false,
        include_groups: [
          {
            employee_ids: [],
            departments: ['Sales'],
            mailing_lists: [],
            job_titles: [],
            joined_less_than_days_ago: null,
          },
        ],
        exclude_groups: [],
        deadline_mode: 'relative',
        deadline_days: 45,
        // A relative deadline never sends a stale date.
        deadline_date: null,
      },
    })
  })
})
