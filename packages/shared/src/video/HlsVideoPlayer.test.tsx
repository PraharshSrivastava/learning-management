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

// Media elements queue volumechange as a task, as the HTML standard requires.
const mediaEvents = () => new Promise((resolve) => setTimeout(resolve, 0))

it('carries the learner volume and mute into the next module and across reloads', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 404 })),
  )
  window.localStorage.clear()
  const { container, rerender, unmount } = render(
    <HlsVideoPlayer hlsUrl="/one_hls/master.m3u8" fallbackUrl="/one.mp4" />,
  )
  const slider = container.querySelector<HTMLInputElement>('input[aria-label="Volume"]')!
  slider.value = '0.35'
  slider.dispatchEvent(new Event('input'))
  container.querySelector<HTMLButtonElement>('button[aria-label="Mute"]')!.click()
  await mediaEvents()

  rerender(<HlsVideoPlayer hlsUrl="/two_hls/master.m3u8" fallbackUrl="/two.mp4" />)
  const next = container.querySelector('video')!
  expect(next.volume).toBeCloseTo(0.35)
  expect(next.muted).toBe(true)
  expect(container.querySelector('button[aria-label="Unmute"]')).not.toBeNull()

  // A reload mounts a fresh player that reads the saved preference.
  unmount()
  const reloaded = render(
    <HlsVideoPlayer hlsUrl="/three_hls/master.m3u8" fallbackUrl="/three.mp4" />,
  )
  const video = reloaded.container.querySelector('video')!
  expect(video.volume).toBeCloseTo(0.35)
  expect(video.muted).toBe(true)
  expect(JSON.parse(window.localStorage.getItem('lms.video-volume.v1')!)).toEqual({
    volume: 0.35,
    muted: true,
  })
})

it('starts each next module at the most recent volume the learner chose', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 404 })),
  )
  window.localStorage.clear()
  const { container, rerender } = render(
    <HlsVideoPlayer hlsUrl="/m1_hls/master.m3u8" fallbackUrl="/m1.mp4" />,
  )
  const setVolume = async (value: string) => {
    const slider = container.querySelector<HTMLInputElement>('input[aria-label="Volume"]')!
    slider.value = value
    slider.dispatchEvent(new Event('input'))
    await mediaEvents()
  }
  const openModule = (number: number) => {
    rerender(
      <HlsVideoPlayer hlsUrl={`/m${number}_hls/master.m3u8`} fallbackUrl={`/m${number}.mp4`} />,
    )
    return container.querySelector('video')!
  }

  await setVolume('0.7')
  expect(openModule(2).volume).toBeCloseTo(0.7)
  await setVolume('0.4')
  expect(openModule(3).volume).toBeCloseTo(0.4)
  expect(openModule(4).volume).toBeCloseTo(0.4)
  container.querySelector<HTMLButtonElement>('button[aria-label="Mute"]')!.click()
  await mediaEvents()
  expect(openModule(5).muted).toBe(true)
  // Moving the slider unmutes, as it does within one video.
  await setVolume('0.8')
  const last = openModule(6)
  expect(last.volume).toBeCloseTo(0.8)
  expect(last.muted).toBe(false)
})

it('ignores a stored volume outside the valid range', () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 404 })),
  )
  window.localStorage.setItem('lms.video-volume.v1', JSON.stringify({ volume: 7, muted: 'yes' }))
  const { container } = render(
    <HlsVideoPlayer hlsUrl="/one_hls/master.m3u8" fallbackUrl="/one.mp4" />,
  )
  const video = container.querySelector('video')!
  expect(video.volume).toBe(1)
  expect(video.muted).toBe(false)
})

it('keeps the volume between modules when storage is blocked', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 404 })),
  )
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  const { container, rerender } = render(
    <HlsVideoPlayer hlsUrl="/one_hls/master.m3u8" fallbackUrl="/one.mp4" />,
  )
  const slider = container.querySelector<HTMLInputElement>('input[aria-label="Volume"]')!
  slider.value = '0.6'
  slider.dispatchEvent(new Event('input'))
  await mediaEvents()
  rerender(<HlsVideoPlayer hlsUrl="/two_hls/master.m3u8" fallbackUrl="/two.mp4" />)
  const next = container.querySelector('video')!
  expect(next.volume).toBeCloseTo(0.6)
  expect(next.muted).toBe(false)
})
