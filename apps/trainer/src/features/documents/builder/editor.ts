// Port of DocumentHtmlEditorController (document_html_editor.dart).
// The editor is a plain contenteditable element that React never renders into.
import { imageBlock, moduleOnly, textBlock, type BuilderBlock } from './models'

const STYLE_ID = 'document-builder-editor-styles'
const STYLE_TEXT = `
figure.editor-image.selected img {
  outline: 2px solid #0b2f86;
  outline-offset: 2px;
}
figure.editor-image figcaption {
  border: 1px dashed #9aa8bd;
  border-radius: 6px;
  background: #f8fafc;
  color: #334155;
  margin-top: 8px;
  padding: 8px 10px;
  min-height: 20px;
}
figure.editor-image figcaption:empty::before {
  content: attr(data-placeholder);
  color: #8a96aa;
}
`
const MOVE_TYPE = 'application/x-editor-image'

function installEditorStyles(): void {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = STYLE_TEXT
  document.head.append(style)
}

function emptyParagraph(): HTMLParagraphElement {
  const p = document.createElement('p')
  p.append(document.createElement('br'))
  return p
}

const nodeText = (node: Node | null): string =>
  (node?.textContent ?? '').replaceAll(' ', ' ').trim()

function readDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '')
    reader.onerror = () => reject(reader.error ?? new Error('Could not read image'))
    reader.readAsDataURL(file)
  })
}

const isImage = (file: File) => file.type.startsWith('image/')

/** Caret range at a viewport point. Chrome and Safari have caretRangeFromPoint, Firefox has caretPositionFromPoint. */
function caretRangeAt(x: number, y: number): Range | null {
  const doc = document as Document & {
    caretRangeFromPoint?: (x: number, y: number) => Range | null
    caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null
  }
  if (doc.caretRangeFromPoint) return doc.caretRangeFromPoint(x, y)
  const position = doc.caretPositionFromPoint?.(x, y)
  if (!position) return null
  const range = document.createRange()
  range.setStart(position.offsetNode, position.offset)
  range.collapse(true)
  return range
}

export class DocumentEditor {
  readonly root: HTMLDivElement
  private readonly listeners = new Set<() => void>()
  private selectedFigure: HTMLElement | null = null
  private savedSelection: Range | null = null

  constructor() {
    installEditorStyles()
    const root = document.createElement('div')
    root.contentEditable = 'true'
    root.tabIndex = 0
    root.setAttribute('aria-label', 'Rich document editor')
    Object.assign(root.style, {
      height: '100%',
      overflowY: 'auto',
      padding: '18px',
      outline: 'none',
      fontFamily: 'Inter, Arial, sans-serif',
      fontSize: '14px',
      lineHeight: '1.5',
      backgroundColor: 'white',
    })
    root.addEventListener('input', () => this.changed())
    root.addEventListener('keyup', () => this.saveSelection())
    root.addEventListener('mouseup', () => this.saveSelection())
    root.addEventListener('focus', () => this.saveSelection())
    root.addEventListener('click', (event) => {
      if ((event.target as Node | null)?.parentNode !== this.selectedFigure) {
        this.selectedFigure?.classList.remove('selected')
        this.selectedFigure = null
      }
    })
    root.addEventListener('paste', (event) => void this.paste(event))
    root.addEventListener('dragover', (event) => event.preventDefault())
    root.addEventListener('drop', (event) => void this.drop(event))
    root.append(emptyParagraph())
    this.root = root
  }

  /** Calls `listener` after each change. Returns a function that stops it. */
  listen(listener: () => void): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private changed(): void {
    for (const listener of this.listeners) listener()
  }

  private saveSelection(): void {
    const selection = window.getSelection()
    if (selection && selection.rangeCount > 0) {
      const range = selection.getRangeAt(0)
      if (this.root.contains(range.commonAncestorContainer)) {
        this.savedSelection = range.cloneRange()
      }
    }
  }

  private restoreSelection(): void {
    this.root.focus()
    const selection = window.getSelection()
    if (!selection) return
    selection.removeAllRanges()
    if (this.savedSelection) selection.addRange(this.savedSelection)
  }

  /** Text and image blocks in document order. */
  get blocks(): BuilderBlock[] {
    const result: BuilderBlock[] = []
    for (const node of Array.from(this.root.childNodes)) this.collect(node, result)
    return result
  }

  /** Text blocks joined by blank lines. Images are left out. */
  get text(): string {
    return this.blocks
      .filter((block) => block.type === 'text')
      .map((block) => block.text)
      .join('\n\n')
      .trim()
  }

  private collect(node: Node, result: BuilderBlock[]): void {
    if (node.nodeType === Node.TEXT_NODE) {
      const clean = nodeText(node)
      if (clean) result.push(textBlock(clean))
      return
    }
    if (!(node instanceof Element)) return
    if (node.classList.contains('image-popover')) return
    if (node.localName === 'figure' && node.classList.contains('editor-image')) {
      const image = node.querySelector('img')
      const src = image?.src ?? ''
      if (src) {
        const element = node as HTMLElement
        const width = Number.parseInt(element.dataset.width ?? '60', 10)
        result.push(
          imageBlock(
            src,
            Number.isNaN(width) ? 60 : width,
            element.dataset.align ?? 'left',
            nodeText(node.querySelector('figcaption')),
          ),
        )
      }
      return
    }
    if (node.querySelector('figure.editor-image')) {
      for (const child of Array.from(node.childNodes)) this.collect(child, result)
      return
    }
    const clean = nodeText(node)
    if (clean) result.push(textBlock(clean))
  }

  /** Replaces the draft with AI text. With `preserveImages`, images move to the end. */
  setText(value: string, { preserveImages = false } = {}): void {
    const images = preserveImages ? this.blocks.filter((block) => block.type === 'image') : []
    this.root.replaceChildren()
    this.selectedFigure = null
    this.savedSelection = null
    for (const part of moduleOnly(value)
      .split(/\n{2,}/)
      .map((item) => item.trim())
      .filter(Boolean)) {
      const p = document.createElement('p')
      p.textContent = part
      this.root.append(p)
    }
    for (const image of images) {
      this.root.append(this.figure(image.src, image.width, image.align, image.caption))
    }
    this.changed()
  }

  /** Builds the figure with its hidden resize, align, and delete controls. */
  figure(src: string, width = 60, align = 'left', caption = ''): HTMLElement {
    const figure = document.createElement('figure')
    figure.classList.add('editor-image', `align-${align}`)
    figure.contentEditable = 'false'
    figure.draggable = false
    figure.dataset.width = String(width)
    figure.dataset.align = align
    Object.assign(figure.style, { position: 'relative', margin: '12px 0', paddingTop: '36px' })

    const controls = document.createElement('div')
    controls.classList.add('image-popover')
    Object.assign(controls.style, {
      display: 'none',
      position: 'absolute',
      top: '0',
      left: '0',
      zIndex: '2',
      backgroundColor: 'white',
      border: '1px solid #dbe3ef',
      padding: '5px',
    })
    const slider = document.createElement('input')
    slider.type = 'range'
    slider.min = '25'
    slider.max = '100'
    slider.value = String(width)
    slider.title = 'Resize image'
    slider.draggable = false
    slider.style.width = '110px'
    const select = document.createElement('select')
    select.title = 'Align image'
    select.draggable = false
    for (const value of ['left', 'center', 'right']) select.append(new Option(value, value))
    select.value = align
    const remove = document.createElement('button')
    remove.type = 'button'
    remove.textContent = 'Delete'
    remove.draggable = false
    remove.style.marginLeft = '6px'
    remove.style.color = '#9b1c1c'

    const image = document.createElement('img')
    image.src = src
    image.alt = ''
    image.draggable = true
    Object.assign(image.style, { width: `${width}%`, maxWidth: '100%', display: 'block' })

    const cap = document.createElement('figcaption')
    cap.contentEditable = 'true'
    cap.textContent = caption
    cap.setAttribute('data-placeholder', 'Caption')
    Object.assign(cap.style, {
      fontSize: '12px',
      color: '#64748b',
      minHeight: '20px',
      boxSizing: 'border-box',
    })

    const stop = (event: Event) => event.stopPropagation()
    for (const element of [controls, slider, select, remove]) {
      element.addEventListener('mousedown', stop)
      element.addEventListener('click', stop)
      element.addEventListener('dragstart', (event) => event.preventDefault())
    }
    slider.addEventListener('input', () => {
      const next = slider.value || '60'
      figure.dataset.width = next
      image.style.width = `${next}%`
      this.changed()
    })
    select.addEventListener('change', () => {
      const next = select.value || 'left'
      figure.classList.remove('align-left', 'align-center', 'align-right')
      figure.classList.add(`align-${next}`)
      figure.dataset.align = next
      applyAlignment(figure, next)
      this.changed()
    })
    remove.addEventListener('click', () => {
      if (this.selectedFigure === figure) this.selectedFigure = null
      figure.remove()
      this.changed()
    })
    cap.addEventListener('input', () => this.changed())
    cap.addEventListener('focus', () => this.select(figure))

    controls.append(slider, select, remove)
    figure.append(controls, image, cap)
    applyAlignment(figure, align)
    figure.addEventListener('click', (event) => {
      event.stopPropagation()
      this.select(figure)
    })
    image.addEventListener('dragstart', (event) => {
      event.stopPropagation()
      event.dataTransfer?.setData(MOVE_TYPE, 'move')
      if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
      this.selectedFigure = figure
    })
    return figure
  }

  private select(figure: HTMLElement): void {
    this.selectedFigure?.classList.remove('selected')
    this.selectedFigure = figure
    figure.classList.add('selected')
    const controls = figure.querySelector<HTMLElement>('.image-popover')
    if (controls) controls.style.display = 'block'
    for (const other of Array.from(this.root.querySelectorAll('figure.editor-image'))) {
      if (other !== figure) {
        other.classList.remove('selected')
        const popover = other.querySelector<HTMLElement>('.image-popover')
        if (popover) popover.style.display = 'none'
      }
    }
  }

  /** The direct child of root that holds `node`. */
  private topLevel(node: Node): Element | null {
    let current: Element | null =
      node instanceof Element ? node : node.parentNode instanceof Element ? node.parentNode : null
    while (current && current.parentNode !== this.root) {
      const parent: Node | null = current.parentNode
      current = parent instanceof Element ? parent : null
    }
    return current?.parentNode === this.root ? current : null
  }

  private placeCaret(node: Node): void {
    const range = document.createRange()
    range.setStart(node, 0)
    range.collapse(true)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    this.savedSelection = range.cloneRange()
  }

  /** Inserts (or moves) a figure at the saved caret, then adds an empty paragraph after it. */
  insertFigure(figure: HTMLElement): void {
    this.restoreSelection()
    const selection = window.getSelection()
    const range = selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null
    if (!range || !this.root.contains(range.commonAncestorContainer)) {
      this.root.append(figure)
    } else if (range.commonAncestorContainer === this.root) {
      const reference = this.root.childNodes[range.startOffset] ?? null
      this.root.insertBefore(figure, reference)
    } else {
      const anchor = this.topLevel(range.startContainer)
      if (anchor && anchor !== figure) anchor.insertAdjacentElement('afterend', figure)
      else this.root.append(figure)
    }
    const spacer = emptyParagraph()
    figure.insertAdjacentElement('afterend', spacer)
    this.placeCaret(spacer)
    this.changed()
  }

  /** Reads image files in order and inserts each one. Other files are ignored. */
  async insertFiles(files: Iterable<File>): Promise<void> {
    for (const file of Array.from(files).filter(isImage)) {
      this.insertFigure(this.figure(await readDataUrl(file)))
    }
  }

  private async paste(event: ClipboardEvent): Promise<void> {
    const images = Array.from(event.clipboardData?.files ?? []).filter(isImage)
    if (images.length === 0) return
    event.preventDefault()
    await this.insertFiles(images)
  }

  private moveCaret(x: number, y: number): void {
    const range = caretRangeAt(Math.round(x), Math.round(y))
    if (!range || !this.root.contains(range.commonAncestorContainer)) return
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    this.savedSelection = range.cloneRange()
  }

  private async drop(event: DragEvent): Promise<void> {
    const moving = this.selectedFigure
    const transfer = event.dataTransfer
    const files = Array.from(transfer?.files ?? [])
    event.preventDefault()
    this.moveCaret(event.clientX, event.clientY)
    if (moving && transfer?.getData(MOVE_TYPE) === 'move') {
      this.insertFigure(moving)
      return
    }
    await this.insertFiles(files)
  }

  dispose(): void {
    this.root.remove()
  }
}

/** Aligns the image and caption with margins. The figure itself does not move. */
function applyAlignment(figure: HTMLElement, align: string): void {
  const left = align === 'center' || align === 'right' ? 'auto' : '0'
  const right = align === 'center' || align === 'left' ? 'auto' : '0'
  for (const item of Array.from(figure.querySelectorAll<HTMLElement>('img,figcaption'))) {
    item.style.marginLeft = left
    item.style.marginRight = right
  }
}
