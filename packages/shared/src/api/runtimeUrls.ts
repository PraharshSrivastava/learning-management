/** Resolves the active public mount without a build-time origin or port. */
export class LmsRuntimeUrls {
  constructor(
    readonly entrypoint: URL,
    readonly publicMount: string,
    readonly configuredApiBase = '',
  ) {}

  /** The matched entry path selects the mount, not a client-supplied header. */
  get activeMount(): string {
    const path = this.entrypoint.pathname
    return path === this.publicMount || path.startsWith(`${this.publicMount}/`)
      ? this.publicMount
      : ''
  }

  /** Relative overrides resolve inside the active mount; absolute ones stay absolute. */
  get apiBaseUrl(): string {
    const configured = this.configuredApiBase.trim()
    if (!configured) return this.activeMount
    if (/^[a-z][a-z0-9+.-]*:/i.test(configured)) return configured.replace(/\/+$/, '')
    const mountUrl = new URL(`${this.activeMount}/`, this.entrypoint.origin)
    return new URL(configured, mountUrl).href.replace(/\/+$/, '')
  }

  /**
   * WebSocket URLs always include the entry origin and retain the API mount.
   * The path is relative to the API base, so a leading slash does not drop the mount.
   */
  websocketEndpoint(path: string, query: Record<string, string>): string {
    const base = new URL(`${this.apiBaseUrl}/`, this.entrypoint)
    const url = new URL(path.replace(/^\/+/, ''), base)
    url.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:'
    url.search = new URLSearchParams(query).toString()
    return url.href
  }
}
