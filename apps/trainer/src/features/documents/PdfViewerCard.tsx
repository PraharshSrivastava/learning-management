import { previewFileUrl } from '@lms/shared/api/client'
import { useHasMediaTicket } from '@lms/shared/api/useMediaTicket'
import type { PdfFile } from '@lms/shared/models'
import { IconButton } from '@lms/shared/ui/Button'
import { Icon } from '@lms/shared/ui/icons/Icon'
import clsx from 'clsx'
import { useState } from 'react'
import { fileIcon } from './fileIcon'
import { useGenerateCourse } from './useGenerateCourse'

interface PdfViewerCardProps {
  file: PdfFile | null
  className?: string
}

/** The selected document in an iframe, with Create Course and Open in new tab. */
export function PdfViewerCard({ file, className }: PdfViewerCardProps) {
  if (!file) {
    return (
      <div className={clsx('card flex flex-col items-center justify-center', className)}>
        <Icon name="folder_open_rounded" size={64} className="text-gray/40" />
        <h2 className="m-0 mt-4 font-inter text-lg leading-[27px] font-bold tracking-normal text-primary-blue">
          No Document Selected
        </h2>
        <p className="m-0 mt-2 text-center font-barlow text-sm leading-[21px] text-gray">
          Upload a document or select one from the list to view it.
        </p>
      </div>
    )
  }
  return <SelectedDocument file={file} className={className} />
}

function SelectedDocument({ file, className }: { file: PdfFile; className?: string }) {
  const generate = useGenerateCourse()
  // The iframe URL carries the media ticket. Wait for it, so the first load is not rejected.
  const hasTicket = useHasMediaTicket()
  const src = hasTicket ? previewFileUrl(file.fileName) : null
  return (
    <div className={clsx('card flex flex-col overflow-hidden', className)}>
      <div className="flex shrink-0 items-center bg-brand-blue-50 px-4 py-2">
        <Icon name={fileIcon(file)} size={24} className="text-primary-blue" />
        <span className="ml-3 min-w-0 flex-1 truncate font-barlow leading-[21px] font-bold text-primary-blue">
          {file.displayName}
        </span>
        <button
          type="button"
          onClick={() => generate(file.fileName)}
          className="inline-flex min-h-9 items-center gap-2 rounded-full bg-primary-blue px-4 py-2 font-dm text-sm leading-[18px] font-bold tracking-normal text-white hover:bg-[#0a3d8a] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light"
        >
          <Icon name="auto_stories" size={16} />
          Create Course
        </button>
        <IconButton
          icon="open_in_new"
          size={20}
          label="Open in new tab"
          className="ml-2"
          // Build the URL on click, so it carries the newest media ticket.
          onClick={() => window.open(previewFileUrl(file.fileName), '_blank', 'noopener')}
        />
      </div>
      {src ? (
        // The key keeps one iframe per file. A ticket refresh does not reload the open document.
        <PreviewFrame key={file.fileName} src={src} title={file.displayName} />
      ) : (
        <div className="flex-1" />
      )}
    </div>
  )
}

function PreviewFrame({ src, title }: { src: string; title: string }) {
  // The first src is kept. A new media ticket changes the URL but must not reload the PDF.
  const [initial] = useState(src)
  return <iframe src={initial} title={title} className="min-h-0 w-full flex-1 border-0" />
}
