import { Icon } from '@lms/shared/ui/icons/Icon'
import { ProgressBar } from '@lms/shared/ui/ProgressBar'
import { useRef } from 'react'
import { ring } from '../training/flutterStyle'
import { CardTitle } from './CardTitle'
import { ACCEPTED_TYPES, useUpload } from './useFiles'

/** Upload Document card: file picker, progress with cancel, and the result banner. */
export function UploadCard() {
  const { state, upload, cancel } = useUpload()
  const input = useRef<HTMLInputElement>(null)
  const uploading = state.status === 'uploading'

  return (
    <div className="card p-5">
      <CardTitle title="Upload Document" subtitle="Supports PDF, DOCX, and PPTX files" />
      <input
        ref={input}
        type="file"
        accept={ACCEPTED_TYPES}
        hidden
        data-testid="upload-input"
        onChange={(event) => {
          const file = event.target.files?.[0]
          // Reset so that picking the same file again fires a change.
          event.target.value = ''
          if (file) void upload(file)
        }}
      />
      <button
        type="button"
        disabled={uploading}
        onClick={() => input.current?.click()}
        className="mt-4 flex w-full flex-col items-center rounded-lg bg-brand-blue-50 px-[17.5px] py-[33.5px] hover:bg-[#e9f1fb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light disabled:cursor-default disabled:hover:bg-brand-blue-50"
        // Flutter draws a 1.5 px border inside the box. The padding includes it.
        style={{ boxShadow: ring(1.5, 'rgb(62 117 200 / 0.35)') }}
      >
        <Icon name="cloud_upload_rounded" size={40} className="text-primary-blue" />
        <span className="mt-3 font-barlow text-sm leading-[21px] font-semibold text-primary-blue">
          Click to select a document
        </span>
        <span className="mt-1 text-xs leading-[16.8px] text-gray">
          PDF, DOCX, or PPTX file up to 20MB
        </span>
      </button>
      {state.status === 'uploading' && (
        <div className="mt-3">
          <ProgressBar
            value={state.progress}
            trackColor="#fff"
            label={`Uploading ${state.fileName}`}
          />
          <div className="mt-2 flex items-center justify-center gap-3">
            <span className="text-xs leading-[16.8px] text-primary-blue" aria-live="polite">
              Uploading document...
              {state.progress != null && ` ${Math.round(state.progress * 100)}%`}
            </span>
            <button
              type="button"
              onClick={cancel}
              className="rounded text-xs leading-[16.8px] font-bold text-accent-red hover:underline focus-visible:outline-2 focus-visible:outline-brand-blue-light"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {state.status === 'success' && <Banner tone="success" message={state.message} />}
      {state.status === 'error' && <Banner tone="error" message={state.message} />}
    </div>
  )
}

function Banner({ tone, message }: { tone: 'success' | 'error'; message: string }) {
  const success = tone === 'success'
  return (
    <div
      role={success ? 'status' : 'alert'}
      className={`mt-3 flex items-center gap-2 rounded-lg px-3 py-2 ${success ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-red/10 text-accent-red'}`}
    >
      <Icon name={success ? 'check_circle_rounded' : 'error_rounded'} size={18} />
      <span className="min-w-0 flex-1 font-barlow text-[13px] leading-[19.5px] font-medium">
        {message}
      </span>
    </div>
  )
}
