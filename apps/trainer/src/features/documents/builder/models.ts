// Document builder data, ported from document_builder_models.dart.

export interface BuilderMetadata {
  courseName: string
  courseDescription: string
  courseObjective: string
  courseDifficulty: string
  language: string
  targetAudience: string
  courseType: string
}

export const emptyMetadata: BuilderMetadata = {
  courseName: '',
  courseDescription: '',
  courseObjective: '',
  courseDifficulty: '',
  language: 'English',
  targetAudience: '',
  courseType: '',
}

const metadataLabels: Record<keyof BuilderMetadata, string> = {
  courseName: 'Course name',
  courseDescription: 'Course description',
  courseObjective: 'Course objective',
  courseDifficulty: 'Course difficulty',
  language: 'Language',
  targetAudience: 'Target audience',
  courseType: 'Course type',
}

export const metadataKeys = Object.keys(metadataLabels) as (keyof BuilderMetadata)[]

/** Labels of the required fields that are blank after trim, in form order. */
export function missingFields(metadata: BuilderMetadata): string[] {
  return metadataKeys.filter((key) => !metadata[key].trim()).map((key) => metadataLabels[key])
}

/** The JSON body sends every metadata value trimmed. */
export function metadataJson(metadata: BuilderMetadata): BuilderMetadata {
  const result = { ...metadata }
  for (const key of metadataKeys) result[key] = metadata[key].trim()
  return result
}

export interface BuilderSettings {
  moduleCount: number
  detailLevel: string
  tone: string
  writingFocus: string
  includeScenarios: boolean
  includeBadGood: boolean
  includeTakeaways: boolean
  includeMistakes: boolean
}

export const defaultSettings: BuilderSettings = {
  moduleCount: 4,
  detailLevel: 'standard',
  tone: 'Clear and professional',
  writingFocus: 'balanced',
  includeScenarios: true,
  includeBadGood: true,
  includeTakeaways: true,
  includeMistakes: true,
}

/** Module count field: integer parse, 4 when not a number, clamped to 2..8. */
export function parseModuleCount(value: string): number {
  // Dart int.tryParse accepts only an optional sign and digits.
  const trimmed = value.trim()
  const parsed = /^[+-]?\d+$/.test(trimmed) ? Number.parseInt(trimmed, 10) : 4
  return Math.min(8, Math.max(2, parsed))
}

export type ImageAlign = 'left' | 'center' | 'right'

export interface BuilderBlock {
  type: 'text' | 'image'
  text: string
  src: string
  width: number
  align: string
  caption: string
}

export const textBlock = (text: string): BuilderBlock => ({
  type: 'text',
  text,
  src: '',
  width: 60,
  align: 'left',
  caption: '',
})

export const imageBlock = (src: string, width: number, align: string, caption: string) =>
  ({ type: 'image', text: '', src, width, align, caption }) satisfies BuilderBlock

export interface ChatMessage {
  user: boolean
  text: string
}

/** Cuts any text before the first "Module N:" line. */
export function moduleOnly(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return ''
  const match = /^Module\s+\d+\s*:/im.exec(trimmed)
  if (!match || match.index <= 0) return trimmed
  return trimmed.slice(match.index).trim()
}

/** Download name stem: lowercase, non [a-z0-9] runs become "-", trimmed, max 60. */
export function safeName(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 60)
}

export const difficultyOptions = [
  { value: '', label: 'Select difficulty' },
  { value: 'Easy', label: 'Easy' },
  { value: 'Beginner to Intermediate', label: 'Beginner to Intermediate' },
  { value: 'Intermediate', label: 'Intermediate' },
  { value: 'Advanced', label: 'Advanced' },
]

export const detailOptions = [
  { value: 'standard', label: 'Standard' },
  { value: 'short', label: 'Short' },
  { value: 'detailed', label: 'Detailed' },
]

export const toneOptions = [
  'Clear and professional',
  'Warm and conversational',
  'Compliance-safe',
  'Step-by-step operational',
].map((value) => ({ value, label: value }))

export const focusOptions = [
  { value: 'balanced', label: 'Balanced explanation and application' },
  { value: 'conceptual', label: 'Concept explanation' },
  { value: 'practical', label: 'Practical application' },
  { value: 'process', label: 'Step-by-step process' },
]

export const builderText = {
  intro:
    'Save metadata separately if you need it for the LMS. Apply builder settings when you want them to affect future AI edits. Type normally in the draft and paste or drag images where you want them.',
  metadataSaved: 'Metadata saved separately. It will not be sent to the AI document writer.',
  settingsApplied: 'Builder settings applied for future AI drafts and edits.',
  questions:
    'Before finalizing, I would ask:\n\nShould the draft be short, standard, or detailed?\nShould examples be practical, policy-focused, process-focused, or avoided?\nWhich module should get the most depth?\nShould the writing focus more on concepts, application, or step-by-step process?',
  emptyDraft: 'Add or generate module content before PDF preview/download.',
  buildDefault: 'I updated the module-only draft on the right.',
  copied: 'Copied the current document text.',
  saved: 'Document saved successfully. It is now available in Documents.',
  missing: (labels: string[]) =>
    `Fill these metadata fields before PDF preview/download:\n\n${labels.join('\n')}`,
  renderError: (error: string) => `Could not render PDF preview.\n\nError: ${error}`,
  buildError: (error: string) => `No LLM document was generated.\n\nError: ${error}`,
  saveError: (error: string) => `Could not save PDF.\n\nError: ${error}`,
  copyError: (error: string) => `Could not copy the document text.\n\nError: ${error}`,
}
