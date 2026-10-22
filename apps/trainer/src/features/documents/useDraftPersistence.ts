import { useCallback, useEffect, useState } from 'react'
import { DraftPersistence } from './draftPersistence'
import { draftApi, initialContent, postDraft, type Content, type Draft } from './workflow'

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
              courseDescription:
                content.metadata.courseDescription.trim() ||
                content.metadata.courseObjective.trim(),
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
