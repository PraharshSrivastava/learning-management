import { useNavigate, useSearch } from '@tanstack/react-router'
import { useCallback } from 'react'
import { z } from 'zod'

export const TRAINER_TABS = [
  { id: 'documents', label: 'Documents' },
  // Labels match Flutter: "Blueprint" opens course details and "Courses" opens the training view.
  { id: 'blueprint', label: 'Blueprint' },
  { id: 'courses', label: 'Courses' },
  { id: 'assign', label: 'Assign' },
  { id: 'performance', label: 'Performance' },
] as const

export type TrainerTab = (typeof TRAINER_TABS)[number]['id']

const tabIds = TRAINER_TABS.map((tab) => tab.id) as [TrainerTab, ...TrainerTab[]]
// The router parses `?course=123` as a number, so ids are coerced back to strings.
const optionalText = z
  .preprocess(
    (value) => (value == null ? undefined : String(value)),
    z.string().trim().min(1).optional(),
  )
  .catch(undefined)

/**
 * Shell state lives in the URL, so reload and the browser back button keep the tab and selection.
 * `course` is shared by the Blueprint, Courses, and Assign tabs, as `selectedCourseProvider` was.
 */
export const trainerSearchSchema = z.object({
  tab: z.enum(tabIds).optional().catch(undefined),
  /** Selected course id. */
  course: optionalText,
  /** Selected document file name. */
  file: optionalText,
  /** Document builder is open on the Documents tab. */
  builder: z.literal(true).optional().catch(undefined),
  /** Persistent document workflow selection; legacy builder links remain valid. */
  draft: optionalText,
  /** The All Courses library is open on the Blueprint and Courses tabs. */
  library: z.literal(true).optional().catch(undefined),
  /** Course open in the All Courses library. */
  libraryCourse: optionalText,
  /** 1-based position of the module open on the Courses tab. It is absent for the first module. */
  module: z.coerce.number().int().min(2).optional().catch(undefined),
})

export type TrainerSearch = z.output<typeof trainerSearchSchema>

export function useTrainerSearch(): TrainerSearch {
  return useSearch({ strict: false }) as TrainerSearch
}

/**
 * Merges a patch into the search params. `undefined` removes a key.
 * Another course opens at its first module, as in Flutter.
 */
export function useUpdateTrainerSearch() {
  const navigate = useNavigate()
  return useCallback(
    (patch: Partial<TrainerSearch>, options: { replace?: boolean } = {}) =>
      void navigate({
        to: '/',
        search: (previous: TrainerSearch) => {
          const next = { ...previous, ...patch }
          if (next.course !== previous.course) delete next.module
          return next
        },
        replace: options.replace,
      }),
    [navigate],
  )
}
