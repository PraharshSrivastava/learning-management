import { setMediaTicket } from '@lms/shared/api/client'
import {
  act,
  cleanup,
  fireEvent,
  renderHook,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { trainerKeys } from '../../shell/queryKeys'
import { useCourseList } from '../courses/courseQueries'
import { FakeXhr, fileJson, renderDocuments, stubBrowser, stubFetch } from './test/renderDocuments'

beforeEach(() => stubBrowser())

afterEach(() => {
  cleanup()
  setMediaTicket(null)
  vi.unstubAllGlobals()
})

const list = () => screen.getByRole('list')

describe('Uploaded Documents list', () => {
  it('shows the files with size and date, and the item count', async () => {
    stubFetch(() => [fileJson('alpha.pdf'), fileJson('beta.docx', { size: 3 * 1024 * 1024 })])
    renderDocuments()
    expect(await screen.findByText('alpha.pdf')).toBeInTheDocument()
    expect(screen.getByText('2 items')).toBeInTheDocument()
    expect(within(list()).getByText('1.5 KB')).toBeInTheDocument()
    expect(within(list()).getByText('3.0 MB')).toBeInTheDocument()
    expect(within(list()).getAllByText('1/1/2026 09:05')).toHaveLength(2)
    expect(screen.getByText('No Document Selected')).toBeInTheDocument()
  })

  it('shows a spinner while loading', async () => {
    stubFetch(() => new Promise(() => {}))
    renderDocuments()
    expect(
      await screen.findByRole('progressbar', { name: 'Loading documents' }),
    ).toBeInTheDocument()
  })

  it('shows the empty state', async () => {
    stubFetch(() => [])
    renderDocuments()
    expect(await screen.findByText('No documents uploaded yet')).toBeInTheDocument()
    expect(screen.getByText('0 items')).toBeInTheDocument()
  })

  it('shows the server error and 0 items', async () => {
    stubFetch(() => new Response(JSON.stringify({ detail: 'Not allowed' }), { status: 403 }))
    renderDocuments()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Error loading files')
    expect(alert).toHaveTextContent('Not allowed')
    expect(screen.getByText('0 items')).toBeInTheDocument()
  })

  it('keeps a bad date as raw text instead of crashing', async () => {
    stubFetch(() => [fileJson('odd.pdf', { created_at: 'yesterday' })])
    renderDocuments()
    expect(await screen.findByText('yesterday')).toBeInTheDocument()
  })

  it('selects a file into the URL and shows it in the viewer', async () => {
    stubFetch(() => [fileJson('alpha.pdf'), fileJson('beta.pdf')])
    const { search } = renderDocuments()
    // configureApi clears the ticket, so set it after render.
    act(() => setMediaTicket('ticket-1'))
    await userEvent.click(await screen.findByRole('button', { name: /beta\.pdf/ }))
    await waitFor(() => expect(search().file).toBe('trainer_0001__beta.pdf'))
    expect(screen.getByRole('button', { name: /beta\.pdf/ })).toHaveAttribute(
      'aria-current',
      'true',
    )
    const frame = screen.getByTitle('beta.pdf')
    expect(frame.getAttribute('src')).toContain('trainer_0001__beta.pdf')
    expect(frame.getAttribute('src')).toContain('media_ticket=ticket-1')
  })

  it('selects nothing when the URL file is not in the list', async () => {
    stubFetch(() => [fileJson('alpha.pdf')])
    renderDocuments('/?tab=documents&file=gone.pdf')
    await screen.findByText('alpha.pdf')
    expect(screen.getByText('No Document Selected')).toBeInTheDocument()
  })

  it('opens the preview in a new tab with the newest ticket', async () => {
    const open = vi.fn()
    vi.stubGlobal('open', open)
    stubFetch(() => [fileJson('alpha.pdf')])
    renderDocuments('/?tab=documents&file=trainer_0001__alpha.pdf')
    act(() => setMediaTicket('old'))
    await screen.findByTitle('alpha.pdf')
    act(() => setMediaTicket('new'))
    await userEvent.click(screen.getByRole('button', { name: 'Open in new tab' }))
    expect(open).toHaveBeenCalledWith(
      expect.stringContaining('media_ticket=new'),
      '_blank',
      'noopener',
    )
    // The open iframe keeps its first URL, so the PDF does not reload.
    expect(screen.getByTitle('alpha.pdf').getAttribute('src')).toContain('media_ticket=old')
  })
})

describe('Upload Document', () => {
  const pick = (name = 'guide.pdf') =>
    fireEvent.change(screen.getByTestId('upload-input'), {
      target: { files: [new File(['x'], name, { type: 'application/pdf' })] },
    })

  it('shows progress, then the success banner, and refetches the list', async () => {
    stubFetch(() => [])
    const { invalidate } = renderDocuments()
    await screen.findByText('No documents uploaded yet')
    pick()
    const xhr = FakeXhr.last!
    expect(xhr.url).toContain('/api/upload')
    expect((xhr.body as FormData).get('file')).toBeInstanceOf(File)
    expect(screen.getByText('Uploading document...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Click to select a document/ })).toBeDisabled()
    act(() => xhr.progress(30, 100))
    const bar = screen.getByRole('progressbar', { name: 'Uploading guide.pdf' })
    expect(bar).toHaveAttribute('aria-valuenow', '30')
    expect(screen.getByText('Uploading document... 30%')).toBeInTheDocument()
    act(() => xhr.respond(200, { file_name: 'guide.pdf' }))
    expect(await screen.findByText('Uploaded successfully!')).toBeInTheDocument()
    expect(invalidate).toHaveBeenCalledWith({ queryKey: trainerKeys.files })
  })

  it('cancels the upload and returns to idle with no banner', async () => {
    stubFetch(() => [])
    renderDocuments()
    await screen.findByText('No documents uploaded yet')
    pick()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByText('Uploading document...')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Click to select a document/ })).toBeEnabled()
  })

  it('shows the server detail when the upload fails', async () => {
    stubFetch(() => [])
    renderDocuments()
    await screen.findByText('No documents uploaded yet')
    pick('big.pdf')
    act(() => FakeXhr.last!.respond(413, { detail: 'File is too large' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('File is too large')
  })

  it('keeps the upload across the breakpoint and while the builder is open', async () => {
    const browser = stubBrowser()
    stubFetch(() => [])
    const { invalidate } = renderDocuments()
    await screen.findByText('No documents uploaded yet')
    pick()
    const xhr = FakeXhr.last!
    const abort = vi.spyOn(xhr, 'abort')
    act(() => xhr.progress(30, 100))
    act(() => browser.setMobile(true))
    expect(await screen.findByText('Uploading document... 30%')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Open Document Builder' }))
    expect(await screen.findByRole('heading', { name: 'Document Builder' })).toBeInTheDocument()
    expect(abort).not.toHaveBeenCalled()
    act(() => xhr.respond(200, { file_name: 'guide.pdf' }))
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: trainerKeys.files }))
  })

  it('shows "Upload error" when the server cannot be reached', async () => {
    stubFetch(() => [])
    renderDocuments()
    await screen.findByText('No documents uploaded yet')
    pick()
    act(() => FakeXhr.last!.onerror?.())
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Upload error: Unable to reach the server.',
    )
  })
})

describe('Create Course', () => {
  it('opens Blueprint, generates the course, and selects it', async () => {
    let resolve: (value: unknown) => void = () => {}
    const fetchMock = stubFetch((url) =>
      url.pathname.endsWith('/api/courses/generate')
        ? new Promise((done) => (resolve = done))
        : [fileJson('alpha.pdf')],
    )
    const { search, invalidate, client } = renderDocuments(
      '/?tab=documents&file=trainer_0001__alpha.pdf&course=old',
    )
    await userEvent.click(await screen.findByRole('button', { name: 'Create Course' }))
    await waitFor(() => expect(search()).toMatchObject({ tab: 'blueprint' }))
    expect(search().course).toBeUndefined()
    expect(screen.getByText('Creating your course outline')).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([input]) => String(input).includes('/generate'))
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ file_name: 'trainer_0001__alpha.pdf' })
    resolve({ course_id: 'c42', course_name: 'Alpha', modules: [] })
    await waitFor(() => expect(search().course).toBe('c42'))
    expect(client.getQueryData(trainerKeys.course('c42'))).toMatchObject({ courseName: 'Alpha' })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: trainerKeys.courses })
    expect(screen.queryByText('Creating your course outline')).not.toBeInTheDocument()
  })

  it('drops a list request that started before the course existed', async () => {
    let resolveGenerate: (value: unknown) => void = () => {}
    const noop = () => {}
    let resolveList: (value: unknown) => void = noop
    stubFetch((url) => {
      if (url.pathname.endsWith('/api/courses/generate')) {
        return new Promise((done) => (resolveGenerate = done))
      }
      if (url.pathname.endsWith('/api/courses')) return new Promise((done) => (resolveList = done))
      return [fileJson('alpha.pdf')]
    })
    const { client, search } = renderDocuments('/?tab=documents&file=trainer_0001__alpha.pdf')
    await userEvent.click(await screen.findByRole('button', { name: 'Create Course' }))
    // Blueprint observes the list and starts its first request before the course exists.
    renderHook(useCourseList, {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    })
    await waitFor(() => expect(resolveList).not.toBe(noop))
    const resolveOldList = resolveList
    resolveGenerate({ course_id: 'c42', course_name: 'Alpha', modules: [] })
    // The reload starts after the course exists, so it includes it.
    await waitFor(() => expect(resolveList).not.toBe(resolveOldList))
    resolveOldList([])
    resolveList([{ course_id: 'c42', course_name: 'Alpha' }])
    await waitFor(() => expect(search().course).toBe('c42'))
    expect(client.getQueryData(trainerKeys.courses)).toEqual([
      expect.objectContaining({ courseId: 'c42', moduleCount: 0 }),
    ])
    expect(client.getQueryData(trainerKeys.course('c42'))).toMatchObject({ courseName: 'Alpha' })
  })

  it('shows the fallback error with the status code', async () => {
    stubFetch((url) =>
      url.pathname.endsWith('/api/courses/generate')
        ? new Response('oops', { status: 502 })
        : [fileJson('alpha.pdf')],
    )
    renderDocuments('/?tab=documents&file=trainer_0001__alpha.pdf')
    await userEvent.click(await screen.findByRole('button', { name: 'Create Course' }))
    expect(
      await screen.findByText('Course outline extraction failed. Server returned 502.'),
    ).toBeInTheDocument()
  })
})

describe('layout', () => {
  it('opens the builder from the Create Document card', async () => {
    stubFetch(() => [])
    const { search } = renderDocuments()
    await userEvent.click(await screen.findByRole('button', { name: 'Open Document Builder' }))
    await waitFor(() => expect(search().builder).toBe(true))
    expect(screen.getByRole('heading', { name: 'Document Builder' })).toBeInTheDocument()
  })

  it('hides the mobile viewer until a file is selected', async () => {
    stubBrowser({ mobile: true })
    stubFetch(() => [fileJson('alpha.pdf')])
    renderDocuments()
    await screen.findByText('alpha.pdf')
    expect(screen.queryByText('No Document Selected')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /alpha\.pdf/ }))
    expect(await screen.findByRole('button', { name: 'Create Course' })).toBeInTheDocument()
  })
})
