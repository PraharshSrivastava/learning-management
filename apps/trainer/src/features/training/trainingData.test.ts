import { ApiError } from '@lms/shared/api/client'
import type { CourseModule } from '@lms/shared/models'
import { describe, expect, it } from 'vitest'
import {
  generationErrorMessage,
  hasVideo,
  quizQuestions,
  slideTitle,
  transcriptSlides,
  videoDownloadFilename,
} from './trainingData'

const question = {
  question_text: 'Q1',
  options: [{ key: 'A', text: 'One' }],
  correct_option: 'A',
  explanation: 'Because',
}

describe('quizQuestions', () => {
  it('parses questions and skips entries that are not records', () => {
    const module = { quiz: { questions: [question, 'junk', null, question] } }
    expect(quizQuestions(module).map((q) => q.questionText)).toEqual(['Q1', 'Q1'])
  })

  it('returns an empty list when there is no quiz or no question list', () => {
    expect(quizQuestions({ quiz: null })).toEqual([])
    expect(quizQuestions({ quiz: {} })).toEqual([])
    expect(quizQuestions({ quiz: { questions: 'x' } })).toEqual([])
  })
})

describe('hasVideo', () => {
  it('is false for a missing or empty path', () => {
    expect(hasVideo({ videoPath: null })).toBe(false)
    expect(hasVideo({ videoPath: '' })).toBe(false)
    expect(hasVideo({ videoPath: 'assets/v.mp4' })).toBe(true)
  })
})

describe('transcriptSlides', () => {
  const module = {
    slides: [
      { slide_title: 'Cover', script: ' Hello ', is_cover_slide: true },
      { slide_title: 'Empty', script: '   ' },
      'junk',
      { script: 'Body', layout_type: 'COVER' },
      { script: 42 },
    ],
  } as Pick<CourseModule, 'slides'>

  it('keeps slides with a script, trims it, and detects cover slides', () => {
    expect(transcriptSlides(module)).toEqual([
      { title: 'Cover', script: 'Hello', isCover: true },
      { title: '', script: 'Body', isCover: true },
      { title: '', script: '42', isCover: false },
    ])
  })

  it('names slides without a title', () => {
    const [cover, body, other] = transcriptSlides(module)
    expect(slideTitle(cover!, 0)).toBe('Cover')
    expect(slideTitle(body!, 1)).toBe('Module Cover')
    expect(slideTitle(other!, 2)).toBe('Slide 3')
  })
})

describe('videoDownloadFilename', () => {
  it('builds a slug from the title', () => {
    expect(videoDownloadFilename('c1', 2, '  Code of Conduct! ')).toBe(
      'c1-module-2-code-of-conduct.mp4',
    )
  })

  it('falls back when the title is empty or has no usable characters', () => {
    expect(videoDownloadFilename('c1', 1, '   ')).toBe('c1-module-1-module.mp4')
    expect(videoDownloadFilename('c1', 1, '!!!')).toBe('c1-module-1-video.mp4')
  })
})

describe('generationErrorMessage', () => {
  it('uses the network message for status 0', () => {
    expect(generationErrorMessage(new ApiError('Offline', 0, null), 'Failed.')).toBe('Offline')
  })

  it('prefers detail.message, then a string detail', () => {
    const nested = new ApiError('x', 500, { detail: { message: 'Nested' } })
    expect(generationErrorMessage(nested, 'Failed.')).toBe('Nested')
    const plain = new ApiError('x', 400, { detail: 'Plain' })
    expect(generationErrorMessage(plain, 'Failed.')).toBe('Plain')
  })

  it('adds the status to the fallback when the body has no detail', () => {
    expect(generationErrorMessage(new ApiError('x', 502, '<html>'), 'Failed.')).toBe(
      'Failed. Server returned 502.',
    )
  })

  it('uses the fallback for other errors', () => {
    expect(generationErrorMessage(new Error('boom'), 'Failed.')).toBe('Failed.')
  })
})
