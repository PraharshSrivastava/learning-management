import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { fileJson, renderDocuments, stubBrowser, stubFetch } from './test/renderDocuments'

vi.mock('./DocumentPreview', () => ({
  DocumentPreview: ({ file, onClose }: { file: { displayName: string }; onClose: () => void }) => (
    <section aria-label={`Complete preview ${file.displayName}`}>
      <button onClick={onClose}>Close complete preview</button>
    </section>
  ),
}))
beforeEach(() => stubBrowser())
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('limits uploaded documents after sorting and searches the complete library before limiting', async () => {
  stubFetch((url) =>
    url.pathname.endsWith('/capabilities')
      ? { workflowEnabled: true }
      : url.pathname === '/api/files'
        ? Array.from({ length: 7 }, (_, i) =>
            fileJson(`Training ${i + 1}.pdf`, { created_at: `2026-10-${10 + i}T10:00:00Z` }),
          )
        : [],
  )
  renderDocuments()
  const library = await screen.findByRole('region', { name: 'Your uploaded documents' })
  expect(await within(library).findAllByRole('button', { name: 'Preview' })).toHaveLength(5)
  expect(within(library).queryByText('Training 1.pdf')).not.toBeInTheDocument()
  expect(within(library).getAllByRole('heading', { level: 3 })[0]).toHaveTextContent(
    'Training 7.pdf',
  )
  fireEvent.click(within(library).getByRole('button', { name: 'View all documents (7)' }))
  expect(within(library).getAllByRole('button', { name: 'Preview' })).toHaveLength(7)
  fireEvent.click(within(library).getByRole('button', { name: 'Show recent documents' }))
  fireEvent.change(within(library).getByRole('textbox', { name: 'Search documents' }), {
    target: { value: 'Training 1' },
  })
  expect(within(library).getAllByRole('button', { name: 'Preview' })).toHaveLength(1)
  expect(within(library).getByText('Training 1.pdf')).toBeInTheDocument()
  expect(within(library).queryByRole('button', { name: 'Edit first' })).not.toBeInTheDocument()
})

it('opens one complete preview immediately after its row and restores focus on close', async () => {
  stubFetch((url) =>
    url.pathname.endsWith('/capabilities')
      ? { workflowEnabled: true }
      : url.pathname === '/api/files'
        ? [fileJson('First.pdf'), fileJson('Second.pdf')]
        : [],
  )
  renderDocuments()
  const previews = await screen.findAllByRole('button', { name: 'Preview' })
  fireEvent.click(previews[0]!)
  const viewer = await screen.findByRole('region', { name: 'Complete preview First.pdf' })
  expect(previews[0]!.closest('.docs-document-row')!.nextElementSibling).toContainElement(viewer)
  fireEvent.click(previews[1]!)
  expect(
    await screen.findByRole('region', { name: 'Complete preview Second.pdf' }),
  ).toBeInTheDocument()
  expect(
    screen.queryByRole('region', { name: 'Complete preview First.pdf' }),
  ).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Close complete preview' }))
  expect(previews[1]).toHaveFocus()
})
