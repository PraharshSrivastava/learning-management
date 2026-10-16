import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { trainerKeys } from '../../../shell/queryKeys'
import {
  fileJson,
  renderDocuments,
  requestBody,
  stubBrowser,
  stubFetch,
} from '../test/renderDocuments'
import { builderText } from './models'

const BUILDER = '/?tab=documents&builder=true'

let browser: ReturnType<typeof stubBrowser>

beforeEach(() => {
  browser = stubBrowser()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const chat = () => screen.getByRole('log', { name: 'Chat messages' })
const editorRoot = () => screen.getByLabelText('Rich document editor')
const button = (name: string | RegExp) => screen.getByRole('button', { name })

async function openBuilder(handler: Parameters<typeof stubFetch>[0] = () => []) {
  const fetchMock = stubFetch(handler)
  const view = renderDocuments(BUILDER)
  await screen.findByRole('heading', { name: 'Document Builder' })
  return { ...view, fetchMock }
}

async function fillMetadata() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Course name'), 'Fire Safety: Level 2')
  await user.type(screen.getByLabelText('Course description'), 'Basics')
  await user.type(screen.getByLabelText('Course objective'), 'Leave safely')
  await user.selectOptions(screen.getByRole('combobox', { name: 'Course difficulty' }), 'Easy')
  await user.type(screen.getByLabelText('Target audience'), 'Staff')
  await user.type(screen.getByLabelText('Course type'), 'Functional Training')
}

/** Simulates typing into the contenteditable: change the DOM, then fire input. */
function typeDraft(text: string) {
  act(() => {
    editorRoot().innerHTML = `<p>${text}</p>`
    fireEvent.input(editorRoot())
  })
}

describe('DocumentBuilder', () => {
  it('starts with the intro, default pills, and the empty draft hint', async () => {
    await openBuilder()
    expect(within(chat()).getByText(builderText.intro)).toBeInTheDocument()
    const metadata = screen.getByRole('region', { name: 'Metadata' })
    expect(within(metadata).getByRole('status')).toHaveTextContent('Not saved')
    const settings = screen.getByRole('region', { name: 'Builder Settings' })
    expect(within(settings).getByRole('status')).toHaveTextContent('Defaults applied')
    expect(screen.getByText('LLM idle')).toBeInTheDocument()
    expect(screen.getByLabelText('Language')).toHaveValue('English')
    expect(
      screen.getByText('Type here, paste images, or drag images into the document.'),
    ).toBeInTheDocument()
    expect(button('Draft')).toHaveAttribute('aria-pressed', 'true')
  })

  it('updates the metadata and settings pills', async () => {
    await openBuilder()
    const user = userEvent.setup()
    const metadata = screen.getByRole('region', { name: 'Metadata' })
    await user.type(screen.getByLabelText('Course name'), 'X')
    expect(within(metadata).getByRole('status')).toHaveTextContent('Unsaved changes')
    await user.click(button('Save metadata'))
    expect(within(metadata).getByRole('status')).toHaveTextContent('Saved')
    expect(within(chat()).getByText(builderText.metadataSaved)).toBeInTheDocument()

    const settings = screen.getByRole('region', { name: 'Builder Settings' })
    await user.click(screen.getByRole('checkbox', { name: 'Include short takeaways' }))
    expect(within(settings).getByRole('status')).toHaveTextContent('Unsaved changes')
    await user.click(button('Apply builder settings'))
    expect(within(settings).getByRole('status')).toHaveTextContent('Applied')
    expect(within(chat()).getByText(builderText.settingsApplied)).toBeInTheDocument()
  })

  it('posts the questions on Ask missing questions', async () => {
    await openBuilder()
    await userEvent.click(button('Ask missing questions'))
    expect(chat()).toHaveTextContent('Before finalizing, I would ask:')
  })

  it('lists the missing metadata before a PDF, then asks for content', async () => {
    const { fetchMock } = await openBuilder()
    await userEvent.click(button('Save PDF'))
    expect(chat()).toHaveTextContent('Fill these metadata fields before PDF preview/download:')
    expect(chat()).toHaveTextContent('Course objective')
    await fillMetadata()
    await userEvent.click(button('Download PDF'))
    expect(within(chat()).getByText(builderText.emptyDraft)).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('document-builder'))).toBe(
      false,
    )
  })

  it('sends the prompt with history, applied settings, and the draft, and keeps images', async () => {
    let resolve: (value: unknown) => void = () => {}
    const { fetchMock } = await openBuilder((url) =>
      url.pathname.endsWith('/build-document') ? new Promise((done) => (resolve = done)) : [],
    )
    const user = userEvent.setup()
    // Applied settings go to the AI. Settings that are not applied stay local.
    await user.clear(screen.getByLabelText('Module count'))
    await user.type(screen.getByLabelText('Module count'), '99')
    const tone = screen.getByRole('combobox', { name: 'Tone' })
    await user.selectOptions(tone, 'Warm and conversational')
    expect(tone).toHaveDisplayValue('Warm and conversational')
    await user.click(button('Apply builder settings'))
    await user.click(screen.getByRole('checkbox', { name: 'Include common mistakes' }))
    typeDraft('Old text')
    const figure = document.createElement('figure')
    figure.className = 'editor-image'
    figure.innerHTML = '<img src="data:image/png;base64,AA"><figcaption>Map</figcaption>'
    editorRoot().append(figure)

    await user.type(screen.getByLabelText('Message to the AI editor'), 'Write 3 modules')
    await user.click(button('Send to AI'))
    expect(screen.getByText('Gemma writing')).toBeInTheDocument()
    expect(button('Writing...')).toBeDisabled()
    expect(screen.getByLabelText('Message to the AI editor')).toHaveValue('')
    expect(requestBody(fetchMock, '/build-document')).toEqual({
      message: 'Write 3 modules',
      instructions: ['Write 3 modules'],
      currentDraft: 'Old text',
      builderSettings: expect.objectContaining({
        moduleCount: 8,
        tone: 'Warm and conversational',
        includeMistakes: true,
      }),
    })
    await act(async () =>
      resolve({
        document: 'Intro\n\nModule 1: Exits\n\nModule 2: Drills',
        reply: 'Done!',
        model: 'gemma3',
      }),
    )
    expect(await screen.findByText('gemma3 done')).toBeInTheDocument()
    expect(within(chat()).getByText('Done!')).toBeInTheDocument()
    const children = Array.from(editorRoot().children).map((node) => node.localName)
    expect(children).toEqual(['p', 'p', 'figure'])
    expect(editorRoot()).toHaveTextContent('Module 1: Exits')
    expect(editorRoot()).not.toHaveTextContent('Intro')
    expect(screen.getByLabelText('Module count')).toHaveValue('8')
  })

  it('reports an AI failure in the chat', async () => {
    await openBuilder((url) =>
      url.pathname.endsWith('/build-document')
        ? new Response(JSON.stringify({ error: 'Model offline' }), { status: 503 })
        : [],
    )
    await userEvent.type(screen.getByLabelText('Message to the AI editor'), 'Go')
    await userEvent.click(button('Send to AI'))
    expect(await screen.findByText('LLM failed')).toBeInTheDocument()
    expect(chat()).toHaveTextContent('No LLM document was generated. Error: Model offline')
  })

  it('edits a pasted figure from its popover and sends the blocks', async () => {
    const { fetchMock } = await openBuilder((url) =>
      url.pathname.endsWith('/render-pdf') ? new Response(new Blob(['%PDF'])) : [],
    )
    await fillMetadata()
    typeDraft('Module 1: Exits')
    // The user clicks at the end of the text before the paste.
    editorRoot().focus()
    const range = document.createRange()
    range.selectNodeContents(editorRoot().querySelector('p')!)
    range.collapse(false)
    window.getSelection()!.removeAllRanges()
    window.getSelection()!.addRange(range)
    fireEvent.mouseUp(editorRoot())
    const image = new File(['png'], 'map.png', { type: 'image/png' })
    const paste = new Event('paste', { bubbles: true, cancelable: true })
    Object.assign(paste, { clipboardData: { files: [image] } })
    act(() => {
      editorRoot().dispatchEvent(paste)
    })
    const figure = await waitFor(() => {
      const found = editorRoot().querySelector<HTMLElement>('figure.editor-image')
      expect(found).not.toBeNull()
      return found!
    })
    expect(paste.defaultPrevented).toBe(true)
    await userEvent.click(figure)
    const popover = figure.querySelector<HTMLElement>('.image-popover')!
    expect(popover.style.display).toBe('block')
    fireEvent.input(within(popover).getByTitle('Resize image'), { target: { value: '40' } })
    fireEvent.change(within(popover).getByTitle('Align image'), { target: { value: 'center' } })
    await userEvent.click(button('Preview Doc'))
    await waitFor(() =>
      expect(screen.getByTitle('PDF preview')).toHaveAttribute('src', 'blob:pdf-1'),
    )
    const body = requestBody(fetchMock, '/render-pdf') as {
      document: string
      documentBlocks: { type: string; width: number; align: string }[]
      metadata: { courseName: string }
    }
    expect(body.document).toBe('Module 1: Exits')
    expect(body.metadata.courseName).toBe('Fire Safety: Level 2')
    expect(body.documentBlocks.map((block) => block.type)).toEqual(['text', 'image'])
    expect(body.documentBlocks[1]).toMatchObject({ width: 40, align: 'center' })

    // An edit drops the stale PDF.
    await userEvent.click(button('Draft'))
    await userEvent.click(within(popover).getByRole('button', { name: 'Delete' }))
    expect(editorRoot().querySelector('figure')).toBeNull()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:pdf-1')
  })

  it('downloads the rendered PDF with a safe name', async () => {
    await openBuilder((url) =>
      url.pathname.endsWith('/render-pdf') ? new Response(new Blob(['%PDF'])) : [],
    )
    await fillMetadata()
    typeDraft('Module 1: Exits')
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      expect(this.download).toBe('fire-safety-level-2-source.pdf')
      expect(this.href).toBe('blob:pdf-1')
    })
    await userEvent.click(button('Download PDF'))
    await waitFor(() => expect(click).toHaveBeenCalledTimes(1))
    click.mockRestore()
  })

  it('reports a render failure in the chat', async () => {
    await openBuilder((url) =>
      url.pathname.endsWith('/render-pdf')
        ? new Response(JSON.stringify({ detail: 'Bad image' }), { status: 422 })
        : [],
    )
    await fillMetadata()
    typeDraft('Module 1: Exits')
    await userEvent.click(button('Preview Doc'))
    expect(await within(chat()).findByText(/Could not render PDF preview/)).toHaveTextContent(
      'Error: Bad image',
    )
  })

  it('saves the PDF, closes, selects the new file, and refetches the list', async () => {
    let saved = false
    const { fetchMock, search, invalidate } = await openBuilder((url) => {
      if (url.pathname.endsWith('/save-pdf')) {
        saved = true
        return { file: fileJson('fire-safety.pdf') }
      }
      return saved ? [fileJson('fire-safety.pdf')] : []
    })
    await fillMetadata()
    typeDraft('Module 1: Exits')
    await userEvent.click(button('Save PDF'))
    await waitFor(() => expect(search().builder).toBeUndefined())
    expect(search().file).toBe('trainer_0001__fire-safety.pdf')
    expect(invalidate).toHaveBeenCalledWith({ queryKey: trainerKeys.files })
    expect(screen.getByText(builderText.saved)).toBeInTheDocument()
    expect(screen.queryByText('Discard this document?')).not.toBeInTheDocument()
    expect(requestBody(fetchMock, '/save-pdf')).toMatchObject({
      document: 'Module 1: Exits',
      metadata: { courseType: 'Functional Training', language: 'English' },
    })
    expect(await screen.findByRole('button', { name: 'Create Course' })).toBeInTheDocument()
  })

  it('keeps the builder open and reports a save failure', async () => {
    const { search } = await openBuilder((url) =>
      url.pathname.endsWith('/save-pdf')
        ? new Response(JSON.stringify({ detail: 'Disk full' }), { status: 500 })
        : [],
    )
    await fillMetadata()
    typeDraft('Module 1: Exits')
    await userEvent.click(button('Save PDF'))
    expect(await within(chat()).findByText(/Could not save PDF/)).toHaveTextContent(
      'Error: Disk full',
    )
    expect(search().builder).toBe(true)
  })

  it('closes at once when there is no work', async () => {
    const { search } = await openBuilder()
    await userEvent.click(button('Close builder'))
    await waitFor(() => expect(search().builder).toBeUndefined())
    expect(await screen.findByRole('button', { name: 'Open Document Builder' })).toBeInTheDocument()
  })

  it('asks before it discards unsaved work', async () => {
    const { search } = await openBuilder()
    typeDraft('Module 1: Draft')
    await userEvent.click(button('Close builder'))
    expect(await screen.findByText('Discard this document?')).toBeInTheDocument()
    await userEvent.click(button('Keep editing'))
    await waitFor(() =>
      expect(screen.queryByText('Discard this document?')).not.toBeInTheDocument(),
    )
    expect(search().builder).toBe(true)
    expect(editorRoot()).toHaveTextContent('Module 1: Draft')

    await userEvent.click(button('Close builder'))
    await userEvent.click(await screen.findByRole('button', { name: 'Discard' }))
    await waitFor(() => expect(search().builder).toBeUndefined())
  })

  it('posts the copy result and the copy failure', async () => {
    await openBuilder()
    typeDraft('Module 1: Copy me')
    const writeText = vi
      .fn()
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error('Denied'))
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await userEvent.click(button('Copy'))
    expect(writeText).toHaveBeenCalledWith('Module 1: Copy me')
    expect(await within(chat()).findByText(builderText.copied)).toBeInTheDocument()
    await userEvent.click(button('Copy'))
    expect(await within(chat()).findByText(/Could not copy/)).toHaveTextContent('Error: Denied')
  })

  it('keeps the draft when the layout crosses the breakpoint', async () => {
    await openBuilder()
    typeDraft('Module 1: Exits')
    const root = editorRoot()
    act(() => browser.setMobile(true))
    expect(editorRoot()).toBe(root)
    expect(root.isConnected).toBe(true)
    expect(root).toHaveTextContent('Module 1: Exits')
    act(() => browser.setMobile(false))
    expect(editorRoot()).toBe(root)
    expect(root.isConnected).toBe(true)
  })

  it('drops a PDF render that finishes after an edit', async () => {
    let finish!: (response: Response) => void
    const { fetchMock } = await openBuilder((url) =>
      url.pathname.endsWith('/render-pdf') ? new Promise<Response>((done) => (finish = done)) : [],
    )
    await fillMetadata()
    typeDraft('Module 1: Exits')
    await userEvent.click(button('Preview Doc'))
    await userEvent.click(button('Draft'))
    typeDraft('Module 1: Exits and stairs')
    await act(async () => finish(new Response(new Blob(['%PDF old']))))
    expect(URL.createObjectURL).not.toHaveBeenCalled()
    const renders = () =>
      fetchMock.mock.calls.filter(([input]) => String(input).includes('/render-pdf'))
    expect(renders()).toHaveLength(1)
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await userEvent.click(button('Download PDF'))
    // The download renders the edited draft again instead of the stale PDF.
    await waitFor(() => expect(renders()).toHaveLength(2))
    click.mockRestore()
  })
})
