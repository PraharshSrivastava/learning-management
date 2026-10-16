export interface CaptionCue {
  start: number
  end: number
  text: string
}
export interface CaptionPlayer extends HTMLDivElement {
  loadCaptions(url: string): Promise<void>
  disposePlayer(): void
}
export function create(
  video: HTMLVideoElement,
  onHeight: (height: number) => void,
  constrainSeek: (seconds: number) => number,
): CaptionPlayer
export function captionUrls(url: string): { metadata: URL; vtt: URL } | null
export function parseVtt(content: string): CaptionCue[]
export function activeCue(cues: CaptionCue[], seconds: number): string
export function sha256(content: string): string
