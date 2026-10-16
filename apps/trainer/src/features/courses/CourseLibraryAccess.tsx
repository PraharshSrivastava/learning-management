import { useLmsAccess } from '@lms/shared/auth/lmsAccess'
import { Icon } from '@lms/shared/ui/icons/Icon'
import clsx from 'clsx'
import type { ReactNode } from 'react'
import { useTrainerSearch, useUpdateTrainerSearch } from '../../shell/search'
import { CourseLibraryInspector } from './CourseLibraryInspector'

/**
 * Wraps the own course portal. A trainer who can view other creators' courses gets a
 * My Courses / All Courses switch. All Courses opens the read-only library inspector.
 * The switch lives in the URL, so reload and the browser back button keep it.
 */
export function CourseLibraryAccess({ children }: { children: ReactNode }) {
  const { access } = useLmsAccess()
  const all = useTrainerSearch().library === true
  const updateSearch = useUpdateTrainerSearch()
  // Each switch opens the library list or the own portal, as a fresh inspector did in Flutter.
  const setAll = (next: boolean) =>
    updateSearch({ library: next || undefined, libraryCourse: undefined })
  if (access?.capabilities.can_view_other_trainers_courses !== true) return <>{children}</>
  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center gap-3 px-6 pt-3">
        <LibraryChip selected={!all} onClick={() => setAll(false)}>
          My Courses
        </LibraryChip>
        <LibraryChip selected={all} onClick={() => setAll(true)}>
          All Courses
        </LibraryChip>
        <p className="m-0 min-w-0 flex-1">Other creators’ courses are read-only.</p>
      </div>
      <div className="min-h-0 flex-1">
        {all ? (
          // A new identity or permission set starts a fresh inspector, as the widget key did.
          <CourseLibraryInspector key={`${access.employee_id}:${access.permissions_version}`} />
        ) : (
          children
        )}
      </div>
    </div>
  )
}

/** Material ChoiceChip with the app chip theme. A selected chip shows a check. */
function LibraryChip({
  selected,
  onClick,
  children,
}: {
  selected: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={clsx(
        'inline-flex h-[30px] shrink-0 items-center gap-[7px] rounded-full border border-light-gray font-roboto text-sm leading-5 tracking-[0.1px] text-text-black transition-colors',
        'focus-visible:outline-2 focus-visible:outline-brand-blue-light',
        selected ? 'bg-brand-blue-100 pr-4 pl-2' : 'bg-white px-4 hover:bg-black/4',
      )}
    >
      {selected && <Icon name="check" size={18} color="#404659" />}
      {children}
    </button>
  )
}
