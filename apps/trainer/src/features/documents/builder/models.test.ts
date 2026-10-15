import { formattedDate, formattedSize, parsePdfFile } from '@lms/shared/models'
import { describe, expect, it } from 'vitest'
import { fileIcon } from '../fileIcon'
import {
  emptyMetadata,
  metadataJson,
  missingFields,
  moduleOnly,
  parseModuleCount,
  safeName,
} from './models'

describe('PdfFile (widget_test.dart)', () => {
  it('formats metadata', () => {
    const file = parsePdfFile({
      document_id: 'document-test',
      file_name: 'trainer_0001__training.pdf',
      display_name: 'training.pdf',
      size: 1536,
      created_at: '2026-01-01T00:00:00+00:00',
    })
    expect(file.displayName).toBe('training.pdf')
    expect(formattedSize(file)).toBe('1.5 KB')
    expect(formattedDate(file)).toContain('2026')
  })

  it('picks the icon from the file type', () => {
    const base = { document_id: 'd', size: 1, created_at: '2026-01-01' }
    expect(fileIcon(parsePdfFile({ ...base, file_name: 'a.pdf' }))).toBe('picture_as_pdf')
    expect(fileIcon(parsePdfFile({ ...base, file_name: 'a.DOCX' }))).toBe('description_outlined')
    expect(fileIcon(parsePdfFile({ ...base, file_name: 'a.pptx' }))).toBe('slideshow_outlined')
  })
})

describe('builder models', () => {
  it('parses the module count like int.tryParse and clamps it to 2..8', () => {
    expect(parseModuleCount('5')).toBe(5)
    expect(parseModuleCount(' 3 ')).toBe(3)
    expect(parseModuleCount('99')).toBe(8)
    expect(parseModuleCount('1')).toBe(2)
    expect(parseModuleCount('-4')).toBe(2)
    expect(parseModuleCount('abc')).toBe(4)
    expect(parseModuleCount('3.5')).toBe(4)
    expect(parseModuleCount('')).toBe(4)
  })

  it('keeps only the text from the first module heading', () => {
    expect(moduleOnly('Sure! Here it is.\n\nModule 1: Intro\nText')).toBe('Module 1: Intro\nText')
    expect(moduleOnly('  module 2 : Late start')).toBe('module 2 : Late start')
    expect(moduleOnly('No modules here')).toBe('No modules here')
    expect(moduleOnly('   ')).toBe('')
  })

  it('makes a safe download name', () => {
    expect(safeName('  Fire Safety: Level 2! ')).toBe('fire-safety-level-2')
    expect(safeName('***')).toBe('')
    expect(safeName('a'.repeat(80))).toHaveLength(60)
  })

  it('lists blank metadata fields in form order and trims the JSON', () => {
    expect(missingFields(emptyMetadata)).toEqual([
      'Course name',
      'Course description',
      'Course objective',
      'Course difficulty',
      'Target audience',
      'Course type',
    ])
    const filled = {
      courseName: ' Safety ',
      courseDescription: 'd',
      courseObjective: 'o',
      courseDifficulty: 'Easy',
      language: ' ',
      targetAudience: 't',
      courseType: 'c',
    }
    expect(missingFields(filled)).toEqual(['Language'])
    expect(metadataJson(filled).courseName).toBe('Safety')
  })
})
