import { errorMessage } from '@lms/shared/api/client'
import { formattedSize, type PdfFile } from '@lms/shared/models'
import { useQuery } from '@tanstack/react-query'
import { Fragment, useEffect, useRef, useState } from 'react'
import { useTrainerSearch, useUpdateTrainerSearch } from '../../shell/search'
import { FocusedWorkspace } from './FocusedWorkspace'
import { DocumentPreview } from './DocumentPreview'
import { DocumentsIcon } from './DocumentsIcon'
import './DocumentsStyles.css'
import { UploadCard } from './UploadCard'
import { useFiles, useUpload } from './useFiles'
import { useGenerateCourse } from './useGenerateCourse'
import { draftApi, postDraft, type DraftSummary } from './workflow'

const button = 'docs-button'

function readableDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Date unavailable'
    : date.toLocaleString(undefined, {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
}

/** Strip only known machine-generated storage prefixes; keep meaningful titles intact. */
export function documentTitle(file: PdfFile) {
  return file.displayName.replace(/^\d{13,}-/, '').replace(/^builder-[a-f\d]{32}-/i, '')
}
export function DocumentsWorkspace() {
  const search = useTrainerSearch()
  const update = useUpdateTrainerSearch()
  const files = useFiles()
  const upload = useUpload()
  const generate = useGenerateCourse()
  const drafts = useQuery({
    queryKey: ['document-workflow-drafts'],
    queryFn: () => draftApi<DraftSummary[]>(),
    retry: false,
  })
  const [mode, setMode] = useState<'ai' | 'blank' | 'existing' | null>(null)
  const [existing, setExisting] = useState(false)
  const [all, setAll] = useState(false)
  const [allFiles, setAllFiles] = useState(Boolean(search.file))
  const previewButtons = useRef(new Map<string, HTMLButtonElement>())
  const generating = useRef(false)
  const [busy, setBusy] = useState(false)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')
  const [removing, setRemoving] = useState(false)
  const [removed, setRemoved] = useState<DraftSummary | null>(null)
  useEffect(() => {
    if (!removed) return
    const timeout = setTimeout(() => setRemoved(null), 10000)
    return () => clearTimeout(timeout)
  }, [removed])
  const close = () => {
    setMode(null)
    update({ builder: undefined, draft: undefined })
    void drafts.refetch()
  }
  if (mode || search.builder || search.draft)
    return (
      <FocusedWorkspace
        key={mode || search.draft || 'new'}
        mode={mode || 'ai'}
        draftId={search.draft}
        onClose={close}
        onCreated={(draft) => update({ builder: true, draft }, { replace: true })}
      />
    )
  const remove = async (value: DraftSummary) => {
    if (removing) return
    setRemoving(true)
    setError('')
    try {
      await postDraft(`/${value.draft_id}/remove`, { expectedRevision: value.revision })
      setRemoved(value)
      await drafts.refetch()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setRemoving(false)
    }
  }
  const undo = async () => {
    if (!removed || removing) return
    setRemoving(true)
    try {
      await postDraft(`/${removed.draft_id}/undo-remove`, { expectedRevision: removed.revision })
      setRemoved(null)
      await drafts.refetch()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setRemoving(false)
    }
  }
  const selected = files.data?.find((file) => file.fileName === search.file) || null
  const list = (files.data || [])
    .filter((file) => documentTitle(file).toLowerCase().includes(filter.trim().toLowerCase()))
    .toSorted(
      (a, b) =>
        (Date.parse(b.createdAt) || 0) - (Date.parse(a.createdAt) || 0) ||
        a.documentId.localeCompare(b.documentId),
    )
  const createCourse = async (fileName: string) => {
    if (generating.current) return
    generating.current = true
    setBusy(true)
    try {
      await generate(fileName)
    } finally {
      generating.current = false
      setBusy(false)
    }
  }
  const closePreview = () => {
    update({ file: undefined })
    if (selected) previewButtons.current.get(selected.documentId)?.focus()
  }
  return (
    <div className="documents-desk docs-landing">
      <header>
        <h1 className="text-3xl font-bold text-slate-900">Documents</h1>
        <p className="mt-2 text-sm text-slate-500">
          Create training content and manage your documents.
        </p>
      </header>
      <section>
        <h2 className="mb-4 text-lg font-semibold">Create a training document</h2>
        <div className="docs-create-grid">
          {[
            {
              label: 'Use existing content',
              description: 'Upload a ready document and open Blueprint.',
              icon: 'upload' as const,
              action: () => setExisting(true),
            },
            {
              label: 'Generate with AI',
              description: 'Describe your topic. Review an AI draft.',
              icon: 'ai' as const,
              action: () => setMode('ai'),
            },
          ].map((item, index) => (
            <button
              key={item.label}
              disabled={upload.state.status === 'uploading'}
              className={`docs-create ${index === 0 ? 'docs-create-upload' : 'docs-create-ai'}`}
              onClick={item.action}
            >
              <span className="docs-emblem">
                <DocumentsIcon name={item.icon} size={24} />
              </span>
              <span className="flex-1">
                <strong className="block text-sm">{item.label}</strong>
                <span className="mt-2 block text-xs text-slate-500">{item.description}</span>
              </span>
              <DocumentsIcon name="arrow" className="shrink-0" />
            </button>
          ))}
        </div>
      </section>
      {error && (
        <div role="alert" className="docs-notice docs-notice-error">
          <DocumentsIcon name="error" />
          {error}
        </div>
      )}
      <section className="docs-panel" aria-label="Drafts">
        <header className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold">{all ? 'All drafts' : 'Recent drafts'}</h2>
          {(drafts.data?.length || 0) > 3 && (
            <button className="text-sm text-primary-blue" onClick={() => setAll(!all)}>
              {all ? 'Show recent' : `View all drafts (${drafts.data?.length})`}
            </button>
          )}
        </header>
        {drafts.isLoading ? (
          <p role="status">Loading drafts…</p>
        ) : drafts.isError ? (
          <p role="alert">
            Could not load drafts.{' '}
            <button className={button} onClick={() => void drafts.refetch()}>
              Retry
            </button>
          </p>
        ) : !drafts.data?.length ? (
          <p className="text-sm text-slate-500">
            Your drafts will appear here as you create training content.
          </p>
        ) : (
          [...(drafts.data || [])]
            .sort(
              (a, b) =>
                (Date.parse(b.updated_at) || 0) - (Date.parse(a.updated_at) || 0) ||
                a.draft_id.localeCompare(b.draft_id),
            )
            .slice(0, all ? undefined : 3)
            .map((value) => (
              <div key={value.draft_id} className="docs-draft-row">
                <span className="docs-file-icon">
                  <DocumentsIcon name="draft" />
                </span>
                <div className="min-w-0 flex-1">
                  <h3 className="truncate text-sm font-semibold">
                    {value.title || 'Untitled document'}
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">
                    {value.module_count ? `${value.module_count} modules` : 'Empty draft'} · Edited{' '}
                    {readableDate(value.updated_at)}
                  </p>
                </div>
                <button
                  className={button}
                  onClick={() => {
                    setMode(null)
                    update({ builder: true, draft: value.draft_id })
                  }}
                >
                  Open
                </button>
                <button
                  className="docs-button docs-button-quiet"
                  disabled={removing}
                  onClick={() => void remove(value)}
                >
                  <DocumentsIcon name="trash" size={15} />
                  Remove
                </button>
              </div>
            ))
        )}
      </section>
      {existing && (
        <section className="docs-panel space-y-4" aria-label="Upload ready document">
          <header className="flex justify-between">
            <h2 className="font-semibold">Use existing content</h2>
            <button
              onClick={() => {
                upload.cancel()
                setExisting(false)
              }}
              aria-label="Close upload"
            >
              <DocumentsIcon name="close" />
            </button>
          </header>
          <UploadCard
            upload={{
              ...upload,
              upload: async (file) => {
                const fileName = await upload.upload(file)
                if (fileName) await createCourse(fileName)
                return fileName
              },
            }}
          />
          <p className="text-sm text-slate-500">
            Upload your ready PDF, DOCX or PPTX to open Blueprint automatically. You can review the
            course outline there before generating videos and quizzes.
          </p>
          <details>
            <summary className="cursor-pointer text-sm text-primary-blue">
              Or paste notes for editing
            </summary>
            <button
              disabled={upload.state.status === 'uploading'}
              className={`${button} mt-3`}
              onClick={() => setMode('existing')}
            >
              Paste notes
            </button>
          </details>
        </section>
      )}
      <section className="docs-panel docs-library" aria-label="Your uploaded documents">
        <header className="docs-library-header">
          <h2>
            Your uploaded documents <small>({list.length})</small>
          </h2>
          <label className="docs-search">
            <DocumentsIcon name="search" size={17} />
            <input
              aria-label="Search documents"
              placeholder="Search documents…"
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value)
                setAllFiles(false)
              }}
            />
          </label>
        </header>
        {files.isLoading ? (
          <p role="status" className="docs-notice docs-notice-info">
            <DocumentsIcon name="loader" />
            Loading documents…
          </p>
        ) : files.isError ? (
          <p role="alert" className="docs-notice docs-notice-error">
            <DocumentsIcon name="error" />
            Unable to load documents.{' '}
            <button className={button} onClick={() => void files.refetch()}>
              Retry
            </button>
          </p>
        ) : list.length === 0 ? (
          <p className="docs-empty">
            {filter.trim()
              ? 'No matching documents. Try a different search.'
              : 'No uploaded documents yet. Use existing content to upload a ready document.'}
          </p>
        ) : (
          list.slice(0, allFiles ? undefined : 5).map((file) => (
            <Fragment key={file.documentId}>
              <div
                className={`docs-document-row ${selected?.documentId === file.documentId ? 'docs-document-selected' : ''}`}
              >
                <span className="docs-file-icon">
                  <DocumentsIcon
                    name={
                      file.fileType.toLowerCase() === 'pdf'
                        ? 'pdf'
                        : file.fileType.toLowerCase() === 'pptx'
                          ? 'presentation'
                          : 'file'
                    }
                  />
                </span>
                <div className="docs-document-name">
                  <h3 title={file.displayName}>{documentTitle(file)}</h3>
                  <p>
                    {file.fileType.toUpperCase()} · {formattedSize(file)} ·{' '}
                    {readableDate(file.createdAt)}
                  </p>
                </div>
                <div className="docs-row-actions">
                  <button
                    className={button}
                    ref={(node) => {
                      if (node) previewButtons.current.set(file.documentId, node)
                      else previewButtons.current.delete(file.documentId)
                    }}
                    aria-expanded={selected?.documentId === file.documentId}
                    aria-controls={
                      selected?.documentId === file.documentId
                        ? 'uploaded-document-preview'
                        : undefined
                    }
                    onClick={() =>
                      selected?.documentId === file.documentId
                        ? closePreview()
                        : update({ file: file.fileName })
                    }
                  >
                    <DocumentsIcon name="eye" size={16} />
                    Preview
                  </button>
                  <button
                    className={`${button} docs-button-soft`}
                    disabled={busy}
                    onClick={() => void createCourse(file.fileName)}
                  >
                    <DocumentsIcon name="book" size={16} />
                    Create course
                  </button>
                </div>
              </div>
              {selected?.documentId === file.documentId && (
                <div id="uploaded-document-preview" className="docs-inline-preview">
                  <DocumentPreview
                    file={file}
                    onClose={closePreview}
                    onCreateCourse={() => void createCourse(file.fileName)}
                    busy={busy}
                  />
                </div>
              )}
            </Fragment>
          ))
        )}
        {list.length > 5 && (
          <footer className="docs-library-footer">
            <button
              className="docs-button docs-button-quiet"
              onClick={() => {
                setAllFiles(!allFiles)
                if (allFiles) update({ file: undefined })
              }}
            >
              {allFiles ? 'Show recent documents' : `View all documents (${list.length})`}
            </button>
          </footer>
        )}
      </section>
      {removed && (
        <div
          role="status"
          className="fixed right-5 bottom-5 left-5 z-50 mx-auto flex max-w-xl items-center justify-between gap-4 rounded-xl bg-slate-900 p-4 text-white shadow-lg"
        >
          <span className="flex items-center gap-2">
            <DocumentsIcon name="check" />
            Draft removed
          </span>
          <button disabled={removing} onClick={() => void undo()}>
            Undo
          </button>
          <button aria-label="Dismiss notification" onClick={() => setRemoved(null)}>
            <DocumentsIcon name="close" />
          </button>
        </div>
      )}
    </div>
  )
}
