import { cleanup, render, waitFor } from '@testing-library/react'
import type { HlsConfig, LoaderContext } from 'hls.js'
import { afterEach, expect, it, vi } from 'vitest'
import { setMediaTicket } from '../api/client'
import { HlsVideoPlayer } from './HlsVideoPlayer'

const created = vi.hoisted(() => [] as Partial<HlsConfig>[])

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
