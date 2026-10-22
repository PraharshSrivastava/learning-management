import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react'
import { SourceAnswer, WorkflowTools } from './WorkflowTools'
import { initialContent, type Draft, type DraftSource } from './workflow'
import { setAuthToken } from '@lms/shared/api/client'
import { stubBrowser, stubFetch } from './test/renderDocuments'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  setAuthToken(null)
})
it('loads the owned original source with authenticated fetch instead of exposing a backend path', async () => {
  stubBrowser()
  setAuthToken('test-token')
  const fetch = stubFetch((url) =>
    url.pathname.endsWith('/original')
      ? new Response('source bytes', { headers: { 'Content-Type': 'application/pdf' } })
      : [],
  )
  const draft: Draft = {
    id: 'd1',
    revision: 2,
    content: initialContent('ai'),
    approvedOutline: null,
    createdAt: 'now',
    updatedAt: 'now',
  }
  render(
    <QueryClientProvider client={new QueryClient()}>
      <WorkflowTools
        draft={draft}
        sources={[{ ...source, documentId: 'doc1' }]}
        disabled={false}
        onAttach={vi.fn()}
        onRestore={vi.fn()}
      />
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByText('Prepare original source'))
  const link = await screen.findByRole('link', { name: 'Open or download Policy' })
  expect(link.getAttribute('href')).toMatch(/^blob:/)
  const call = fetch.mock.calls.find(([url]) => String(url).includes('/sources/s1/original'))
  expect(call?.[1]).toMatchObject({
    credentials: 'same-origin',
    headers: { Authorization: 'Bearer test-token' },
  })
  fireEvent.click(screen.getByText('Close source preview'))
  expect(URL.revokeObjectURL).toHaveBeenCalled()
})
const source: DraftSource = {
  id: 's1',
  name: 'Policy',
  issues: [],
  acknowledged: true,
  spans: [{ id: 'p1', text: 'Contact your supervisor.', location: 'Page 2' }],
}
it('shows only cited source excerpts and separates unsupported source answers', () => {
  render(
    <SourceAnswer
      operation={{
        id: 'o1',
        status: 'completed',
        request: { task: 'answer' },
        result: {
          answer: 'Contact your supervisor.',
          insufficientEvidence: false,
          sourceReferences: [{ sourceId: 's1', spanId: 'p1' }],
        },
      }}
      sources={[source]}
    />,
  )
  expect(screen.getByText('Page 2')).toBeInTheDocument()
  expect(
    screen.getByText('Contact your supervisor.', { selector: 'blockquote' }),
  ).toBeInTheDocument()
})
it('loads version history without restoring until explicit confirmation', async () => {
  stubBrowser()
  stubFetch((url) =>
    url.pathname.endsWith('/revisions')
      ? [{ revision: 1, reason: 'manual save', created_at: '2026-10-21' }]
      : [],
  )
  const restore = vi.fn()
  vi.spyOn(window, 'confirm').mockReturnValue(false)
  const draft: Draft = {
    id: 'd1',
    revision: 2,
    content: initialContent('ai'),
    approvedOutline: null,
    createdAt: 'now',
    updatedAt: 'now',
  }
  render(
    <QueryClientProvider client={new QueryClient()}>
      <WorkflowTools
        draft={draft}
        sources={[source]}
        disabled={false}
        onAttach={vi.fn()}
        onRestore={restore}
      />
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByText('Version history'))
  fireEvent.click(await screen.findByText('Restore revision 1'))
  expect(restore).not.toHaveBeenCalled()
  vi.mocked(window.confirm).mockReturnValue(true)
  fireEvent.click(screen.getByText('Restore revision 1'))
  await waitFor(() => expect(restore).toHaveBeenCalledWith(1))
  vi.restoreAllMocks()
})
