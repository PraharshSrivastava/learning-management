const sdk = vi.hoisted(() => ({
  loaded: false,
  init: vi.fn(),
  register: vi.fn(),
  capture: vi.fn(),
  identify: vi.fn(),
  get_distinct_id: () => 'd1',
  get_session_id: () => 's1',
}))

vi.mock('posthog-js', () => {
  sdk.loaded = true
  return { default: sdk }
})

beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
  sdk.loaded = false
})

const loadModule = () => import('./posthog')
const initCall = () => sdk.init.mock.calls[0]!

describe('startAnalytics', () => {
  it('does not load the SDK without a token', async () => {
    const analytics = await loadModule()
    analytics.startAnalytics({ app: 'trainer', token: '' })
    analytics.captureEvent('course_published')
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(sdk.loaded).toBe(false)
    expect(analytics.analyticsHeaders()).toEqual({})
  })

  it('loads the SDK later and replays calls made before it loaded', async () => {
    const analytics = await loadModule()
    analytics.startAnalytics({ app: 'employee', token: 'phc_test' })
    analytics.identifyPerson('e1', { role: 'employee' })
    analytics.captureEvent('module_video_watched', { course_id: 'c1' })
    expect(sdk.init).not.toHaveBeenCalled()

    await vi.waitFor(() => expect(sdk.init).toHaveBeenCalled())
    expect(initCall()[0]).toBe('phc_test')
    expect(initCall()[1]).toMatchObject({
      mask_all_text: true,
      mask_all_element_attributes: true,
      session_recording: { maskAllInputs: true, maskTextSelector: '*' },
    })
    expect(sdk.register).toHaveBeenCalledWith({ lms_app: 'employee' })
    expect(sdk.identify).toHaveBeenCalledWith('e1', { role: 'employee' })
    expect(sdk.capture).toHaveBeenCalledWith('module_video_watched', { course_id: 'c1' })
    expect(analytics.analyticsHeaders()).toEqual({
      'X-POSTHOG-DISTINCT-ID': 'd1',
      'X-POSTHOG-SESSION-ID': 's1',
    })
  })

  it('removes the media ticket from recorded network URLs and attributes', async () => {
    const analytics = await loadModule()
    analytics.startAnalytics({ app: 'trainer', token: 'phc_test' })
    await vi.waitFor(() => expect(sdk.init).toHaveBeenCalled())
    const recording = initCall()[1].session_recording
    const url = 'https://lms.test/assets/a.mp4?x=1&media_ticket=secret'
    expect(recording.maskCapturedNetworkRequestFn({ name: url }).name).toBe(
      'https://lms.test/assets/a.mp4?x=1',
    )
    expect(recording.maskAttributeFn('href', url)).toBe('https://lms.test/assets/a.mp4?x=1')
  })

  it('masks text attributes in session replay', async () => {
    const analytics = await loadModule()
    analytics.startAnalytics({ app: 'trainer', token: 'phc_test' })
    await vi.waitFor(() => expect(sdk.init).toHaveBeenCalled())
    const { maskAttributeFn } = initCall()[1].session_recording
    expect(maskAttributeFn('aria-label', 'Resend to Priya')).toBe('***************')
    expect(maskAttributeFn('class', 'flex gap-2')).toBe('flex gap-2')
  })
})
