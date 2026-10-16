// Document builder endpoints (document_builder_provider.dart).
import { ApiError, apiRequest, apiUrl, authHeaders, errorDetail } from '@lms/shared/api/client'
import { parsePdfFile, type PdfFile } from '@lms/shared/models'
import {
  metadataJson,
  type BuilderBlock,
  type BuilderMetadata,
  type BuilderSettings,
} from './models'

export interface BuildResult {
  document: string
  reply: string | null
  model: string | null
}

const optionalText = (value: unknown): string | null => (value == null ? null : String(value))

export async function buildDocument(
  body: {
    message: string
    instructions: string[]
    currentDraft: string
    builderSettings: BuilderSettings
  },
  signal?: AbortSignal,
): Promise<BuildResult> {
  let data: unknown
  try {
    data = await apiRequest('/api/document-builder/build-document', { json: body, signal })
  } catch (error) {
    // Dart: detail ?? error ?? 'LLM request failed'.
    if (error instanceof ApiError && error.status > 0) {
      const raw = error.body as { error?: unknown } | null
      const fallback =
        raw && typeof raw === 'object' && raw.error != null ? String(raw.error) : null
      throw new Error(errorDetail(error.body) ?? fallback ?? 'LLM request failed', {
        cause: error,
      })
    }
    throw error
  }
  const json = (data ?? {}) as Record<string, unknown>
  return {
    document: optionalText(json.document) ?? '',
    reply: optionalText(json.reply),
    model: optionalText(json.model),
  }
}

const pdfPayload = (metadata: BuilderMetadata, document: string, blocks: BuilderBlock[]) => ({
  metadata: metadataJson(metadata),
  document,
  documentBlocks: blocks,
})

/** Renders the draft to PDF bytes. */
export async function renderPdf(
  metadata: BuilderMetadata,
  document: string,
  blocks: BuilderBlock[],
): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(apiUrl('/api/document-builder/render-pdf'), {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(pdfPayload(metadata, document, blocks)),
      credentials: 'same-origin',
    })
  } catch {
    throw new Error('Unable to reach the server. Check your connection and try again.')
  }
  if (!response.ok) {
    const text = await response.text()
    let body: unknown = null
    try {
      body = JSON.parse(text)
    } catch {
      // A 500 from FastAPI can be plain text.
    }
    throw new Error(errorDetail(body) ?? 'PDF render failed')
  }
  const bytes = await response.arrayBuffer()
  return new Blob([bytes], { type: 'application/pdf' })
}

/** Saves the draft as a PDF in the trainer's document library. */
export async function savePdf(
  metadata: BuilderMetadata,
  document: string,
  blocks: BuilderBlock[],
): Promise<PdfFile> {
  let data: unknown
  try {
    data = await apiRequest('/api/document-builder/save-pdf', {
      json: pdfPayload(metadata, document, blocks),
    })
  } catch (error) {
    if (error instanceof ApiError && error.status > 0) {
      throw new Error(errorDetail(error.body) ?? 'PDF save failed', { cause: error })
    }
    throw error
  }
  return parsePdfFile((data as { file?: unknown } | null)?.file)
}
