import { useEffect, useState } from 'react'
import { apiUrl, authHeaders, errorMessage } from '@lms/shared/api/client'
import { useFiles, useUpload } from './useFiles'
import { UploadCard } from './UploadCard'
import {
  draftApi,
  type Draft,
  type DraftSource,
  type DraftRevision,
  type Operation,
} from './workflow'

const button =
  'rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-primary-blue disabled:opacity-40'
export function WorkflowTools({
  draft,
  sources,
  disabled,
  onAttach,
  onRestore,
}: {
  draft: Draft | null
  sources: DraftSource[]
  disabled: boolean
  onAttach: (source: { documentId?: string; text?: string }) => void
  onRestore: (revision: number) => void
}) {
  const files = useFiles()
  const upload = useUpload()
  const [history, setHistory] = useState<DraftRevision[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [documentId, setDocumentId] = useState('')
  const [text, setText] = useState('')
  const [original, setOriginal] = useState<{ url: string; name: string } | null>(null)
  const [opening, setOpening] = useState(false)
  useEffect(
    () => () => {
      if (original) URL.revokeObjectURL(original.url)
    },
    [original],
  )
  const openOriginal = async (source: DraftSource) => {
    if (!draft) return
    setOpening(true)
    setError('')
    try {
      const response = await fetch(
        apiUrl(`/api/document-builder/drafts/${draft.id}/sources/${source.id}/original`),
        { headers: authHeaders(), credentials: 'same-origin' },
      )
      if (!response.ok)
        throw new Error('Cannot open this source. Your document and sources are unchanged.')
      setOriginal({
        url: URL.createObjectURL(await response.blob()),
        name: source.name || 'Original source',
      })
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setOpening(false)
    }
  }
  const showHistory = async () => {
    if (!draft) return
    setLoading(true)
    setError('')
    try {
      setHistory(await draftApi<DraftRevision[]>(`/${draft.id}/revisions`))
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }
  return (
    <section className="mb-5 space-y-3" aria-label="Sources and history">
      <details className="rounded-xl border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer font-semibold">
          Reference sources ({sources.length})
        </summary>
        <p className="my-3 text-sm text-slate-500">
          Attach a document or notes to ground AI generation and source questions. This keeps your
          existing training content.
        </p>
        <fieldset disabled={disabled} className="space-y-3">
          <details>
            <summary className="cursor-pointer text-sm text-primary-blue">
              Upload a new reference document
            </summary>
            <div className="mt-3">
              <UploadCard upload={upload} />
            </div>
          </details>
          <label className="block text-sm">
            Uploaded reference document
            <select
              aria-label="Reference document"
              className="mt-2 block w-full min-w-0 max-w-full rounded border p-2"
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
            >
              <option value="">Choose a document</option>
              {files.data?.map((file) => (
                <option key={file.documentId} value={file.documentId}>
                  {file.displayName}
                </option>
              ))}
            </select>
          </label>
          {files.isError && (
            <p role="alert">
              Could not load reference documents.{' '}
              <button onClick={() => void files.refetch()}>Retry</button>
            </p>
          )}
          <button
            className={button}
            disabled={!documentId}
            onClick={() => onAttach({ documentId })}
          >
            Attach reference document
          </button>
          <label className="block text-sm">
            Reference notes
            <textarea
              aria-label="Reference notes"
              className="mt-2 block w-full rounded border p-3"
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={100000}
            />
          </label>
          <button className={button} disabled={!text.trim()} onClick={() => onAttach({ text })}>
            Attach reference notes
          </button>
        </fieldset>
        {sources.map((source) => (
          <details className="mt-3 rounded border p-3" key={source.id}>
            <summary>
              {source.name || 'Reference source'} · {source.spans.length} excerpts
            </summary>
            {source.documentId && (
              <button
                className={`${button} mt-3`}
                disabled={opening}
                onClick={() => void openOriginal(source)}
              >
                Prepare original source
              </button>
            )}
            {source.spans.map((span) => (
              <div className="mt-3" key={span.id}>
                <p className="text-xs font-semibold">{span.location}</p>
                <blockquote className="whitespace-pre-wrap border-l-2 pl-3 text-sm">
                  {span.text}
                </blockquote>
              </div>
            ))}
          </details>
        ))}
      </details>
      {original && (
        <p className="rounded border bg-white p-3">
          <a href={original.url} target="_blank" rel="noopener noreferrer" download={original.name}>
            Open or download {original.name}
          </a>
          <button className="ml-3" onClick={() => setOriginal(null)}>
            Close source preview
          </button>
        </p>
      )}
      {draft && (
        <button
          className={button}
          disabled={disabled || loading}
          onClick={() => void showHistory()}
        >
          {loading ? 'Loading history…' : 'Version history'}
        </button>
      )}
      {error && <p role="alert">{error}</p>}
      {history && (
        <section className="rounded-xl border bg-white p-4" aria-label="Version history">
          <header className="mb-3 flex justify-between">
            <h2 className="font-semibold">Saved versions</h2>
            <button onClick={() => setHistory(null)}>Close history</button>
          </header>
          <p className="mb-3 text-sm">
            Restoring creates a new revision. Your current edits are saved first; outline approval
            must be reviewed again.
          </p>
          {history.map((item) => (
            <div key={item.revision} className="flex flex-wrap justify-between gap-3 border-t py-3">
              <p>
                Revision {item.revision} · {item.reason} · {item.created_at}
              </p>
              <button
                className={button}
                disabled={disabled || item.revision === draft?.revision}
                onClick={() => {
                  if (
                    window.confirm(
                      `Restore revision ${item.revision}? Current edits will be saved first.`,
                    )
                  )
                    onRestore(item.revision)
                }}
              >
                Restore revision {item.revision}
              </button>
            </div>
          ))}
        </section>
      )}
    </section>
  )
}

export function SourceAnswer({
  operation,
  sources,
}: {
  operation: Operation
  sources: DraftSource[]
}) {
  const result = operation.result
  if (operation.request.task !== 'answer' || operation.status !== 'completed') return null
  return (
    <section
      className="mb-5 rounded-xl border border-blue-200 bg-white p-5"
      aria-label="Source answer"
    >
      <h2 className="font-semibold">Answer from your sources</h2>
      {result?.insufficientEvidence && (
        <p className="mt-3 rounded bg-amber-50 p-3">
          The attached sources do not provide enough evidence for a reliable answer.
        </p>
      )}
      <p className="my-3 whitespace-pre-wrap">{result?.answer}</p>
      <h3 className="text-sm font-semibold">Cited source excerpts</h3>
      {result?.sourceReferences?.map((ref, index) => {
        const source = sources.find((item) => item.id === ref.sourceId)
        const span = source?.spans.find((item) => item.id === ref.spanId)
        return (
          <div className="mt-3 rounded border p-3" key={`${ref.sourceId}:${ref.spanId}:${index}`}>
            <p className="text-xs font-semibold">
              {span?.location || 'Source excerpt unavailable'}
            </p>
            {span && (
              <blockquote className="mt-2 whitespace-pre-wrap text-sm">{span.text}</blockquote>
            )}
          </div>
        )
      })}
      <p className="mt-4 border-t pt-3 text-xs text-slate-500">
        This is a source answer. Your document has not been changed.
      </p>
    </section>
  )
}
