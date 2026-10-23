import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { initialContent, type Draft } from './workflow'
import { renderDocuments, stubBrowser, stubFetch } from './test/renderDocuments'

beforeEach(() => stubBrowser())
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
it('blocks editing and draft creation when an existing draft cannot be loaded, then retries the same ID', async () => {
  let failing = true
  const fetch = stubFetch((url) => {
    if (url.pathname.endsWith('/capabilities')) return { workflowEnabled: true }
    if (url.pathname.endsWith('/d1'))
      return failing
        ? new Response(JSON.stringify({ detail: 'Draft unavailable' }), { status: 503 })
        : draft()
    return []
  })
  renderDocuments('/?tab=documents&builder=true&draft=d1')
  expect(await screen.findByText('Could not open this draft')).toBeInTheDocument()
  expect(screen.queryByRole('textbox')).toBeNull()
  expect(
    fetch.mock.calls.some(
      ([url, init]) => String(url).endsWith('/drafts') && init?.method === 'POST',
    ),
  ).toBe(false)
  failing = false
  fireEvent.click(screen.getByText('Retry loading draft'))
  expect(await screen.findByRole('textbox', { name: 'paragraph text' })).toBeInTheDocument()
})
const draft = (): Draft => {
  const content = initialContent('blank')
  content.metadata.courseName = 'Training'
  return {
    id: 'd1',
    revision: 2,
    content,
    approvedOutline: null,
    createdAt: 'now',
    updatedAt: 'now',
  }
}
it('keeps edits after the first autosave updates the draft URL without fetching a stale server echo', async () => {
  const fetch = stubFetch((url, init) => {
    if (url.pathname.endsWith('/capabilities')) return { workflowEnabled: true }
    if (url.pathname.endsWith('/drafts') && init?.method === 'POST')
      return { ...draft(), content: JSON.parse(String(init.body)) }
    if (url.pathname.endsWith('/d1'))
      return {
        ...draft(),
        content: {
          ...initialContent('blank'),
          metadata: { ...initialContent('blank').metadata, courseName: 'STALE SERVER ECHO' },
        },
      }
    return []
  })
  const view = renderDocuments('/?tab=documents')
  // New authoring starts through AI; existing blank drafts still reopen by ID.
  fireEvent.click(await screen.findByRole('button', { name: /Generate with AI/ }))
  const topic = screen.getByRole('textbox', { name: 'Topic or title' })
  fireEvent.change(topic, { target: { value: 'Autosaved title' } })
  await waitFor(() => expect(view.search().draft).toBe('d1'), { timeout: 2500 })
  fireEvent.change(topic, { target: { value: 'New edits after URL update' } })
  expect(
    fetch.mock.calls.filter(
      ([url, init]) => String(url).endsWith('/d1') && (!init?.method || init.method === 'GET'),
    ),
  ).toHaveLength(0)
  expect(topic).toHaveValue('New edits after URL update')
})
it('saves current edits before restoring history and keeps the restored document unapproved', async () => {
  let current = draft()
  const requests: { path: string; body: Record<string, unknown> }[] = []
  stubFetch((url, init) => {
    if (url.pathname.endsWith('/capabilities')) return { workflowEnabled: true }
    if (url.pathname.endsWith('/revisions'))
      return [{ revision: 1, reason: 'original', created_at: 'yesterday' }]
    if (url.pathname.endsWith('/restore')) {
      const body = JSON.parse(String(init?.body))
      requests.push({ path: 'restore', body })
      current = {
        ...current,
        revision: 4,
        content: {
          ...current.content,
          modules: current.content.modules.map((m) => ({ ...m, blocks: [] })),
        },
        approvedOutline: null,
      }
      return current
    }
    if (url.pathname.endsWith('/d1')) {
      if (init?.method === 'PATCH') {
        const body = JSON.parse(String(init.body))
        requests.push({ path: 'save', body })
        current = { ...current, content: body.content, revision: 3 }
      }
      return current
    }
    return []
  })
  renderDocuments('/?tab=documents&builder=true&draft=d1')
  const text = await screen.findByRole('textbox', { name: 'paragraph text' })
  fireEvent.change(text, { target: { value: 'Important unsaved edits' } })
  fireEvent.click(screen.getByText('Version history'))
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  fireEvent.click(await screen.findByText('Restore revision 1'))
  await waitFor(() => expect(requests.map((request) => request.path)).toEqual(['save', 'restore']))
  expect(requests[0]?.body.expectedRevision).toBe(2)
  expect(requests[1]?.body).toEqual({ expectedRevision: 3, restoreRevision: 1 })
  await waitFor(() => expect(screen.queryByRole('textbox', { name: 'paragraph text' })).toBeNull())
  expect(screen.getByRole('button', { name: 'Create course' })).toBeDisabled()
})
it('attaches reference notes without replacing AI setup', async () => {
  let current = draft()
  current.content = { ...initialContent('ai'), metadata: current.content.metadata }
  let attached = false
  const source = {
    id: 's1',
    issues: [],
    acknowledged: true,
    spans: [{ id: 'p1', text: 'Notify the supervisor.', location: 'Reference notes' }],
  }
  let task = ''
  const fetch = stubFetch((url, init) => {
    if (url.pathname.endsWith('/capabilities')) return { workflowEnabled: true }
    if (url.pathname.endsWith('/d1')) return current
    if (url.pathname.endsWith('/sources')) return attached ? [source] : []
    if (url.pathname.endsWith('/operations') && init?.method === 'POST') {
      const body = JSON.parse(String(init.body))
      task = body.task
      if (task === 'import')
        expect(body.sourceImport).toEqual({
          expectedRevision: 2,
          referenceOnly: true,
          text: 'Notify the supervisor.',
        })
      return { id: 'o1', status: 'queued', request: { task, sourceImport: body.sourceImport } }
    }
    if (url.pathname.endsWith('/operations/o1')) {
      attached = true
      current = { ...current, revision: 3 }
      return {
        id: 'o1',
        status: 'completed',
        request: { task, sourceImport: { referenceOnly: true } },
      }
    }
    return []
  })
  renderDocuments('/?tab=documents&builder=true&draft=d1')
  await screen.findByRole('textbox', { name: 'Topic or title' })
  fireEvent.change(screen.getByRole('textbox', { name: 'Reference notes' }), {
    target: { value: 'Notify the supervisor.' },
  })
  fireEvent.click(screen.getByText('Attach reference notes'))
  await waitFor(() => expect(screen.getByText('Reference sources (1)')).toBeInTheDocument(), {
    timeout: 2500,
  })
  expect(screen.getByRole('button', { name: 'Generate outline' })).toBeInTheDocument()
  expect(
    fetch.mock.calls.some(
      ([url, init]) => String(url).endsWith('/operations') && init?.method === 'POST',
    ),
  ).toBe(true)
})

it('asks a source question using the saved revision and displays citations without replacement actions', async () => {
  const current = draft()
  const source = {
    id: 's1',
    issues: [],
    acknowledged: true,
    spans: [{ id: 'p1', text: 'Notify the supervisor.', location: 'Page 2' }],
  }
  const fetch = stubFetch((url, init) => {
    if (url.pathname.endsWith('/capabilities')) return { workflowEnabled: true }
    if (url.pathname.endsWith('/d1')) return current
    if (url.pathname.endsWith('/sources')) return [source]
    if (url.pathname.endsWith('/operations') && init?.method === 'POST')
      return {
        id: 'answer1',
        status: 'completed',
        request: { task: 'answer' },
        result: {
          answer: 'Notify the supervisor.',
          insufficientEvidence: false,
          sourceReferences: [{ sourceId: 's1', spanId: 'p1' }],
        },
      }
    return []
  })
  renderDocuments('/?tab=documents&builder=true&draft=d1')
  await screen.findByRole('textbox', { name: 'paragraph text' })
  fireEvent.change(screen.getByRole('textbox', { name: 'AI instruction' }), {
    target: { value: 'Who should employees notify?' },
  })
  fireEvent.click(screen.getByText('Ask about source'))
  expect(await screen.findByRole('region', { name: 'Source answer' })).toHaveTextContent(
    'Notify the supervisor.',
  )
  expect(screen.getByRole('region', { name: 'Source answer' })).toHaveTextContent('Page 2')
  expect(screen.queryByRole('button', { name: 'Accept changes' })).toBeNull()
  const call = fetch.mock.calls.find(
    ([url, init]) => String(url).endsWith('/operations') && init?.method === 'POST',
  )
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
    task: 'answer',
    instruction: 'Who should employees notify?',
    expectedRevision: 2,
  })
})

it('approves ready existing content and creates its course using the returned approval revision without AI drafting', async () => {
  let current = draft()
  current.content.entryMode = 'existing'
  const block = current.content.modules[0]?.blocks[0]
  if (block && 'text' in block) block.text = 'Ready training content'
  const actions: string[] = []
  const fetch = stubFetch((url, init) => {
    if (url.pathname.endsWith('/capabilities')) return { workflowEnabled: true }
    if (url.pathname.endsWith('/d1')) return current
    if (url.pathname.endsWith('/approve-outline')) {
      actions.push('approve')
      current = { ...current, revision: 3, approvedOutline: 'approved' }
      return current
    }
    if (url.pathname.endsWith('/create-course')) {
      actions.push('handoff')
      expect(JSON.parse(String(init?.body))).toEqual({ expectedRevision: 3 })
      return { course_id: 'c1', course_name: 'Training' }
    }
    return []
  })
  const view = renderDocuments('/?tab=documents&builder=true&draft=d1')
  fireEvent.click(await screen.findByText('Review outline'))
  fireEvent.click(screen.getByText('Approve and create course'))
  await waitFor(() => expect(view.search().tab).toBe('blueprint'))
  expect(view.search().course).toBe('c1')
  expect(actions).toEqual(['approve', 'handoff'])
  expect(
    fetch.mock.calls.some(
      ([url, init]) => String(url).endsWith('/operations') && init?.method === 'POST',
    ),
  ).toBe(false)
})
