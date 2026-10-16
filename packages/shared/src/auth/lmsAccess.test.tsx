import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { configureApi, protectedUrl } from '../api/client'
import { useLmsAccess } from './lmsAccess'
import { SessionProvider } from './session'

afterEach(() => vi.unstubAllGlobals())

it('keeps the newest media ticket when an older refresh finishes last', async () => {
  configureApi({ app: 'employee', publicMount: '/lms' })
  const tickets: ((ticket: string) => void)[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      if (!String(input).includes('/api/media-ticket')) return new Response('{}')
      const ticket = await new Promise<string>((resolve) => tickets.push(resolve))
      return new Response(JSON.stringify({ ticket }))
    }),
  )
  const queryClient = new QueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <SessionProvider initialPerson={{ id: 'e1' }}>{children}</SessionProvider>
    </QueryClientProvider>
  )
  const { result } = renderHook(() => useLmsAccess(), { wrapper })
  await waitFor(() => expect(tickets).toHaveLength(1))
  await act(async () => tickets[0]!('first'))
  await waitFor(() => expect(result.current.access).not.toBeNull())
  // With data present, a second refetch cancels the first one, but its request still finishes.
  void act(() => result.current.refetch())
  await waitFor(() => expect(tickets).toHaveLength(2))
  void act(() => result.current.refetch())
  await waitFor(() => expect(tickets).toHaveLength(3))

  await act(async () => tickets[2]!('new'))
  await waitFor(() => expect(protectedUrl('/a')).toBe('/a?media_ticket=new'))
  await act(async () => tickets[1]!('old'))
  await act(() => new Promise((resolve) => setTimeout(resolve, 0)))
  expect(protectedUrl('/a')).toBe('/a?media_ticket=new')
  queryClient.clear()
})
