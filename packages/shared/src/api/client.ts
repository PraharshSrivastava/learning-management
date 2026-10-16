import { LmsRuntimeUrls } from './runtimeUrls'

export type LmsApp = 'trainer' | 'employee'

export interface ApiConfig {
  app: LmsApp
  publicMount: string
  configuredApiBase?: string
}

let config: ApiConfig = { app: 'trainer', publicMount: '/lms/trainer' }
let authToken: string | null = null
let mediaTicket: string | null = null

/** Called once by each app before render. */
export function configureApi(next: ApiConfig): void {
  config = next
  authToken = null
  setMediaTicket(null)
}

export const lmsApp = (): LmsApp => config.app

export function runtimeUrls(): LmsRuntimeUrls {
  return new LmsRuntimeUrls(
    new URL(window.location.href),
    config.publicMount,
    config.configuredApiBase ?? '',
  )
}

export const apiBaseUrl = (): string => runtimeUrls().apiBaseUrl

/** Builds an API URL from a path such as `/api/courses`. */
export const apiUrl = (path: string): string => `${apiBaseUrl()}${path}`

export const websocketUrl = (path: string, query: Record<string, string>): string =>
  runtimeUrls().websocketEndpoint(path, query)

/** Bearer token from local dev login. Hub-session users have none. */
export function setAuthToken(token: string | null): void {
  authToken = token
}

const ticketListeners = new Set<() => void>()

/**
 * The ticket is read when a URL is built, so no long-lived object holds a stale value.
 * Listeners hear only when a ticket appears or disappears. A routine 30 s renewal does not
 * re-render media, so loaded images and playing videos are not reloaded.
 */
export function setMediaTicket(ticket: string | null): void {
  // A direct set, such as on sign-in, also makes pending ticket requests obsolete.
  latestTicketRequest++
  storeMediaTicket(ticket)
}

function storeMediaTicket(ticket: string | null): void {
  const changed = Boolean(ticket) !== Boolean(mediaTicket)
  mediaTicket = ticket
  if (changed) for (const listener of ticketListeners) listener()
}

let latestTicketRequest = 0

/**
 * Starts a ticket request and returns the function that stores its result. Only the newest
 * request stores its ticket, so an obsolete response cannot replace or clear a newer ticket.
 */
export function beginMediaTicketRequest(): (ticket: string | null) => void {
  const request = ++latestTicketRequest
  return (ticket) => {
    if (request === latestTicketRequest) storeMediaTicket(ticket)
  }
}

export function hasMediaTicket(): boolean {
  return Boolean(mediaTicket)
}

export function subscribeMediaTicket(listener: () => void): () => void {
  ticketListeners.add(listener)
  return () => ticketListeners.delete(listener)
}

export function authHeaders(): Record<string, string> {
  return {
    'X-LMS-App': config.app,
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  }
}

/** Adds the media ticket to same-origin http(s) URLs so <video> and <iframe> loads are authorized. */
export function protectedUrl(url: string): string {
  if (!mediaTicket) return url
  const isAbsolute = /^[a-z][a-z0-9+.-]*:/i.test(url) || url.startsWith('//')
  const api = new URL(apiBaseUrl() || '/', window.location.href)
  const parsed = new URL(url, api)
  if (isAbsolute && parsed.host !== api.host) return url
  if (!['http:', 'https:'].includes(parsed.protocol)) return url
  parsed.searchParams.set('media_ticket', mediaTicket)
  return isAbsolute ? parsed.href : `${parsed.pathname}${parsed.search}${parsed.hash}`
}

/**
 * Puts the current ticket in a URL that carries an older one. A ticket expires after 15 minutes,
 * so a long video sends its later requests with the renewed ticket. URLs without one are unchanged.
 */
export function withCurrentMediaTicket(url: string): string {
  if (!mediaTicket) return url
  const parsed = new URL(url, window.location.href)
  const ticket = parsed.searchParams.get('media_ticket')
  if (ticket == null || ticket === mediaTicket) return url
  parsed.searchParams.set('media_ticket', mediaTicket)
  return parsed.href
}

/** Resolves a backend path such as `assets/slides/x.png` against the API base. */
export function assetUrl(path: string): string {
  if (path.startsWith('http')) return protectedUrl(path)
  return protectedUrl(`${apiBaseUrl()}/${path.replace(/^\/+/, '')}`)
}

export const videoAssetUrl = assetUrl

export const hlsVideoAssetUrl = (videoPath: string): string =>
  videoAssetUrl(videoPath.replace(/\.mp4$/i, '_hls/master.m3u8'))

export const viewFileUrl = (filename: string): string =>
  protectedUrl(apiUrl(`/api/files/${encodeURIComponent(filename)}`))

export const previewFileUrl = (filename: string): string =>
  protectedUrl(apiUrl(`/api/files/${encodeURIComponent(filename)}/preview`))

export const slideshowHtmlUrl = (courseId: string, moduleNumber: number): string =>
  protectedUrl(apiUrl(`/assets/slides/${courseId}/module_${moduleNumber}.html`))

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** FastAPI returns `detail` as a string or as a list of validation errors. */
export function errorDetail(body: unknown): string | null {
  if (!body || typeof body !== 'object' || !('detail' in body)) return null
  const detail = (body as { detail: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const parts = detail.map((item) =>
      item && typeof item === 'object' && 'msg' in item ? String(item.msg) : String(item),
    )
    return parts.join('\n') || null
  }
  return detail == null ? null : String(detail)
}

function parseBody(text: string): unknown {
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  json?: unknown
  body?: BodyInit
  headers?: Record<string, string>
  signal?: AbortSignal
}

/** Sends a request to the backend and returns the decoded JSON body. Non-2xx throws ApiError. */
export async function apiRequest(path: string, options: RequestOptions = {}): Promise<unknown> {
  const headers: Record<string, string> = { ...authHeaders(), ...options.headers }
  let body = options.body
  if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.json)
  }
  let response: Response
  try {
    response = await fetch(apiUrl(path), {
      method: options.method ?? (body === undefined ? 'GET' : 'POST'),
      headers,
      body,
      signal: options.signal,
      credentials: 'same-origin',
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('Unable to reach the server. Check your connection and try again.', 0, null)
  }
  const data = parseBody(await response.text())
  if (!response.ok) {
    throw new ApiError(
      errorDetail(data) ?? `Server returned ${response.status}`,
      response.status,
      data,
    )
  }
  return data
}

/** Same as apiRequest, then parses the body with a zod-style parser. */
export async function apiGet<T>(
  path: string,
  parse: (json: unknown) => T,
  options: RequestOptions = {},
): Promise<T> {
  return parse(await apiRequest(path, options))
}

/** Uploads with XHR because fetch has no upload progress events. */
export function uploadWithProgress(
  path: string,
  form: FormData,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', apiUrl(path))
    for (const [key, value] of Object.entries(authHeaders())) xhr.setRequestHeader(key, value)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total)
    }
    xhr.onload = () => {
      const data = parseBody(xhr.responseText)
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else
        reject(new ApiError(errorDetail(data) ?? `Server returned ${xhr.status}`, xhr.status, data))
    }
    xhr.onerror = () =>
      reject(
        new ApiError('Unable to reach the server. Check your connection and try again.', 0, null),
      )
    xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'))
    signal?.addEventListener('abort', () => xhr.abort(), { once: true })
    xhr.send(form)
  })
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return String(error)
}
