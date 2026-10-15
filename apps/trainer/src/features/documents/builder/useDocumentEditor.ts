import { useEffect, useRef, useState } from 'react'
import { DocumentEditor } from './editor'

/**
 * One editor per builder. React never renders inside the editor element, so the caret and the
 * figures stay where the user put them. Returns the editor, a ref for its host, and whether it is empty.
 */
export function useDocumentEditor(onChanged: () => void) {
  const [editor] = useState(() => new DocumentEditor())
  const host = useRef<HTMLDivElement>(null)
  const [empty, setEmpty] = useState(true)
  const changed = useRef(onChanged)
  useEffect(() => {
    changed.current = onChanged
  })

  useEffect(() => {
    host.current?.append(editor.root)
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
