import type { PostHog, PostHogConfig, Properties } from 'posthog-js'
import type { LmsApp } from '../api/client'

export interface AnalyticsConfig {
  app: LmsApp
  /** PostHog project token. Empty turns analytics off: the SDK is never downloaded. */
  token?: string
  host?: string
}

type Call = (posthog: PostHog) => void

let client: PostHog | null = null
/** Calls made before the SDK loads. Null while analytics is off. */
let pending: Call[] | null = null

/** Attributes that hold readable text, such as an employee name in an aria-label. */
const TEXT_ATTRIBUTES = new Set([
  'aria-label',
  'aria-description',
  'aria-valuetext',
  'title',
  'alt',
  'placeholder',
  'label',
])

/**
 * Session replay masks all text and text attributes, and blocks media. Almost every screen shows
 * employee names, scores, or uploaded document content, so masking everything is the robust choice.
 * Media and links can carry a `media_ticket` URL.
 */
const SESSION_RECORDING: PostHogConfig['session_recording'] = {
  maskAllInputs: true,
  maskTextSelector: '*',
  maskAttributeFn: (name, value) => {
    if (TEXT_ATTRIBUTES.has(name)) return '*'.repeat(value.length)
    if (name === 'href' || name === 'src') return withoutTicket(value)
    return value
  },
  blockSelector: 'img, video, iframe, canvas',
  maskCapturedNetworkRequestFn: (request) => ({ ...request, name: withoutTicket(request.name) }),
}

function withoutTicket(url: string): string {
  if (!url.includes('media_ticket')) return url
  const parsed = new URL(url, window.location.href)
  parsed.searchParams.delete('media_ticket')
  return parsed.href
}

/** Starts PostHog when a token is configured. The SDK loads in its own chunk when the browser is idle. */
export function startAnalytics({ app, token, host }: AnalyticsConfig): void {
  if (!token || pending || client) return
  pending = []
  const load = () => {
    import('posthog-js')
      .then(({ default: posthog }) => {
        posthog.init(token, {
          api_host: host || 'https://us.i.posthog.com',
          defaults: '2026-08-30',
          person_profiles: 'identified_only',
          capture_exceptions: true,
          // Autocapture sends clicked element text and attributes, which can hold names and tickets.
          mask_all_text: true,
          mask_all_element_attributes: true,
          session_recording: SESSION_RECORDING,
        })
        posthog.register({ lms_app: app })
        client = posthog
        for (const call of pending ?? []) call(posthog)
        pending = null
      })
      .catch(() => {
        // An ad blocker or a network fault must not affect the app.
        pending = null
      })
  }
  if ('requestIdleCallback' in window) window.requestIdleCallback(load, { timeout: 3000 })
  else setTimeout(load, 0)
}

function run(call: Call): void {
  if (client) call(client)
  else pending?.push(call)
}

export function captureEvent(event: string, properties?: Properties): void {
  run((posthog) => posthog.capture(event, properties))
}

export function captureError(error: unknown, properties?: Properties): void {
  run((posthog) => posthog.captureException(error, properties))
}

/** Links later events to the signed-in person. Pass ids and non-identifying traits only. */
export function identifyPerson(distinctId: string, properties?: Properties): void {
  run((posthog) => posthog.identify(distinctId, properties))
}

/** Unlinks the device from the previous person, for example when another person signs in. */
export function resetAnalytics(): void {
  run((posthog) => posthog.reset())
}

/** Lets backend events join the browser session. Empty until the SDK has loaded. */
export function analyticsHeaders(): Record<string, string> {
  if (!client) return {}
  return {
    'X-POSTHOG-DISTINCT-ID': client.get_distinct_id(),
    'X-POSTHOG-SESSION-ID': client.get_session_id(),
  }
}
