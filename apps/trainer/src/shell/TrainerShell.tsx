import { useLmsAccess } from '@lms/shared/auth/lmsAccess'
import { useSession } from '@lms/shared/auth/session'
import { IconButton } from '@lms/shared/ui/Button'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState, type ComponentType } from 'react'
import type { Trainer } from '../auth/trainer'
import { AssignTab } from '../features/assignments/AssignTab'
import { BlueprintTab } from '../features/courses/BlueprintTab'
import { useCourseSaveOverlay } from '../features/courses/courseQueries'
import { useFullCourseGenerationOverlay } from '../features/courses/useFullCourseGeneration'
import { DocumentsTab } from '../features/documents/DocumentsTab'
import { fetchJourneys } from '../features/journeys/api'
import { JourneysTab } from '../features/journeys/JourneysTab'
import { PerformanceTab } from '../features/performance/PerformanceTab'
import { CoursesTab } from '../features/training/CoursesTab'
import './desk.css'
import { trainerKeys } from './queryKeys'
import { TRAINER_TABS, useTrainerSearch, useUpdateTrainerSearch, type TrainerTab } from './search'

const tabPanels: Record<TrainerTab, ComponentType> = {
  documents: DocumentsTab,
  blueprint: BlueprintTab,
  courses: CoursesTab,
  journeys: JourneysTab,
  assign: AssignTab,
  performance: PerformanceTab,
}

/** Queries each tab reloads when it is opened, as `_activateTrainerTab` did. */
const tabQueries: Record<TrainerTab, readonly (readonly string[])[]> = {
  documents: [trainerKeys.files],
  blueprint: [trainerKeys.courses],
  courses: [trainerKeys.courses],
  journeys: [trainerKeys.journeys],
  assign: [trainerKeys.assignableCourses],
  performance: [trainerKeys.performance],
}

export function TrainerShell() {
  const { person, token } = useSession<Trainer>()
  const { access } = useLmsAccess()
  const queryClient = useQueryClient()
  const search = useTrainerSearch()
  const updateSearch = useUpdateTrainerSearch()
  // The Journeys tab appears only once the backend reports Learning Journeys as enabled.
  const journeys = useQuery({
    queryKey: trainerKeys.journeys,
    queryFn: fetchJourneys,
    enabled: person != null,
  })
  const journeysEnabled = journeys.data?.enabled === true
  const tabs = TRAINER_TABS.filter((tab) => tab.id !== 'journeys' || journeysEnabled)
  const requestedTab = search.tab ?? 'documents'
  const activeTab = requestedTab === 'journeys' && !journeysEnabled ? 'documents' : requestedTab
  // Visited tabs stay mounted, like Flutter's IndexedStack, so their state survives a tab switch.
  const [visited, setVisited] = useState<ReadonlySet<TrainerTab>>(() => new Set([activeTab]))
  if (!visited.has(activeTab)) setVisited(new Set(visited).add(activeTab))
  // Registered here, not in BlueprintEditor, so Back/Forward or a tab change cannot unmount the
  // overlay while the job it is blocking for keeps running in the background.
  useFullCourseGenerationOverlay()
  useCourseSaveOverlay()

  const openTab = (tab: TrainerTab) => {
    for (const queryKey of tabQueries[tab]) void queryClient.invalidateQueries({ queryKey })
    if (tab !== activeTab) updateSearch({ tab })
  }

  const refreshAll = () => {
    for (const queryKey of [
      trainerKeys.files,
      trainerKeys.courses,
      trainerKeys.assignableCourses,
      trainerKeys.journeys,
      trainerKeys.performance,
    ]) {
      void queryClient.invalidateQueries({ queryKey })
    }
  }

  // A capability or report-scope change resets the performance tab, as the Flutter widget key did.
  const performanceKey = `${person?.trainerId}:${token}:${access?.permissions_version}:${access?.report_scope_version}`

  return (
    <div className="page-gradient flex h-full min-w-0 flex-col">
      <header className="box-content flex h-[72px] shrink-0 items-center border-b border-light-gray bg-white/94 pr-4 pl-4">
        <span className="font-inter text-xl font-bold tracking-[-0.5px] text-primary-blue">
          PhillipCapital
        </span>
        <span className="mr-3 ml-2 h-6 w-px bg-light-gray" aria-hidden />
        <nav className="flex min-w-0 flex-1 gap-2 overflow-x-auto" aria-label="Trainer sections">
          {tabs.map((tab) => {
            const active = tab.id === activeTab
            return (
              <button
                key={tab.id}
                type="button"
                aria-current={active ? 'page' : undefined}
                onClick={() => openTab(tab.id)}
                className={clsx(
                  'min-h-11 shrink-0 rounded-full border px-[18px] py-2.5 font-barlow text-[15px] leading-none transition-colors',
                  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light',
                  active
                    ? 'border-brand-blue-light bg-brand-blue-100 font-bold text-primary-blue'
                    : 'border-transparent font-semibold text-text-secondary hover:bg-brand-blue-50',
                )}
              >
                {tab.label}
              </button>
            )
          })}
        </nav>
        <span className="mr-1.5 ml-2 font-barlow font-bold text-primary-blue">
          {person?.name ?? ''}
        </span>
        <IconButton icon="refresh" label="Refresh All Data" onClick={refreshAll} />
      </header>
      <div className="relative min-h-0 flex-1">
        {tabs.map(({ id }) => {
          if (!visited.has(id)) return null
          const Panel = tabPanels[id]
          return (
            <section
              key={id === 'performance' ? `${id}:${performanceKey}` : id}
              className="trainer-desk absolute inset-0 overflow-auto"
              hidden={id !== activeTab}
              aria-label={TRAINER_TABS.find((tab) => tab.id === id)?.label}
            >
              <Panel />
            </section>
          )
        })}
      </div>
    </div>
  )
}
