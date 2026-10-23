import { hasQuizQuestions, type Course, type CourseModule } from '@lms/shared/models'

/** Sidebar availability filter values, in Flutter order. */
export const COURSE_FILTERS = ['all', 'active', 'disabled', 'ready', 'draft'] as const
export type CourseFilter = (typeof COURSE_FILTERS)[number]

export const capitalize = (value: string): string =>
  value ? value[0]!.toUpperCase() + value.slice(1) : value

export const filterLabel = (filter: CourseFilter): string =>
  filter === 'all' ? 'All courses' : capitalize(filter)

export const filterCourses = (courses: readonly Course[], filter: CourseFilter): Course[] =>
  filter === 'all' ? [...courses] : courses.filter((course) => course.lifecycleState === filter)

/** Sidebar difficulty text color. Unknown values are gray. */
export function difficultyColor(difficulty: string): string {
  switch (difficulty.toLowerCase()) {
    case 'easy':
    case 'beginner':
      return 'var(--color-accent-green)'
    case 'medium':
    case 'intermediate':
      return 'var(--color-accent-orange)'
    case 'hard':
    case 'advanced':
      return 'var(--color-accent-red)'
    default:
      return 'var(--color-gray)'
  }
}

export const DIFFICULTIES = ['Easy', 'Medium', 'Hard'] as const
export type Difficulty = (typeof DIFFICULTIES)[number]

/** Maps a stored difficulty to the editor choice. Unknown values become Easy, as in Flutter. */
export function editorDifficulty(raw: string): Difficulty {
  switch (raw.toLowerCase()) {
    case 'medium':
    case 'intermediate':
      return 'Medium'
    case 'hard':
    case 'advanced':
      return 'Hard'
    default:
      return 'Easy'
  }
}

/** Lifecycle badge text and color. Returns null when the course has no state. */
export function lifecycleBadge(
  course: Pick<Course, 'lifecycleState' | 'status'>,
): { label: string; color: string } | null {
  const state = course.lifecycleState || course.status
  if (!state) return null
  const color = state === 'active' ? '#087F68' : state === 'archived' ? '#667085' : '#175CD3'
  return { label: capitalize(state), color }
}

export type CourseAction = 'Disable' | 'Enable' | 'Delete'

/** Actions the owner can take. Archive and Restore no longer exist. */
export function courseActions(
  course: Pick<Course, 'lifecycleState' | 'canDelete'>,
): CourseAction[] {
  const actions: CourseAction[] = []
  if (course.lifecycleState === 'active') actions.push('Disable')
  if (course.lifecycleState === 'disabled') actions.push('Enable')
  if (course.canDelete) actions.push('Delete')
  return actions
}

export const isGenerationBusy = (course: Pick<Course, 'generationStatus'>): boolean =>
  course.generationStatus === 'pending' || course.generationStatus === 'running'

const moduleIsBuilt = (module: CourseModule): boolean =>
  !!module.videoPath &&
  module.quiz != null &&
  (hasQuizQuestions(module.quiz) || module.numQuestions <= 0)

export interface GenerateButtonState {
  label: string
  icon: 'play_arrow' | 'auto_awesome'
  /** Gray when the course is complete, else orange. */
  complete: boolean
  enabled: boolean
  /** True when the button continues from a failed checkpoint. */
  resume: boolean
  tooltip: string | null
}

/** The header "Generate Course" button, from course_portal.dart. */
export function generateButtonState(
  course: Course,
  editorModuleCount: number,
  jobRunning: boolean,
): GenerateButtonState {
  const hasModules = editorModuleCount > 0
  const checkpoint = course.failedCheckpoint || course.currentCheckpoint
  const resume = course.generationStatus === 'failed' && checkpoint !== ''
  const generating = jobRunning || (course.generationStatus === 'running' && !resume)
  const fullyGenerated =
    hasModules && course.thumbnailPath !== '' && course.modules.every(moduleIsBuilt)
  const label = generating
    ? 'Generating...'
    : resume
      ? checkpoint === 'wave_1'
        ? 'Continue generation'
        : `Continue from ${checkpoint}`
      : fullyGenerated
        ? 'Already Generated'
        : 'Generate Course'
  return {
    label,
    icon: resume ? 'play_arrow' : 'auto_awesome',
    complete: fullyGenerated && !resume,
    enabled: !generating && (resume || (hasModules && !fullyGenerated)),
    resume,
    tooltip: resume && course.generationError ? course.generationError : null,
  }
}

/** True when every module has a video and its quiz. Used to pick the tab after a resume. */
export const isCourseFullyGenerated = (course: Course): boolean =>
  course.modules.length > 0 && course.thumbnailPath !== '' && course.modules.every(moduleIsBuilt)

/** One module row in the blueprint editor. */
export interface ModuleDraft {
  /** Stable React key. */
  key: string
  /** The loaded module, or null for a module added in the editor. */
  original: CourseModule | null
  title: string
  sourceText: string
  numQuestions: string
}

export interface BlueprintDraft {
  name: string
  description: string
  objective: string
  audience: string
  language: string
  difficulty: Difficulty
  modules: ModuleDraft[]
}

let draftSerial = 0
const nextKey = () => `module-${++draftSerial}`

export function blueprintDraft(course: Course): BlueprintDraft {
  return {
    name: course.courseName,
    description: course.courseDescription,
    objective: course.courseObjective,
    audience: course.targetAudience,
    language: course.language,
    difficulty: editorDifficulty(course.courseDifficulty),
    modules: course.modules.map((module) => ({
      key: nextKey(),
      original: module,
      title: module.title,
      sourceText: module.sourceText,
      numQuestions: String(module.numQuestions),
    })),
  }
}

export const newModuleDraft = (): ModuleDraft => ({
  key: nextKey(),
  original: null,
  title: '',
  sourceText: '',
  numQuestions: '3',
})

/** Dart int.tryParse: whole decimal integers only, else null. */
function parseWholeNumber(text: string): number | null {
  return /^[+-]?\d+$/.test(text) ? Number.parseInt(text, 10) : null
}

/** PUT /api/courses/{id} body. Modules with a blank title are left out, as in Flutter. */
export function blueprintPayload(draft: BlueprintDraft) {
  return {
    course_name: draft.name.trim(),
    course_description: draft.description.trim(),
    course_objective: draft.objective.trim(),
    target_audience: draft.audience.trim(),
    language: draft.language.trim(),
    course_difficulty: draft.difficulty,
    modules: draft.modules
      .filter((module) => module.title.trim() !== '')
      .map((module) => ({
        title: module.title.trim(),
        source_text: module.sourceText.trim(),
        num_questions: parseWholeNumber(module.numQuestions.trim()) ?? 0,
        start_line: module.original?.startLine ?? '',
      })),
  }
}

/** Fields that reset the editor when the server copy changes, as in didUpdateWidget. */
export const editorSignature = (course: Course): string =>
  JSON.stringify([
    course.courseId,
    course.courseName,
    course.courseDescription,
    course.courseObjective,
    course.courseDifficulty,
    course.language,
    course.targetAudience,
    course.modules.length,
    course.thumbnailPath,
  ])

/** Module number that holds an extracted image, from the editor order. */
export function moduleNumberForImage(
  modules: readonly ModuleDraft[],
  imageId: string,
): number | null {
  for (const [index, module] of modules.entries()) {
    if (module.original?.images.some((image) => image.imageId === imageId)) {
      return index + 1
    }
  }
  return null
}

export function moveItem<T>(items: readonly T[], from: number, to: number): T[] {
  const next = [...items]
  const [item] = next.splice(from, 1)
  if (item === undefined) return next
  next.splice(to, 0, item)
  return next
}
