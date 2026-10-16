import {
  apiRequest,
  assetUrl,
  configureApi,
  hlsVideoAssetUrl,
  protectedUrl,
  setAuthToken,
  setMediaTicket,
  withCurrentMediaTicket,
} from './client'

beforeEach(() => {
  window.history.replaceState(null, '', '/lms/trainer/')
  configureApi({ app: 'trainer', publicMount: '/lms/trainer' })
})

describe('protectedUrl', () => {
  it('returns the URL unchanged without a ticket', () => {
    expect(protectedUrl('/lms/trainer/assets/videos/a.mp4')).toBe(
      '/lms/trainer/assets/videos/a.mp4',
    )
  })

  it('adds the ticket to relative and same-origin URLs only', () => {
    setMediaTicket('t&1')
    expect(protectedUrl('/lms/trainer/assets/videos/a.mp4?x=1')).toBe(
      '/lms/trainer/assets/videos/a.mp4?x=1&media_ticket=t%261',
    )
    expect(protectedUrl(`${window.location.origin}/assets/a.png`)).toBe(
      `${window.location.origin}/assets/a.png?media_ticket=t%261`,
    )
    expect(protectedUrl('https://cdn.example.test/a.png')).toBe('https://cdn.example.test/a.png')
    expect(protectedUrl('data:image/png;base64,AAA')).toBe('data:image/png;base64,AAA')
  })
})

describe('withCurrentMediaTicket', () => {
  it('replaces an old ticket and leaves other URLs unchanged', () => {
    const segment = `${window.location.origin}/lms/trainer/assets/v_hls/1.ts?media_ticket=old&x=1`
    setMediaTicket('new')
    expect(withCurrentMediaTicket(segment)).toBe(
      `${window.location.origin}/lms/trainer/assets/v_hls/1.ts?media_ticket=new&x=1`,
    )
    const plain = `${window.location.origin}/lms/trainer/assets/v_hls/1.ts`
    expect(withCurrentMediaTicket(plain)).toBe(plain)
    setMediaTicket(null)
    expect(withCurrentMediaTicket(segment)).toBe(segment)
  })
})

it('builds mount-relative asset and HLS URLs', () => {
  expect(assetUrl('assets/slides/c/1.png')).toBe('/lms/trainer/assets/slides/c/1.png')
  expect(hlsVideoAssetUrl('/assets/videos/c/m1.MP4')).toBe(
    '/lms/trainer/assets/videos/c/m1_hls/master.m3u8',
  )
})

describe('apiRequest', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends app and bearer headers and decodes JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"ok":true}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    setAuthToken('tok')
    await expect(apiRequest('/api/courses')).resolves.toEqual({ ok: true })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('/lms/trainer/api/courses')
    expect(init.headers).toMatchObject({ 'X-LMS-App': 'trainer', Authorization: 'Bearer tok' })
  })

  it('uses detail from the error body, or the status when the body is not JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(new Response('{"detail":"Course not found"}', { status: 404 }))
        .mockResolvedValueOnce(new Response('<html>Bad gateway</html>', { status: 502 })),
    )
    await expect(apiRequest('/api/courses/x')).rejects.toMatchObject({
      message: 'Course not found',
      status: 404,
    })
    await expect(apiRequest('/api/courses/x')).rejects.toThrow('Server returned 502')
  })
})
