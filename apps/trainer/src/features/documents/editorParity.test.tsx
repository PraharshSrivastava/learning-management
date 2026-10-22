import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useState } from 'react'
import {
  TextBlockEditor,
  replaceTextPreservingMarks,
  toggleMark,
  splitModule,
  mergeModules,
  isEmptyModule,
} from './editorParity'
import { initialContent, newModule, paragraph, type TextBlock } from './workflow'
import { renderDocuments, stubBrowser, stubFetch } from './test/renderDocuments'
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
it('preserves overlapping marks and provenance while editing Unicode text', () => {
  const block = {
    ...paragraph('A😀 bold tail'),
    marks: [
      { start: 3, end: 7, type: 'bold' },
      { start: 3, end: 7, type: 'italic' },
    ],
    sourceReferences: [{ sourceId: 'source', spanId: 'span' }],
  }
  const next = replaceTextPreservingMarks(block, 'A😀 bolder tail')
  expect(next.marks).toEqual([
    { start: 3, end: 9, type: 'bold' },
    { start: 3, end: 9, type: 'italic' },
  ])
  expect(next.sourceReferences).toEqual(block.sourceReferences)
})
it('formats only the selected codepoints and rejects unsafe links', () => {
  const block = paragraph('A😀 text')
  expect(toggleMark(block, 1, 2, 'bold').marks).toEqual([{ start: 1, end: 2, type: 'bold' }])
  expect(() => toggleMark(block, 0, 1, 'link', 'javascript:alert(1)')).toThrow(/https/)
  expect(toggleMark(block, 0, 1, 'link', 'HTTPS://Example.com/CaseSensitive').marks[0]?.href).toBe(
    'https://Example.com/CaseSensitive',
  )
})
it('supports selection formatting and displays its saved formatting preview', () => {
  function Editor() {
    const [block, setBlock] = useState<TextBlock>(paragraph('Hello world'))
    return <TextBlockEditor block={block} onChange={setBlock} onSelect={() => {}} />
  }
  render(<Editor />)
  const text = screen.getByRole('textbox', { name: 'paragraph text' }) as HTMLTextAreaElement
  text.setSelectionRange(0, 5)
  fireEvent.select(text)
  fireEvent.click(screen.getByRole('button', { name: 'Bold' }))
  expect(screen.getByTestId('formatted-preview').querySelector('strong')).toHaveTextContent('Hello')
  fireEvent.change(text, { target: { value: 'Hello nice world' } })
  expect(screen.getByTestId('formatted-preview').querySelector('strong')).toHaveTextContent('Hello')
})
it('recognizes new placeholders and splits/merges without duplicating block identities', () => {
  const module = newModule()
  expect(isEmptyModule(module)).toBe(true)
  module.blocks = [
    { ...paragraph('One'), sourceReferences: [{ sourceId: 's', spanId: 'one' }] },
    { ...paragraph('Two'), sourceReferences: [{ sourceId: 's', spanId: 'two' }] },
  ]
  const [left, right] = splitModule(module, 1)
  expect(left?.blocks.map((b) => b.id)).toEqual([module.blocks[0]?.id])
  expect(right?.blocks.map((b) => b.id)).toEqual([module.blocks[1]?.id])
  const merged = mergeModules(left!, right!)
  expect(merged.blocks).toEqual(module.blocks)
  expect(merged.sourceReferences).toHaveLength(2)
})

it('preserves module-only evidence on both split segments when attribution is uncertain', () => {
  const module = {
    ...newModule(),
    blocks: [paragraph('One'), paragraph('Two')],
    sourceReferences: [{ sourceId: 'source', spanId: 'module-only' }],
  }
  const [left, right] = splitModule(module, 1)
  expect(left.sourceReferences).toContainEqual(module.sourceReferences[0])
  expect(right.sourceReferences).toContainEqual(module.sourceReferences[0])
})

it('offers AI drafting for new placeholders and inserts editable bullet and numbered lists', async () => {
  stubBrowser()
  const content = initialContent('blank')
  content.metadata.courseName = 'Training'
  const record = {
    id: 'draft1',
    revision: 1,
    content,
    approvedOutline: null,
    createdAt: 'now',
    updatedAt: 'now',
  }
  stubFetch((url) =>
    url.pathname.endsWith('/capabilities')
      ? { workflowEnabled: true }
      : url.pathname.endsWith('/draft1')
        ? record
        : [],
  )
  renderDocuments('/?tab=documents&builder=true&draft=draft1')
  expect(await screen.findByRole('button', { name: 'Draft this module' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '+ Bullet list' }))
  expect(screen.getByRole('textbox', { name: 'List items (one per line)' })).toHaveValue(
    'First item',
  )
  expect(screen.getByRole('checkbox', { name: 'Numbered list' })).not.toBeChecked()
  fireEvent.click(screen.getByRole('button', { name: '+ Numbered list' }))
  expect(screen.getAllByRole('checkbox', { name: 'Numbered list' })[1]).toBeChecked()
})

it('exposes image layout controls and keeps block content when moving it', async () => {
  stubBrowser()
  const content = initialContent('blank')
  content.metadata.courseName = 'Training'
  content.modules[0]!.blocks = [
    paragraph('First'),
    {
      id: 'image',
      type: 'image',
      assetId: 'asset',
      caption: 'Illustration',
      width: 40,
      align: 'right',
      sourceReferences: [],
    },
  ]
  const record = {
    id: 'draft1',
    revision: 1,
    content,
    approvedOutline: null,
    createdAt: 'now',
    updatedAt: 'now',
  }
  stubFetch((url) =>
    url.pathname.endsWith('/capabilities')
      ? { workflowEnabled: true }
      : url.pathname.endsWith('/draft1')
        ? record
        : url.pathname.endsWith('/asset')
          ? new Response(new Blob(['png']))
          : [],
  )
  renderDocuments('/?tab=documents&builder=true&draft=draft1')
  const width = await screen.findByRole('combobox', { name: 'Image width' })
  expect(width).toHaveValue('40')
  fireEvent.change(width, { target: { value: '80' } })
  expect(width).toHaveValue('80')
  fireEvent.change(screen.getByRole('combobox', { name: 'Alignment' }), {
    target: { value: 'center' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Move block 2 up' }))
  expect(screen.getByRole('button', { name: 'Move block 1 up' })).toBeDisabled()
  expect(screen.getByRole('textbox', { name: 'paragraph text' })).toHaveValue('First')
  expect(screen.getByRole('textbox', { name: 'Caption' })).toHaveValue('Illustration')
})

it('edits module learning goals and reorders the actual outline', async () => {
  stubBrowser()
  const content = initialContent('ai')
  content.metadata.courseName = 'Training'
  content.modules = [
    { ...newModule(), title: 'First module', objective: 'First goal' },
    { ...newModule(), title: 'Second module', objective: 'Second goal' },
  ]
  const record = {
    id: 'draft1',
    revision: 1,
    content,
    approvedOutline: null,
    createdAt: 'now',
    updatedAt: 'now',
  }
  stubFetch((url) =>
    url.pathname.endsWith('/capabilities')
      ? { workflowEnabled: true }
      : url.pathname.endsWith('/draft1')
        ? record
        : [],
  )
  renderDocuments('/?tab=documents&builder=true&draft=draft1')
  fireEvent.click(await screen.findByRole('button', { name: 'Review outline' }))
  const goals = screen.getAllByRole('textbox', { name: 'Learning goal' })
  fireEvent.change(goals[0]!, { target: { value: 'Apply revised learning' } })
  fireEvent.click(screen.getAllByRole('button', { name: 'Move module down' })[0]!)
  expect(screen.getByRole('textbox', { name: 'Module 1 title' })).toHaveValue('Second module')
  expect(screen.getAllByRole('textbox', { name: 'Learning goal' })[1]).toHaveValue(
    'Apply revised learning',
  )
})
