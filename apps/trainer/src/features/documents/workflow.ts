import { apiRequest, type RequestOptions } from '@lms/shared/api/client'
import { sha256Text } from '@lms/shared/crypto/sha256Text.js'

export type TextBlock = {
  id: string
  type: 'paragraph' | 'heading' | 'scenario' | 'takeaway'
  text: string
  marks: { start: number; end: number; type: string; href?: string | null }[]
  level: number
  sourceReferences: unknown[]
}
export type Block =
  | TextBlock
  | { id: string; type: 'list'; items: string[]; ordered: boolean; sourceReferences: unknown[] }
  | { id: string; type: 'table'; rows: string[][]; sourceReferences: unknown[] }
  | {
      id: string
      type: 'image'
      assetId: string
      caption: string
      width: number
      align: 'left' | 'center' | 'right'
      sourceReferences: unknown[]
    }
export type Module = {
  id: string
  title: string
  objective: string
  included: boolean
  sections: string[]
  blocks: Block[]
  sourceReferences: unknown[]
  status: 'empty' | 'ready' | 'generating' | 'failed'
}
export type Content = {
  schemaVersion: 1
  entryMode: 'ai' | 'blank' | 'existing'
  metadata: {
    courseName: string
    courseDescription: string
    courseObjective: string
    targetAudience: string
    courseDifficulty: string
    language: string
    courseType: string
  }
  settings: {
    moduleCount: number
    detailLevel: 'short' | 'standard' | 'detailed'
    tone: string
    writingFocus: string
    includeScenarios: boolean
    includeBadGood: boolean
    includeTakeaways: boolean
    includeMistakes: boolean
  }
  modules: Module[]
}
export type Draft = {
  id: string
  revision: number
  content: Content
  approvedOutline: string | null
  createdAt: string
  updatedAt: string
}
export type DraftSummary = {
  draft_id: string
  revision: number
  title: string
  module_count: number
  updated_at: string
  entry_mode?: string | null
  /** Uploaded document an imported draft came from; such drafts open in Blueprint. */
  source_document_id?: string | null
}
export type Change = {
  moduleId: string
  blockId: string
  originalText: string
  replacementText: string
}
export type Operation = {
  id: string
  status: string
  error?: string
  request: { task: string; sourceImport?: { referenceOnly?: boolean } }
  result?: {
    blocks?: { type: string; text: string }[]
    modules?: { title: string; objective: string; sections: string[] }[]
    changes?: Change[]
    originalText?: string
    replacementText?: string
    summary?: string
    answer?: string
    insufficientEvidence?: boolean
    sourceReferences?: SourceReference[]
  }
}
export type SourceReference = { sourceId: string; spanId: string }
export type DraftSource = {
  id: string
  documentId?: string
  name?: string
  issues: string[]
  acknowledged: boolean
  spans: { id: string; text: string; location: string }[]
}
export type DraftRevision = { revision: number; reason: string; created_at: string }
export const id = () =>
  Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
    byte.toString(16).padStart(2, '0'),
  ).join('')
export const paragraph = (text = ''): TextBlock => ({
  id: id(),
  type: 'paragraph',
  text,
  marks: [],
  level: 2,
  sourceReferences: [],
})
export const newModule = (): Module => ({
  id: id(),
  title: 'New module',
  objective: '',
  included: true,
  sections: [],
  blocks: [paragraph()],
  sourceReferences: [],
  status: 'empty',
})
export const initialContent = (entryMode: Content['entryMode']): Content => ({
  schemaVersion: 1,
  entryMode,
  metadata: {
    courseName: '',
    courseDescription: '',
    courseObjective: '',
    targetAudience: '',
    courseDifficulty: 'Beginner',
    language: 'English',
    courseType: 'Training guide',
  },
  settings: {
    moduleCount: 4,
    detailLevel: 'standard',
    tone: 'Clear and professional',
    writingFocus: 'balanced',
    includeScenarios: true,
    includeBadGood: true,
    includeTakeaways: true,
    includeMistakes: true,
  },
  modules: entryMode === 'blank' ? [newModule()] : [],
})
export const draftApi = <T>(path = '', options: RequestOptions = {}) =>
  apiRequest(`/api/document-builder/drafts${path}`, options) as Promise<T>
export const postDraft = <T>(path: string, json: unknown, signal?: AbortSignal) =>
  draftApi<T>(path, { json, signal })
/** Python's fingerprint hashes JSON strings (UTF-8), not the raw selection bytes. */
export async function selectionTarget(
  moduleId: string,
  blockId: string,
  text: string,
  start: number,
  end: number,
) {
  const selected = text.slice(start, end)
  return {
    moduleId,
    blockId,
    start: Array.from(text.slice(0, start)).length,
    end: Array.from(text.slice(0, end)).length,
    textHash: sha256Text(JSON.stringify(selected)),
  }
}
