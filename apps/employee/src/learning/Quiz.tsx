import type { PublishedCourseModule, PublishedQuizQuestion } from '@lms/shared/models'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import clsx from 'clsx'
import { percentLabel } from '../dashboard/progress'
import { optionKey } from './moduleRules'

export interface QuizState {
  selectedAnswers: Record<number, string>
  answerResults: Record<number, boolean>
  submitted: boolean
}

export const emptyQuizState = (): QuizState => ({
  selectedAnswers: {},
  answerResults: {},
  submitted: false,
})

interface QuizSectionProps {
  module: PublishedCourseModule
  unlocked: boolean
  alreadyPassed: boolean
  score: number | null
  state: QuizState
  onSelect: (questionIndex: number, answer: string) => void
  onSubmit: () => void
  review: import('@lms/shared/models').QuizSubmissionResult | null
  reviewAction: string
  onReviewAction: () => void
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
  review,
  reviewAction,
  onReviewAction,
}: QuizSectionProps) {
  if (!unlocked && !review && !alreadyPassed) {
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
        {!state.submitted && !alreadyPassed && (
          <span className="rounded-xl bg-light-gray px-2.5 py-1 text-xs font-semibold text-gray">
            Answered {answered} of {questions.length}
          </span>
        )}
      </div>
      {(review || alreadyPassed) && (
        <div
          role="status"
          className={clsx(
            'mt-4 rounded-lg border p-4',
            review && !review.passed
              ? 'border-accent-red bg-accent-red/5'
              : 'border-accent-green bg-accent-green/5',
          )}
        >
          <h3 className="font-bold">
            {review ? (review.passed ? 'Quiz passed' : 'Quiz not passed') : 'Quiz already passed'}
          </h3>
          <p className="font-bold">
            {review ? `${review.correctCount} of ${review.totalQuestions} correct · ` : ''}
            {review
              ? `${percentLabel(review.score)}%`
              : score == null
                ? 'Saved score unavailable'
                : `${percentLabel(score)}%`}
          </p>
          <p>Pass requirement: {percentLabel(review?.passMark ?? module.passMark)}%.</p>
          <p>
            {review && !review.passed
              ? 'Rewatch the lesson before trying again.'
              : 'Review your selected answers, then continue.'}
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
      {review || alreadyPassed ? (
        <button
          type="button"
          onClick={onReviewAction}
          className="my-6 w-full rounded-lg bg-primary-blue py-4 font-bold text-white"
        >
          {reviewAction}
        </button>
      ) : (
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
  const answerCorrect = state.answerResults[index] ?? question.answerCorrect
  const groupValue = selected
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
              correct={answerCorrect}
              submitted={submitted}
              onSelect={() => onSelect(index, key)}
            />
          )
        })}
      </div>
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
  onSelect,
}: {
  name: string
  value: string
  label: string
  checked: boolean
  selected: boolean
  correct: boolean | undefined
  submitted: boolean
  onSelect: () => void
}) {
  let border = 'var(--color-light-gray)'
  let background = '#ffffff'
  let suffix: { icon: IconName; color: string } | null = null
  if (submitted) {
    if (selected && correct !== undefined) {
      border = correct ? 'var(--color-accent-green)' : 'var(--color-accent-red)'
      background = correct ? 'rgb(0 168 120 / 0.08)' : 'rgb(217 45 32 / 0.08)'
      suffix = { icon: correct ? 'check_circle_rounded' : 'cancel_rounded', color: border }
    }
  } else if (selected) {
    border = 'var(--color-primary-blue)'
    background = 'rgb(0 49 122 / 0.05)'
  }
  const emphasis = selected
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
          color:
            submitted && selected && correct !== undefined ? border : 'var(--color-text-black)',
        }}
      >
        {label}
        {submitted && selected && (
          <span className="mt-1 block text-xs">
            Your answer ·{' '}
            {correct === undefined ? 'Result unavailable' : correct ? 'Correct' : 'Incorrect'}
          </span>
        )}
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
