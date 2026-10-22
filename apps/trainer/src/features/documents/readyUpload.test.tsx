import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { FakeXhr, renderDocuments, stubBrowser, stubFetch } from './test/renderDocuments'

beforeEach(() => stubBrowser())
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function readyWorkspace() {
  const fetch = stubFetch((url) => {
    if (url.pathname.endsWith('/capabilities')) return { workflowEnabled: true }
    if (url.pathname === '/api/courses/generate') return new Promise(() => {})
    return []
  })
  return { ...renderDocuments(), fetch }
}

async function uploadReadyFile() {
  fireEvent.click(await screen.findByRole('button', { name: /Use existing content/ }))
  fireEvent.change(screen.getByTestId('upload-input'), {
    target: { files: [new File(['document'], 'Ready.pdf', { type: 'application/pdf' })] },
  })
}

it('opens Blueprint after a ready upload using the server filename, without a Builder draft', async () => {
  const { fetch, search } = readyWorkspace()
  await uploadReadyFile()
  await act(async () => {
    FakeXhr.last!.respond(200, { file_name: 'trainer__unique_Ready.pdf', document_id: 'owned-doc' })
  })
  await waitFor(() => expect(search().tab).toBe('blueprint'))
  const calls = fetch.mock.calls.filter(([url]) => String(url).endsWith('/api/courses/generate'))
  expect(calls).toHaveLength(1)
  expect(JSON.parse(String(calls[0]![1]?.body))).toEqual({ file_name: 'trainer__unique_Ready.pdf' })
  expect(
    fetch.mock.calls.some(
      ([url, init]) => String(url).includes('/drafts') && init?.method === 'POST',
    ),
  ).toBe(false)
})

it.each(['failed', 'cancelled', 'malformed'] as const)(
  'does not create a course after a %s upload',
  async (outcome) => {
    const { fetch, search } = readyWorkspace()
    await uploadReadyFile()
    await act(async () => {
      if (outcome === 'cancelled') fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
      else
        FakeXhr.last!.respond(
          outcome === 'failed' ? 413 : 200,
          outcome === 'failed' ? { detail: 'File too large' } : {},
        )
    })
    expect(search().tab).toBe('documents')
    expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/api/courses/generate'))).toBe(
      false,
    )
    if (outcome !== 'cancelled') expect(screen.getByRole('alert')).toBeInTheDocument()
  },
)
