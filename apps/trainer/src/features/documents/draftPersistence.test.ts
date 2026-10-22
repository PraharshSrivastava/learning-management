import { DraftPersistence } from './draftPersistence'
import { initialContent, type Content, type Draft } from './workflow'

const record = (content: Content, revision = 1): Draft => ({
  id: 'd1',
  revision,
  content,
  approvedOutline: null,
  createdAt: 'now',
  updatedAt: 'now',
})

it('keeps edits made during a save and serializes their next revision', async () => {
  const original = initialContent('blank')
  let finish!: (draft: Draft) => void
  const writes: { content: Content; expected: number | undefined }[] = []
  const persist = new DraftPersistence(
    original,
    async (content, draft) => {
      writes.push({ content, expected: draft?.revision })
      if (writes.length === 1)
        return new Promise<Draft>((resolve) => {
          finish = resolve
        })
      return record(content, 3)
    },
    () => {},
  )
  persist.load(record(original))
  const first = { ...original, metadata: { ...original.metadata, courseName: 'First' } }
  persist.edit(first)
  const saving = persist.save()
  const latest = { ...first, metadata: { ...first.metadata, courseName: 'Latest' } }
  persist.edit(latest)
  finish(record(first, 2))
  await saving
  expect(persist.snapshot().content.metadata.courseName).toBe('Latest')
  expect(persist.snapshot().dirty).toBe(true)
  await persist.save()
  expect(writes[1]?.expected).toBe(2)
  expect(persist.snapshot().dirty).toBe(false)
})

it('keeps local edits and revision after conflicts and requires an explicit retry', async () => {
  const original = initialContent('blank')
  const writer = vi.fn(async () => {
    throw new Error('Revision conflict')
  })
  const persist = new DraftPersistence(original, writer, () => {})
  persist.load(record(original, 4))
  persist.edit({ ...original, metadata: { ...original.metadata, courseName: 'Keep me' } })
  await expect(persist.save()).rejects.toThrow('Revision conflict')
  expect(persist.snapshot()).toMatchObject({
    dirty: true,
    error: 'Revision conflict',
    draft: { revision: 4 },
  })
  expect(persist.snapshot().content.metadata.courseName).toBe('Keep me')
  expect(writer).toHaveBeenCalledTimes(1)
})

it('deduplicates concurrent saves and ignores late responses after disposal', async () => {
  const original = initialContent('blank')
  let finish!: (value: Draft) => void
  const writer = vi.fn(
    () =>
      new Promise<Draft>((resolve) => {
        finish = resolve
      }),
  )
  const notify = vi.fn()
  const persist = new DraftPersistence(original, writer, notify)
  persist.edit(original)
  const first = persist.save()
  const second = persist.save()
  expect(writer).toHaveBeenCalledTimes(1)
  persist.dispose()
  notify.mockClear()
  finish(record(original))
  await Promise.all([first, second])
  expect(notify).not.toHaveBeenCalled()
  expect(persist.snapshot().draft).toBeNull()
})

it('does not roll back a restored revision when an older save completes', async () => {
  const original = initialContent('blank')
  let finish!: (value: Draft) => void
  const persist = new DraftPersistence(
    original,
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
    () => {},
  )
  persist.load(record(original))
  persist.edit({ ...original, metadata: { ...original.metadata, courseName: 'Old save' } })
  const pending = persist.save()
  const restored = { ...original, metadata: { ...original.metadata, courseName: 'Restored' } }
  persist.load(record(restored, 5))
  finish(record(original, 2))
  await expect(pending).rejects.toThrow('superseded')
  expect(persist.snapshot()).toMatchObject({
    draft: { revision: 5 },
    dirty: false,
    content: { metadata: { courseName: 'Restored' } },
  })
})
