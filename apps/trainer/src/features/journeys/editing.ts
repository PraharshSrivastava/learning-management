import type { JourneyStage, JourneyStep } from './api'

/**
 * Moves one course a single place up (-1) or down (+1) within its section.
 * At a section edge it moves into the neighbouring section instead.
 */
export function moveStep(
  stages: JourneyStage[],
  stageIndex: number,
  stepIndex: number,
  direction: -1 | 1,
): JourneyStage[] {
  const next = stages.map((stage) => ({ ...stage, steps: [...stage.steps] }))
  const stage = next[stageIndex]
  const step = stage?.steps[stepIndex]
  if (!stage || !step) return stages
  const target = stepIndex + direction
  if (target >= 0 && target < stage.steps.length) {
    stage.steps.splice(stepIndex, 1)
    stage.steps.splice(target, 0, step)
    return next
  }
  // Cross into the neighbouring section: the end of the one above, or the start of the one below.
  const neighbour = next[stageIndex + direction]
  if (!neighbour) return stages
  stage.steps.splice(stepIndex, 1)
  if (direction < 0) neighbour.steps.push(step)
  else neighbour.steps.unshift(step)
  return next
}

export interface StepAt {
  stage: number
  step: number
}

/**
 * Drag and drop: the dragged course takes the place of the course it is dropped on.
 * A `step` equal to the section's length drops it at the end of that section.
 */
export function moveStepTo(stages: JourneyStage[], from: StepAt, to: StepAt): JourneyStage[] {
  if (from.stage === to.stage && from.step === to.step) return stages
  const next = stages.map((stage) => ({ ...stage, steps: [...stage.steps] }))
  const source = next[from.stage]
  const target = next[to.stage]
  const step = source?.steps[from.step]
  if (!source || !target || !step) return stages
  source.steps.splice(from.step, 1)
  target.steps.splice(Math.min(to.step, target.steps.length), 0, step)
  return next
}

export type OrderMode = 'in_order' | 'any_order'

const allSteps = (stages: JourneyStage[]): JourneyStep[] => stages.flatMap((stage) => stage.steps)

/** A journey is "any order" when every course is open from the start. */
export function orderModeOf(stages: JourneyStage[]): OrderMode {
  const steps = allSteps(stages)
  return steps.length > 0 && steps.every((step) => step.unlockRule === 'open')
    ? 'any_order'
    : 'in_order'
}

/** Applies a journey-wide order: any order opens every course; in order clears the exceptions. */
export function withOrderMode(stages: JourneyStage[], mode: OrderMode): JourneyStage[] {
  const unlockRule = mode === 'any_order' ? 'open' : 'after_previous'
  return stages.map((stage) => ({
    ...stage,
    steps: stage.steps.map((step) => ({ ...step, unlockRule })),
  }))
}

/** What publishing assigns now, in words that match the journey's order. */
export function publishSummary(stages: JourneyStage[]): string {
  const steps = allSteps(stages)
  const total = steps.length
  const opensNow = steps.filter((step, index) => index === 0 || step.unlockRule === 'open').length
  if (total <= 1) return 'The course is assigned now.'
  if (opensNow === total)
    return `All ${total} courses are assigned now, and learners can take them in any order.`
  if (opensNow === 1)
    return 'Only the first course is assigned now. Each next course is assigned when the one before it is passed.'
  return `${opensNow} of ${total} courses are assigned now. The others are assigned in order, each when the one before it is passed.`
}

export interface RemovedCourse {
  courseId: string
  courseName: string
  learnerCount: number
  startedCount: number
}

/** Saved courses the draft removes that learners already hold. */
export function removedWithLearners(saved: JourneyStage[], draft: JourneyStage[]): RemovedCourse[] {
  const kept = new Set(allSteps(draft).map((step) => step.courseId))
  return allSteps(saved)
    .filter((step) => !kept.has(step.courseId) && step.learnerCount > 0)
    .map(({ courseId, courseName, learnerCount, startedCount }) => ({
      courseId,
      courseName,
      learnerCount,
      startedCount,
    }))
}
