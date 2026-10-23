import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { isModelUnavailable } from './FocusedWorkspace'
import { initialContent, paragraph } from './workflow'
import { renderDocuments, stubBrowser, stubFetch } from './test/renderDocuments'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('only classifies explicit model connectivity failures as unavailable', () => {
  expect(isModelUnavailable('Document model is unavailable')).toBe(true)
  expect(isModelUnavailable('Could not reach the AI service')).toBe(true)
  for (const error of [
    'Permission denied',
    'Invalid document',
    'PDF conversion failed',
    'Revision conflict',
    'HTTP 503',
  ]) {
    expect(isModelUnavailable(error)).toBe(false)
  }
})

it('formats the selected text from the simplified module toolbar without changing other text', async () => {
  stubBrowser()
  const content = initialContent('blank')
  content.modules[0]!.blocks = [paragraph('Hello world')]
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
  renderDocuments('/?tab=documents&builder=true&draft=draft1')
  const text = (await screen.findByRole('textbox', {
    name: 'paragraph text',
  })) as HTMLTextAreaElement
  const toolbar = within(screen.getByRole('toolbar', { name: 'Module formatting and images' }))
  expect(toolbar.getByRole('button', { name: 'Bold' })).toBeDisabled()
  text.setSelectionRange(0, 5)
  fireEvent.select(text)
  fireEvent.click(toolbar.getByRole('button', { name: 'Bold' }))
  expect(screen.getByTestId('formatted-preview').querySelector('strong')).toHaveTextContent('Hello')
  expect(text).toHaveValue('Hello world')
  expect(toolbar.getByRole('button', { name: 'Heading' })).toBeInTheDocument()
  expect(toolbar.getByLabelText('Image')).toHaveAttribute('type', 'file')
})

it('retains edits and request scope when retrying an unavailable model operation', async () => {
  stubBrowser()
  const content = initialContent('blank')
  content.modules[0]!.blocks = [paragraph('Existing content')]
  const record = {
    id: 'draft1',
    revision: 1,
    content,
    approvedOutline: null,
    createdAt: 'now',
    updatedAt: 'now',
  }
  const failed = {
    id: 'op1',
    status: 'failed',
    error: 'Model unavailable',
    request: { task: 'rewrite', scope: 'module', moduleId: content.modules[0]!.id },
  }
  const fetch = stubFetch((url, init) =>
    url.pathname.endsWith('/capabilities')
      ? { workflowEnabled: true }
      : url.pathname.endsWith('/draft1')
        ? record
        : url.pathname.endsWith('/operations')
          ? init?.method === 'POST'
            ? { ...failed, id: 'op2', status: 'queued' }
            : [failed]
          : [],
  )
  renderDocuments('/?tab=documents&builder=true&draft=draft1')
  expect(await screen.findByText('Document model is unavailable')).toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveClass('text-[#865515]')
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText(/AI request queued/)).toBeInTheDocument()
  const call = fetch.mock.calls.find(
    ([url, init]) => String(url).endsWith('/operations') && init?.method === 'POST',
  )
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
    expectedRevision: 1,
    task: 'rewrite',
    scope: 'module',
    moduleId: content.modules[0]!.id,
  })
  expect(screen.getByRole('textbox', { name: 'paragraph text' })).toHaveValue('Existing content')
})
