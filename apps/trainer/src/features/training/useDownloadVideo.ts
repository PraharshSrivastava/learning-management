import { useCallback } from 'react'

function clickLink(href: string, filename: string, openInNewTab = false): void {
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  anchor.style.display = 'none'
  if (openInNewTab) {
    anchor.target = '_blank'
    anchor.rel = 'noopener'
  }
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
}

/** Saves the MP4 as a file. When the fetch fails the browser opens the direct URL instead. */
export function useDownloadVideo(): (url: string, filename: string) => Promise<void> {
  return useCallback(async (url, filename) => {
    try {
      const response = await fetch(url)
      if (!response.ok) throw new Error(`Server returned ${response.status}`)
      const objectUrl = URL.createObjectURL(await response.blob())
      clickLink(objectUrl, filename)
      // Revoke later: some browsers start the download after the click handler returns.
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
    } catch {
      clickLink(url, filename, true)
    }
  }, [])
}
