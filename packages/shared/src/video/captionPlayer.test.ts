import { create, captionUrls, parseVtt, activeCue, sha256 } from './captionPlayer.js'
import { setMediaTicket } from '../api/client'

const vtt = 'WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nListen &amp; respond.\n\n'

beforeEach(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
})
afterEach(() => {
  setMediaTicket(null)
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.body.replaceChildren()
})

it('derives sidecars without losing authorization or the mounted path', () => {
  const urls = captionUrls('/lms/trainer/assets/videos/a.mp4?media_ticket=old')!
  expect(urls.metadata.pathname).toBe('/lms/trainer/assets/videos/a.captions.json')
  expect(urls.vtt.searchParams.get('media_ticket')).toBe('old')
  expect(captionUrls('/a_hls/master.m3u8')).toBeNull()
})

it('checks caption integrity on HTTP and rejects malformed or overlapping timelines', () => {
  expect(sha256('abc')).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
  const cues = parseVtt(vtt)
  expect(activeCue(cues, 0.5)).toBe('Listen & respond.')
  expect(activeCue(cues, 1)).toBe('')
  expect(() => parseVtt('not captions')).toThrow()
  expect(() => parseVtt(vtt + '00:00:00.500 --> 00:00:02.000\nOverlap')).toThrow()
})

async function loadFixture(overrides: Record<string, unknown> = {}, body = vtt) {
  const fingerprint = sha256(vtt)
  const video = document.createElement('video')
  Object.defineProperty(video, 'duration', { value: 1 })
  const requests: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      requests.push(String(url))
      if (String(url).includes('.captions.json'))
        return new Response(
          JSON.stringify({
            version: 1,
            fingerprint,
            vtt_sha256: fingerprint,
            duration: 1,
            video_size: 100,
            video_mtime: 1000,
            cue_count: 1,
            ...overrides,
          }),
        )
      if (options?.method === 'HEAD')
        return new Response(null, {
          headers: { 'Content-Length': '100', 'Last-Modified': new Date(1000000).toUTCString() },
        })
      return new Response(body)
    }),
  )
  const player = create(
    video,
    () => {},
    (seconds) => seconds,
  )
  document.body.append(player)
  setMediaTicket('renewed')
  await player.loadCaptions('/lms/assets/videos/a.mp4?media_ticket=old')
  return { player, requests }
}

it('loads validated sidecars using the current ticket and exposes working caption controls', async () => {
  const { player, requests } = await loadFixture()
  expect(requests).toHaveLength(3)
  expect(
    requests.every(
      (url) => new URL(url, location.href).searchParams.get('media_ticket') === 'renewed',
    ),
  ).toBe(true)
  const cc = player.querySelector<HTMLButtonElement>('.lms-cc')!
  expect(cc.disabled).toBe(false)
  cc.click()
  expect(player.querySelector('.lms-captions')!.textContent).toBe('Listen & respond.')
  player.disposePlayer()
})

it.each([
  [{ video_size: 99 }, vtt],
  [{ video_mtime: 999 }, vtt],
  [{ cue_count: 2 }, vtt],
  [{ duration: 2 }, vtt],
  [{}, vtt.replace('Listen', 'Tampered')],
])('keeps unavailable or stale captions disabled', async (metadata, body) => {
  const { player } = await loadFixture(metadata, body)
  expect(player.querySelector<HTMLButtonElement>('.lms-cc')!.disabled).toBe(true)
  player.disposePlayer()
})
