import { afterEach, describe, expect, it, vi } from 'vitest'
import { DocumentEditor } from './editor'

let editor: DocumentEditor

function mount() {
  editor = new DocumentEditor()
  document.body.append(editor.root)
  return editor
}

afterEach(() => editor.dispose())

const html = () => editor.root.innerHTML

describe('DocumentEditor', () => {
  it('starts with one empty paragraph and no blocks', () => {
    mount()
    expect(html()).toBe('<p><br></p>')
    expect(editor.blocks).toEqual([])
    expect(editor.text).toBe('')
    expect(editor.root.contentEditable).toBe('true')
    expect(document.getElementById('document-builder-editor-styles')).not.toBeNull()
  })

  it('setText writes one paragraph per blank-line part and drops text before Module 1', () => {
    mount()
    const changed = vi.fn()
    editor.listen(changed)
    editor.setText('Here you go:\n\nModule 1: Intro\nLine two\n\n\n\nModule 2: Next')
    expect(html()).toBe('<p>Module 1: Intro\nLine two</p><p>Module 2: Next</p>')
    expect(editor.text).toBe('Module 1: Intro\nLine two\n\nModule 2: Next')
    expect(changed).toHaveBeenCalledTimes(1)
  })

  it('reads typed text, nested blocks, and non-breaking spaces', () => {
    mount()
    editor.root.innerHTML =
      '<p>One&nbsp;two</p>loose text<div><figure class="editor-image" data-width="40" data-align="right"><img src="data:image/png;base64,AA"><figcaption>Cap</figcaption></figure></div><p> </p>'
    expect(editor.blocks).toEqual([
      { type: 'text', text: 'One two', src: '', width: 60, align: 'left', caption: '' },
      { type: 'text', text: 'loose text', src: '', width: 60, align: 'left', caption: '' },
      {
        type: 'image',
        text: '',
        src: 'data:image/png;base64,AA',
        width: 40,
        align: 'right',
        caption: 'Cap',
      },
    ])
    expect(editor.text).toBe('One two\n\nloose text')
  })

  it('builds the figure HTML with hidden controls', () => {
    mount()
    const figure = editor.figure('data:image/png;base64,AA', 50, 'center', 'Hello')
    expect(figure.className).toBe('editor-image align-center')
    expect(figure.contentEditable).toBe('false')
    expect(figure.dataset).toMatchObject({ width: '50', align: 'center' })
    const popover = figure.querySelector<HTMLElement>('.image-popover')!
    expect(popover.style.display).toBe('none')
    expect(popover.querySelector('input')).toMatchObject({
      type: 'range',
      min: '25',
      max: '100',
      value: '50',
    })
    expect(popover.querySelector('select')!.value).toBe('center')
    expect(popover.querySelector('button')!.textContent).toBe('Delete')
    const image = figure.querySelector('img')!
    expect(image.style.width).toBe('50%')
    expect(image.style.marginLeft).toBe('auto')
    expect(image.style.marginRight).toBe('auto')
    expect(figure.querySelector('figcaption')!.textContent).toBe('Hello')
  })

  it('selects a figure on click and shows only its popover', () => {
    mount()
    editor.setText('Module 1: A')
    const first = editor.figure('data:image/png;base64,AA')
    const second = editor.figure('data:image/png;base64,BB')
    editor.root.append(first, second)
    first.click()
    expect(first.classList.contains('selected')).toBe(true)
    expect(first.querySelector<HTMLElement>('.image-popover')!.style.display).toBe('block')
    second.click()
    expect(first.classList.contains('selected')).toBe(false)
    expect(first.querySelector<HTMLElement>('.image-popover')!.style.display).toBe('none')
    expect(second.classList.contains('selected')).toBe(true)
    editor.root.querySelector('p')!.click()
    expect(second.classList.contains('selected')).toBe(false)
  })

  it('resizes, aligns, and deletes a figure from its popover', () => {
    mount()
    const changed = vi.fn()
    editor.listen(changed)
    const figure = editor.figure('data:image/png;base64,AA')
    editor.root.append(figure)
    const slider = figure.querySelector('input')!
    slider.value = '80'
    slider.dispatchEvent(new Event('input'))
    expect(figure.dataset.width).toBe('80')
    expect(figure.querySelector('img')!.style.width).toBe('80%')

    const select = figure.querySelector('select')!
    select.value = 'right'
    select.dispatchEvent(new Event('change'))
    expect(figure.className).toBe('editor-image align-right')
    expect(figure.querySelector('img')!.style.marginLeft).toBe('auto')
    expect(figure.querySelector('img')!.style.marginRight).toBe('0px')
    expect(editor.blocks[0]).toMatchObject({ width: 80, align: 'right' })

    figure.querySelector('button')!.click()
    expect(editor.root.contains(figure)).toBe(false)
    expect(changed).toHaveBeenCalledTimes(3)
  })

  it('keeps images at the end when AI text replaces the draft', () => {
    mount()
    editor.root.append(editor.figure('data:image/png;base64,AA', 30, 'left', 'Kept'))
    editor.setText('Module 1: New', { preserveImages: true })
    expect(editor.blocks.map((block) => block.type)).toEqual(['text', 'image'])
    expect(editor.blocks[1]).toMatchObject({ width: 30, caption: 'Kept' })
    editor.setText('Module 1: Only text')
    expect(editor.blocks.map((block) => block.type)).toEqual(['text'])
  })

  it('inserts a figure after the paragraph with the caret and adds an empty paragraph', () => {
    mount()
    editor.setText('Module 1: A\n\nModule 2: B')
    // The user is typing, so the editor has focus before the caret moves.
    editor.root.focus()
    const first = editor.root.querySelector('p')!
    const range = document.createRange()
    range.setStart(first.firstChild!, 3)
    range.collapse(true)
    window.getSelection()!.removeAllRanges()
    window.getSelection()!.addRange(range)
    editor.root.dispatchEvent(new Event('keyup'))
    const figure = editor.figure('data:image/png;base64,AA')
    editor.insertFigure(figure)
    const children = Array.from(editor.root.children).map((node) => node.localName)
    expect(children).toEqual(['p', 'figure', 'p', 'p'])
    expect(figure.nextElementSibling!.innerHTML).toBe('<br>')
  })

  it('appends a figure when there is no caret, and reads only image files', async () => {
    mount()
    window.getSelection()!.removeAllRanges()
    await editor.insertFiles([
      new File(['x'], 'notes.txt', { type: 'text/plain' }),
      new File(['png'], 'a.png', { type: 'image/png' }),
    ])
    const figures = editor.root.querySelectorAll('figure.editor-image')
    expect(figures).toHaveLength(1)
    expect(figures[0]!.querySelector('img')!.src).toMatch(/^data:image\/png;base64,/)
  })

  it('stops calling a listener after it unsubscribes', () => {
    mount()
    const changed = vi.fn()
    const stop = editor.listen(changed)
    stop()
    editor.setText('Module 1: A')
    expect(changed).not.toHaveBeenCalled()
  })
})
