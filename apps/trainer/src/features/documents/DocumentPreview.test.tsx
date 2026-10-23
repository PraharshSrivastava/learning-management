import { configureApi, setMediaTicket } from '@lms/shared/api/client'
import { parsePdfFile } from '@lms/shared/models'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DocumentPreview } from './DocumentPreview'

const mocked = vi.hoisted(() => ({ getDocument: vi.fn() }))
vi.mock('pdfjs-dist', () => ({ getDocument: mocked.getDocument, GlobalWorkerOptions: {} }))
const file = (name = 'guide.pdf') =>
  parsePdfFile({ document_id: name, file_name: name, size: 10, created_at: '2026-01-01' })

beforeEach(() => {
  configureApi({ app: 'trainer', publicMount: '/lms/trainer' })
  setMediaTicket('first-ticket')
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(new Uint8Array([1, 2, 3]))),
  )
  mocked.getDocument.mockImplementation(() => ({
    promise: Promise.resolve({
      numPages: 8,
      getPage: vi.fn(async () => ({ getViewport: () => ({ width: 600, height: 800 }) })),
    }),
    destroy: vi.fn(),
  }))
})
afterEach(() => vi.unstubAllGlobals())

it('uses actual page count and allows last-page navigation, zoom and callbacks', async () => {
  const close = vi.fn(),
    create = vi.fn()
  render(<DocumentPreview file={file()} onClose={close} onCreateCourse={create} />)
  await screen.findByText('of 8')
  expect(screen.getAllByRole('group', { name: /^Page / })).toHaveLength(8)
  const input = screen.getByRole('spinbutton', { name: 'PDF page number' })
  fireEvent.change(input, { target: { value: '8' } })
  fireEvent.submit(input.closest('form')!)
  expect(input).toHaveValue(8)
  expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Previous page' }))
  expect(input).toHaveValue(7)
  await userEvent.selectOptions(screen.getByLabelText('PDF zoom'), '150')
  expect(screen.getByLabelText('PDF zoom')).toHaveValue('150')
  await userEvent.click(screen.getByRole('button', { name: 'Create course' }))
  await userEvent.click(screen.getByRole('button', { name: 'Close preview' }))
  expect(create).toHaveBeenCalledOnce()
  expect(close).toHaveBeenCalledOnce()
})

it('does not reload bytes on routine ticket renewal and retries using the latest ticket', async () => {
  vi.mocked(fetch).mockResolvedValueOnce(new Response('', { status: 403 }))
  render(<DocumentPreview file={file('ready.docx')} onClose={vi.fn()} onCreateCourse={vi.fn()} />)
  await screen.findByRole('alert')
  act(() => setMediaTicket('renewed-ticket'))
  await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
  await screen.findByText('of 8')
  expect(vi.mocked(fetch).mock.calls[1]?.[0]).toContain('renewed-ticket')
  act(() => setMediaTicket('another-ticket'))
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(vi.mocked(fetch).mock.calls[1]?.[0]).toContain('ready.docx/preview')
})

it('aborts obsolete requests when another file is selected', async () => {
  const requests: AbortSignal[] = []
  vi.mocked(fetch).mockImplementation((_url, options) => {
    requests.push(options!.signal as AbortSignal)
    return new Promise(() => {})
  })
  const { rerender, unmount } = render(
    <DocumentPreview file={file()} onClose={vi.fn()} onCreateCourse={vi.fn()} />,
  )
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
  rerender(<DocumentPreview file={file('second.pdf')} onClose={vi.fn()} onCreateCourse={vi.fn()} />)
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
  expect(requests[0]?.aborted).toBe(true)
  unmount()
  expect(requests[1]?.aborted).toBe(true)
})
it('reads any PDF source and shows its own failure message', async () => {
  const { PdfReader } = await import('./DocumentPreview')
  const load = vi.fn(async () => {
    throw new Error('PDF preview failed. Check your document and try again.')
  })
  render(<PdfReader id="draft" title="Course.pdf" load={load} actions={null} />)
  expect(screen.getByRole('region', { name: 'Preview of Course.pdf' })).toBeInTheDocument()
  expect(
    await screen.findByText(/PDF preview failed\. Check your document and try again\./),
  ).toBeInTheDocument()
  expect(load).toHaveBeenCalledTimes(1)
  expect(screen.queryByRole('button', { name: 'Open document' })).not.toBeInTheDocument()
})
