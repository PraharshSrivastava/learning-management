import { errorMessage } from '@lms/shared/api/client'
import type { PdfFile } from '@lms/shared/models'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTrainerSearch, useUpdateTrainerSearch } from '../../shell/search'
import { FocusedWorkspace } from './FocusedWorkspace'
import { PdfViewerCard } from './PdfViewerCard'
import { UploadCard } from './UploadCard'
import { useFiles, useUpload } from './useFiles'
import { useGenerateCourse } from './useGenerateCourse'
import { draftApi, postDraft, type DraftSummary } from './workflow'

const button =
  'rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-primary-blue disabled:opacity-40'
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
  const [importFile, setImportFile] = useState<PdfFile | null>(null)
  const [existing, setExisting] = useState(false)
  const [all, setAll] = useState(false)
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
    setImportFile(null)
    update({ builder: undefined, draft: undefined })
    void drafts.refetch()
  }
  if (mode || search.builder || search.draft)
    return (
      <FocusedWorkspace
        key={mode || search.draft || 'new'}
        mode={mode || 'ai'}
        draftId={search.draft}
        documentId={importFile?.documentId}
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
  const list = (files.data || []).filter((file) =>
    file.displayName.toLowerCase().includes(filter.toLowerCase()),
  )
  return (
    <div className="mx-auto max-w-[1280px] space-y-6 p-5 md:p-8">
      <header>
        <h1 className="text-3xl font-bold text-slate-900">Documents</h1>
        <p className="mt-2 text-sm text-slate-500">
          Create training content and manage your documents.
        </p>
      </header>
      <section>
        <h2 className="mb-4 text-lg font-semibold">Create a training document</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            {
              label: 'Use existing content',
              description: 'Upload a ready document and open Blueprint.',
              icon: '↥',
              action: () => setExisting(true),
            },
            {
              label: 'Generate with AI',
              description: 'Describe your topic. Review an AI draft.',
              icon: '✧',
              action: () => setMode('ai'),
            },
            {
              label: 'Start blank',
              description: 'Write your own training document.',
              icon: '＋',
              action: () => setMode('blank'),
            },
          ].map((item, index) => (
            <button
              key={item.label}
              disabled={upload.state.status === 'uploading'}
              className={`flex items-center gap-4 rounded-xl border border-slate-200 p-5 text-left transition hover:border-blue-400 hover:shadow-sm ${index === 0 ? 'bg-blue-50' : 'bg-white'}`}
              onClick={item.action}
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-blue-50 text-2xl text-primary-blue">
                {item.icon}
              </span>
              <span className="flex-1">
                <strong className="block text-sm">{item.label}</strong>
                <span className="mt-2 block text-xs text-slate-500">{item.description}</span>
              </span>
              <span className="text-primary-blue">→</span>
            </button>
          ))}
        </div>
      </section>
      {error && (
        <div role="alert" className="rounded-lg bg-red-50 p-4">
          {error}
        </div>
      )}
      <section className="card p-5">
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
          (drafts.data || []).slice(0, all ? 100 : 3).map((value) => (
            <div
              key={value.draft_id}
              className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 py-4"
            >
              <div className="min-w-0 flex-1">
                <h3 className="truncate text-sm font-semibold">
                  {value.title || 'Untitled document'}
                </h3>
                <p className="mt-1 text-xs text-slate-500">
                  {value.module_count ? `${value.module_count} modules` : 'Empty draft'} · Edited{' '}
                  {new Date(value.updated_at).toLocaleString()}
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
                className="text-sm text-slate-500"
                disabled={removing}
                onClick={() => void remove(value)}
              >
                Remove
              </button>
            </div>
          ))
        )}
      </section>
      {existing && (
        <section className="card space-y-4 p-5">
          <header className="flex justify-between">
            <h2 className="font-semibold">Use existing content</h2>
            <button
              onClick={() => {
                upload.cancel()
                setExisting(false)
              }}
              aria-label="Close upload"
            >
              ×
            </button>
          </header>
          <UploadCard
            upload={{
              ...upload,
              upload: async (file) => {
                const fileName = await upload.upload(file)
                if (fileName) await generate(fileName)
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
      <section className="card p-5">
        <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">Your documents</h2>
          <input
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            aria-label="Search documents"
            placeholder="Search documents…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </header>
        {files.isLoading ? (
          <p role="status">Loading documents…</p>
        ) : files.isError ? (
          <p role="alert">
            Unable to load documents.{' '}
            <button className={button} onClick={() => void files.refetch()}>
              Retry
            </button>
          </p>
        ) : list.length === 0 ? (
          <p className="text-sm text-slate-500">
            No documents found. Upload an existing document or create one above.
          </p>
        ) : (
          list.map((file) => (
            <div
              key={file.documentId}
              className="flex flex-wrap items-center gap-3 border-t border-slate-100 py-4"
            >
              <p className="min-w-40 flex-1 truncate text-sm" title={file.displayName}>
                {file.displayName}
              </p>
              <button className={button} onClick={() => update({ file: file.fileName })}>
                Preview
              </button>
              <button
                className={`${button} bg-blue-50`}
                onClick={() => void generate(file.fileName)}
              >
                Create course
              </button>
              <button
                className="text-sm text-slate-500"
                onClick={() => {
                  setImportFile(file)
                  setMode('existing')
                }}
              >
                Edit first
              </button>
            </div>
          ))
        )}
      </section>
      {selected && (
        <section className="card p-4">
          <button className={`${button} mb-3`} onClick={() => update({ file: undefined })}>
            Close preview
          </button>
          <PdfViewerCard file={selected} className="h-[650px]" />
        </section>
      )}
      {removed && (
        <div
          role="status"
          className="fixed right-5 bottom-5 left-5 z-50 mx-auto flex max-w-xl items-center justify-between gap-4 rounded-xl bg-slate-900 p-4 text-white shadow-lg"
        >
          <span>Draft removed</span>
          <button disabled={removing} onClick={() => void undo()}>
            Undo
          </button>
          <button aria-label="Dismiss notification" onClick={() => setRemoved(null)}>
            ×
          </button>
        </div>
      )}
    </div>
  )
}
