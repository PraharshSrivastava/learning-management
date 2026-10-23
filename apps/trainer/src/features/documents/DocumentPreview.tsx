import { authHeaders, previewFileUrl } from '@lms/shared/api/client'
import { useHasMediaTicket } from '@lms/shared/api/useMediaTicket'
import type { PdfFile } from '@lms/shared/models'
import { useEffect, useRef, useState } from 'react'
import type { PDFDocumentLoadingTask, PDFDocumentProxy, RenderTask } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

const control =
  'rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-[#153c83] disabled:opacity-40'

/** Loads the complete converted PDF once; routine ticket renewal never reloads its bytes. */
export function DocumentPreview(props: {
  file: PdfFile
  onClose: () => void
  onCreateCourse: () => void
  busy?: boolean
}) {
  return <Preview key={props.file.fileName} {...props} />
}

function Preview({
  file,
  onClose,
  onCreateCourse,
  busy,
}: {
  file: PdfFile
  onClose: () => void
  onCreateCourse: () => void
  busy?: boolean
}) {
  const hasTicket = useHasMediaTicket()
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [page, setPage] = useState(1)
  const [input, setInput] = useState('1')
  const [zoom, setZoom] = useState('fit')
  const [width, setWidth] = useState(600)
  const viewport = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!hasTicket) return
    const abort = new AbortController()
    let active = true
    let task: PDFDocumentLoadingTask | undefined
    void (async () => {
      try {
        await Promise.resolve()
        if (!active) return
        setDocument(null)
        setError('')
        const response = await fetch(previewFileUrl(file.fileName), {
          headers: authHeaders(),
          credentials: 'include',
          signal: abort.signal,
        })
        if (!response.ok)
          throw new Error('Unable to open this document. Please retry or sign in again.')
        const bytes = await response.arrayBuffer()
        if (!active) return
        const { getDocument, GlobalWorkerOptions } = await import('pdfjs-dist')
        if (!active) return
        // Browsers cached this worker for a year while nginx served it with the wrong type;
        // the query makes them fetch the corrected copy.
        GlobalWorkerOptions.workerSrc = `${workerUrl}?type=js`
        task = getDocument({
          data: new Uint8Array(bytes),
          cMapUrl: new URL('./static/pdf-support/cmaps/', globalThis.document.baseURI).href,
          cMapPacked: true,
          standardFontDataUrl: new URL(
            './static/pdf-support/standard_fonts/',
            globalThis.document.baseURI,
          ).href,
          wasmUrl: new URL('./static/pdf-support/wasm/', globalThis.document.baseURI).href,
        })
        const pdf = await task.promise
        if (active) setDocument(pdf)
      } catch (e) {
        if (active)
          setError(
            e instanceof Error && e.message.includes('Unable to open')
              ? e.message
              : 'The PDF preview could not be loaded. Please try again.',
          )
      }
    })()
    return () => {
      active = false
      abort.abort()
      void task?.destroy()
    }
  }, [file.fileName, hasTicket, attempt])
  useEffect(() => {
    const node = viewport.current
    if (!node) return
    const measure = () => setWidth(Math.max(180, node.clientWidth - 40))
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  const trackPage = () => {
    const node = viewport.current
    if (!node) return
    const pages = [...node.querySelectorAll<HTMLElement>('[data-page]')]
    const current = pages.find(
      (element) => element.offsetTop + element.offsetHeight > node.scrollTop + 24,
    )
    if (current) {
      const number = Number(current.dataset.page)
      setPage(number)
      setInput(String(number))
    }
  }
  const jump = (value: number) => {
    const next = Math.min(document?.numPages || 1, Math.max(1, Math.trunc(value) || 1))
    setPage(next)
    setInput(String(next))
    const node = viewport.current?.querySelector<HTMLElement>(`[data-page="${next}"]`)
    if (node && viewport.current) viewport.current.scrollTop = node.offsetTop - 16
  }
  return (
    <section
      className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-slate-50"
      aria-label={`Preview of ${file.displayName}`}
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white p-4">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-medium">{file.displayName}</h3>
          <p className="mt-1 text-xs text-slate-500">
            {document ? `${document.numPages} pages` : 'Complete document'} · Read-only preview
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={control} disabled={busy} onClick={onCreateCourse}>
            Create course
          </button>
          <button type="button" className={control} onClick={onClose}>
            Close preview
          </button>
        </div>
      </header>
      <div
        className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-4 py-3"
        aria-label="PDF controls"
      >
        <button
          type="button"
          className={control}
          disabled={!document || page <= 1}
          onClick={() => jump(page - 1)}
        >
          Previous page
        </button>
        <form
          className="flex items-center gap-2 text-xs"
          onSubmit={(event) => {
            event.preventDefault()
            jump(Number(input))
          }}
        >
          <label htmlFor={`page-${file.documentId}`}>Page</label>
          <input
            id={`page-${file.documentId}`}
            aria-label="PDF page number"
            type="number"
            min="1"
            max={document?.numPages || 1}
            disabled={!document}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onBlur={() => jump(Number(input))}
            className="w-14 rounded-lg border border-slate-200 p-2 text-center"
          />
          <span>of {document?.numPages ?? '—'}</span>
        </form>
        <button
          type="button"
          className={control}
          disabled={!document || page >= document.numPages}
          onClick={() => jump(page + 1)}
        >
          Next page
        </button>
        <button
          type="button"
          aria-label="Zoom out"
          className={control}
          disabled={!document || zoom === '75'}
          onClick={() => setZoom(String(Math.max(75, (zoom === 'fit' ? 100 : Number(zoom)) - 25)))}
        >
          −
        </button>
        <label className="text-xs">
          Zoom{' '}
          <select
            aria-label="PDF zoom"
            className={`${control} ml-2`}
            value={zoom}
            onChange={(event) => setZoom(event.target.value)}
          >
            <option value="fit">Fit width</option>
            {['75', '100', '125', '150'].map((value) => (
              <option key={value} value={value}>
                {value}%
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          aria-label="Zoom in"
          className={control}
          disabled={!document || zoom === '150'}
          onClick={() => setZoom(String(Math.min(150, (zoom === 'fit' ? 100 : Number(zoom)) + 25)))}
        >
          +
        </button>
        <button type="button" className={control} onClick={() => setZoom('fit')}>
          Fit width
        </button>
      </div>
      <div
        ref={viewport}
        onScroll={trackPage}
        tabIndex={0}
        aria-label="PDF document pages"
        className="relative h-[480px] overflow-auto p-4 md:h-[530px]"
      >
        {error ? (
          <div
            role="alert"
            className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
          >
            {error}{' '}
            <button
              type="button"
              className={control}
              onClick={() => {
                setDocument(null)
                setAttempt((value) => value + 1)
              }}
            >
              Try again
            </button>
            <button
              type="button"
              className={`${control} ml-2`}
              onClick={() =>
                window.open(previewFileUrl(file.fileName), '_blank', 'noopener,noreferrer')
              }
            >
              Open document
            </button>
          </div>
        ) : !document || !hasTicket ? (
          <p role="status" className="text-sm text-blue-800">
            {hasTicket ? 'Loading complete document…' : 'Preparing secure preview…'}
          </p>
        ) : (
          Array.from({ length: document.numPages }, (_, index) => (
            <PdfPage
              key={index}
              pdf={document}
              pageNumber={index + 1}
              width={width}
              zoom={zoom}
              root={viewport}
            />
          ))
        )}
      </div>
      {document && (
        <p className="border-t border-slate-200 px-4 py-3 text-xs text-slate-500">
          Complete document · {document.numPages} pages · Scroll to review all pages
        </p>
      )}
    </section>
  )
}

function PdfPage({
  pdf,
  pageNumber,
  width,
  zoom,
  root,
}: {
  pdf: PDFDocumentProxy
  pageNumber: number
  width: number
  zoom: string
  root: React.RefObject<HTMLDivElement | null>
}) {
  const container = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const [visible, setVisible] = useState(false)
  const [height, setHeight] = useState(width * 1.414)
  const [pageWidth, setPageWidth] = useState(width)
  const [text, setText] = useState('')
  const [error, setError] = useState(false)
  useEffect(() => {
    const node = container.current
    if (!node) return
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(Boolean(entry?.isIntersecting)),
      { root: root.current, rootMargin: '600px' },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [root])
  useEffect(() => {
    let active = true
    let render: RenderTask | undefined
    void (async () => {
      try {
        const page = await pdf.getPage(pageNumber)
        if (!active) return
        const base = page.getViewport({ scale: 1 })
        const scale = zoom === 'fit' ? width / base.width : Number(zoom) / 100
        const display = page.getViewport({ scale })
        setHeight(display.height)
        setPageWidth(display.width)
        if (!visible || !canvas.current) return
        const ratio = Math.min(globalThis.devicePixelRatio || 1, 2)
        const target = canvas.current
        target.width = Math.ceil(display.width * ratio)
        target.height = Math.ceil(display.height * ratio)
        render = page.render({
          canvas: target,
          viewport: display,
          transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
        })
        await render.promise
        const content = await page.getTextContent()
        if (active) {
          setText(content.items.map((item) => ('str' in item ? item.str : '')).join(' '))
          setError(false)
        }
      } catch (e) {
        if (active && !(e instanceof Error && e.name === 'RenderingCancelledException'))
          setError(true)
      }
    })()
    return () => {
      active = false
      render?.cancel()
    }
  }, [pdf, pageNumber, width, zoom, visible])
  return (
    <div
      ref={container}
      data-page={pageNumber}
      className="relative mx-auto mb-4 bg-white shadow-sm"
      style={{ width: pageWidth, minHeight: height }}
      role="group"
      aria-label={`Page ${pageNumber}`}
    >
      {visible && (
        <canvas
          ref={canvas}
          style={{ width: pageWidth, height }}
          role="img"
          aria-label={`PDF page ${pageNumber}`}
        />
      )}
      <span className="sr-only">{text}</span>
      {error && (
        <p role="alert" className="p-4 text-sm text-red-800">
          Unable to render page {pageNumber}. Close the preview and try again.
        </p>
      )}
    </div>
  )
}
