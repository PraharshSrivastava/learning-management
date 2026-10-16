import { errorMessage } from '@lms/shared/api/client'
import { formattedDate, formattedSize, type PdfFile } from '@lms/shared/models'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { Spinner } from '@lms/shared/ui/Spinner'
import clsx from 'clsx'
import { fileIcon } from './fileIcon'
import { useFiles } from './useFiles'

// formattedDate throws on a bad date, as DateTime.parse did. Show the raw value instead of crashing.
function safeDate(file: PdfFile): string {
  try {
    return formattedDate(file)
  } catch {
    return file.createdAt
  }
}

interface DocumentListProps {
  selected: string | undefined
  onSelect: (file: PdfFile) => void
  /** Desktop fills the column height. Mobile grows with its content. */
  fill: boolean
}

/** Uploaded Documents card: loading, error, empty, or the selectable list. */
export function DocumentList({ selected, onSelect, fill }: DocumentListProps) {
  const files = useFiles()
  // Flutter clears the list on an error, so the counter shows 0.
  const list = files.isError ? [] : (files.data ?? [])
  // Flutter hides the list while a fetch runs, so a refetch shows the spinner too.
  const loading = files.isFetching
  return (
    <div className={clsx('card flex flex-col overflow-hidden', fill && 'h-full')}>
      <div className="flex items-center justify-between p-4">
        <h2 className="m-0 font-manrope text-lg leading-[24.3px] font-bold tracking-normal text-primary-blue">
          Uploaded Documents
        </h2>
        <span className="text-xs leading-[16.8px] text-gray">{list.length} items</span>
      </div>
      <div className="h-px shrink-0 bg-light-gray" />
      <div className={clsx('min-h-0', fill && 'flex-1 overflow-y-auto')}>
        {loading ? (
          <div className="flex h-full min-h-24 items-center justify-center">
            <Spinner label="Loading documents" />
          </div>
        ) : files.isError ? (
          <div
            role="alert"
            className="flex h-full flex-col items-center justify-center p-4 text-center"
          >
            <Icon name="error_outline_rounded" size={32} className="text-accent-red" />
            <p className="m-0 mt-2 font-barlow leading-[21px] font-bold">Error loading files</p>
            <p className="m-0 mt-1 text-xs leading-[16.8px] text-gray">
              {errorMessage(files.error)}
            </p>
          </div>
        ) : list.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center p-8">
            <Icon name="picture_as_pdf_outlined" size={48} className="text-gray/50" />
            <p className="m-0 mt-3 text-center font-barlow leading-[21px] font-medium text-gray">
              No documents uploaded yet
            </p>
          </div>
        ) : (
          <ul className="m-0 list-none p-0" aria-label="Uploaded documents">
            {list.map((file, index) => {
              const isSelected = file.fileName === selected
              return (
                <li key={file.fileName}>
                  {index > 0 && <div className="h-px bg-light-gray" />}
                  <button
                    type="button"
                    aria-current={isSelected || undefined}
                    onClick={() => onSelect(file)}
                    className={clsx(
                      'flex min-h-16 w-full items-center gap-4 py-2 pr-6 pl-4 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-blue-light',
                      isSelected ? 'bg-brand-blue-100' : 'hover:bg-[#1a1b20]/8',
                    )}
                  >
                    <Icon
                      name={fileIcon(file)}
                      size={24}
                      className={isSelected ? 'text-primary-blue' : 'text-gray'}
                    />
                    <span className="min-w-0 flex-1">
                      <span
                        className={clsx(
                          'block truncate font-barlow text-[15px] leading-[22.5px]',
                          isSelected
                            ? 'font-bold text-primary-blue'
                            : 'font-medium text-text-black',
                        )}
                      >
                        {file.displayName}
                      </span>
                      <span className="flex justify-between gap-2 text-xs leading-[16.8px] text-gray">
                        <span>{formattedSize(file)}</span>
                        <span>{safeDate(file)}</span>
                      </span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
