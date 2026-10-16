import {
  ApiError,
  apiRequest,
  errorDetail,
  errorMessage,
  uploadWithProgress,
} from '@lms/shared/api/client'
import { parsePdfFile, type PdfFile } from '@lms/shared/models'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { trainerKeys } from '../../shell/queryKeys'

export async function fetchFiles(): Promise<PdfFile[]> {
  const data = await apiRequest('/api/files')
  if (!Array.isArray(data)) throw new Error('Unexpected file list response')
  return data.map(parsePdfFile)
}

/** The trainer's uploaded documents. The shell refetches them when the tab opens. */
export function useFiles() {
  return useQuery({ queryKey: trainerKeys.files, queryFn: fetchFiles })
}

export type UploadState =
  | { status: 'idle' }
  | { status: 'uploading'; progress: number | null; fileName: string }
  | { status: 'success'; message: string }
  | { status: 'error'; message: string }

export const ACCEPTED_TYPES = '.pdf,.docx,.pptx'

/** Flutter: server detail or "Upload failed.", and "Upload error: ..." when the request fails. */
function uploadError(error: unknown): string {
  if (error instanceof ApiError && error.status > 0) {
    return errorDetail(error.body) ?? 'Upload failed.'
  }
  return `Upload error: ${errorMessage(error)}`
}

/** Upload with progress and cancel. The banner stays until the next upload, as in Flutter. */
export function useUpload() {
  const queryClient = useQueryClient()
  const [state, setState] = useState<UploadState>({ status: 'idle' })
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  const upload = useCallback(
    async (file: File) => {
      if (controller.current) return
      const abort = new AbortController()
      controller.current = abort
      setState({ status: 'uploading', progress: null, fileName: file.name })
      const form = new FormData()
      form.append('file', file, file.name)
      try {
        await uploadWithProgress(
          '/api/upload',
          form,
          (fraction) =>
            setState((current) =>
              current.status === 'uploading' ? { ...current, progress: fraction } : current,
            ),
          abort.signal,
        )
        setState({ status: 'success', message: 'Uploaded successfully!' })
        void queryClient.invalidateQueries({ queryKey: trainerKeys.files })
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          setState({ status: 'idle' })
        } else {
          setState({ status: 'error', message: uploadError(error) })
        }
      } finally {
        controller.current = null
      }
    },
    [queryClient],
  )

  const cancel = useCallback(() => controller.current?.abort(), [])

  return { state, upload, cancel }
}

export type Upload = ReturnType<typeof useUpload>
