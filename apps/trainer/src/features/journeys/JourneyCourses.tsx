// The journey's courses: their order, optional sections, and which courses open without waiting.
import { assetUrl } from '@lms/shared/api/client'
import { useHasMediaTicket } from '@lms/shared/api/useMediaTicket'
import { Icon } from '@lms/shared/ui/icons/Icon'
import clsx from 'clsx'
import { useState } from 'react'
import { ActionButton, ChoiceChip, Switch } from '../assignments/controls'
import type { CourseOption, JourneyStage, JourneyStep } from './api'
import { moveStep, moveStepTo, withOrderMode, type OrderMode, type StepAt } from './editing'

const fieldClass =
  'w-full rounded-lg border border-input-border bg-white px-3 py-2 text-sm text-[#19273e] focus-visible:outline-2 focus-visible:outline-brand-blue-light'

export function JourneyCourses({
  stages,
  options,
  mode,
  onModeChange,
  onChange,
}: {
  stages: JourneyStage[]
  options: CourseOption[]
  mode: OrderMode
  onModeChange: (mode: OrderMode) => void
  onChange: (stages: JourneyStage[]) => void
}) {
  const [picking, setPicking] = useState<number | null>(null)
  const [pick, setPick] = useState('')
  const [dragging, setDragging] = useState<StepAt | null>(null)
  const [over, setOver] = useState<string | null>(null)
  const used = new Set(stages.flatMap((stage) => stage.steps.map((step) => step.courseId)))
  const available = options.filter((option) => option.eligible && !used.has(option.courseId))
  const unavailable = options.filter((option) => !option.eligible && !used.has(option.courseId))
  const total = stages.reduce((sum, stage) => sum + stage.steps.length, 0)
  const sectioned = stages.length > 1
  // Step numbers run across the whole journey: a section continues from the one before.
  const firstNumber = stages.map((_, index) =>
    stages.slice(0, index).reduce((sum, stage) => sum + stage.steps.length, 1),
  )

  const setStage = (index: number, stage: JourneyStage) =>
    onChange(stages.map((item, i) => (i === index ? stage : item)))
  const setStep = (stageIndex: number, stepIndex: number, patch: Partial<JourneyStep>) =>
    setStage(stageIndex, {
      ...stages[stageIndex]!,
      steps: stages[stageIndex]!.steps.map((item, i) =>
        i === stepIndex ? { ...item, ...patch } : item,
      ),
    })
  // Removing a section keeps its courses: they join the section above (or below for the first).
  const removeSection = (index: number) => {
    const into = index === 0 ? 1 : index - 1
    const moved = stages[index]?.steps ?? []
    onChange(
      stages
        .map((stage, i) =>
          i === into
            ? {
                ...stage,
                steps: index === 0 ? [...moved, ...stage.steps] : [...stage.steps, ...moved],
              }
            : stage,
        )
        .filter((_, i) => i !== index),
    )
  }
  const drop = (to: StepAt) => {
    if (dragging) onChange(moveStepTo(stages, dragging, to))
    setDragging(null)
    setOver(null)
  }

  return (
    <div className="flex flex-col gap-3">
      <div role="group" aria-label="Course order" className="flex flex-wrap gap-2">
        <ChoiceChip
          selected={mode === 'in_order'}
          onClick={() => {
            // Choosing the current order again keeps the per-course exceptions.
            if (mode === 'in_order') return
            onModeChange('in_order')
            onChange(withOrderMode(stages, 'in_order'))
          }}
        >
          In order
        </ChoiceChip>
        <ChoiceChip
          selected={mode === 'any_order'}
          onClick={() => {
            // Choosing the current order again keeps the per-course exceptions.
            if (mode === 'any_order') return
            onModeChange('any_order')
            onChange(withOrderMode(stages, 'any_order'))
          }}
        >
          In any order
        </ChoiceChip>
      </div>
      <p className="text-xs text-[#5b6980]">
        {mode === 'in_order'
          ? 'Each course opens when the one before it is passed. Turn on “Opens anytime” for a course that should not wait. Drag courses or use the arrows to reorder.'
          : 'Every course is assigned at once, and learners take them in any order.'}
      </p>
      {stages.map((stage, stageIndex) => (
        <div
          key={stageIndex}
          className={clsx(sectioned && 'rounded-xl border border-[#e6e9ef] bg-[#f7f9fc] p-3')}
        >
          {sectioned && (
            <div className="mb-2 flex items-center gap-2">
              <input
                aria-label={`Section ${stageIndex + 1} name`}
                className={clsx(fieldClass, 'font-semibold')}
                value={stage.title}
                maxLength={200}
                onChange={(event) => setStage(stageIndex, { ...stage, title: event.target.value })}
              />
              <ActionButton
                variant="text"
                icon="delete_outline"
                aria-label={`Remove section ${stageIndex + 1}`}
                title="Remove this section. Its courses move to the section next to it."
                onClick={() => removeSection(stageIndex)}
              />
            </div>
          )}
          <ol className="m-0 flex list-none flex-col gap-2 p-0">
            {stage.steps.map((step, stepIndex) => {
              const position = (firstNumber[stageIndex] ?? 1) + stepIndex
              const dropKey = `${stageIndex}:${stepIndex}`
              return (
                <li
                  key={step.courseId}
                  draggable
                  onDragStart={(event) => {
                    event.dataTransfer.effectAllowed = 'move'
                    event.dataTransfer.setData('text/plain', step.courseId)
                    setDragging({ stage: stageIndex, step: stepIndex })
                  }}
                  onDragEnd={() => {
                    setDragging(null)
                    setOver(null)
                  }}
                  onDragOver={(event) => {
                    if (!dragging) return
                    event.preventDefault()
                    setOver(dropKey)
                  }}
                  onDrop={(event) => {
                    event.preventDefault()
                    drop({ stage: stageIndex, step: stepIndex })
                  }}
                  className={clsx(
                    'flex gap-3 rounded-lg border bg-white p-2.5',
                    over === dropKey ? 'border-brand-blue-light' : 'border-[#e6e9ef]',
                    dragging?.stage === stageIndex && dragging.step === stepIndex && 'opacity-50',
                  )}
                >
                  <span
                    className="flex cursor-grab items-center text-[#98a2b3]"
                    title="Drag to reorder"
                    aria-hidden="true"
                  >
                    <Icon name="drag_indicator" size={18} />
                  </span>
                  <span className="inline-flex size-7 shrink-0 items-center justify-center self-start rounded-full bg-brand-blue-100 text-xs font-bold text-primary-blue">
                    {position}
                  </span>
                  <Thumbnail path={step.thumbnailPath} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start gap-2">
                      <span className="min-w-0 flex-1 text-sm leading-5 font-semibold break-words text-[#19273e]">
                        {step.courseName}
                      </span>
                      <ActionButton
                        variant="text"
                        icon="close"
                        className="-mt-1.5 -mr-1"
                        aria-label={`Remove ${step.courseName}`}
                        onClick={() =>
                          setStage(stageIndex, {
                            ...stage,
                            steps: stage.steps.filter((_, i) => i !== stepIndex),
                          })
                        }
                      />
                    </div>
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[#5b6980]">
                      {step.eligible ? (
                        <span>
                          {step.moduleCount} module{step.moduleCount === 1 ? '' : 's'}
                        </span>
                      ) : (
                        <span className="text-accent-red">{step.reason ?? 'Not available'}</span>
                      )}
                      {step.otherJourneys.length > 0 && (
                        <span
                          className="rounded-full bg-[#eef2f7] px-2 py-0.5 text-[11px] text-[#344054]"
                          title={step.otherJourneys.map((j) => j.title).join(', ')}
                        >
                          Also in {step.otherJourneys.map((j) => j.title).join(', ')}
                        </span>
                      )}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
                      {mode === 'in_order' && position > 1 && (
                        <label className="flex items-center gap-2 text-xs text-[#19273e]">
                          <Switch
                            checked={step.unlockRule === 'open'}
                            label={`${step.courseName} opens anytime`}
                            onChange={(open) =>
                              setStep(stageIndex, stepIndex, {
                                unlockRule: open ? 'open' : 'after_previous',
                              })
                            }
                          />
                          Opens anytime
                        </label>
                      )}
                      <label className="flex items-center gap-2 text-xs text-[#19273e]">
                        <Switch
                          checked={!step.isRequired}
                          label={`${step.courseName} is optional`}
                          onChange={(optional) =>
                            setStep(stageIndex, stepIndex, { isRequired: !optional })
                          }
                        />
                        Optional
                      </label>
                      <span className="ml-auto flex">
                        <ActionButton
                          variant="text"
                          icon="arrow_upward"
                          aria-label={`Move ${step.courseName} up`}
                          disabled={position === 1}
                          onClick={() => onChange(moveStep(stages, stageIndex, stepIndex, -1))}
                        />
                        <ActionButton
                          variant="text"
                          icon="arrow_downward"
                          aria-label={`Move ${step.courseName} down`}
                          disabled={position === total}
                          onClick={() => onChange(moveStep(stages, stageIndex, stepIndex, 1))}
                        />
                      </span>
                    </div>
                  </div>
                </li>
              )
            })}
          </ol>
          {dragging && (
            <div
              onDragOver={(event) => {
                event.preventDefault()
                setOver(`${stageIndex}:end`)
              }}
              onDrop={(event) => {
                event.preventDefault()
                drop({ stage: stageIndex, step: stage.steps.length })
              }}
              className={clsx(
                'mt-2 rounded-lg border border-dashed p-2 text-center text-xs text-[#5b6980]',
                over === `${stageIndex}:end`
                  ? 'border-brand-blue-light bg-white'
                  : 'border-[#cfd6e2]',
              )}
            >
              {sectioned
                ? 'Drop here to move to the end of this section'
                : 'Drop here to move to the end'}
            </div>
          )}
          {picking === stageIndex ? (
            <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-brand-blue-light bg-white p-2.5">
              <select
                aria-label="Course to add"
                className="min-w-0 flex-1 rounded-lg border border-input-border bg-white px-2 py-1.5 text-sm"
                value={pick}
                onChange={(event) => setPick(event.target.value)}
              >
                <option value="">Choose a course</option>
                {available.map((option) => (
                  <option key={option.courseId} value={option.courseId}>
                    {option.courseName} ({option.moduleCount} modules)
                    {option.journeys.length > 0
                      ? `, also in ${option.journeys.map((j) => j.title).join(', ')}`
                      : ''}
                  </option>
                ))}
                {unavailable.map((option) => (
                  <option key={option.courseId} value={option.courseId} disabled>
                    {option.courseName}: {option.reason}
                  </option>
                ))}
              </select>
              <ActionButton
                variant="filled"
                disabled={!pick}
                onClick={() => {
                  const option = available.find((item) => item.courseId === pick)
                  if (!option) return
                  setStage(stageIndex, {
                    ...stage,
                    steps: [
                      ...stage.steps,
                      {
                        courseId: option.courseId,
                        courseName: option.courseName,
                        moduleCount: option.moduleCount,
                        thumbnailPath: option.thumbnailPath,
                        unlockRule: mode === 'any_order' ? 'open' : 'after_previous',
                        isRequired: true,
                        eligible: true,
                        reason: null,
                        otherJourneys: option.journeys,
                        learnerCount: 0,
                        startedCount: 0,
                      },
                    ],
                  })
                  setPick('')
                  setPicking(null)
                }}
              >
                Add
              </ActionButton>
              <ActionButton variant="text" onClick={() => setPicking(null)}>
                Cancel
              </ActionButton>
            </div>
          ) : (
            <ActionButton
              variant="text"
              icon="add"
              className="mt-1"
              onClick={() => {
                setPick('')
                setPicking(stageIndex)
              }}
            >
              Add existing course
            </ActionButton>
          )}
        </div>
      ))}
      <div>
        <ActionButton
          variant="text"
          icon="format_list_numbered"
          onClick={() =>
            onChange([...stages, { title: `Section ${stages.length + 1}`, steps: [] }])
          }
        >
          {sectioned ? 'Add section' : 'Split into sections'}
        </ActionButton>
      </div>
      {options.length > 0 && available.length === 0 && (
        <p className="text-xs text-[#5b6980]">
          All your eligible courses are in this journey. Only fully generated courses you created
          can be added.
        </p>
      )}
    </div>
  )
}

function Thumbnail({ path }: { path: string }) {
  // Re-render when the media ticket appears, so a protected image retries with it.
  useHasMediaTicket()
  const src = path ? assetUrl(path) : ''
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  if (!src || failedSrc === src)
    return (
      <span className="primary-gradient flex h-[45px] w-20 shrink-0 items-center justify-center rounded-md text-white">
        <Icon name="school_outlined" size={18} />
      </span>
    )
  return (
    <img
      src={src}
      alt=""
      className="h-[45px] w-20 shrink-0 rounded-md bg-brand-blue-100 object-cover"
      onError={() => setFailedSrc(src)}
    />
  )
}
