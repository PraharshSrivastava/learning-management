import type { ReactNode } from 'react'

export type DocumentsIconName =
  | 'upload'
  | 'ai'
  | 'draft'
  | 'pdf'
  | 'file'
  | 'document'
  | 'presentation'
  | 'arrow'
  | 'trash'
  | 'search'
  | 'eye'
  | 'close'
  | 'check'
  | 'warning'
  | 'error'
  | 'loader'
  | 'save'
  | 'image'
  | 'book'
  | 'undo'
  | 'chevron-left'
  | 'chevron-right'
  | 'minus'
  | 'plus'

/** Bundled, decorative product marks; the enclosing control supplies its accessible name. */
export function DocumentsIcon({
  name,
  size = 20,
  className = '',
}: {
  name: DocumentsIconName
  size?: number
  className?: string
}) {
  const page = <path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8zm0 0v5h5" />
  const marks: Record<DocumentsIconName, ReactNode> = {
    upload: (
      <>
        {page}
        <path d="M12 17v-6m-3 3 3-3 3 3" />
      </>
    ),
    ai: (
      <>
        <path d="M12 21H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h8l5 5v4M14 3v5h5M8 11h6m-6 4h4" />
        <path d="m13 20 5-5 2 2-5 5h-2z" fill="currentColor" strokeWidth="1.3" />
        <path
          d="m20 10 .7 2.3L23 13l-2.3.7L20 16l-.7-2.3L17 13l2.3-.7z"
          fill="#8057d9"
          stroke="none"
        />
      </>
    ),
    draft: (
      <>
        {page}
        <path d="M8 12h7m-7 4h5" />
      </>
    ),
    pdf: (
      <>
        {page}
        <text
          x="7"
          y="17"
          fill="currentColor"
          stroke="none"
          fontSize="5.5"
          fontFamily="Arial,sans-serif"
          fontWeight="700"
        >
          PDF
        </text>
      </>
    ),
    file: page,
    document: (
      <>
        {page}
        <path d="M8 12h7m-7 4h7" />
      </>
    ),
    presentation: (
      <>
        <path d="M3 4h18M5 4v13h14V4M12 17v4m-4 0 4-3 4 3M8 9h8m-8 4h5" />
      </>
    ),
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    trash: (
      <>
        <path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15m-8 4v7m4-7v7" />
      </>
    ),
    search: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 5 5" />
      </>
    ),
    eye: (
      <>
        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    close: <path d="m6 6 12 12M6 18 18 6" />,
    check: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),
    warning: (
      <>
        <path d="m12 3 10 18H2zM12 9v5" />
        <circle cx="12" cy="17.3" r=".7" fill="currentColor" />
      </>
    ),
    error: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v6" />
        <circle cx="12" cy="17" r=".7" fill="currentColor" />
      </>
    ),
    loader: <path d="M21 12a9 9 0 1 1-9-9" />,
    save: (
      <>
        <path d="M20 21H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h13l4 4v13a1 1 0 0 1-1 1zM7 3v6h9V3M7 21v-8h10v8" />
      </>
    ),
    image: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <circle cx="8" cy="8" r="1.5" />
        <path d="m3 17 6-6 4 4 3-3 5 5" />
      </>
    ),
    book: <path d="M12 5v16M12 5C9 3 5 3 2 4v15c4-1 7-1 10 2 3-3 6-3 10-2V4c-3-1-7-1-10 1z" />,
    undo: <path d="M8 5 3 10l5 5M3 10h12a5 5 0 0 1 0 10" />,
    'chevron-left': <path d="m15 5-7 7 7 7" />,
    'chevron-right': <path d="m9 5 7 7-7 7" />,
    minus: <path d="M5 12h14" />,
    plus: <path d="M5 12h14M12 5v14" />,
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={`documents-icon ${className}`}
    >
      {marks[name]}
    </svg>
  )
}
