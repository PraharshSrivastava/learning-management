// Trainer document library file (Dart: frontend models.dart PDFFile).
import { z } from 'zod'
import { optStr } from './parse'

// Hard casts in Dart: these four fields are required and throw when wrong.
const rawSchema = z.object({
  document_id: z.string(),
  file_name: z.string(),
  display_name: optStr(),
  file_type: optStr(),
  size: z.number().refine(Number.isInteger),
  created_at: z.string(),
})

export const pdfFileSchema = rawSchema.transform((j) => {
  const lower = j.file_name.toLowerCase()
  return {
    documentId: j.document_id,
    fileName: j.file_name,
    displayName: j.display_name ?? j.file_name,
    fileType:
      j.file_type ?? (lower.endsWith('.pptx') ? 'pptx' : lower.endsWith('.docx') ? 'docx' : 'pdf'),
    size: j.size,
    createdAt: j.created_at,
  }
})
export type PdfFile = z.output<typeof pdfFileSchema>
export const parsePdfFile = (json: unknown): PdfFile => pdfFileSchema.parse(json)

export const isPptx = (file: PdfFile) => file.fileType.toLowerCase() === 'pptx'
export const isDocx = (file: PdfFile) => file.fileType.toLowerCase() === 'docx'

export function formattedSize(file: PdfFile): string {
  if (file.size < 1024) return `${file.size} B`
  if (file.size < 1024 * 1024) return `${(file.size / 1024).toFixed(1)} KB`
  return `${(file.size / (1024 * 1024)).toFixed(1)} MB`
}

// d/m/yyyy hh:mm in local time. Throws on a bad date, as DateTime.parse does.
export function formattedDate(file: PdfFile): string {
  const date = new Date(file.createdAt)
  if (Number.isNaN(date.getTime())) throw new Error(`Invalid date: ${file.createdAt}`)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getDate()}/${date.getMonth() + 1}/${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
