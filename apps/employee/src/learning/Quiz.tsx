import type { PublishedCourseModule, PublishedQuizQuestion } from '@lms/shared/models'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import clsx from 'clsx'
import { percentLabel } from '../dashboard/progress'
import { optionKey } from './moduleRules'

export interface QuizState {
  selectedAnswers: Record<number, string>
  gradedCorrectAnswers: Record<number, string>
  gradedExplanations: Record<number, string>
  submitted: boolean
}

export const emptyQuizState = (): QuizState => ({
  selectedAnswers: {},
  gradedCorrectAnswers: {},
  gradedExplanations: {},
  submitted: false,
})

interface QuizSectionProps {
  module: PublishedCourseModule
  unlocked: boolean
  alreadyPassed: boolean
  score: number
  state: QuizState
  onSelect: (questionIndex: number, answer: string) => void
  onSubmit: () => void
}

/** Flutter `_buildQuizSection`: locked, no quiz, or the questions with grading. */
export function QuizSection({
  module,
  unlocked,
  alreadyPassed,
  score,
  state,
  onSelect,
  onSubmit,
}: QuizSectionProps) {
  if (!unlocked) {
    return (
      <div className="flex items-start gap-3 rounded-[10px] border border-[#f3d19c] bg-[#fff8e8] p-6">
        <Icon name="lock_outline" color="#8a5a00" />
        <div className="min-w-0 flex-1">
          <p className="m-0 font-bold text-[#704a00]">Quiz locked</p>
          <p className="m-0 mt-1 text-[13px] text-[#704a00]">
            Finish the video lesson to unlock this knowledge check.
          </p>
        </div>
      </div>
    )
  }
  const questions = module.quiz
  if (questions.length === 0) {
    return (
      <div className="flex items-center gap-3 rounded-[10px] border border-[#b7e4c7] bg-[#effaf3] p-5">
        <Icon name="check_circle_outline" color="#087443" />
        <p className="m-0 min-w-0 flex-1 font-semibold text-[#087443]">
          No quiz is required for this module. Finish the video lesson to continue.
        </p>
      </div>
    )
  }
  const answered = Object.keys(state.selectedAnswers).length
  return (
    <section aria-label="Module quiz">
      <div className="flex items-center justify-between">
        <h2 className="m-0 font-inter text-[18px] font-bold text-primary-blue">Module Quiz</h2>
        <span className="rounded-xl bg-accent-green/12 px-2.5 py-1 font-inter text-[12px] font-bold text-accent-green">
          {answered}/{questions.length} answered
        </span>
      </div>
      {alreadyPassed && (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-accent-green bg-accent-green/10 p-4">
          <Icon name="check_circle" color="var(--color-accent-green)" />
          <p className="m-0 min-w-0 flex-1 font-inter font-bold text-accent-green">
            You have already passed this quiz with a score of {percentLabel(score)}%. You can review
            the questions below.
          </p>
        </div>
      )}
      <div className="h-5" />
      {questions.map((question, index) => (
        <QuestionCard
          key={`${module.moduleNumber}_${index}`}
          index={index}
          question={question}
          alreadyPassed={alreadyPassed}
          state={state}
          onSelect={onSelect}
        />
      ))}
      {!alreadyPassed && (
        <div className="py-6">
          <button
            type="button"
            disabled={state.submitted || answered < questions.length}
            onClick={onSubmit}
            className="w-full rounded-lg bg-primary-blue py-4 text-[16px] font-bold text-white transition-colors hover:bg-[#0a3d8a] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light disabled:cursor-not-allowed disabled:bg-[#1a1c1e]/12 disabled:text-[#1a1c1e]/38"
          >
            {state.submitted ? 'Submitted' : 'Submit Quiz'}
          </button>
        </div>
      )}
    </section>
  )
}

function QuestionCard({
  index,
  question,
  alreadyPassed,
  state,
  onSelect,
}: {
  index: number
  question: PublishedQuizQuestion
  alreadyPassed: boolean
  state: QuizState
  onSelect: (questionIndex: number, answer: string) => void
}) {
  const selected = state.selectedAnswers[index]
  const submitted = state.submitted || alreadyPassed
  const correct = question.correct || state.gradedCorrectAnswers[index] || ''
  const explanation = question.explanation || state.gradedExplanations[index] || ''
  // When passed, the radio shows the correct answer, as the Flutter groupValue does.
  const groupValue = alreadyPassed && correct ? correct : selected
  const name = `question-${index}`
  return (
    <div className="mb-5 rounded-xl border border-light-gray bg-white p-5">
      <p className="m-0 font-inter text-[11px] font-bold tracking-[1px] text-gray">
        QUESTION {index + 1}
      </p>
      <p
        id={`${name}-text`}
        className="m-0 mt-2 font-inter text-[14px] leading-[1.4] font-semibold text-text-black"
      >
        {question.question}
      </p>
      <div role="radiogroup" aria-labelledby={`${name}-text`} className="mt-4">
        {question.options.map((option, optionIndex) => {
          const key = optionKey(optionIndex)
          return (
            <Option
              key={key}
              name={name}
              value={key}
              label={option}
              checked={groupValue === key}
              selected={selected === key}
              correct={correct === key}
              submitted={submitted}
              alreadyPassed={alreadyPassed}
              onSelect={() => onSelect(index, key)}
            />
          )
        })}
      </div>
      {submitted && explanation && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-light-gray/50 p-3">
          <Icon name="lightbulb_outline" size={18} color="var(--color-accent-orange)" />
          <p className="m-0 min-w-0 flex-1 font-inter text-[13px] text-text-black/80 italic">
            {explanation}
          </p>
        </div>
      )}
    </div>
  )
}

function Option({
  name,
  value,
  label,
  checked,
  selected,
  correct,
  submitted,
  alreadyPassed,
  onSelect,
}: {
  name: string
  value: string
  label: string
  checked: boolean
  selected: boolean
  correct: boolean
  submitted: boolean
  alreadyPassed: boolean
  onSelect: () => void
}) {
  let border = 'var(--color-light-gray)'
  let background = '#ffffff'
  let suffix: { icon: IconName; color: string } | null = null
  if (submitted) {
    if (correct) {
      border = 'var(--color-accent-green)'
      background = 'rgb(0 168 120 / 0.08)'
      suffix = { icon: 'check_circle_rounded', color: 'var(--color-accent-green)' }
    } else if (selected && !alreadyPassed) {
      border = 'var(--color-accent-red)'
      background = 'rgb(217 45 32 / 0.08)'
      suffix = { icon: 'cancel_rounded', color: 'var(--color-accent-red)' }
    } else {
      background = '#fafafa'
    }
  } else if (selected) {
    border = 'var(--color-primary-blue)'
    background = 'rgb(0 49 122 / 0.05)'
  }
  const emphasis = selected || (submitted && correct)
  return (
    // `relative` holds the hidden radio inside the row, so it cannot stretch the page.
    <label
      className={clsx(
        'relative mb-2 flex min-h-14 items-center rounded-lg pr-6 pl-4',
        submitted ? 'cursor-default' : 'cursor-pointer hover:brightness-[0.98]',
      )}
      style={{ backgroundColor: background, border: `${emphasis ? 2 : 1}px solid ${border}` }}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        disabled={submitted}
        onChange={onSelect}
        className="peer sr-only"
      />
      <RadioMark checked={checked} disabled={submitted} />
      <span
        className={clsx(
          'ml-4 min-w-0 flex-1 py-2 font-inter text-[14px]',
          emphasis ? 'font-semibold' : 'font-normal',
        )}
        style={{
          color: submitted && correct ? 'var(--color-accent-green)' : 'var(--color-text-black)',
        }}
      >
        {label}
      </span>
      {suffix && <Icon name={suffix.icon} size={18} color={suffix.color} className="ml-4" />}
    </label>
  )
}

/** Material 3 radio: 20 px ring with a 10 px dot. Disabled radios use the grey on-surface colour. */
function RadioMark({ checked, disabled }: { checked: boolean; disabled: boolean }) {
  const color = disabled
    ? 'rgb(26 28 30 / 0.38)'
    : checked
      ? 'var(--color-primary-blue)'
      : '#44474e'
  return (
    <span
      aria-hidden
      className="flex size-10 shrink-0 items-center justify-center rounded-full peer-focus-visible:bg-primary-blue/12"
    >
      <span
        className="flex size-5 items-center justify-center rounded-full border-2"
        style={{ borderColor: color }}
      >
        {checked && <span className="size-2.5 rounded-full" style={{ backgroundColor: color }} />}
      </span>
    </span>
  )
}
