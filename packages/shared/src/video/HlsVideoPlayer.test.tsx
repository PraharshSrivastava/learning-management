import { cleanup, render, waitFor } from '@testing-library/react'
import type { HlsConfig, LoaderContext } from 'hls.js'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { setMediaTicket } from '../api/client'
import { HlsVideoPlayer } from './HlsVideoPlayer'

const created = vi.hoisted(() => [] as Partial<HlsConfig>[])

beforeEach(() => {
  created.length = 0
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
  vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {})
})

vi.mock('hls.js', () => ({
  default: class {
    static isSupported = () => true
    constructor(config: Partial<HlsConfig>) {
      created.push(config)
    }
    loadSource() {}
    attachMedia() {}
    destroy() {}
  },
}))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  setMediaTicket(null)
  vi.restoreAllMocks()
})

it('sends each hls.js request with the current media ticket', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 200 })),
  )
  setMediaTicket('first')
  render(
    <HlsVideoPlayer
      hlsUrl="/lms/assets/v_hls/master.m3u8?media_ticket=first"
      fallbackUrl="/lms/assets/v.mp4?media_ticket=first"
    />,
  )
  await waitFor(() => expect(created).toHaveLength(1))
  setMediaTicket('renewed')
  const xhr = { open: vi.fn() }
  const segment = `${window.location.origin}/lms/assets/v_hls/360p/1.ts?media_ticket=first`
  created[0]!.xhrSetup!(xhr as unknown as XMLHttpRequest, segment, {
    url: segment,
  } as LoaderContext)
  expect(xhr.open).toHaveBeenCalledWith(
    'GET',
    `${window.location.origin}/lms/assets/v_hls/360p/1.ts?media_ticket=renewed`,
    true,
  )
})

it('keeps one caption toolbar across source changes and does not remount on ticket renewal', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 404 })),
  )
  const { container, rerender, unmount } = render(
    <HlsVideoPlayer hlsUrl="/one_hls/master.m3u8" fallbackUrl="/one.mp4?media_ticket=first" />,
  )
  const original = container.querySelector('video')!
  expect(original.controls).toBe(false)
  expect(container.querySelectorAll('.lms-controls')).toHaveLength(1)
  rerender(
    <HlsVideoPlayer hlsUrl="/one_hls/master.m3u8" fallbackUrl="/one.mp4?media_ticket=renewed" />,
  )
  expect(container.querySelector('video')).toBe(original)
  rerender(<HlsVideoPlayer hlsUrl="/two_hls/master.m3u8" fallbackUrl="/two.mp4" />)
  expect(container.querySelector('video')).not.toBe(original)
  expect(container.querySelectorAll('video')).toHaveLength(1)
  expect(container.querySelectorAll('.lms-controls')).toHaveLength(1)
  unmount()
  expect(container.querySelector('video')).toBeNull()
})
