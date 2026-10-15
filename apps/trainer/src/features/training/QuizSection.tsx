import { Icon } from '@lms/shared/ui/icons/Icon'
import { ProgressBar } from '@lms/shared/ui/ProgressBar'
import type { QuizQuestion } from '@lms/shared/models'
import clsx from 'clsx'
import { ActionButton } from './ActionButton'
import { ring } from './flutterStyle'

export interface QuizAnswers {
  selected: Readonly<Record<string, string>>
  submitted: Readonly<Record<string, boolean>>
}

interface QuizSectionProps {
  moduleIndex: number
  questions: QuizQuestion[]
  answers: QuizAnswers
  onSelect: (key: string, option: string) => void
  onSubmit: (key: string) => void
  onReset: (keys: string[]) => void
}

/** Answer state is keyed by position plus question text, so a regenerated quiz starts clean. */
export const answerKey = (moduleIndex: number, index: number, question: QuizQuestion): string =>
  `${moduleIndex}-${index}-${question.questionText}`

export function QuizSection({
  moduleIndex,
  questions,
  answers,
  onSelect,
  onSubmit,
  onReset,
}: QuizSectionProps) {
  const keys = questions.map((question, index) => answerKey(moduleIndex, index, question))
  let submittedCount = 0
  let correctCount = 0
  questions.forEach((question, index) => {
    const key = keys[index]
    if (key === undefined || answers.submitted[key] !== true) return
    submittedCount++
    if (answers.selected[key] === question.correctOption) correctCount++
  })

  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between">
        <h3 className="m-0 font-inter text-lg font-bold text-primary-blue">Module Quiz</h3>
        <span className="rounded-xl bg-accent-green/12 px-2.5 py-1 font-inter text-xs font-bold text-accent-green">
          {questions.length} Questions
        </span>
      </div>
      <div className="h-5" />
      {questions.map((question, index) => {
        const key = keys[index] ?? String(index)
        return (
          <QuestionCard
            key={key}
            index={index}
            question={question}
            selected={answers.selected[key]}
            submitted={answers.submitted[key] === true}
            onSelect={(option) => onSelect(key, option)}
            onSubmit={() => onSubmit(key)}
          />
        )
      })}
      <SummaryCard
        total={questions.length}
        submitted={submittedCount}
        correct={correctCount}
        onReset={() => onReset(keys)}
      />
    </div>
  )
}

interface QuestionCardProps {
  index: number
  question: QuizQuestion
  selected: string | undefined
  submitted: boolean
  onSelect: (option: string) => void
  onSubmit: () => void
}

function QuestionCard({
  index,
  question,
  selected,
  submitted,
  onSelect,
  onSubmit,
}: QuestionCardProps) {
  return (
    <article className="mb-5 rounded-xl border border-light-gray bg-white p-5">
      <p className="m-0 font-inter text-[11px] font-bold tracking-[1px] text-gray">
        QUESTION {index + 1}
      </p>
      <div className="h-2" />
      <p className="m-0 font-inter text-sm leading-[1.4] font-semibold text-text-black">
        {question.questionText}
      </p>
      <div className="h-4" />
      <div role="radiogroup" aria-label={`Question ${index + 1} options`}>
        {question.options.map((option) => (
          <OptionRow
            key={option.key}
            optionKey={option.key}
            text={option.text}
            isSelected={selected === option.key}
            isCorrect={question.correctOption === option.key}
            submitted={submitted}
            onSelect={() => onSelect(option.key)}
          />
        ))}
      </div>
      <div className="h-3" />
      {submitted ? (
        <>
          <div className="h-2" />
          <div className="flex items-start rounded-lg border border-[#eee] bg-[#fafafa] p-3.5">
            <Icon name="info_outline_rounded" size={18} color="rgb(0 49 122 / 0.8)" />
            <div className="ml-2.5 min-w-0 flex-1">
              <p className="m-0 font-inter text-xs font-bold text-text-black">Explanation</p>
              <p className="mt-1 mb-0 font-inter text-xs leading-[1.4] text-gray">
                {question.explanation}
              </p>
            </div>
          </div>
        </>
      ) : (
        <div className="flex justify-end">
          <ActionButton
            iconSize={16}
            padding="8px 16px"
            disabled={selected === undefined}
            onClick={onSubmit}
            disabledClassName="disabled:bg-[#eee] disabled:text-[#bdbdbd]"
          >
            Check Answer
          </ActionButton>
        </div>
      )}
    </article>
  )
}

interface OptionRowProps {
  optionKey: string
  text: string
  isSelected: boolean
  isCorrect: boolean
  submitted: boolean
  onSelect: () => void
}

function OptionRow({
  optionKey,
  text,
  isSelected,
  isCorrect,
  submitted,
  onSelect,
}: OptionRowProps) {
  const correctShown = submitted && isCorrect
  const wrongShown = submitted && !isCorrect && isSelected
  const highlighted = isSelected || correctShown

  let borderColor = 'var(--color-light-gray)'
  let background = '#fff'
  if (submitted) {
    if (isCorrect) {
      borderColor = 'var(--color-accent-green)'
      background = 'rgb(0 168 120 / 0.08)'
    } else if (isSelected) {
      borderColor = 'var(--color-accent-red)'
      background = 'rgb(217 45 32 / 0.08)'
    } else {
      background = '#fafafa'
    }
  } else if (isSelected) {
    borderColor = 'var(--color-primary-blue)'
    background = 'rgb(0 49 122 / 0.05)'
  }

  let circle = '#f5f5f5'
  if (isSelected) {
    circle = submitted
      ? isCorrect
        ? 'var(--color-accent-green)'
        : 'var(--color-accent-red)'
      : 'var(--color-primary-blue)'
  } else if (correctShown) {
    circle = 'var(--color-accent-green)'
  }

  return (
    <button
      type="button"
      role="radio"
      aria-checked={isSelected}
      disabled={submitted}
      onClick={onSelect}
      className="mb-2 flex w-full items-center rounded-lg px-[15px] py-[11px] text-left font-inter transition-shadow focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light disabled:cursor-default"
      style={{
        background,
        boxShadow: ring(isSelected || correctShown ? 1.5 : 1, borderColor),
      }}
    >
      <span
        className="flex size-[22px] shrink-0 items-center justify-center rounded-full text-[11px] leading-none font-bold"
        style={{
          background: circle,
          color: highlighted ? '#fff' : 'var(--color-text-black)',
          boxShadow: highlighted ? undefined : 'inset 0 0 0 1px #e0e0e0',
        }}
      >
        {optionKey}
      </span>
      <span
        className={clsx(
          'ml-3 min-w-0 flex-1 text-[13.5px]',
          isSelected ? 'font-semibold' : 'font-medium',
          submitted && !isCorrect && !isSelected ? 'text-gray' : 'text-text-black',
        )}
      >
        {text}
      </span>
      {correctShown && (
        <Icon
          name="check_circle_rounded"
          size={18}
          color="var(--color-accent-green)"
          className="ml-2.5"
        />
      )}
      {wrongShown && (
        <Icon name="cancel_rounded" size={18} color="var(--color-accent-red)" className="ml-2.5" />
      )}
    </button>
  )
}

interface SummaryCardProps {
  total: number
  submitted: number
  correct: number
  onReset: () => void
}

function SummaryCard({ total, submitted, correct, onReset }: SummaryCardProps) {
  return (
    <section className="mt-2 mb-5 rounded-xl bg-primary-blue p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="m-0 font-inter text-[11px] font-bold text-white/70">Quiz Progress</p>
          <p className="mt-1 mb-0 font-inter text-lg font-bold text-white">
            {submitted === total ? 'Completed!' : 'In Progress'}
          </p>
        </div>
        <span className="rounded-full bg-white/15 p-2.5 font-inter text-lg font-bold text-white">
          {correct} / {total}
        </span>
      </div>
      <div className="h-4" />
      <ProgressBar
        value={total > 0 ? submitted / total : 0}
        color="#fff"
        trackColor="rgb(255 255 255 / 0.24)"
        height={6}
        radius={10}
        label="Quiz progress"
      />
      <div className="h-4" />
      <div className="flex justify-end">
        <ActionButton
          outlined
          icon="refresh_rounded"
          iconSize={14}
          padding="10px 14px"
          onClick={onReset}
          className="text-white shadow-[inset_0_0_0_1px_rgb(255_255_255/0.6)] hover:bg-white/8"
        >
          Reset Quiz
        </ActionButton>
      </div>
    </section>
  )
}
