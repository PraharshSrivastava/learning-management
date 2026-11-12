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

/**
 * Attributes that replay may record as is: layout, state, and SVG drawing data. Every other
 * attribute is masked, because attributes such as `aria-label`, `title`, or `download` can hold
 * employee names and file names.
 */
const SAFE_ATTRIBUTES = new Set([
  'class',
  'style',
  'id',
  'type',
  'role',
  'tabindex',
  'dir',
  'lang',
  'hidden',
  'disabled',
  'checked',
  'selected',
  'readonly',
  'required',
  'open',
  'for',
  'rel',
  'target',
  'width',
  'height',
  'colspan',
  'rowspan',
  'viewbox',
  'xmlns',
  'd',
  'points',
  'x',
  'y',
  'x1',
  'y1',
  'x2',
  'y2',
  'cx',
  'cy',
  'r',
  'rx',
  'ry',
  'fill',
  'stroke',
  'stroke-width',
  'stroke-linecap',
  'stroke-linejoin',
  'fill-rule',
  'clip-rule',
  'transform',
  'opacity',
  'offset',
  'stop-color',
  'aria-hidden',
  'aria-expanded',
  'aria-selected',
  'aria-checked',
  'aria-pressed',
  'aria-disabled',
  'aria-current',
  'aria-busy',
  'aria-modal',
  'aria-haspopup',
  'aria-orientation',
  'data-state',
  'data-side',
  'data-orientation',
])
const URL_ATTRIBUTES = new Set(['href', 'src'])

/**
 * Session replay masks all text and unsafe attributes, and blocks media. Almost every screen shows
 * employee names, scores, or uploaded document content, so masking everything is the robust choice.
 * Media and links can carry a `media_ticket` URL, and `mailto:` links carry email addresses.
 */
const SESSION_RECORDING: PostHogConfig['session_recording'] = {
  maskAllInputs: true,
  maskTextSelector: '*',
  maskAttributeFn: (name, value) => {
    const attribute = name.toLowerCase()
    if (SAFE_ATTRIBUTES.has(attribute) || attribute.startsWith('rr_')) return value
    if (URL_ATTRIBUTES.has(attribute) && !/^(mailto|tel):/i.test(value)) return withoutTicket(value)
    return '*'.repeat(value.length)
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
