import type { JourneyStage } from './api'

/**
 * Moves one course a single place up (-1) or down (+1) within its stage.
 * At a stage edge it moves into the neighbouring stage instead.
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
  // Cross into the neighbouring stage: the end of the one above, or the start of the one below.
  const neighbour = next[stageIndex + direction]
  if (!neighbour) return stages
  stage.steps.splice(stepIndex, 1)
  if (direction < 0) neighbour.steps.push(step)
  else neighbour.steps.unshift(step)
  return next
}
