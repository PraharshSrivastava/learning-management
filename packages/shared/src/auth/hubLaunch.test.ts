import { configureApi, type LmsApp } from '../api/client'
import { consumeHubLaunchToken } from './hubLaunch'

afterEach(() => {
  window.history.replaceState(null, '', '/')
})

describe.each([
  ['employee', '/lms'],
  ['trainer', '/lms/trainer'],
] as [LmsApp, string][])('%s app', (app, mount) => {
  beforeEach(() => configureApi({ app, publicMount: mount }))

  it.each(['', mount])('sends the token to the launch endpoint of mount "%s"', (active) => {
    const pathname = `${active}/`
    window.history.replaceState(null, '', `${pathname}?hub_launch_token=a.b%2B&tab=courses`)
    const replace = vi.fn()

    expect(
      consumeHubLaunchToken({ pathname, search: window.location.search, hash: '#top', replace }),
    ).toBe(true)
    expect(window.location.pathname + window.location.search + window.location.hash).toBe(
      `${pathname}?tab=courses#top`,
    )
    expect(replace).toHaveBeenCalledWith(`${active}/api/hub/launch/${app}?hub_launch_token=a.b%2B`)
  })
})

it('does nothing without a token', () => {
  configureApi({ app: 'employee', publicMount: '/lms' })
  const replace = vi.fn()
  expect(consumeHubLaunchToken({ pathname: '/', search: '?tab=x', hash: '', replace })).toBe(false)
  expect(replace).not.toHaveBeenCalled()
})
