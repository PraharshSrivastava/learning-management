import { useCallback, useEffect, useRef, useState } from 'react'
import { DocumentEditor } from './editor'

/**
 * One editor per builder. React never renders inside the editor element, so the caret and the
 * figures stay where the user put them. Returns the editor, a ref for its host, and whether it is empty.
 * A layout change mounts a new host. The ref callback moves the same editor into it.
 */
export function useDocumentEditor(onChanged: () => void) {
  const [editor] = useState(() => new DocumentEditor())
  const host = useCallback(
    (element: HTMLDivElement | null) => {
      if (element) element.append(editor.root)
    },
    [editor],
  )
  const [empty, setEmpty] = useState(true)
  const changed = useRef(onChanged)
  useEffect(() => {
    changed.current = onChanged
  })

  useEffect(() => {
    const stop = editor.listen(() => {
      // Flutter read `blocks` only on rebuild, so its hint stayed after typing. This updates it.
      setEmpty(editor.blocks.length === 0)
      changed.current()
    })
    return () => {
      stop()
      editor.dispose()
    }
  }, [editor])

  return { editor, host, empty }
}
