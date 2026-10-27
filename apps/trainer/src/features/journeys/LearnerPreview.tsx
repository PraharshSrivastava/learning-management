// "Preview as learner": the journey's roadmap as an employee will see it when it opens.
import { Dialog } from '@lms/shared/ui/Dialog'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { ActionButton } from '../assignments/controls'
import type { JourneyDetail } from './api'

export function LearnerPreview({
  open,
  onOpenChange,
  journey,
  prerequisiteTitle,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  journey: JourneyDetail
  prerequisiteTitle: string | null
}) {
  const steps = journey.stages.flatMap((stage) => stage.steps)
  const showSections = journey.stages.length > 1
  const offsets = journey.stages.map((_, i) =>
    journey.stages.slice(0, i).reduce((sum, stage) => sum + stage.steps.length, 0),
  )
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Preview as learner"
      width={640}
      actions={
        <ActionButton variant="filled" onClick={() => onOpenChange(false)}>
          Close
        </ActionButton>
      }
    >
      <div className="rounded-2xl bg-white p-5 text-[#172033]">
        <p className="text-[11px] font-semibold tracking-[1.1px] text-[#5f6878] uppercase">
          Learning journey
        </p>
        <h3 className="mt-1 text-xl leading-7 font-bold text-primary-blue">
          {journey.title || 'Untitled journey'}
        </h3>
        {journey.description && (
          <p className="mt-2 text-sm whitespace-pre-line text-[#5f6878]">{journey.description}</p>
        )}
        <p className="mt-2 text-xs text-[#5f6878]">
          {steps.length} course{steps.length === 1 ? '' : 's'}
          {prerequisiteTitle ? ` · Opens after finishing ${prerequisiteTitle}` : ''}
        </p>
        {steps.length === 0 ? (
          <p className="mt-4 text-sm text-[#5f6878]">Add courses to see the roadmap.</p>
        ) : (
          journey.stages.map((stage, stageIndex) =>
            stage.steps.length === 0 ? null : (
              <section key={stageIndex} className="mt-4">
                {showSections && (
                  <h4 className="mb-2 text-xs font-semibold tracking-[0.6px] text-[#5f6878] uppercase">
                    {stage.title || `Section ${stageIndex + 1}`}
                  </h4>
                )}
                <ol className="m-0 flex list-none flex-col gap-2 p-0">
                  {stage.steps.map((step, stepIndex) => {
                    const index = (offsets[stageIndex] ?? 0) + stepIndex
                    const previous = steps[index - 1]
                    const opens = index === 0 || step.unlockRule === 'open'
                    return (
                      <li
                        key={step.courseId}
                        className="flex items-start gap-3 rounded-xl border border-[#ebeff4] p-3"
                      >
                        <span
                          className={
                            opens
                              ? 'inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-primary-blue text-sm font-bold text-white'
                              : 'inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-[#ebeff4] text-sm font-bold text-[#5f6878]'
                          }
                        >
                          {index + 1}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm font-semibold break-words">
                            {step.courseName}
                            {!step.isRequired && (
                              <span className="ml-2 rounded-full bg-[#ebeff4] px-2 py-0.5 text-[11px] font-medium text-[#5f6878]">
                                Optional
                              </span>
                            )}
                          </span>
                          <span className="mt-0.5 flex items-center gap-1 text-xs text-[#5f6878]">
                            <Icon name={opens ? 'play_circle_outline' : 'lock_outline'} size={14} />
                            {opens
                              ? 'Available when the journey opens'
                              : `Opens after ${previous?.courseName ?? 'the previous course'} is passed`}
                            {` · ${step.moduleCount} module${step.moduleCount === 1 ? '' : 's'}`}
                          </span>
                        </span>
                      </li>
                    )
                  })}
                </ol>
              </section>
            ),
          )
        )}
        {journey.certificateEnabled && steps.length > 0 && (
          <p className="mt-4 flex items-center gap-2 rounded-xl bg-[#f2f6fc] p-3 text-xs text-[#172033]">
            <Icon name="verified_outlined" size={18} className="text-primary-blue" />A certificate
            of completion from PhillipCapital India Pvt Ltd, downloadable as a PDF once every
            required course is passed.
          </p>
        )}
      </div>
    </Dialog>
  )
}
