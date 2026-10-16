import { apiUrl, authHeaders, errorMessage } from '@lms/shared/api/client'
import { parseCourse } from '@lms/shared/models'
import { useBlocker } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'
import { useStoreCourse } from '../courses/courseQueries'
import { useUpdateTrainerSearch } from '../../shell/search'
import {
  draftApi,
  postDraft,
  id,
  initialContent,
  newModule,
  paragraph,
  selectionTarget,
  type Block,
  type Content,
  type Draft,
  type Operation,
} from './workflow'

const input = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900'
const button =
  'rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-primary-blue disabled:opacity-40'
const primary = `${button} !bg-primary-blue !text-white`
type Props = {
  draftId?: string
  mode: 'ai' | 'blank' | 'existing'
  documentId?: string
  onClose: () => void
  onCreated: (id: string) => void
}

export function FocusedWorkspace({ draftId, mode, documentId, onClose, onCreated }: Props) {
  const [draft, setDraft] = useState<Draft | null>(null)
  const [content, setContent] = useState<Content>(() => initialContent(mode))
  const [stage, setStage] = useState<'setup' | 'outline' | 'editor'>(draftId ? 'editor' : 'setup')
  const [moduleIndex, setModuleIndex] = useState(0)
  const [busy, setBusy] = useState(Boolean(draftId))
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')
  const [operation, setOperation] = useState<Operation | null>(null)
  const [instruction, setInstruction] = useState('')
  const [scope, setScope] = useState<'selected' | 'module' | 'document'>('module')
  const [selection, setSelection] = useState<{
    blockId: string
    start: number
    end: number
    text: string
  } | null>(null)
  const [pasted, setPasted] = useState('')
  const [sources, setSources] = useState<{ id: string; issues: string[]; acknowledged: boolean }[]>(
    [],
  )
  const controller = useRef<AbortController | null>(null)
  const allowConfirmedLeave = useRef(false)
  useBlocker({
    shouldBlockFn: () =>
      dirty && !allowConfirmedLeave.current && !window.confirm('Leave with unsaved changes?'),
    enableBeforeUnload: false,
  })
  const store = useStoreCourse()
  const navigate = useUpdateTrainerSearch()
  const module = content.modules[moduleIndex]
  const load = (value: Draft) => {
    setDraft(value)
    setContent(value.content)
    setDirty(false)
    setSelection(null)
  }
  useEffect(() => {
    const abort = new AbortController()
    controller.current = abort
    if (draftId) {
      draftApi<Draft>(`/${draftId}`, { signal: abort.signal })
        .then((value) => {
          load(value)
          setStage(value.content.modules.length ? 'editor' : 'setup')
        })
        .catch((e) => {
          if (!abort.signal.aborted) setError(errorMessage(e))
        })
        .finally(() => {
          if (!abort.signal.aborted) setBusy(false)
        })
      draftApi<Operation[]>(`/${draftId}/operations`, { signal: abort.signal })
        .then((values) => {
          const pending = values.find((v) =>
            ['queued', 'running', 'proposed', 'failed'].includes(v.status),
          )
          if (pending) setOperation(pending)
        })
        .catch(() => {})
    }
    return () => {
      abort.abort()
    }
  }, [draftId])
  useEffect(() => {
    if (!draft || !operation || !['queued', 'running'].includes(operation.status)) return
    const abort = new AbortController()
    const poll = async () => {
      try {
        const next = await draftApi<Operation>(`/${draft.id}/operations/${operation.id}`, {
          signal: abort.signal,
        })
        if (abort.signal.aborted) return
        if (next.status === 'completed') {
          load(await draftApi<Draft>(`/${draft.id}`, { signal: abort.signal }))
          setStage('editor')
        }
        setOperation(next)
      } catch (e) {
        if (!abort.signal.aborted)
          setError(`Cannot check generation: ${errorMessage(e)}. Reopen this draft to reconnect.`)
      }
    }
    const timer = setTimeout(poll, 500)
    return () => {
      clearTimeout(timer)
      abort.abort()
    }
  }, [draft, operation])
  useEffect(() => {
    if (!draft) return
    const abort = new AbortController()
    draftApi<typeof sources>(`/${draft.id}/sources`, { signal: abort.signal })
      .then(setSources)
      .catch(() => {})
    return () => abort.abort()
  }, [draft])
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty) {
        event.preventDefault()
        event.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  const working = busy || (!!operation && ['queued', 'running'].includes(operation.status))
  useEffect(() => {
    if (draft && !draftId && !working && !dirty) onCreated(draft.id)
  }, [draft, draftId, working, dirty, onCreated])
  const mutate = (value: Content) => {
    setContent(value)
    setDirty(true)
    setSelection(null)
  }
  const changeBlock = (blockId: string, next: Block) =>
    mutate({
      ...content,
      modules: content.modules.map((m, i) =>
        i === moduleIndex
          ? { ...m, status: 'ready', blocks: m.blocks.map((b) => (b.id === blockId ? next : b)) }
          : m,
      ),
    })
  const run = async (action: () => Promise<void>) => {
    if (working) return
    setBusy(true)
    setError('')
    try {
      await action()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }
  const save = async () => {
    const savedContent = {
      ...content,
      metadata: {
        ...content.metadata,
        courseDescription:
          content.metadata.courseDescription.trim() || content.metadata.courseObjective.trim(),
      },
    }
    const value = draft
      ? await draftApi<Draft>(`/${draft.id}`, {
          method: 'PATCH',
          json: { expectedRevision: draft.revision, content: savedContent },
          signal: controller.current?.signal,
        })
      : await postDraft<Draft>('', savedContent, controller.current?.signal)
    load(value)
    return value
  }
  const start = async (task: string, extra: Record<string, unknown> = {}) => {
    const value = await save()
    setOperation(
      await postDraft<Operation>(
        `/${value.id}/operations`,
        { expectedRevision: value.revision, task, key: id(), ...extra },
        controller.current?.signal,
      ),
    )
  }
  const accept = () =>
    run(async () => {
      if (!draft || !operation) return
      const next = await postDraft<Draft>(`/${draft.id}/proposals/${operation.id}/accept`, {
        expectedRevision: draft.revision,
      })
      load(next)
      setStage(operation.request.task === 'outline' ? 'outline' : 'editor')
      setOperation(null)
    })
  const dismiss = () =>
    run(async () => {
      if (!draft || !operation) return
      await postDraft(`/${draft.id}/proposals/${operation.id}/reject`, {})
      setOperation(null)
    })
  const approve = async () => {
    const value = await save()
    const next = await postDraft<Draft>(`/${value.id}/approve-outline`, {
      expectedRevision: value.revision,
    })
    load(next)
    return next
  }
  const createCourse = () =>
    run(async () => {
      const value = await save()
      if (!value.approvedOutline)
        throw new Error('Review and approve the current outline before creating a course.')
      const course = parseCourse(
        await postDraft(`/${value.id}/create-course`, { expectedRevision: value.revision }),
      )
      store(course)
      navigate({ tab: 'blueprint', course: course.courseId, builder: undefined, draft: undefined })
    })
  const preview = () =>
    run(async () => {
      const value = await save()
      const response = await fetch(apiUrl(`/api/document-builder/drafts/${value.id}/render-pdf`), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ expectedRevision: value.revision }),
      })
      if (!response.ok) throw new Error('PDF preview failed. Check your document and try again.')
      const url = URL.createObjectURL(await response.blob())
      window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    })
  const ask = () =>
    run(async () => {
      let extra: Record<string, unknown> = { scope, moduleId: module?.id, instruction }
      if (scope === 'selected') {
        if (!module || !selection || selection.start === selection.end)
          throw new Error('Select text inside a paragraph first.')
        extra = {
          ...extra,
          target: await selectionTarget(
            module.id,
            selection.blockId,
            selection.text,
            selection.start,
            selection.end,
          ),
        }
      }
      await start(scope === 'selected' ? 'edit' : 'revise', extra)
    })
  const importText = () =>
    run(async () => {
      const value = await save()
      setOperation(
        await postDraft<Operation>(`/${value.id}/operations`, {
          expectedRevision: value.revision,
          task: 'import',
          key: id(),
          sourceImport: {
            expectedRevision: value.revision,
            ...(documentId ? { documentId } : { text: pasted }),
          },
        }),
      )
    })
  const addBlock = (block: Block) => {
    if (module)
      mutate({
        ...content,
        modules: content.modules.map((m, i) =>
          i === moduleIndex ? { ...m, blocks: [...m.blocks, block], status: 'ready' } : m,
        ),
      })
  }

  return (
    <section className="mx-auto max-w-[1440px] p-4 md:p-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <button
            className="text-sm text-primary-blue"
            onClick={() => {
              if (!dirty || window.confirm('Leave with unsaved changes?')) {
                allowConfirmedLeave.current = true
                onClose()
              }
            }}
          >
            ← Documents
          </button>
          <h1 className="mt-2 text-2xl font-bold">
            {draft
              ? content.metadata.courseName || 'Untitled document'
              : 'Create a training document'}
          </h1>
          <p className="text-sm text-slate-500">
            {busy
              ? 'Saving…'
              : dirty
                ? 'Unsaved changes'
                : draft
                  ? 'All changes saved'
                  : 'Choose your content and review before creating a course.'}
          </p>
        </div>
        {draft && (
          <div className="flex gap-2">
            <button
              className={button}
              disabled={working}
              onClick={() =>
                void run(async () => {
                  await save()
                })
              }
            >
              Save draft
            </button>
            <button className={button} disabled={working} onClick={preview}>
              Preview PDF
            </button>
            <button
              className={primary}
              disabled={
                working ||
                !draft?.approvedOutline ||
                !content.modules.some((m) => m.included) ||
                content.modules
                  .filter((m) => m.included)
                  .some(
                    (m) =>
                      !m.blocks.some(
                        (b) =>
                          ('text' in b && b.text.trim()) ||
                          (b.type === 'list' && b.items.some((v) => v.trim())) ||
                          (b.type === 'table' && b.rows.some((row) => row.some((v) => v.trim()))),
                      ),
                  )
              }
              onClick={createCourse}
            >
              Create course
            </button>
          </div>
        )}
      </header>
      {error && (
        <div role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4">
          {error}
          <p className="mt-1 text-sm">
            Your local edits are kept. If another session changed this draft, reopen it before
            trying again.
          </p>
        </div>
      )}
      {operation && ['queued', 'running'].includes(operation.status) && (
        <div role="status" className="mb-4 flex justify-between rounded-xl bg-blue-50 p-4">
          <span>AI is working. Completed content is saved on the server.</span>
          <button className={button} onClick={() => void run(async () => {})} hidden>
            Working
          </button>
          <button
            className={button}
            onClick={() => {
              if (draft)
                void postDraft<Operation>(`/${draft.id}/operations/${operation.id}/cancel`, {})
                  .then(setOperation)
                  .catch((e) => setError(errorMessage(e)))
            }}
          >
            Cancel generation
          </button>
        </div>
      )}
      {operation?.status === 'failed' && (
        <div role="alert" className="mb-4 rounded-lg bg-red-50 p-4">
          {operation.error || 'Generation failed. Your saved content is unchanged.'}
          <button className={`${button} ml-3`} onClick={() => setOperation(null)}>
            Dismiss
          </button>
        </div>
      )}
      {operation?.status === 'proposed' && (
        <Proposal
          operation={operation}
          disabled={working || dirty}
          accept={accept}
          dismiss={dismiss}
        />
      )}
      <fieldset disabled={working} className="min-w-0">
        {stage === 'setup' ? (
          <div className="card mx-auto max-w-3xl space-y-5 p-6 md:p-8">
            <h2 className="text-xl font-bold">
              {mode === 'existing' ? 'Use existing content' : 'What would you like to teach?'}
            </h2>
            <label className="block text-sm">
              Topic or title
              <input
                className={`${input} mt-2`}
                value={content.metadata.courseName}
                onChange={(e) =>
                  mutate({
                    ...content,
                    metadata: { ...content.metadata, courseName: e.target.value },
                  })
                }
              />
            </label>
            {mode === 'ai' && (
              <>
                <label className="block text-sm">
                  Who is this for?
                  <input
                    className={`${input} mt-2`}
                    value={content.metadata.targetAudience}
                    onChange={(e) =>
                      mutate({
                        ...content,
                        metadata: { ...content.metadata, targetAudience: e.target.value },
                      })
                    }
                  />
                </label>
                <label className="block text-sm">
                  What should employees be able to do?
                  <textarea
                    className={`${input} mt-2`}
                    rows={4}
                    value={content.metadata.courseObjective}
                    onChange={(e) =>
                      mutate({
                        ...content,
                        metadata: { ...content.metadata, courseObjective: e.target.value },
                      })
                    }
                  />
                </label>
                <details>
                  <summary className="cursor-pointer text-sm">
                    Customize generation · optional
                  </summary>
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <label>
                      Modules
                      <select
                        className={input}
                        value={content.settings.moduleCount}
                        onChange={(e) =>
                          mutate({
                            ...content,
                            settings: { ...content.settings, moduleCount: Number(e.target.value) },
                          })
                        }
                      >
                        {[2, 3, 4, 5, 6, 7, 8].map((n) => (
                          <option key={n} value={n}>
                            {n === 4 ? 'Default — 4 modules' : `${n} modules`}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Document length
                      <select
                        className={input}
                        value={content.settings.detailLevel}
                        onChange={(e) =>
                          mutate({
                            ...content,
                            settings: {
                              ...content.settings,
                              detailLevel: e.target.value as Content['settings']['detailLevel'],
                            },
                          })
                        }
                      >
                        {['short', 'standard', 'detailed'].map((v) => (
                          <option key={v}>{v}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <label className="mt-3 block">
                    <input
                      type="checkbox"
                      checked={content.settings.includeScenarios}
                      onChange={(e) =>
                        mutate({
                          ...content,
                          settings: { ...content.settings, includeScenarios: e.target.checked },
                        })
                      }
                    />{' '}
                    Include workplace scenarios
                  </label>
                </details>
                <button
                  className={primary}
                  disabled={
                    working ||
                    !content.metadata.courseName.trim() ||
                    !content.metadata.targetAudience.trim() ||
                    !content.metadata.courseObjective.trim()
                  }
                  onClick={() => void run(() => start('outline'))}
                >
                  Generate outline
                </button>
              </>
            )}
            {mode === 'blank' && (
              <button
                className={primary}
                disabled={working || !content.metadata.courseName.trim()}
                onClick={() =>
                  void run(async () => {
                    await save()
                    setStage('editor')
                  })
                }
              >
                Start writing
              </button>
            )}
            {mode === 'existing' && (
              <>
                {!documentId && (
                  <label className="block">
                    Paste your notes
                    <textarea
                      className={`${input} mt-2`}
                      rows={8}
                      value={pasted}
                      onChange={(e) => setPasted(e.target.value)}
                    />
                  </label>
                )}
                <p className="text-sm text-slate-500">
                  Import keeps your source content. Review the extracted modules before editing.
                </p>
                <button
                  className={primary}
                  disabled={working || (!documentId && !pasted.trim())}
                  onClick={importText}
                >
                  Import content
                </button>
              </>
            )}
          </div>
        ) : (
          <>
            <details className="card mb-4 p-4">
              <summary className="cursor-pointer font-semibold">Training details</summary>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {(
                  ['courseName', 'targetAudience', 'courseObjective', 'courseDescription'] as const
                ).map((key) => (
                  <label key={key}>
                    {
                      {
                        courseName: 'Course title',
                        targetAudience: 'Audience',
                        courseObjective: 'Learning goals',
                        courseDescription: 'Description',
                      }[key]
                    }
                    <textarea
                      className={input}
                      value={content.metadata[key]}
                      onChange={(e) =>
                        mutate({
                          ...content,
                          metadata: { ...content.metadata, [key]: e.target.value },
                        })
                      }
                    />
                  </label>
                ))}
              </div>
            </details>
            {sources.map(
              (source) =>
                source.issues.length > 0 &&
                !source.acknowledged && (
                  <div key={source.id} className="mb-4 rounded-lg bg-amber-50 p-4">
                    <h3 className="font-semibold">Review source extraction</h3>
                    {source.issues.map((issue, i) => (
                      <p key={i}>{issue}</p>
                    ))}
                    <button
                      className={button}
                      disabled={working || dirty}
                      onClick={() =>
                        void run(async () => {
                          if (draft)
                            load(
                              await postDraft<Draft>(
                                `/${draft.id}/sources/${source.id}/acknowledge`,
                                { expectedRevision: draft.revision, acknowledged: true },
                              ),
                            )
                        })
                      }
                    >
                      I have reviewed these issues
                    </button>
                  </div>
                ),
            )}
            {stage === 'outline' ? (
              <div className="card mx-auto max-w-3xl space-y-4 p-6">
                <h2 className="text-xl font-bold">Review your outline</h2>
                {content.modules.map((m, i) => (
                  <div key={m.id} className="rounded-lg border border-slate-200 p-4">
                    <label>
                      <input
                        type="checkbox"
                        checked={m.included}
                        onChange={(e) =>
                          mutate({
                            ...content,
                            modules: content.modules.map((v, n) =>
                              n === i ? { ...v, included: e.target.checked } : v,
                            ),
                          })
                        }
                      />{' '}
                      Include module {i + 1}
                    </label>
                    <input
                      aria-label={`Module ${i + 1} title`}
                      className={`${input} mt-2`}
                      value={m.title}
                      onChange={(e) =>
                        mutate({
                          ...content,
                          modules: content.modules.map((v, n) =>
                            n === i ? { ...v, title: e.target.value } : v,
                          ),
                        })
                      }
                    />
                    <p className="mt-2 text-sm">{m.objective}</p>
                    <ul className="list-inside list-disc text-sm text-slate-500">
                      {m.sections.map((s, n) => (
                        <li key={n}>{s}</li>
                      ))}
                    </ul>
                  </div>
                ))}
                <div className="flex flex-wrap gap-3">
                  <button
                    className={primary}
                    disabled={working}
                    onClick={() =>
                      void run(async () => {
                        const value = await approve()
                        setOperation(
                          await postDraft<Operation>(`/${value.id}/operations`, {
                            expectedRevision: value.revision,
                            task: 'draft',
                            key: id(),
                          }),
                        )
                        setStage('editor')
                      })
                    }
                  >
                    Approve and draft empty modules
                  </button>
                  <button
                    className={button}
                    disabled={working}
                    onClick={() =>
                      void run(async () => {
                        await approve()
                        setStage('editor')
                      })
                    }
                  >
                    Approve outline and review in editor
                  </button>
                </div>
                <p className="text-xs text-slate-500">
                  Create course becomes available when the included modules contain training
                  content.
                </p>
              </div>
            ) : (
              <div className="grid items-start gap-4 lg:grid-cols-[210px_minmax(0,1fr)_300px]">
                <nav className="card p-4" aria-label="Document modules">
                  <h2 className="mb-3 font-semibold">Modules</h2>
                  {content.modules.map((m, i) => (
                    <button
                      key={m.id}
                      className={`mb-2 block w-full rounded-lg p-3 text-left text-sm ${moduleIndex === i ? 'bg-blue-50 text-primary-blue' : 'text-slate-600'}`}
                      onClick={() => {
                        setModuleIndex(i)
                        setSelection(null)
                      }}
                    >
                      {i + 1}. {m.title}
                      {!m.included ? ' (excluded)' : ''}
                    </button>
                  ))}
                  <button
                    className={button}
                    disabled={working}
                    onClick={() => {
                      mutate({ ...content, modules: [...content.modules, newModule()] })
                      setModuleIndex(content.modules.length)
                    }}
                  >
                    + Add module
                  </button>
                  <button className={`${button} mt-3`} onClick={() => setStage('outline')}>
                    Review outline
                  </button>
                </nav>
                <main className="card min-w-0 p-5 md:p-7">
                  <fieldset disabled={working}>
                    <legend className="sr-only">Module editor</legend>
                    {module ? (
                      <>
                        <input
                          aria-label="Module title"
                          className={`${input} mb-5 !text-xl !font-semibold`}
                          value={module.title}
                          onChange={(e) =>
                            mutate({
                              ...content,
                              modules: content.modules.map((m, i) =>
                                i === moduleIndex ? { ...m, title: e.target.value } : m,
                              ),
                            })
                          }
                        />
                        <div className="mb-5 flex flex-wrap gap-2">
                          <button className={button} onClick={() => addBlock(paragraph())}>
                            + Paragraph
                          </button>
                          <button
                            className={button}
                            onClick={() => addBlock({ ...paragraph('Heading'), type: 'heading' })}
                          >
                            + Heading
                          </button>
                          <button
                            className={button}
                            onClick={() =>
                              addBlock({
                                id: id(),
                                type: 'table',
                                rows: [
                                  ['Column 1', 'Column 2'],
                                  ['Value', 'Value'],
                                ],
                                sourceReferences: [],
                              })
                            }
                          >
                            + Table
                          </button>
                          <label className={`${button} cursor-pointer`}>
                            + Image
                            <input
                              className="sr-only"
                              type="file"
                              accept="image/png,image/jpeg,image/webp"
                              onChange={(e) => {
                                const file = e.target.files?.[0]
                                if (file)
                                  void run(async () => {
                                    const value = await save()
                                    const body = new FormData()
                                    body.append('file', file)
                                    const asset = await draftApi<{ assetId: string }>(
                                      `/${value.id}/assets`,
                                      { body },
                                    )
                                    addBlock({
                                      id: id(),
                                      type: 'image',
                                      assetId: asset.assetId,
                                      caption: file.name,
                                      width: 60,
                                      align: 'left',
                                      sourceReferences: [],
                                    })
                                  })
                                e.target.value = ''
                              }}
                            />
                          </label>
                        </div>
                        {module.blocks.length === 0 && (
                          <div className="mb-4 rounded-lg bg-blue-50 p-4">
                            <p>This module is empty. Write content or ask AI to prepare a draft.</p>
                            <button
                              className={`${button} mt-3`}
                              disabled={working}
                              onClick={() =>
                                void run(() =>
                                  start('draft_module', { moduleId: module.id, scope: 'module' }),
                                )
                              }
                            >
                              Draft this module
                            </button>
                          </div>
                        )}
                        {module.blocks.map((block, index) => (
                          <div
                            className="group mb-5 rounded-lg border border-slate-100 p-3"
                            key={block.id}
                          >
                            <BlockEditor
                              block={block}
                              draftId={draft?.id}
                              onChange={(next) => changeBlock(block.id, next)}
                              onSelect={(start, end) => {
                                if ('text' in block)
                                  setSelection({ blockId: block.id, start, end, text: block.text })
                              }}
                            />
                            <button
                              className="mt-2 text-xs text-slate-500"
                              aria-label={`Remove block ${index + 1}`}
                              onClick={() =>
                                mutate({
                                  ...content,
                                  modules: content.modules.map((m, i) =>
                                    i === moduleIndex
                                      ? { ...m, blocks: m.blocks.filter((b) => b.id !== block.id) }
                                      : m,
                                  ),
                                })
                              }
                            >
                              Remove block
                            </button>
                          </div>
                        ))}
                      </>
                    ) : (
                      <p>Select or add a module to begin.</p>
                    )}
                  </fieldset>
                </main>
                <aside className="card space-y-4 p-5">
                  <h2 className="text-lg font-semibold">AI assistant</h2>
                  <p className="text-sm text-slate-500">
                    Describe the change. Review suggestions before applying them.
                  </p>
                  <label className="block text-sm">
                    Apply to
                    <select
                      className={`${input} mt-2`}
                      value={scope}
                      disabled={working}
                      onChange={(e) => setScope(e.target.value as typeof scope)}
                    >
                      <option value="selected">Selected text</option>
                      <option value="module">This module</option>
                      <option value="document">Complete document</option>
                    </select>
                  </label>
                  {scope === 'selected' && (
                    <p className="rounded-lg bg-blue-50 p-3 text-sm">
                      {selection && selection.end > selection.start
                        ? `Selected: ${selection.text.slice(selection.start, selection.end)}`
                        : 'Highlight text inside a paragraph in the editor.'}
                    </p>
                  )}
                  <textarea
                    aria-label="AI instruction"
                    className={input}
                    rows={5}
                    value={instruction}
                    disabled={working}
                    onChange={(e) => setInstruction(e.target.value)}
                    placeholder="Make this easier for a new employee to understand…"
                  />
                  <button
                    className={`${primary} w-full`}
                    disabled={working || !instruction.trim() || !module}
                    onClick={ask}
                  >
                    Suggest changes
                  </button>
                  <div className="flex flex-wrap gap-2">
                    <button
                      className={button}
                      disabled={working}
                      onClick={() =>
                        setInstruction(
                          'Simplify the wording for a new employee. Keep the meaning and do not invent company policies.',
                        )
                      }
                    >
                      Simplify
                    </button>
                    <button
                      className={button}
                      disabled={working || !module}
                      onClick={() =>
                        void run(() =>
                          start('insert', {
                            scope: 'module',
                            moduleId: module?.id,
                            instruction:
                              'Add a practical workplace scenario. Do not invent company policies.',
                          }),
                        )
                      }
                    >
                      Add scenario
                    </button>
                  </div>
                  <p className="border-t border-slate-200 pt-3 text-xs text-slate-500">
                    AI suggestions may need correction. Nothing replaces your content until you
                    accept.
                  </p>
                </aside>
              </div>
            )}
          </>
        )}
      </fieldset>
    </section>
  )
}

function BlockEditor({
  block,
  draftId,
  onChange,
  onSelect,
}: {
  block: Block
  draftId?: string
  onChange: (value: Block) => void
  onSelect: (start: number, end: number) => void
}) {
  if ('text' in block)
    return (
      <textarea
        aria-label={`${block.type} text`}
        className={`${input} min-h-28 ${block.type === 'heading' ? '!text-lg !font-bold' : ''}`}
        value={block.text}
        onChange={(e) => onChange({ ...block, text: e.target.value, marks: [] })}
        onSelect={(e) => onSelect(e.currentTarget.selectionStart, e.currentTarget.selectionEnd)}
      />
    )
  if (block.type === 'list')
    return (
      <label>
        List items (one per line)
        <textarea
          className={input}
          value={block.items.join('\n')}
          onChange={(e) =>
            onChange({ ...block, items: e.target.value.split('\n').filter(Boolean) })
          }
        />
      </label>
    )
  if (block.type === 'image')
    return (
      <>
        <DraftImage draftId={draftId} assetId={block.assetId} caption={block.caption} />
        <label className="block text-sm">
          Caption
          <input
            className={input}
            value={block.caption}
            onChange={(e) => onChange({ ...block, caption: e.target.value })}
          />
        </label>
      </>
    )
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <tbody>
          {block.rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, c) => (
                <td className="border border-slate-200 p-1" key={c}>
                  <input
                    aria-label={`Row ${r + 1} column ${c + 1}`}
                    className={input}
                    value={cell}
                    onChange={(e) =>
                      onChange({
                        ...block,
                        rows: block.rows.map((v, i) =>
                          i === r ? v.map((x, j) => (j === c ? e.target.value : x)) : v,
                        ),
                      })
                    }
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 flex gap-2">
        <button
          className={button}
          disabled={block.rows.length >= 100}
          onClick={() =>
            onChange({ ...block, rows: [...block.rows, (block.rows[0] || []).map(() => '')] })
          }
        >
          Add row
        </button>
        <button
          className={button}
          disabled={(block.rows[0]?.length || 0) >= 20}
          onClick={() => onChange({ ...block, rows: block.rows.map((row) => [...row, '']) })}
        >
          Add column
        </button>
      </div>
    </div>
  )
}

function DraftImage({
  draftId,
  assetId,
  caption,
}: {
  draftId?: string
  assetId: string
  caption: string
}) {
  const [url, setUrl] = useState('')
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    const abort = new AbortController()
    let objectUrl = ''
    void fetch(apiUrl(`/api/document-builder/drafts/${draftId}/assets/${assetId}`), {
      headers: authHeaders(),
      credentials: 'same-origin',
      signal: abort.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Image unavailable')
        const blob = await response.blob()
        if (!abort.signal.aborted) {
          objectUrl = URL.createObjectURL(blob)
          setUrl(objectUrl)
        }
      })
      .catch(() => {
        if (!abort.signal.aborted) setFailed(true)
      })
    return () => {
      abort.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [draftId, assetId])
  return failed ? (
    <p role="alert">Image unavailable. Your image reference is preserved.</p>
  ) : url ? (
    <img className="mx-auto max-h-96 max-w-full object-contain" alt={caption} src={url} />
  ) : (
    <p role="status">Loading image…</p>
  )
}

function Proposal({
  operation,
  disabled,
  accept,
  dismiss,
}: {
  operation: Operation
  disabled: boolean
  accept: () => void
  dismiss: () => void
}) {
  const result = operation.result
  return (
    <section
      aria-label="Review AI suggestion"
      className="card mb-6 overflow-hidden border border-blue-200"
    >
      <header className="bg-blue-50 p-4">
        <h2 className="font-semibold">Review AI suggestion</h2>
        <p className="text-sm text-slate-500">Your document has not been changed.</p>
      </header>
      <div className="max-h-[500px] space-y-4 overflow-y-auto p-5">
        {result?.modules?.map((module, i) => (
          <article key={i} className="rounded-lg border border-slate-200 p-4">
            <h3 className="font-semibold">
              {i + 1}. {module.title}
            </h3>
            <p>{module.objective}</p>
            <ul>
              {module.sections.map((s, j) => (
                <li key={j}>• {s}</li>
              ))}
            </ul>
          </article>
        ))}
        {result?.blocks && (
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
            <h3 className="mb-2 text-xs font-bold uppercase text-primary-blue">
              Suggested module content
            </h3>
            {result.blocks.map((block, i) => (
              <p key={i} className="mb-3 whitespace-pre-wrap">
                {block.text}
              </p>
            ))}
          </div>
        )}
        {(
          result?.changes ||
          (result?.replacementText
            ? [
                {
                  originalText: result.originalText || 'New content',
                  replacementText: result.replacementText,
                },
              ]
            : [])
        ).map((change, i) => (
          <div key={i} className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <h3 className="mb-2 text-xs font-bold uppercase text-slate-500">Original</h3>
              <p className="whitespace-pre-wrap">{change.originalText}</p>
            </div>
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
              <h3 className="mb-2 text-xs font-bold uppercase text-primary-blue">Suggested</h3>
              <p className="whitespace-pre-wrap">{change.replacementText}</p>
            </div>
          </div>
        ))}
      </div>
      <footer className="border-t border-slate-200 bg-slate-50 p-4">
        <p className="mb-3 text-sm text-slate-600">
          Review notice: Check accuracy before accepting. Accepting replaces only the requested
          content. Unsaved edits must be saved first.
        </p>
        <div className="flex gap-3">
          <button className={primary} disabled={disabled} onClick={accept}>
            Accept changes
          </button>
          <button className={button} disabled={disabled} onClick={dismiss}>
            Dismiss suggestion
          </button>
        </div>
      </footer>
    </section>
  )
}
