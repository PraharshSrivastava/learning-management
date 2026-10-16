import { LmsRuntimeUrls } from './runtimeUrls'

describe.each(['/lms', '/lms/trainer'])('mount %s', (mount) => {
  it('root and mount entrypoints infer separate API mounts', () => {
    for (const path of ['/', '/dashboard', `${mount}/`, `${mount}/dashboard`]) {
      const urls = new LmsRuntimeUrls(
        new URL(`https://example.test:9443${path}?launch=secret`),
        mount,
      )
      const expected = path.startsWith(`${mount}/`) ? mount : ''
      expect(urls.apiBaseUrl).toBe(expected)
      for (const wsPath of ['api/me/courses/ws', '/api/me/courses/ws']) {
        expect(urls.websocketEndpoint(wsPath, { token: 'a&b' })).toBe(
          `wss://example.test:9443${expected}/api/me/courses/ws?token=a%26b`,
        )
      }
    }
  })

  it('relative API overrides retain origin and mount', () => {
    for (const configured of ['proxy/', '/proxy/', 'http://api.test:9000/']) {
      const urls = new LmsRuntimeUrls(
        new URL(`https://example.test:9443${mount}/dashboard`),
        mount,
        configured,
      )
      const expected =
        {
          'proxy/': `https://example.test:9443${mount}/proxy`,
          '/proxy/': 'https://example.test:9443/proxy',
        }[configured] ?? 'http://api.test:9000'
      expect(urls.apiBaseUrl).toBe(expected)
      expect(urls.websocketEndpoint('api/me/courses/ws', {})).toBe(
        `${expected.replace('https:', 'wss:').replace('http:', 'ws:')}/api/me/courses/ws`,
      )
    }
  })
})

it('mount inference requires a full path segment', () => {
  const urls = new LmsRuntimeUrls(new URL('http://example.test/lms-other/'), '/lms')
  expect(urls.apiBaseUrl).toBe('')
})
