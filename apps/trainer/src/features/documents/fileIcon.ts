import { isDocx, isPptx, type PdfFile } from '@lms/shared/models'
import type { IconName } from '@lms/shared/ui/icons/Icon'

export const fileIcon = (file: PdfFile): IconName =>
  isDocx(file) ? 'description_outlined' : isPptx(file) ? 'slideshow_outlined' : 'picture_as_pdf'
