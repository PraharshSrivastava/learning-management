import { apiUrl, lmsApp } from '../api/client'

type LaunchLocation = Pick<Location, 'pathname' | 'search' | 'hash' | 'replace'>

/**
 * Hub can launch a frontend URL such as `/lms/?hub_launch_token=...`. Removes the token
 * from browser history, then sends it to the backend launch endpoint of the active
 * mount, which sets the session cookie and redirects back to the mount.
 * Returns true when the page is navigating away and must not render.
 */
export function consumeHubLaunchToken(location: LaunchLocation = window.location): boolean {
  const params = new URLSearchParams(location.search)
  const token = params.get('hub_launch_token')
  if (!token) return false
  params.delete('hub_launch_token')
  const query = params.toString()
  window.history.replaceState(
    window.history.state,
    '',
    `${location.pathname}${query ? `?${query}` : ''}${location.hash}`,
  )
  location.replace(
    `${apiUrl(`/api/hub/launch/${lmsApp()}`)}?hub_launch_token=${encodeURIComponent(token)}`,
  )
  return true
}
