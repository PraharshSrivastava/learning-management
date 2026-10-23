import type { PdfFile } from '@lms/shared/models'
import { apiRequest } from '@lms/shared/api/client'
import { useQuery } from '@tanstack/react-query'
import { DocumentsWorkspace } from './DocumentsWorkspace'
import { useTrainerSearch, useUpdateTrainerSearch } from '../../shell/search'
import { DocumentBuilder } from './builder/DocumentBuilder'
import { CardTitle } from './CardTitle'
import { CompactButton } from './controls'
import { DocumentList } from './DocumentList'
import { PdfViewerCard } from './PdfViewerCard'
import { UploadCard } from './UploadCard'
import { useFiles, useUpload } from './useFiles'
import { useIsMobile } from './useIsMobile'

/** Documents tab (`_buildDocumentsPortal`): upload, create, list, and viewer, or the builder. */
export function DocumentsTab() {
  const capability = useQuery({
    queryKey: ['document-workflow-capabilities'],
    queryFn: () =>
      apiRequest('/api/document-builder/capabilities') as Promise<{ workflowEnabled: boolean }>,
    retry: false,
  })
  if (capability.isPending)
    return (
      <div role="status" className="p-8">
        Loading document workspace…
      </div>
    )
  return capability.data?.workflowEnabled ? (
    <div className="documents-frame">
      <DocumentsWorkspace />
    </div>
  ) : (
    <OldDocumentsTab />
  )
}

function OldDocumentsTab() {
  const search = useTrainerSearch()
  const updateSearch = useUpdateTrainerSearch()
  const mobile = useIsMobile()
  const files = useFiles()
  // Kept here, so opening the builder or crossing the breakpoint does not cancel an upload.
  const upload = useUpload()

  if (search.builder) {
    return (
      <div className={mobile ? 'h-full p-3' : 'h-full p-5'}>
        <DocumentBuilder mobile={mobile} />
      </div>
    )
  }

  // The URL keeps the file name. A name that is not in the list selects nothing.
  const selected = files.data?.find((file) => file.fileName === search.file) ?? null
  const select = (file: PdfFile) => updateSearch({ file: file.fileName })

  if (mobile) {
    return (
      <div className="flex flex-col">
        <div className="p-4">
          <UploadCard upload={upload} />
        </div>
        <div className="px-4 pb-4">
          <CreateDocumentCard />
        </div>
        <div className="px-4">
          <DocumentList selected={selected?.fileName} onSelect={select} fill={false} />
        </div>
        {selected && (
          <div className="p-4">
            <PdfViewerCard file={selected} className="h-[600px]" />
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-[600px]">
      <div className="flex w-[380px] shrink-0 flex-col">
        <div className="p-5">
          <UploadCard upload={upload} />
        </div>
        <div className="px-5 pb-5">
          <CreateDocumentCard />
        </div>
        <div className="min-h-0 flex-1 px-5">
          <DocumentList selected={selected?.fileName} onSelect={select} fill />
        </div>
        <div className="h-5 shrink-0" />
      </div>
      <div className="min-w-0 flex-1 pt-5 pr-6 pb-6 pl-6">
        <PdfViewerCard file={selected} className="h-full" />
      </div>
    </div>
  )
}

function CreateDocumentCard() {
  const updateSearch = useUpdateTrainerSearch()
  return (
    <div className="card p-5">
      <CardTitle
        title="Create Document"
        subtitle="Build a training PDF with the document builder"
      />
      <CompactButton
        icon="edit_document"
        className="mt-4 w-full px-6"
        onClick={() => updateSearch({ builder: true })}
      >
        Open Document Builder
      </CompactButton>
    </div>
  )
}
