import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react'

interface Thumb {
  left: number
  width: number
}

/**
 * Flutter `Scrollbar(thumbVisibility: true)` over a horizontal scroll view. The thumb (8 px,
 * 2 px from the edges) floats over the content, so the panels keep their full height.
 */
export function HorizontalScroller({ children }: { children: ReactNode }) {
  const viewport = useRef<HTMLDivElement>(null)
  const [thumb, setThumb] = useState<Thumb | null>(null)
  const drag = useRef<{ x: number; scroll: number } | null>(null)

  useEffect(() => {
    const element = viewport.current
    if (!element) return
    const update = () => {
      const { clientWidth, scrollWidth, scrollLeft } = element
      if (scrollWidth <= clientWidth + 0.5) {
        setThumb(null)
        return
      }
      const track = clientWidth - 4
      const width = Math.max(18, (track * clientWidth) / scrollWidth)
      const left = 2 + ((track - width) * scrollLeft) / (scrollWidth - clientWidth)
      setThumb({ left, width })
    }
    update()
    const observer = new ResizeObserver(update)
    observer.observe(element)
    if (element.firstElementChild) observer.observe(element.firstElementChild)
    element.addEventListener('scroll', update, { passive: true })
    return () => {
      observer.disconnect()
      element.removeEventListener('scroll', update)
    }
  }, [])

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (!viewport.current) return
    event.currentTarget.setPointerCapture(event.pointerId)
    drag.current = { x: event.clientX, scroll: viewport.current.scrollLeft }
  }
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const element = viewport.current
    if (!drag.current || !element || !thumb) return
    const track = element.clientWidth - 4
    const ratio = (element.scrollWidth - element.clientWidth) / (track - thumb.width)
    element.scrollLeft = drag.current.scroll + (event.clientX - drag.current.x) * ratio
  }
  const onPointerUp = () => {
    drag.current = null
  }

  return (
    <div className="relative h-full min-h-0">
      <div
        ref={viewport}
        className="h-full overflow-x-auto overflow-y-hidden [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {children}
      </div>
      {thumb && (
        <div
          aria-hidden
          data-testid="builder-scroll-thumb"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          className="absolute bottom-0.5 h-2 touch-none rounded-full bg-[#1a1b20]/10 hover:bg-[#1a1b20]/20"
          style={{ left: thumb.left, width: thumb.width }}
        />
      )}
    </div>
  )
}
