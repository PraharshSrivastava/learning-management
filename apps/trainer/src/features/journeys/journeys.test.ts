import { describe, expect, it } from 'vitest'
import { parseDetail, savePayload, type JourneyStage } from './api'
import { moveStep } from './editing'

const step = (courseId: string) => ({
  courseId,
  courseName: courseId,
  moduleCount: 1,
  unlockRule: 'after_previous' as const,
  isRequired: true,
  eligible: true,
  reason: null,
})

const stages = (): JourneyStage[] => [
  { title: 'One', steps: [step('a'), step('b')] },
  { title: 'Two', steps: [step('c')] },
]

const order = (list: JourneyStage[]) => list.map((stage) => stage.steps.map((s) => s.courseId))

describe('moveStep', () => {
  it('moves within a stage', () => {
    expect(order(moveStep(stages(), 0, 1, -1))).toEqual([['b', 'a'], ['c']])
  })

  it('crosses into the neighbouring stage at an edge', () => {
    expect(order(moveStep(stages(), 0, 1, 1))).toEqual([['a'], ['b', 'c']])
    expect(order(moveStep(stages(), 1, 0, -1))).toEqual([['a', 'b', 'c'], []])
  })

  it('leaves the first and last courses where they are', () => {
    const original = stages()
    expect(moveStep(original, 0, 0, -1)).toBe(original)
    expect(moveStep(original, 1, 0, 1)).toBe(original)
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
        { title: 'Stage 1', steps: [{ course_id: 'c1', unlock_rule: 'open', is_required: false }] },
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
