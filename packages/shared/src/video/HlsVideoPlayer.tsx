import type Hls from 'hls.js'
import { useEffect, useRef } from 'react'
import { withCurrentMediaTicket } from '../api/client'
import { LinearPlaybackGuard } from './linearPlaybackGuard'
import { create } from './captionPlayer.js'

interface HlsVideoPlayerProps {
  hlsUrl: string
  fallbackUrl: string
  onEnded?: () => void
  /** Blocks forward seeking until the video has been watched to the end once. */
  enforceLinearPlayback?: boolean
  initiallyCompleted?: boolean
  className?: string
}

async function playlistExists(url: string, signal: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(url, { method: 'HEAD', signal, credentials: 'same-origin' })
    return response.ok
  } catch {
    return false
  }
}

/** The media ticket changes on renewal. It must not reload a playing video. */
function withoutTicket(url: string): string {
  return url.replace(/([?&])media_ticket=[^&#]*&?/, '$1').replace(/[?&]$/, '')
}

function canPlayNativeHls(video: HTMLVideoElement): boolean {
  return (
    video.canPlayType('application/vnd.apple.mpegurl') !== '' ||
    video.canPlayType('application/x-mpegURL') !== ''
  )
}

/** Plays the HLS rendition when it exists and falls back to the progressive MP4. */
export function HlsVideoPlayer({
  hlsUrl,
  fallbackUrl,
  onEnded,
  enforceLinearPlayback = false,
  initiallyCompleted = false,
  className,
}: HlsVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const onEndedRef = useRef(onEnded)
  const urlsRef = useRef({ hlsUrl, fallbackUrl })
  useEffect(() => {
    onEndedRef.current = onEnded
    urlsRef.current = { hlsUrl, fallbackUrl }
  }, [onEnded, hlsUrl, fallbackUrl])
  const hlsSource = withoutTicket(hlsUrl)
  const fallbackSource = withoutTicket(fallbackUrl)

  // Keep the established caption controls outside React's child reconciliation. The media
  // source effect still owns HLS, authorization renewal, and the playback guard below.
  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const video = document.createElement('video')
    video.playsInline = true
    video.preload = 'auto'
    videoRef.current = video
    const player = create(
      video,
      () => {},
      (seconds) => seconds,
    )
    container.append(player)
    void player.loadCaptions(urlsRef.current.fallbackUrl)
    return () => {
      player.disposePlayer()
      player.remove()
      videoRef.current = null
    }
  }, [hlsSource, fallbackSource])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const guard = new LinearPlaybackGuard(enforceLinearPlayback, initiallyCompleted)
    let correctingSeek = false

    const handleTimeUpdate = () => {
      if (correctingSeek || video.seeking) return
      guard.observePosition(video.currentTime)
    }
    const handleSeeking = () => {
      if (correctingSeek) return
      const requested = video.currentTime
      const allowed = guard.constrainSeek(requested)
      if (Math.abs(requested - allowed) < 0.01) return
      correctingSeek = true
      video.currentTime = allowed
      queueMicrotask(() => {
        correctingSeek = false
      })
    }
    const handleEnded = () => {
      if (!guard.tryMarkCompleted(video.duration)) {
        video.currentTime = guard.furthestWatchedSeconds
        return
      }
      onEndedRef.current?.()
    }
    video.addEventListener('timeupdate', handleTimeUpdate)
    video.addEventListener('seeking', handleSeeking)
    video.addEventListener('ended', handleEnded)
    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate)
      video.removeEventListener('seeking', handleSeeking)
      video.removeEventListener('ended', handleEnded)
    }
  }, [enforceLinearPlayback, initiallyCompleted, hlsSource, fallbackSource])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const controller = new AbortController()
    const { hlsUrl, fallbackUrl } = urlsRef.current
    let hls: Hls | null = null

    void (async () => {
      const hasPlaylist = await playlistExists(hlsUrl, controller.signal)
      if (controller.signal.aborted) return
      if (!hasPlaylist) {
        video.src = fallbackUrl
        return
      }
      if (canPlayNativeHls(video)) {
        video.src = hlsUrl
        return
      }
      try {
        const { default: HlsJs } = await import('hls.js')
        if (controller.signal.aborted) return
        if (HlsJs.isSupported()) {
          hls = new HlsJs({
            // The backend puts the ticket of the first request in each playlist line. hls.js does
            // not open the request again when this callback opened it, so each request uses the
            // current ticket.
            xhrSetup: (xhr, url) => xhr.open('GET', withCurrentMediaTicket(url), true),
          })
          hls.loadSource(hlsUrl)
          hls.attachMedia(video)
          return
        }
      } catch {
        // Fall back to the progressive MP4 below.
      }
      video.src = fallbackUrl
    })()

    // A source the browser loads itself keeps its first ticket. When a later range request fails
    // with an expired ticket, load the source again with the current ticket at the same position.
    const handleError = () => {
      const source = video.currentSrc
      const renewed = withCurrentMediaTicket(source)
      if (hls || !source || renewed === source) return
      const position = video.currentTime
      const playing = !video.paused
      video.src = renewed
      video.currentTime = position
      if (playing) void video.play().catch(() => {})
    }
    video.addEventListener('error', handleError)

    return () => {
      controller.abort()
      video.removeEventListener('error', handleError)
      hls?.destroy()
      video.removeAttribute('src')
      video.load()
    }
  }, [hlsSource, fallbackSource])

  return <div ref={containerRef} className={className ?? 'h-full w-full bg-black'} />
}
