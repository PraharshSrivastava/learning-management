import { useCallback, useEffect, useState } from 'react'
import { DraftPersistence } from './draftPersistence'
import { draftApi, initialContent, postDraft, type Content, type Draft } from './workflow'

/**
 * A course needs a description. Without one, summarize the audience and module titles once the
 * outline exists, rather than repeating the learning goals.
 */
export function courseDescription(content: Content): string {
  const { courseDescription, courseName, targetAudience } = content.metadata
  if (courseDescription.trim()) return courseDescription.trim()
  const titles = content.modules
    .filter((m) => m.included && m.title.trim())
    .map((m) => m.title.trim())
  if (!titles.length) return ''
  const audience = targetAudience.trim()
  // Lower-case a leading capital ("New staff" → "new staff") but keep acronyms ("HR staff").
  const reader = /^[A-Z][a-z]/.test(audience)
    ? audience[0]!.toLowerCase() + audience.slice(1)
    : audience
  const list =
    titles.length === 1 ? titles[0] : `${titles.slice(0, -1).join(', ')} and ${titles.at(-1)}`
  return `${courseName.trim() || 'This course'}${reader ? ` for ${reader}` : ''}, in ${titles.length} module${titles.length === 1 ? '' : 's'}: ${list}.`
}

export function useDraftPersistence(mode: Content['entryMode'], paused: boolean) {
  const [, render] = useState(0)
  const [persistence] = useState(
    () =>
      new DraftPersistence(
        initialContent(mode),
        async (content, draft) => {
          const savedContent = {
            ...content,
            metadata: {
              ...content.metadata,
              courseDescription: courseDescription(content),
            },
          }
          return draft
            ? draftApi<Draft>(`/${draft.id}`, {
                method: 'PATCH',
                json: { expectedRevision: draft.revision, content: savedContent },
              })
            : postDraft<Draft>('', savedContent)
        },
        () => render((value) => value + 1),
      ),
  )
  const snapshot = persistence.snapshot()
  useEffect(() => {
    if (paused || !snapshot.dirty || snapshot.saving || snapshot.error) return
    const timer = setTimeout(() => {
      void persistence.save().catch(() => {})
    }, 1000)
    return () => clearTimeout(timer)
  }, [paused, snapshot, persistence])
  // Responses from an exited workspace cannot mutate its replacement.
  useEffect(() => {
    persistence.activate()
    return () => persistence.dispose()
  }, [persistence])
  const save = useCallback(async () => {
    let value = await persistence.save()
    while (persistence.isActive() && persistence.snapshot().dirty) value = await persistence.save()
    return value
  }, [persistence])
  const load = useCallback((value: Draft) => persistence.load(value), [persistence])
  const edit = useCallback((value: Content) => persistence.edit(value), [persistence])
  return {
    ...snapshot,
    load,
    edit,
    save,
    getSnapshot: persistence.snapshot,
  }
}
