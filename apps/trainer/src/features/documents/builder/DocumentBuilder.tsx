import { errorMessage } from '@lms/shared/api/client'
import { Button, IconButton } from '@lms/shared/ui/Button'
import { Dialog } from '@lms/shared/ui/Dialog'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { useToast } from '@lms/shared/ui/Toast'
import { useQueryClient } from '@tanstack/react-query'
import { useBlocker } from '@tanstack/react-router'
import clsx from 'clsx'
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { trainerKeys } from '../../../shell/queryKeys'
import { useUpdateTrainerSearch, type TrainerSearch } from '../../../shell/search'
import {
  BuilderInput,
  BuilderSelect,
  BuilderTextArea,
  CheckboxRow,
  CompactButton,
  FieldLabel,
} from '../controls'
import { buildDocument, renderPdf, savePdf } from './api'
import { HorizontalScroller } from './HorizontalScroller'
import {
  builderText,
  defaultSettings,
  detailOptions,
  difficultyOptions,
  emptyMetadata,
  focusOptions,
  metadataKeys,
  missingFields,
  parseModuleCount,
  safeName,
  toneOptions,
  type BuilderMetadata,
  type BuilderSettings,
  type ChatMessage,
} from './models'
import { Panel, PanelHeader } from './Panel'
import { useDocumentEditor } from './useDocumentEditor'

const sameSettings = (a: BuilderSettings, b: BuilderSettings) =>
  (Object.keys(a) as (keyof BuilderSettings)[]).every((key) => a[key] === b[key])

/** Document Builder (DocumentBuilderPortal): metadata, settings, AI chat, and the draft editor. */
export function DocumentBuilder({ mobile }: { mobile: boolean }) {
  const queryClient = useQueryClient()
  const updateSearch = useUpdateTrainerSearch()
  const toast = useToast()
  const id = useId()

  const [metadata, setMetadata] = useState<BuilderMetadata>(emptyMetadata)
  const [metadataDirty, setMetadataDirty] = useState(false)
  const [metadataSaved, setMetadataSaved] = useState(false)

  const [form, setForm] = useState<BuilderSettings>(defaultSettings)
  const [moduleText, setModuleText] = useState('4')
  const [applied, setApplied] = useState<BuilderSettings>(defaultSettings)
  const [settingsDirty, setSettingsDirty] = useState(false)
  const [settingsApplied, setSettingsApplied] = useState(false)

  const [messages, setMessages] = useState<ChatMessage[]>([
    { user: false, text: builderText.intro },
  ])
  const instructions = useRef<string[]>([])
  const [prompt, setPrompt] = useState('')
  const [llmStatus, setLlmStatus] = useState('LLM idle')
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const [preview, setPreview] = useState(false)

  // The PDF object URL lives in a ref too, so it can be revoked at once and on unmount.
  const [pdfUrl, setPdfUrlState] = useState<string | null>(null)
  const pdfUrlRef = useRef<string | null>(null)
  const setPdfUrl = useCallback((next: string | null) => {
    if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current)
    pdfUrlRef.current = next
    setPdfUrlState(next)
  }, [])
  // Each edit and each render takes a new number. A render that finishes after a newer one
  // started, or after an edit, is dropped, so the cached PDF always matches the content.
  const pdfVersion = useRef(0)
  const clearPdf = useCallback(() => {
    pdfVersion.current += 1
    setPdfUrl(null)
  }, [setPdfUrl])

  const { editor, host, empty } = useDocumentEditor(clearPdf)

  const alive = useRef(true)
  const buildAbort = useRef<AbortController | null>(null)
  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      buildAbort.current?.abort()
      if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current)
      pdfUrlRef.current = null
    }
  }, [])

  const bot = useCallback((text: string) => {
    if (alive.current) setMessages((current) => [...current, { user: false, text }])
  }, [])

  // Unsaved work: any metadata, a settings change, an AI request, or draft content.
  const hasWork =
    metadataKeys.some((key) => metadata[key] !== emptyMetadata[key]) ||
    !sameSettings(form, defaultSettings) ||
    !sameSettings(applied, defaultSettings) ||
    messages.some((message) => message.user) ||
    !empty
  const hasWorkRef = useRef(hasWork)
  useEffect(() => {
    hasWorkRef.current = hasWork
  })
  const allowLeave = useRef(false)
  const blocker = useBlocker({
    shouldBlockFn: ({ next }) =>
      !allowLeave.current && hasWorkRef.current && (next.search as TrainerSearch).builder !== true,
    enableBeforeUnload: () => !allowLeave.current && hasWorkRef.current,
    withResolver: true,
  })

  const close = () => updateSearch({ builder: undefined })

  const changeMetadata = (key: keyof BuilderMetadata, value: string) => {
    setMetadata((current) => ({ ...current, [key]: value }))
    setMetadataDirty(true)
    clearPdf()
  }

  const changeSettings = (patch: Partial<BuilderSettings>) => {
    setForm((current) => ({ ...current, ...patch }))
    setSettingsDirty(true)
  }

  const validate = (): boolean => {
    const missing = missingFields(metadata)
    if (missing.length > 0) {
      bot(builderText.missing(missing))
      return false
    }
    if (!editor.text) {
      bot(builderText.emptyDraft)
      return false
    }
    return true
  }

  const render = async (): Promise<string | null> => {
    if (!validate()) return null
    const version = (pdfVersion.current += 1)
    try {
      const blob = await renderPdf(metadata, editor.text, editor.blocks)
      if (!alive.current || version !== pdfVersion.current) return null
      const url = URL.createObjectURL(blob)
      setPdfUrl(url)
      return url
    } catch (error) {
      bot(builderText.renderError(errorMessage(error)))
      return null
    }
  }

  const send = async () => {
    const message = prompt.trim()
    if (!message || busy) return
    instructions.current = [...instructions.current, message]
    setMessages((current) => [...current, { user: true, text: message }])
    setPrompt('')
    setBusy(true)
    setLlmStatus('Gemma writing')
    const abort = new AbortController()
    buildAbort.current = abort
    try {
      const result = await buildDocument(
        {
          message,
          instructions: instructions.current,
          currentDraft: editor.text,
          builderSettings: applied,
        },
        abort.signal,
      )
      editor.setText(result.document, { preserveImages: true })
      setLlmStatus(`${result.model ?? 'Gemma'} done`)
      bot(result.reply ?? builderText.buildDefault)
    } catch (error) {
      // The builder closed while the request ran. Nothing to show.
      if (abort.signal.aborted) return
      setLlmStatus('LLM failed')
      bot(builderText.buildError(errorMessage(error)))
    } finally {
      if (buildAbort.current === abort) buildAbort.current = null
      if (alive.current) setBusy(false)
    }
  }

  const showPreview = async () => {
    setPreview(true)
    await render()
  }

  const download = async () => {
    const url = pdfUrlRef.current ?? (await render())
    if (!url) return
    const name = safeName(metadata.courseName)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${name || 'document'}-source.pdf`
    anchor.style.display = 'none'
    document.body.append(anchor)
    anchor.click()
    anchor.remove()
  }

  const copy = async () => {
    try {
      // The Clipboard API is missing outside a secure context.
      if (!navigator.clipboard) throw new Error('Clipboard is not available in this browser.')
      await navigator.clipboard.writeText(editor.text)
      bot(builderText.copied)
    } catch (error) {
      bot(builderText.copyError(errorMessage(error)))
    }
  }

  const save = async () => {
    if (saving || !validate()) return
    setSaving(true)
    try {
      const file = await savePdf(metadata, editor.text, editor.blocks)
      void queryClient.invalidateQueries({ queryKey: trainerKeys.files })
      if (!alive.current) return
      // Flutter posted this in the chat and then closed it. A toast stays visible after close.
      toast(builderText.saved, { tone: 'success' })
      allowLeave.current = true
      updateSearch({ builder: undefined, file: file.fileName })
    } catch (error) {
      bot(builderText.saveError(errorMessage(error)))
    } finally {
      if (alive.current) setSaving(false)
    }
  }

  const field = (key: keyof BuilderMetadata) => ({
    id: `${id}-${key}`,
    value: metadata[key],
    onChange: (event: { target: { value: string } }) => changeMetadata(key, event.target.value),
  })

  const metadataPanel = (
    <Panel label="Metadata" className={mobile ? 'h-[520px]' : 'w-[288px] shrink-0'}>
      <PanelHeader
        title="Metadata"
        status={metadataDirty ? 'Unsaved changes' : metadataSaved ? 'Saved' : 'Not saved'}
        active={!metadataDirty && metadata.courseName !== ''}
      />
      <div className="min-h-0 flex-1 overflow-y-auto p-3.5">
        <FieldLabel htmlFor={`${id}-courseName`} label="Course name">
          <BuilderInput placeholder="Workplace Training" {...field('courseName')} />
        </FieldLabel>
        <FieldLabel htmlFor={`${id}-courseDescription`} label="Course description">
          <BuilderTextArea
            placeholder="Short LMS-facing course description"
            {...field('courseDescription')}
          />
        </FieldLabel>
        <FieldLabel htmlFor={`${id}-courseObjective`} label="Course objective">
          <BuilderTextArea
            placeholder="What the learner should be able to do"
            {...field('courseObjective')}
          />
        </FieldLabel>
        <FieldLabel htmlFor={`${id}-courseDifficulty`} label="Course difficulty">
          <BuilderSelect
            id={`${id}-courseDifficulty`}
            value={metadata.courseDifficulty}
            options={difficultyOptions}
            onChange={(value) => changeMetadata('courseDifficulty', value)}
          />
        </FieldLabel>
        <FieldLabel htmlFor={`${id}-language`} label="Language">
          <BuilderInput {...field('language')} />
        </FieldLabel>
        <FieldLabel htmlFor={`${id}-targetAudience`} label="Target audience">
          <BuilderInput placeholder="New employees" {...field('targetAudience')} />
        </FieldLabel>
        <FieldLabel htmlFor={`${id}-courseType`} label="Course type">
          <BuilderInput placeholder="Functional Training" {...field('courseType')} />
        </FieldLabel>
        <CompactButton
          className="w-full"
          onClick={() => {
            setMetadataDirty(false)
            setMetadataSaved(true)
            bot(builderText.metadataSaved)
          }}
        >
          Save metadata
        </CompactButton>
      </div>
    </Panel>
  )

  const settingsPanel = (
    <Panel label="Builder Settings" className={mobile ? 'h-[520px]' : 'w-[292px] shrink-0'}>
      <PanelHeader
        title="Builder Settings"
        status={
          settingsDirty ? 'Unsaved changes' : settingsApplied ? 'Applied' : 'Defaults applied'
        }
        active={!settingsDirty}
      />
      <div className="min-h-0 flex-1 overflow-y-auto p-3.5">
        <FieldLabel htmlFor={`${id}-moduleCount`} label="Module count">
          <BuilderInput
            id={`${id}-moduleCount`}
            inputMode="numeric"
            value={moduleText}
            onChange={(event) => {
              setModuleText(event.target.value)
              changeSettings({ moduleCount: parseModuleCount(event.target.value) })
            }}
            // Flutter kept "99" in the field but stored 8. Show the stored value after editing.
            onBlur={() => setModuleText(String(form.moduleCount))}
          />
        </FieldLabel>
        <FieldLabel htmlFor={`${id}-detailLevel`} label="Detail level">
          <BuilderSelect
            id={`${id}-detailLevel`}
            value={form.detailLevel}
            options={detailOptions}
            onChange={(detailLevel) => changeSettings({ detailLevel })}
          />
        </FieldLabel>
        <FieldLabel htmlFor={`${id}-tone`} label="Tone">
          <BuilderSelect
            id={`${id}-tone`}
            value={form.tone}
            options={toneOptions}
            onChange={(tone) => changeSettings({ tone })}
          />
        </FieldLabel>
        <FieldLabel htmlFor={`${id}-writingFocus`} label="Writing focus">
          <BuilderSelect
            id={`${id}-writingFocus`}
            value={form.writingFocus}
            options={focusOptions}
            onChange={(writingFocus) => changeSettings({ writingFocus })}
          />
        </FieldLabel>
        <div className="h-px bg-light-gray" />
        <CheckboxRow
          label="Include scenarios inside modules"
          checked={form.includeScenarios}
          onChange={(includeScenarios) => changeSettings({ includeScenarios })}
        />
        <CheckboxRow
          label="Include weak vs better examples"
          checked={form.includeBadGood}
          onChange={(includeBadGood) => changeSettings({ includeBadGood })}
        />
        <CheckboxRow
          label="Include short takeaways"
          checked={form.includeTakeaways}
          onChange={(includeTakeaways) => changeSettings({ includeTakeaways })}
        />
        <CheckboxRow
          label="Include common mistakes"
          checked={form.includeMistakes}
          onChange={(includeMistakes) => changeSettings({ includeMistakes })}
        />
        <CompactButton
          variant="outlined"
          className="mt-2 w-full"
          onClick={() => {
            setApplied(form)
            setSettingsDirty(false)
            setSettingsApplied(true)
            bot(builderText.settingsApplied)
          }}
        >
          Apply builder settings
        </CompactButton>
      </div>
    </Panel>
  )

  const chatPanel = (
    <Panel label="AI Editor Chat" className={mobile ? 'h-[520px]' : 'w-[384px] shrink-0'}>
      <PanelHeader
        title="AI Editor Chat"
        status={llmStatus}
        active={llmStatus.includes('done')}
        error={llmStatus.includes('failed')}
      />
      <ChatMessages messages={messages} />
      <div className="shrink-0 border-t border-light-gray p-3.5">
        <BuilderTextArea
          rows={5}
          aria-label="Message to the AI editor"
          placeholder="Example: Create a 5-module document about clear communication. Or: rewrite Module 2 with a stronger scenario."
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />
        <div className="mt-2.5 flex gap-2">
          <CompactButton
            className="min-w-0 flex-1 basis-0"
            disabled={busy}
            onClick={() => void send()}
          >
            {busy ? 'Writing...' : 'Send to AI'}
          </CompactButton>
          <CompactButton
            variant="outlined"
            // Padding sits on the text so both Expanded buttons get the same width.
            className="h-9 min-w-0 flex-1 basis-0 justify-start! px-0"
            onClick={() => bot(builderText.questions)}
          >
            <span className="px-[22px] text-left">Ask missing questions</span>
          </CompactButton>
        </div>
      </div>
    </Panel>
  )

  const documentPanel = (
    <Panel
      label="Document Draft"
      className={clsx('@container', mobile ? 'h-[650px]' : 'min-w-0 flex-1')}
    >
      {/* Below 620 px Flutter stacks the title over the buttons and shrinks the bar to its content. */}
      <div className="flex shrink-0 flex-col self-center border-b border-light-gray p-3.5 @min-[620px]:flex-row @min-[620px]:items-center @min-[620px]:self-stretch">
        <h3 className="m-0 truncate font-inter text-[17px] leading-[25.5px] font-bold tracking-[0.25px] text-text-black @min-[620px]:mr-2.5 @min-[620px]:flex-1">
          Document Draft
        </h3>
        <div className="mt-2.5 flex flex-wrap gap-1.5 @min-[620px]:mt-0">
          <ToolbarButton active={!preview} onClick={() => setPreview(false)}>
            Draft
          </ToolbarButton>
          <ToolbarButton active={preview} onClick={() => void showPreview()}>
            Preview Doc
          </ToolbarButton>
          <ToolbarButton onClick={() => void copy()}>Copy</ToolbarButton>
          <ToolbarButton disabled={saving} onClick={() => void save()}>
            {saving ? 'Saving...' : 'Save PDF'}
          </ToolbarButton>
          <CompactButton className="px-2.5" onClick={() => void download()}>
            Download PDF
          </CompactButton>
        </div>
      </div>
      <div className="relative min-h-0 flex-1">
        {/* The editor stays mounted in preview mode, so the caret and images are kept. */}
        <div ref={host} className="h-full" hidden={preview} />
        {!preview && empty && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-center">
            Type here, paste images, or drag images into the document.
          </div>
        )}
        {preview && (
          <iframe
            title="PDF preview"
            src={pdfUrl ?? 'about:blank'}
            className="block size-full border-0"
          />
        )}
      </div>
    </Panel>
  )

  const panels = [metadataPanel, settingsPanel, chatPanel, documentPanel]

  return (
    <div className="flex h-full flex-col">
      <div className="card flex h-[52px] shrink-0 items-center px-4">
        <Icon name="edit_document" size={24} className="text-primary-blue" />
        <h2 className="m-0 ml-2.5 flex-1 font-inter text-[17px] leading-[25.5px] font-bold tracking-[0.25px] text-primary-blue">
          Document Builder
        </h2>
        <IconButton
          icon="close"
          label="Close builder"
          className="text-[#44474e]!"
          onClick={close}
        />
      </div>
      <div className="mt-3 min-h-0 flex-1">
        {mobile ? (
          <div className="flex h-full flex-col gap-3 overflow-y-auto *:shrink-0">
            {withKeys(panels)}
          </div>
        ) : (
          <HorizontalScroller>
            <div className="flex h-full w-full min-w-[1520px] gap-3">{withKeys(panels)}</div>
          </HorizontalScroller>
        )}
      </div>
      <Dialog
        open={blocker.status === 'blocked'}
        onOpenChange={(open) => {
          if (!open) blocker.reset?.()
        }}
        title="Discard this document?"
        width={420}
        actions={
          <>
            <Button variant="text" onClick={() => blocker.reset?.()}>
              Keep editing
            </Button>
            <Button
              variant="text"
              className="text-accent-red!"
              onClick={() => {
                allowLeave.current = true
                blocker.proceed?.()
              }}
            >
              Discard
            </Button>
          </>
        }
      >
        The builder keeps its metadata, settings, chat, and draft only while it is open. If you
        close it, this work is lost.
      </Dialog>
    </div>
  )
}

const withKeys = (nodes: ReactNode[]) =>
  nodes.map((node, index) => (
    <div key={index} className="contents">
      {node}
    </div>
  ))

function ToolbarButton({
  active = false,
  disabled,
  onClick,
  children,
}: {
  active?: boolean
  disabled?: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <CompactButton
      variant="outlined"
      active={active}
      aria-pressed={active || undefined}
      disabled={disabled}
      className="px-2.5"
      onClick={onClick}
    >
      {children}
    </CompactButton>
  )
}

function ChatMessages({ messages }: { messages: ChatMessage[] }) {
  const list = useRef<HTMLDivElement>(null)
  // Keep the newest message in view. Flutter did not scroll, so new replies were easy to miss.
  useEffect(() => {
    const element = list.current
    if (element) element.scrollTop = element.scrollHeight
  }, [messages.length])
  return (
    <div
      ref={list}
      role="log"
      aria-label="Chat messages"
      className="min-h-0 flex-1 overflow-y-auto p-3.5"
    >
      {messages.map((message, index) => (
        <div
          key={index}
          className={clsx(
            // Chrome lays out DM Sans about 2 px wider per line than Flutter.
            // The smaller right padding keeps the Flutter line breaks.
            'mb-3 w-fit max-w-[340px] rounded-lg p-3 pr-2.5 whitespace-pre-wrap',
            message.user ? 'ml-auto bg-brand-blue-100' : 'bg-brand-blue-50',
          )}
        >
          {message.text}
        </div>
      ))}
    </div>
  )
}
