import { parseCourse } from '@lms/shared/models'
import { describe, expect, it } from 'vitest'
import {
  blueprintDraft,
  blueprintPayload,
  courseActions,
  editorDifficulty,
  filterCourses,
  generateButtonState,
  lifecycleBadge,
  moveItem,
  moduleNumberForImage,
  newModuleDraft,
} from './courseLogic'
import { courseJson } from './test/renderCourses'

const builtModule = (n: number) => ({
  module_number: n,
  title: `M${n}`,
  video_path: `assets/videos/c1/m${n}.mp4`,
  num_questions: 1,
  quiz: { questions: [{ question_text: 'Q', options: [], correct_option: 'A' }] },
})

describe('courseLogic', () => {
  it('keeps source image badges aligned with the current module order and marks removed mappings unassigned', () => {
    const course = parseCourse(
      courseJson({
        images: [{ image_id: 'img1', file_path: 'assets/chart.png', caption: 'Chart' }],
      }),
    )
    course.modules[0]!.images = [course.images[0]!]
    const modules = blueprintDraft(course).modules
    expect(moduleNumberForImage(modules, 'img1')).toBe(1)
    expect(moduleNumberForImage(moveItem(modules, 0, 1), 'img1')).toBe(2)
    expect(moduleNumberForImage(modules.slice(1), 'img1')).toBeNull()
  })
  it('filters by lifecycle state', () => {
    const courses = ['active', 'disabled', 'draft'].map((state, i) =>
      parseCourse(courseJson({ course_id: `c${i}`, lifecycle_state: state })),
    )
    expect(filterCourses(courses, 'all')).toHaveLength(3)
    expect(filterCourses(courses, 'disabled').map((c) => c.courseId)).toEqual(['c1'])
    expect(filterCourses(courses, 'ready')).toEqual([])
  })

  it('maps difficulties to the editor choice, unknown as Easy', () => {
    expect(editorDifficulty('Intermediate')).toBe('Medium')
    expect(editorDifficulty('advanced')).toBe('Hard')
    expect(editorDifficulty('Expert')).toBe('Easy')
  })

  it('offers lifecycle actions by state', () => {
    expect(courseActions({ lifecycleState: 'active', canDelete: false })).toEqual(['Disable'])
    expect(courseActions({ lifecycleState: 'disabled', canDelete: false })).toEqual(['Enable'])
    expect(courseActions({ lifecycleState: 'draft', canDelete: true })).toEqual(['Delete'])
    expect(courseActions({ lifecycleState: 'archived', canDelete: false })).toEqual([])
  })

  it('labels the lifecycle badge, with status as the fallback', () => {
    expect(lifecycleBadge({ lifecycleState: 'active', status: '' })).toEqual({
      label: 'Active',
      color: '#087F68',
    })
    expect(lifecycleBadge({ lifecycleState: '', status: 'ready' })?.label).toBe('Ready')
    expect(lifecycleBadge({ lifecycleState: '', status: '' })).toBeNull()
  })

  it('drops blank module titles and parses whole quiz counts only', () => {
    const draft = blueprintDraft(parseCourse(courseJson()))
    draft.name = '  Renamed  '
    draft.modules[1]!.numQuestions = '2.5'
    draft.modules.push({ ...newModuleDraft(), title: '   ' })
    const payload = blueprintPayload(draft)
    expect(payload.course_name).toBe('Renamed')
    expect(payload.course_difficulty).toBe('Medium')
    expect(payload.modules.map((m) => [m.title, m.num_questions])).toEqual([
      ['Basics', 2],
      ['Reporting', 0],
    ])
  })

  it('moves items', () => {
    expect(moveItem(['a', 'b', 'c'], 0, 2)).toEqual(['b', 'c', 'a'])
    expect(moveItem(['a', 'b'], 5, 0)).toEqual(['a', 'b'])
  })

  describe('generate button', () => {
    it('is orange and enabled for a course with modules', () => {
      const state = generateButtonState(parseCourse(courseJson()), 2, false)
      expect(state).toMatchObject({ label: 'Generate Course', enabled: true, complete: false })
    })

    it('is disabled without modules', () => {
      expect(generateButtonState(parseCourse(courseJson()), 0, false).enabled).toBe(false)
    })

    it('shows Already Generated when every module is built', () => {
      const course = parseCourse(
        courseJson({ thumbnail_path: 'thumb.png', modules: [builtModule(1), builtModule(2)] }),
      )
      expect(generateButtonState(course, 2, false)).toMatchObject({
        label: 'Already Generated',
        enabled: false,
        complete: true,
      })
    })

    it('resumes from the failed checkpoint with the error as tooltip', () => {
      const course = parseCourse(
        courseJson({
          generation: { status: 'failed', failed_checkpoint: 'wave_2', error: 'Boom' },
        }),
      )
      expect(generateButtonState(course, 2, false)).toMatchObject({
        label: 'Continue from wave_2',
        icon: 'play_arrow',
        resume: true,
        enabled: true,
        tooltip: 'Boom',
      })
      const first = parseCourse(
        courseJson({ generation: { status: 'failed', failed_checkpoint: 'wave_1' } }),
      )
      expect(generateButtonState(first, 2, false).label).toBe('Continue generation')
    })

    it('shows Generating... while a job runs', () => {
      const state = generateButtonState(parseCourse(courseJson()), 2, true)
      expect(state).toMatchObject({ label: 'Generating...', enabled: false })
    })
  })
})
