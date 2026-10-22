import { useRef, useState, type ReactNode } from 'react'
import { id, type Module, type TextBlock } from './workflow'
const input = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900'
const button =
  'rounded border border-slate-200 px-3 py-1 text-xs font-semibold text-primary-blue disabled:opacity-40'
export function replaceTextPreservingMarks(block: TextBlock, text: string): TextBlock {
  const before = Array.from(block.text),
    after = Array.from(text)
  let start = 0,
    end = before.length,
    nextEnd = after.length
  while (start < end && start < nextEnd && before[start] === after[start]) start++
  while (end > start && nextEnd > start && before[end - 1] === after[nextEnd - 1]) {
    end--
    nextEnd--
  }
  const delta = nextEnd - end
  const marks = block.marks
    .map((mark) => {
      if (mark.end < start || (mark.end === start && start !== end)) return mark
      if (mark.start >= end && !(start === end && mark.start < start))
        return { ...mark, start: mark.start + delta, end: mark.end + delta }
      return {
        ...mark,
        start: Math.min(mark.start, start),
        end: mark.end >= end ? mark.end + delta : nextEnd,
      }
    })
    .filter((mark) => mark.end > mark.start && mark.end <= after.length)
  return { ...block, text, marks }
}
export function toggleMark(
  block: TextBlock,
  start: number,
  end: number,
  type: 'bold' | 'italic' | 'link',
  href?: string,
): TextBlock {
  if (start >= end) return block
  if (type === 'link' && (!href || !/^(https?:\/\/|mailto:)/i.test(href)))
    throw new Error('Use an https://, http:// or mailto: link.')
  if (href) href = href.replace(/^[a-z]+:/i, (scheme) => scheme.toLowerCase())
  const covered = block.marks.some((m) => m.type === type && m.start <= start && m.end >= end)
  const marks = block.marks.flatMap((m) =>
    m.type !== type || m.end <= start || m.start >= end
      ? [m]
      : [
          ...(m.start < start ? [{ ...m, end: start }] : []),
          ...(m.end > end ? [{ ...m, start: end }] : []),
        ],
  )
  if (!covered || type === 'link') marks.push({ start, end, type, ...(href ? { href } : {}) })
  return { ...block, marks }
}
function FormattedText({ block }: { block: TextBlock }) {
  const chars = Array.from(block.text),
    points = [...new Set([0, chars.length, ...block.marks.flatMap((m) => [m.start, m.end])])].sort(
      (a, b) => a - b,
    )
  return (
    <div
      data-testid="formatted-preview"
      aria-label="Formatted preview"
      className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-3 text-sm"
    >
      {points.slice(0, -1).map((start, i) => {
        const end = points[i + 1] || start
        let node: ReactNode = chars.slice(start, end).join('')
        for (const mark of block.marks.filter((m) => m.start <= start && m.end >= end)) {
          if (mark.type === 'bold') node = <strong>{node}</strong>
          if (mark.type === 'italic') node = <em>{node}</em>
          if (mark.type === 'link' && mark.href && /^(https?:\/\/|mailto:)/i.test(mark.href))
            node = (
              <a
                className="text-blue-700 underline"
                href={mark.href}
                target="_blank"
                rel="noopener noreferrer"
              >
                {node}
              </a>
            )
        }
        return <span key={start}>{node}</span>
      })}
    </div>
  )
}
export function TextBlockEditor({
  block,
  onChange,
  onSelect,
}: {
  block: TextBlock
  onChange: (block: TextBlock) => void
  onSelect: (start: number, end: number) => void
}) {
  const range = useRef({ start: 0, end: 0 })
  const [href, setHref] = useState('https://')
  const [error, setError] = useState('')
  const [hasSelection, setHasSelection] = useState(false)
  const format = (type: 'bold' | 'italic' | 'link') => {
    try {
      onChange(
        toggleMark(
          block,
          range.current.start,
          range.current.end,
          type,
          type === 'link' ? href : undefined,
        ),
      )
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Invalid format')
    }
  }
  return (
    <>
      <div role="toolbar" aria-label="Text formatting" className="mb-2 flex flex-wrap gap-2">
        <button
          type="button"
          className={button}
          disabled={!hasSelection}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => format('bold')}
        >
          Bold
        </button>
        <button
          type="button"
          className={button}
          disabled={!hasSelection}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => format('italic')}
        >
          Italic
        </button>
        <details className="text-xs">
          <summary className="cursor-pointer rounded border border-slate-200 px-3 py-1 font-semibold text-primary-blue">
            Link
          </summary>
          <div className="mt-2 flex gap-2">
            <input
              className="min-w-0 rounded border border-slate-200 px-2 text-xs"
              aria-label="Link URL"
              value={href}
              onChange={(e) => setHref(e.target.value)}
            />
            <button
              type="button"
              className={button}
              disabled={!hasSelection}
              onClick={() => format('link')}
            >
              Apply link
            </button>
          </div>
        </details>
      </div>
      <textarea
        aria-label={`${block.type} text`}
        className={`${input} min-h-28 ${block.type === 'heading' ? '!text-lg !font-bold' : ''}`}
        value={block.text}
        onChange={(e) => onChange(replaceTextPreservingMarks(block, e.target.value))}
        onSelect={(e) => {
          const { selectionStart: start, selectionEnd: end } = e.currentTarget
          range.current = {
            start: Array.from(block.text.slice(0, start)).length,
            end: Array.from(block.text.slice(0, end)).length,
          }
          setHasSelection(start !== end)
          onSelect(start, end)
        }}
      />
      {error && <p role="alert">{error}</p>}
      {block.marks.length > 0 && <FormattedText block={block} />}
    </>
  )
}
const refs = (modules: Module[]) => {
  const values = modules.flatMap((m) => [
    ...m.sourceReferences,
    ...m.blocks.flatMap((b) => b.sourceReferences),
  ])
  return [...new Map(values.map((v) => [JSON.stringify(v), v])).values()]
}
export const isEmptyModule = (module: Module) =>
  module.blocks.every((b) => 'text' in b && !b.text.trim())
export function splitModule(module: Module, boundary: number): [Module, Module] {
  if (boundary < 1 || boundary >= module.blocks.length)
    throw new Error('Choose a boundary between content blocks.')
  const left: Module = { ...module, blocks: module.blocks.slice(0, boundary) },
    right: Module = {
      ...module,
      id: id(),
      title: `${module.title} — continued`,
      blocks: module.blocks.slice(boundary),
      sourceReferences: [...module.sourceReferences],
    }
  right.sourceReferences = refs([right])
  // Keep module-level evidence that is not attached to individual blocks.
  left.sourceReferences = refs([left])
  return [left, right]
}
export function mergeModules(left: Module, right: Module): Module {
  return {
    ...left,
    blocks: [...left.blocks, ...right.blocks],
    sections: [...left.sections, ...right.sections],
    sourceReferences: refs([left, right]),
  }
}
