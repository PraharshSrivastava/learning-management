/* Existing corporate media controls, bundled once for both React applications. */
import { withCurrentMediaTicket } from '../api/client'
import { sha256Text as sha256 } from '../crypto/sha256Text.js'
const global = window

;('use strict')
function captionUrls(videoUrl) {
  const url = new URL(videoUrl, global.location ? global.location.href : 'http://localhost/')
  if (!/\.mp4$/i.test(url.pathname)) return null
  const metadata = new URL(url)
  metadata.pathname = metadata.pathname.replace(/\.mp4$/i, '.captions.json')
  const vtt = new URL(url)
  vtt.pathname = vtt.pathname.replace(/\.mp4$/i, '.vtt')
  return { metadata, vtt }
}
function parseVtt(content) {
  if (!/^WEBVTT(?:\s|$)/.test(content)) throw new Error('Invalid caption header')
  const cues = []
  let previous = 0
  function time(value) {
    const match = /^(\d{2,}):(\d{2}):(\d{2})\.(\d{3})$/.exec(value)
    if (!match || +match[2] > 59 || +match[3] > 59) throw new Error('Invalid caption timestamp')
    return +match[1] * 3600 + +match[2] * 60 + +match[3] + +match[4] / 1000
  }
  for (const block of content
    .replace(/\r/g, '')
    .split(/\n\s*\n/)
    .slice(1)) {
    if (!block.trim()) continue
    const lines = block.trim().split('\n')
    const match = /^(\S+) --> (\S+)$/.exec(lines.shift())
    if (!match || !lines.length) throw new Error('Invalid caption cue')
    const start = time(match[1]),
      end = time(match[2])
    if (start < previous || end <= start) throw new Error('Invalid cue order')
    const text = lines
      .join('\n')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#x27;/g, "'")
      .replace(/&amp;/g, '&')
    if (!text.trim()) throw new Error('Empty cue')
    cues.push({ start, end, text })
    previous = end
  }
  if (!cues.length) throw new Error('No captions')
  return cues
}
function activeCue(cues, time) {
  let low = 0,
    high = cues.length - 1
  while (low <= high) {
    const mid = (low + high) >> 1,
      cue = cues[mid]
    if (time < cue.start) high = mid - 1
    else if (time >= cue.end) low = mid + 1
    else return cue.text
  }
  return ''
}
// HTTP deployments do not expose SubtleCrypto; integrity still needs verification.
const doc = global.document
function create(video, onHeight, constrainSeek) {
  const root = doc.createElement('div')
  root.className = 'lms-caption-player'
  root.tabIndex = 0
  root.setAttribute('aria-label', 'Lesson video player')
  const style = doc.createElement('style')
  style.textContent = `
      .lms-caption-player{position:relative;display:flex;flex-direction:column;width:100%;height:100%;background:#000;color:#fff;font:14px Inter,Arial,sans-serif;outline-offset:-3px}
      .lms-caption-player *{box-sizing:border-box}.lms-caption-player [hidden]{display:none!important}
      .lms-caption-player .lms-viewport{position:relative;flex:1;min-height:0;overflow:hidden}
      .lms-caption-player video{width:100%;height:100%;object-fit:contain;background:#000}
      .lms-caption-player .lms-controls{position:absolute;bottom:0;left:0;right:0;padding:28px 12px 8px;background:linear-gradient(transparent,#000c);display:flex;flex-wrap:wrap;align-items:center;gap:8px}
      .lms-caption-player button{border:0;background:transparent;color:inherit;font:inherit;border-radius:4px;min-height:32px;min-width:32px;padding:6px}
      .lms-caption-player button:hover{background:#ffffff16}.lms-caption-player button:disabled{opacity:.45}
      .lms-caption-player input[type=range]{accent-color:#3e75c8;min-width:0}.lms-caption-player .lms-seek{width:100%;margin:0;height:14px}
      .lms-caption-player .lms-time{font-size:12px;font-variant-numeric:tabular-nums}.lms-caption-player .lms-spacer{flex:1}
      .lms-caption-player .lms-volume{width:70px}.lms-caption-player .lms-cc[aria-pressed=true]{box-shadow:inset 0 -3px #3e75c8}
      .lms-caption-player .lms-captions{background:#202630;text-align:center;padding:14px 24px;line-height:1.55;flex:none;white-space:pre-line;overflow-wrap:anywhere;min-height:56px}
      .lms-caption-player .lms-menu{position:absolute;right:12px;bottom:74px;background:#22272f;border:1px solid #ffffff14;width:250px;max-width:calc(100% - 24px);padding:6px;border-radius:8px;box-shadow:0 8px 24px #0005;z-index:3;color:#f4f6f9;font-size:13px}
      .lms-caption-player .lms-menu button{display:flex;align-items:center;gap:12px;justify-content:space-between;width:100%;text-align:left;padding:10px 12px}
      .lms-caption-player .lms-divider{border-bottom:1px solid #ffffff16;padding-bottom:12px;margin-bottom:4px}
      .lms-caption-player .lms-setting{display:flex;align-items:center;justify-content:space-between;padding:12px;gap:10px}.lms-caption-player .lms-setting input{accent-color:#0b4e9b;width:18px;height:18px}
      .lms-caption-player .lms-label{font-size:11px;color:#afb8c6;padding:10px 12px 6px;letter-spacing:.4px}
      .lms-caption-player .lms-menu [aria-pressed=true]{background:#00317a}.lms-caption-player .lms-value{color:#b5bdc9;font-size:12px}
      .lms-caption-player .lms-status{position:absolute;top:10px;left:10px;right:10px;text-align:center;font-size:12px;color:#fff;pointer-events:none;background:#172033d9;padding:8px;border-radius:4px}
      .lms-caption-player:fullscreen{width:100vw;height:100vh}.lms-caption-player:fullscreen .lms-captions{font-size:inherit}
      @media(max-width:420px){.lms-caption-player .lms-volume{display:none}.lms-caption-player .lms-captions{padding:12px}.lms-caption-player .lms-controls{gap:3px}}
      @media(pointer:coarse){.lms-caption-player button{min-height:44px;min-width:44px}.lms-caption-player .lms-menu{bottom:86px}}
    `
  root.append(style)
  const viewport = doc.createElement('div')
  viewport.className = 'lms-viewport'
  root.append(viewport)
  viewport.append(video)
  const controls = doc.createElement('div')
  controls.className = 'lms-controls'
  viewport.append(controls)
  const listeners = [],
    sizes = { Small: 14, Medium: 16, Large: 20 }
  let disposed = false,
    generation = 0,
    abort = null,
    cues = [],
    available = false,
    enabled = false,
    size = 'Medium',
    metadata = null,
    panel = 'main'
  try {
    const saved = JSON.parse(global.localStorage.getItem('lms.caption-preferences.v1') || '{}')
    enabled = saved.enabled === true
    if (sizes[saved.size]) size = saved.size
  } catch (_) {}
  function listen(target, name, fn) {
    target.addEventListener(name, fn)
    listeners.push(() => target.removeEventListener(name, fn))
  }
  function button(label, text, parent, action) {
    const node = doc.createElement('button')
    node.type = 'button'
    node.setAttribute('aria-label', label)
    node.textContent = text
    parent.append(node)
    if (action) node.addEventListener('click', action)
    return node
  }
  function icon(node, name) {
    const paths = {
      play: 'M8 5l11 7-11 7z',
      pause: 'M8 5v14M16 5v14',
      volume: 'M3 9h4l5-4v14l-5-4H3zM16 8c3 2 3 6 0 8M19 5c5 4 5 10 0 14',
      mute: 'M3 9h4l5-4v14l-5-4H3zM16 9l6 6M22 9l-6 6',
      fullscreen: 'M9 3H3v6M15 3h6v6M3 15v6h6M21 15v6h-6',
      more: 'M12 4v1M12 11v1M12 18v1',
    }
    const svg = doc.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.setAttribute('viewBox', '0 0 24 24')
    svg.setAttribute('width', '18')
    svg.setAttribute('height', '18')
    svg.setAttribute('aria-hidden', 'true')
    const path = doc.createElementNS(svg.namespaceURI, 'path')
    path.setAttribute('d', paths[name])
    path.setAttribute('fill', name === 'play' ? 'currentColor' : 'none')
    path.setAttribute('stroke', 'currentColor')
    path.setAttribute('stroke-width', name === 'more' ? '3' : '1.7')
    path.setAttribute('stroke-linecap', 'round')
    path.setAttribute('stroke-linejoin', 'round')
    svg.append(path)
    node.replaceChildren(svg)
  }
  const seek = doc.createElement('input')
  seek.type = 'range'
  seek.min = '0'
  seek.max = '1'
  seek.step = '.1'
  seek.value = '0'
  seek.className = 'lms-seek'
  seek.setAttribute('aria-label', 'Seek video')
  controls.append(seek)
  const play = button('Play', '▶', controls, () => {
    if (video.paused) video.play().catch(() => showStatus('Unable to start playback.'))
    else video.pause()
  })
  const time = doc.createElement('span')
  time.className = 'lms-time'
  controls.append(time)
  const spacer = doc.createElement('span')
  spacer.className = 'lms-spacer'
  controls.append(spacer)
  const mute = button('Mute', '🔊', controls, () => {
    video.muted = !video.muted
  })
  const volume = doc.createElement('input')
  volume.type = 'range'
  volume.min = '0'
  volume.max = '1'
  volume.step = '.05'
  volume.value = '1'
  volume.className = 'lms-volume'
  volume.setAttribute('aria-label', 'Volume')
  controls.append(volume)
  const cc = button('Captions unavailable', 'CC', controls, () => {
    enabled = !enabled
    save()
    renderCaptions()
  })
  cc.className = 'lms-cc'
  const fullscreen = button('Enter fullscreen', '⛶', controls, async () => {
    try {
      if (doc.fullscreenElement === root) await doc.exitFullscreen()
      else await root.requestFullscreen()
    } catch (_) {
      showStatus('Fullscreen is unavailable in this browser.')
    }
  })
  const more = button('More video options', '⋮', controls, () => {
    menu.hidden = !menu.hidden
    mainPanel()
  })
  more.setAttribute('aria-expanded', 'false')
  const menu = doc.createElement('div')
  menu.className = 'lms-menu'
  menu.hidden = true
  viewport.append(menu)
  const captions = doc.createElement('div')
  captions.className = 'lms-captions'
  captions.hidden = true
  captions.setAttribute('aria-label', 'Video captions')
  root.append(captions)
  const status = doc.createElement('div')
  status.className = 'lms-status'
  status.hidden = true
  status.setAttribute('role', 'status')
  viewport.append(status)
  icon(fullscreen, 'fullscreen')
  icon(more, 'more')
  let statusTimer
  function showStatus(message) {
    status.textContent = message
    status.hidden = !message
    clearTimeout(statusTimer)
    if (message)
      statusTimer = global.setTimeout(() => {
        status.hidden = true
      }, 5000)
  }
  function save() {
    try {
      global.localStorage.setItem('lms.caption-preferences.v1', JSON.stringify({ enabled, size }))
    } catch (_) {}
  }
  function height() {
    if (!disposed) onHeight(captions.hidden ? 0 : captions.getBoundingClientRect().height)
  }
  function renderCaptions() {
    captions.hidden = !(available && enabled)
    captions.style.fontSize = sizes[size] + 'px'
    captions.textContent = available && enabled ? activeCue(cues, video.currentTime) : ''
    cc.disabled = !available
    cc.setAttribute('aria-pressed', String(available && enabled))
    cc.setAttribute(
      'aria-label',
      available ? (enabled ? 'Turn captions off' : 'Turn captions on') : 'Captions unavailable',
    )
    height()
  }
  function closeMenu() {
    menu.hidden = true
    more.setAttribute('aria-expanded', 'false')
  }
  function refreshMenu() {
    if (!menu.hidden) {
      if (panel === 'cc') captionPanel()
      else if (panel === 'main') mainPanel()
    }
  }
  function mainPanel() {
    panel = 'main'
    menu.replaceChildren()
    more.setAttribute('aria-expanded', String(!menu.hidden))
    button(
      'Caption settings',
      'Captions (CC)  ' + (available ? (enabled ? 'On' : 'Off') : 'Unavailable') + '  ›',
      menu,
      captionPanel,
    )
    button('Playback speed', 'Playback speed  ' + video.playbackRate + 'x  ›', menu, speedPanel)
  }
  function captionPanel() {
    panel = 'cc'
    menu.replaceChildren()
    const back = button('Back to video options', '‹  Captions (CC)', menu, mainPanel)
    back.className = 'lms-divider'
    const label = doc.createElement('label')
    label.className = 'lms-setting'
    label.textContent = available ? 'Enable captions' : 'Captions unavailable'
    const toggle = doc.createElement('input')
    toggle.type = 'checkbox'
    toggle.checked = available && enabled
    toggle.disabled = !available
    toggle.setAttribute('aria-label', 'Enable captions')
    label.append(toggle)
    menu.append(label)
    toggle.addEventListener('change', () => {
      enabled = toggle.checked
      save()
      renderCaptions()
    })
    const title = doc.createElement('div')
    title.className = 'lms-label'
    title.textContent = 'FONT SIZE'
    menu.append(title)
    for (const name of Object.keys(sizes)) {
      const choice = button(
        name + ' caption font',
        name + (name === size ? '   ✓' : ''),
        menu,
        () => {
          size = name
          save()
          renderCaptions()
          captionPanel()
          menu.querySelector('[aria-pressed=true]')?.focus()
        },
      )
      choice.setAttribute('aria-pressed', String(name === size))
      choice.disabled = !available
    }
  }
  function speedPanel() {
    panel = 'speed'
    menu.replaceChildren()
    button('Back to video options', '‹  Playback speed', menu, mainPanel)
    for (const rate of [0.5, 0.75, 1, 1.25, 1.5, 2]) {
      const choice = button(
        rate + 'x playback speed',
        rate + 'x' + (video.playbackRate === rate ? '   ✓' : ''),
        menu,
        () => {
          video.playbackRate = rate
          speedPanel()
          menu.querySelector('[aria-pressed=true]')?.focus()
        },
      )
      choice.setAttribute('aria-pressed', String(video.playbackRate === rate))
    }
  }
  function format(value) {
    if (!Number.isFinite(value)) return '0:00'
    const seconds = Math.max(0, Math.floor(value))
    return Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0')
  }
  function update() {
    icon(play, video.paused ? 'play' : 'pause')
    play.setAttribute('aria-label', video.paused ? 'Play' : 'Pause')
    time.textContent = format(video.currentTime) + ' / ' + format(video.duration)
    seek.max = String(Number.isFinite(video.duration) ? video.duration : 1)
    seek.value = String(video.currentTime)
    seek.disabled = !Number.isFinite(video.duration)
    icon(mute, video.muted || video.volume === 0 ? 'mute' : 'volume')
    mute.setAttribute('aria-label', video.muted ? 'Unmute' : 'Mute')
    volume.value = String(video.volume)
    renderCaptions()
  }
  function seekTo(value) {
    if (Number.isFinite(video.duration))
      video.currentTime = Math.max(0, Math.min(video.duration, constrainSeek(value)))
  }
  listen(seek, 'input', () => seekTo(+seek.value))
  listen(volume, 'input', () => {
    video.volume = +volume.value
    video.muted = false
  })
  for (const event of [
    'timeupdate',
    'seeked',
    'play',
    'pause',
    'ended',
    'volumechange',
    'ratechange',
  ])
    listen(video, event, update)
  for (const event of ['loadedmetadata', 'durationchange'])
    listen(video, event, () => {
      if (
        metadata &&
        Number.isFinite(video.duration) &&
        Math.abs(metadata.duration - video.duration) > 0.15
      ) {
        available = false
        cues = []
        refreshMenu()
      }
      update()
    })
  listen(video, 'waiting', () => showStatus('Buffering…'))
  listen(video, 'playing', () => showStatus(''))
  listen(video, 'error', () => showStatus('Unable to load video. Please reload the lesson.'))
  listen(doc, 'fullscreenchange', () => {
    fullscreen.setAttribute(
      'aria-label',
      doc.fullscreenElement === root ? 'Exit fullscreen' : 'Enter fullscreen',
    )
    height()
  })
  listen(root, 'keydown', (event) => {
    if (event.key === 'Escape') {
      closeMenu()
      more.focus()
      return
    }
    if (/^(INPUT|BUTTON|SELECT|TEXTAREA)$/.test(event.target.tagName)) return
    if (event.key === ' ') {
      event.preventDefault()
      play.click()
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault()
      seekTo(video.currentTime - 10)
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      seekTo(video.currentTime + 10)
    } else if (event.key.toLowerCase() === 'c' && available) {
      cc.click()
    } else if (event.key.toLowerCase() === 'f') {
      fullscreen.click()
    }
  })
  listen(doc, 'pointerdown', (event) => {
    if (!menu.contains(event.target) && !more.contains(event.target)) closeMenu()
  })
  const observer = new ResizeObserver(height)
  observer.observe(captions)
  async function loadCaptions(url) {
    const request = ++generation
    if (abort) abort.abort()
    abort = new AbortController()
    const signal = abort.signal
    available = false
    cues = []
    metadata = null
    renderCaptions()
    refreshMenu()
    try {
      const urls = captionUrls(url)
      if (!urls) return
      const response = await fetch(withCurrentMediaTicket(urls.metadata.href), {
        cache: 'no-store',
        signal,
      })
      if (!response.ok) throw new Error('No metadata')
      const data = await response.json()
      if (
        data.version !== 1 ||
        !/^[a-f0-9]{64}$/.test(data.fingerprint) ||
        !Number.isFinite(data.duration) ||
        data.duration <= 0 ||
        !Number.isInteger(data.cue_count) ||
        data.cue_count <= 0
      )
        throw new Error('Invalid metadata')
      const head = await fetch(withCurrentMediaTicket(url), {
        method: 'HEAD',
        cache: 'no-store',
        signal,
      })
      if (
        !head.ok ||
        +head.headers.get('Content-Length') !== data.video_size ||
        Math.floor(Date.parse(head.headers.get('Last-Modified')) / 1000) !== data.video_mtime
      )
        throw new Error('Stale captions')
      urls.vtt.searchParams.set('v', data.fingerprint)
      const vttResponse = await fetch(withCurrentMediaTicket(urls.vtt.href), {
        cache: 'no-store',
        signal,
      })
      if (!vttResponse.ok) throw new Error('Missing caption file')
      const content = await vttResponse.text()
      const hash = sha256(content)
      if (hash !== data.fingerprint || hash !== data.vtt_sha256)
        throw new Error('Caption integrity mismatch')
      const parsed = parseVtt(content)
      if (
        parsed.length !== data.cue_count ||
        parsed[parsed.length - 1].end > data.duration ||
        (Number.isFinite(video.duration) && Math.abs(data.duration - video.duration) > 0.15)
      )
        throw new Error('Invalid timeline')
      if (disposed || request !== generation) return
      cues = parsed
      metadata = data
      available = true
      renderCaptions()
      refreshMenu()
    } catch (_) {
      if (!disposed && request === generation) {
        available = false
        cues = []
        renderCaptions()
        refreshMenu()
      }
    }
  }
  root.loadCaptions = loadCaptions
  root.disposePlayer = () => {
    disposed = true
    generation++
    if (abort) abort.abort()
    clearTimeout(statusTimer)
    observer.disconnect()
    for (const remove of listeners) remove()
    video.pause()
  }
  update()
  return root
}
export { create, captionUrls, parseVtt, activeCue, sha256 }
