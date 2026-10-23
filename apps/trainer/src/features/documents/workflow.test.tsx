/// <reference types="node" />
import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { initialContent, selectionTarget } from './workflow'
import { fileJson, renderDocuments, stubBrowser, stubFetch } from './test/renderDocuments'

beforeEach(() => stubBrowser())
afterEach(() => {
  vi.useRealTimers()
  cleanup()
  vi.unstubAllGlobals()
})

it('protects unsaved edits when leaving through global tab navigation', async () => {
  const content = initialContent('blank')
  content.metadata.courseName = 'Training'
  const record = {
    id: 'draft1',
    revision: 1,
    content,
    approvedOutline: null,
    createdAt: 'now',
    updatedAt: 'now',
  }
  stubFetch((url) =>
    url.pathname.endsWith('/capabilities')
      ? { workflowEnabled: true }
      : url.pathname.endsWith('/draft1')
        ? record
        : [],
  )
  const view = renderDocuments('/?tab=documents&builder=true&draft=draft1')
  const paragraph = await screen.findByRole('textbox', { name: 'paragraph text' })
  fireEvent.change(paragraph, { target: { value: 'Unsaved training notes' } })
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  await act(async () => {
    void view.router.navigate({ to: '/', search: { tab: 'courses' } })
  })
  await waitFor(() => expect(confirm).toHaveBeenCalledWith('Leave with unsaved changes?'))
  expect(view.search().tab).toBe('documents')
  expect(screen.getByRole('textbox', { name: 'paragraph text' })).toHaveValue(
    'Unsaved training notes',
  )
  confirm.mockReturnValue(true)
  await act(async () => {
    void view.router.navigate({ to: '/', search: { tab: 'courses' } })
  })
  await waitFor(() => expect(view.search().tab).toBe('courses'))
  confirm.mockRestore()
})

it.each(['module', 'document', 'selected'] as const)(
  'sends %s scope and keeps a stale suggestion reviewable',
  async (scope) => {
    const content = initialContent('ai')
    content.metadata.courseName = 'Training'
    content.metadata.targetAudience = 'Employees'
    content.metadata.courseObjective = 'Learn'
    content.modules = [
      {
        id: 'm1',
        title: 'Service',
        objective: 'Listen',
        included: true,
        sections: [],
        blocks: [
          {
            id: 'b1',
            type: 'paragraph',
            text: 'Original paragraph',
            marks: [],
            level: 2,
            sourceReferences: [],
          },
        ],
        sourceReferences: [],
        status: 'ready',
      },
    ]
    const record = {
      id: 'd1',
      revision: 2,
      content,
      approvedOutline: 'approved',
      createdAt: 'now',
      updatedAt: 'now',
    }
    const proposal = {
      id: 'op1',
      status: 'proposed',
      request: { task: scope === 'selected' ? 'edit' : 'revise' },
      result:
        scope === 'selected'
          ? { originalText: 'Original', replacementText: 'Improved' }
          : {
              changes: [
                {
                  moduleId: 'm1',
                  blockId: 'b1',
                  originalText: 'Original paragraph',
                  replacementText: 'Improved paragraph',
                },
              ],
            },
    }
    const fetch = stubFetch((url, init) => {
      if (url.pathname.endsWith('/capabilities')) return { workflowEnabled: true }
      if (url.pathname.endsWith('/d1')) return record
      if (
        url.pathname.endsWith('/sources') ||
        (url.pathname.endsWith('/operations') && init?.method !== 'POST') ||
        url.pathname === '/api/files'
      )
        return []
      if (url.pathname.endsWith('/operations')) return proposal
      if (url.pathname.endsWith('/accept'))
        return new Response(
          JSON.stringify({ detail: 'Suggestion is stale. Reload before accepting.' }),
          { status: 409 },
        )
      return []
    })
    renderDocuments('/?tab=documents&builder=true&draft=d1')
    const text = await screen.findByRole('textbox', { name: 'paragraph text' })
    fireEvent.change(screen.getByRole('combobox', { name: 'Apply to' }), {
      target: { value: scope },
    })
    if (scope === 'selected') {
      ;(text as HTMLTextAreaElement).setSelectionRange(0, 8)
      fireEvent.select(text)
    }
    fireEvent.change(screen.getByRole('textbox', { name: 'AI instruction' }), {
      target: { value: 'Simplify' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Suggest changes' }))
    expect(await screen.findByText('Suggested')).toBeInTheDocument()
    expect(screen.getByText('Original', { selector: 'h3' })).toBeInTheDocument()
    expect(screen.getByText(/Review notice:/)).toBeInTheDocument()
    const call = fetch.mock.calls.find(
      ([url, init]) => String(url).endsWith('/operations') && init?.method === 'POST',
    )
    const payload = JSON.parse(String(call?.[1]?.body))
    expect(payload.scope).toBe(scope)
    expect(payload.moduleId).toBe('m1')
    if (scope === 'selected')
      expect(payload.target).toMatchObject({ moduleId: 'm1', blockId: 'b1', start: 0, end: 8 })
    fireEvent.click(screen.getByRole('button', { name: 'Accept changes' }))
    expect(await screen.findByText(/Suggestion is stale/)).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'paragraph text' })).toHaveValue(
      'Original paragraph',
    )
    expect(screen.getByRole('button', { name: 'Dismiss suggestion' })).toBeInTheDocument()
  },
)

it('automatically dismisses the removal notice after ten seconds', async () => {
  const value = {
    draft_id: 'd1',
    revision: 1,
    title: 'Draft',
    module_count: 0,
    updated_at: '2026-10-16T10:00:00Z',
  }
  let removed = false
  stubFetch((url) => {
    if (url.pathname.endsWith('/capabilities')) return { workflowEnabled: true }
    if (url.pathname.endsWith('/remove')) {
      removed = true
      return null
    }
    if (url.pathname.endsWith('/drafts')) return removed ? [] : [value]
    return []
  })
  renderDocuments()
  const remove = await screen.findByRole('button', { name: 'Remove' })
  vi.useFakeTimers()
  await act(async () => {
    fireEvent.click(remove)
    await vi.advanceTimersByTimeAsync(1)
  })
  expect(screen.getByText('Draft removed')).toBeInTheDocument()
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000)
  })
  expect(screen.queryByText('Draft removed')).not.toBeInTheDocument()
})
it('hashes selected Unicode text with codepoint offsets without secure-context crypto', async () => {
  const { createHash } = await import('node:crypto')
  const target = await selectionTarget('module', 'block', 'A😀हेलो', 1, 3)
  expect(target.start).toBe(1)
  expect(target.end).toBe(2)
  expect(target.textHash).toBe(createHash('sha256').update(JSON.stringify('😀')).digest('hex'))
})
it('shows approved ordered entry choices and routes ready files directly to Blueprint', async () => {
  const fetch = stubFetch((url) =>
    url.pathname.endsWith('/capabilities')
      ? { workflowEnabled: true }
      : url.pathname.endsWith('/drafts')
        ? []
        : url.pathname === '/api/files'
          ? [fileJson('Ready.pdf')]
          : new Promise(() => {}),
  )
  renderDocuments()
  expect(await screen.findByText('Recent drafts')).toBeInTheDocument()
  const choices = screen
    .getAllByRole('button')
    .filter((b) => /(Use existing content|Generate with AI|Start blank)/.test(b.textContent || ''))
  expect(choices.map((b) => b.textContent)).toEqual([
    expect.stringContaining('Use existing content'),
    expect.stringContaining('Generate with AI'),
  ])
  expect(screen.queryByRole('button', { name: /Start blank/ })).not.toBeInTheDocument()
  fireEvent.click(await screen.findByRole('button', { name: 'Create course' }))
  await waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => String(url).includes('/api/courses/generate'))).toBe(
      true,
    ),
  )
  expect(fetch.mock.calls.some(([url]) => String(url).includes('/operations'))).toBe(false)
})
it('opens drafts imported from an uploaded document in Blueprint, not the editor', async () => {
  const draft = (id: string, overrides: Record<string, unknown> = {}) => ({
    draft_id: id,
    revision: 1,
    title: id,
    module_count: 2,
    updated_at: '2026-10-16T10:00:00Z',
    ...overrides,
  })
  const fetch = stubFetch((url) =>
    url.pathname.endsWith('/capabilities')
      ? { workflowEnabled: true }
      : url.pathname.endsWith('/drafts')
        ? [
            draft('Imported', { entry_mode: 'existing', source_document_id: 'doc-Ready.pdf' }),
            draft('Uncoursed', { entry_mode: 'existing', source_document_id: 'doc-Other.pdf' }),
          ]
        : url.pathname === '/api/files'
          ? [fileJson('Ready.pdf'), fileJson('Other.pdf')]
          : url.pathname === '/api/courses'
            ? [{ course_id: 'c1', trainer_id: 't', document_id: 'doc-Ready.pdf', status: 'draft' }]
            : new Promise(() => {}),
  )
  const view = renderDocuments()
  await screen.findByText('Imported')
  await waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/api/courses'))).toBe(true),
  )
  fireEvent.click(screen.getAllByRole('button', { name: 'Open' })[0]!)
  await waitFor(() => expect(view.search()).toMatchObject({ tab: 'blueprint', course: 'c1' }))
  expect(view.search().draft).toBeUndefined()
  void view.router.navigate({ to: '/', search: { tab: 'documents' } })
  await screen.findByText('Uncoursed')
  fireEvent.click(screen.getAllByRole('button', { name: 'Open' })[1]!)
  await waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => String(url).includes('/api/courses/generate'))).toBe(
      true,
    ),
  )
  expect(view.search().draft).toBeUndefined()
})
it('starts AI outline once after creating a persistent draft and shows proposal without changing it', async () => {
  let current = {
    id: 'draft1',
    revision: 1,
    content: initialContent('ai'),
    approvedOutline: null,
    createdAt: 'now',
    updatedAt: 'now',
  }
  const proposed = {
    id: 'operation1',
    status: 'proposed',
    request: { task: 'outline' },
    result: {
      modules: [
        { title: 'Listening', objective: 'Listen carefully', sections: ['Active listening'] },
        { title: 'Following up', objective: 'Follow up reliably', sections: ['Next steps'] },
      ],
    },
  }
  const fetch = stubFetch((url, init) => {
    if (url.pathname.endsWith('/capabilities')) return { workflowEnabled: true }
    if (url.pathname === '/api/files') return []
    if (url.pathname.endsWith('/drafts') && init?.method === 'POST') {
      current = { ...current, content: JSON.parse(String(init.body)) }
      return current
    }
    if (url.pathname.endsWith('/drafts')) return []
    if (url.pathname.endsWith('/operations') && init?.method === 'POST') return proposed
    if (url.pathname.endsWith('/operations')) return [proposed]
    if (url.pathname.endsWith('/sources')) return []
    if (url.pathname.endsWith('/draft1')) return current
    return null
  })
  renderDocuments()
  fireEvent.click(await screen.findByRole('button', { name: /Generate with AI/ }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Topic or title' }), {
    target: { value: 'Customer service' },
  })
  fireEvent.change(screen.getByRole('textbox', { name: 'Who is this for?' }), {
    target: { value: 'New employees' },
  })
  fireEvent.change(screen.getByRole('textbox', { name: 'What should employees be able to do?' }), {
    target: { value: 'Listen and follow up' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Generate outline' }))
  await waitFor(() =>
    expect(screen.getByRole('region', { name: 'Review AI suggestion' })).toBeInTheDocument(),
  )
  expect(await screen.findByText('1. Listening')).toBeInTheDocument()
  expect(screen.getByText('Your document has not been changed.')).toBeInTheDocument()
  expect(
    fetch.mock.calls.filter(
      ([url, init]) => String(url).endsWith('/operations') && init?.method === 'POST',
    ),
  ).toHaveLength(1)
  expect(current.content.modules).toHaveLength(0)
})
it('removes a draft with its revision and supports undo', async () => {
  const value = {
    draft_id: 'draft1',
    revision: 3,
    title: 'Training draft',
    module_count: 4,
    updated_at: '2026-10-16T10:00:00Z',
  }
  let removed = false
  const fetch = stubFetch((url) => {
    if (url.pathname.endsWith('/capabilities')) return { workflowEnabled: true }
    if (url.pathname.endsWith('/remove')) {
      removed = true
      return null
    }
    if (url.pathname.endsWith('/undo-remove')) {
      removed = false
      return null
    }
    if (url.pathname.endsWith('/drafts')) return removed ? [] : [value]
    return []
  })
  renderDocuments()
  fireEvent.click(await screen.findByRole('button', { name: 'Remove' }))
  expect(await screen.findByText('Draft removed')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
  expect(await screen.findByText('Training draft')).toBeInTheDocument()
  expect(
    fetch.mock.calls.some(
      ([url, init]) =>
        String(url).endsWith('/remove') && JSON.parse(String(init?.body)).expectedRevision === 3,
    ),
  ).toBe(true)
})
