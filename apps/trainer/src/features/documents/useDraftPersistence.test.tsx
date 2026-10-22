import { act, cleanup, renderHook } from '@testing-library/react'
import { StrictMode, type ReactNode } from 'react'
import { useDraftPersistence } from './useDraftPersistence'
import { initialContent, type Draft } from './workflow'
import { stubFetch } from './test/renderDocuments'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
const wrapper = ({ children }: { children: ReactNode }) => <StrictMode>{children}</StrictMode>
it('debounces edits under StrictMode, preserves later edits and retries failed saves explicitly', async () => {
  vi.useFakeTimers()
  let revision = 1
  let failing = false
  let finish!: (value: unknown) => void
  const fetch = stubFetch(async (url, init) => {
    if (url.pathname.endsWith('/d1') && init?.method === 'PATCH') {
      const payload = JSON.parse(String(init.body))
      if (failing) return new Response(JSON.stringify({ detail: 'Save conflict' }), { status: 409 })
      return new Promise((resolve) => {
        finish = () =>
          resolve({
            id: 'd1',
            revision: ++revision,
            content: payload.content,
            approvedOutline: null,
            createdAt: 'now',
            updatedAt: 'now',
          })
      })
    }
    return []
  })
  const { result } = renderHook(() => useDraftPersistence('blank', false), { wrapper })
  const original = initialContent('blank')
  const draft: Draft = {
    id: 'd1',
    revision: 1,
    content: original,
    approvedOutline: null,
    createdAt: 'now',
    updatedAt: 'now',
  }
  act(() => result.current.load(draft))
  act(() =>
    result.current.edit({ ...original, metadata: { ...original.metadata, courseName: 'First' } }),
  )
  await act(() => vi.advanceTimersByTimeAsync(999))
  expect(fetch).not.toHaveBeenCalled()
  await act(() => vi.advanceTimersByTimeAsync(1))
  expect(result.current.saving).toBe(true)
  act(() =>
    result.current.edit({ ...original, metadata: { ...original.metadata, courseName: 'Latest' } }),
  )
  await act(async () => finish(null))
  expect(result.current.content.metadata.courseName).toBe('Latest')
  expect(result.current.dirty).toBe(true)
  failing = true
  await act(() => vi.advanceTimersByTimeAsync(1000))
  expect(result.current.error).toBe('Save conflict')
  const calls = fetch.mock.calls.length
  await act(() => vi.advanceTimersByTimeAsync(10000))
  expect(fetch).toHaveBeenCalledTimes(calls)
  failing = false
  let saving!: Promise<Draft>
  act(() => {
    saving = result.current.save()
  })
  await act(async () => {
    finish(null)
    await saving
  })
  expect(result.current.dirty).toBe(false)
  expect(result.current.content.metadata.courseName).toBe('Latest')
})
