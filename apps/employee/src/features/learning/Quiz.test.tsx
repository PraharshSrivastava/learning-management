import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { parsePublishedCourseModule } from '@lms/shared/models'
import { QuizSection } from './Quiz'

afterEach(cleanup)
describe('selected-answer review', () => {
  it('keeps incorrect alternatives neutral even on a passed two-of-three attempt', () => {
    const module = parsePublishedCourseModule({
      module_number: 1,
      quiz: [0, 1, 2].map((i) => ({
        question: `Question ${i}`,
        options: ['Selected answer', 'Secret correct alternative'],
        correct: 'B',
        explanation: 'Secret explanation',
      })),
    })
    render(
      <QuizSection
        module={module}
        unlocked
        alreadyPassed
        score={2 / 3}
        state={{
          selectedAnswers: { 0: 'A', 1: 'A', 2: 'A' },
          answerResults: { 0: true, 1: false, 2: true },
          submitted: true,
        }}
        review={{
          passed: true,
          score: 2 / 3,
          correctCount: 2,
          totalQuestions: 3,
          passMark: 2 / 3,
          answerResults: { 0: true, 1: false, 2: true },
        }}
        onSelect={vi.fn()}
        onSubmit={vi.fn()}
        reviewAction="Continue to next module"
        onReviewAction={vi.fn()}
      />,
    )
    expect(screen.queryByText(/Answered/)).not.toBeInTheDocument()
    expect(screen.queryByText('Secret explanation')).not.toBeInTheDocument()
    const groups = screen.getAllByRole('radiogroup')
    const wrong = within(groups[1]!).getAllByRole('radio')
    expect(wrong[0]).toBeChecked()
    expect(wrong[0]!.closest('label')?.getAttribute('style')).toContain(
      '2px solid var(--color-accent-red)',
    )
    expect(wrong[1]).not.toBeChecked()
    expect(wrong[1]!.closest('label')?.getAttribute('style')).toContain(
      '1px solid var(--color-light-gray)',
    )
    expect(screen.getAllByText('Your answer · Correct')).toHaveLength(2)
    expect(screen.getAllByText('Your answer · Incorrect')).toHaveLength(1)
  })
})
