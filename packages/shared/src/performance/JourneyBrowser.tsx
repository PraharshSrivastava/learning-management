// The Journeys tab: the Courses tab's search, cards and paging, for Learning Journeys.
import { useRef, useState } from 'react'
import type { JourneyReport } from '../models/performance'
import { IconButton } from '../ui/Button'
import { Icon } from '../ui/icons/Icon'
import { ProgressBar } from '../ui/ProgressBar'
import { TextField } from '../ui/TextField'
import { useReport } from './context'
import { colors, matchesWords } from './format'
import { Heading } from './primitives'
import { useElementWidth } from './useElementWidth'

const pageSize = 12

export function JourneysView({
  journeys,
  isLoading,
  onOpenJourney,
}: {
  journeys: JourneyReport[]
  isLoading: boolean
  onOpenJourney: (journeyId: string) => void
}) {
  const { contextKey, state } = useReport()
  return (
    <div>
      <Heading
        title="Journey performance"
        subtitle="Search a learning journey, then open it to see each course and every learner."
      />
      {/* A new scope or reset version clears the search and the page, as in the Courses tab. */}
      <JourneyBrowser
        key={`${contextKey}|${state.employeeResetVersion}`}
        journeys={journeys}
        isLoading={isLoading}
        onOpenJourney={onOpenJourney}
      />
    </div>
  )
}

function JourneyBrowser({
  journeys,
  isLoading,
  onOpenJourney,
}: {
  journeys: JourneyReport[]
  isLoading: boolean
  onOpenJourney: (journeyId: string) => void
}) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const gridRef = useRef<HTMLDivElement>(null)
  const width = useElementWidth(gridRef)
  const matches = journeys.filter((journey) => matchesWords(search, journey.title))
  const pages = Math.max(1, Math.ceil(matches.length / pageSize))
  const clamped = Math.min(Math.max(page, 1), pages)
  if (!isLoading && clamped !== page) setPage(clamped)
  const current = isLoading ? page : clamped
  const shown = matches.slice((current - 1) * pageSize, current * pageSize)
  const columns = width >= 850 ? 2 : 1
  return (
    <div className="flex flex-col items-start">
      <div className="relative w-full">
        <Icon
          name="search"
          size={24}
          className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-primary-blue"
        />
        <TextField
          aria-label="Search learning journeys"
          placeholder="Search learning journeys"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value)
            setPage(1)
          }}
          className="pl-12 pr-12"
        />
        {search && (
          <IconButton
            icon="close"
            label="Clear journey search"
            className="absolute top-1/2 right-1 -translate-y-1/2 text-[#44474e]"
            onClick={() => {
              setSearch('')
              setPage(1)
            }}
          />
        )}
      </div>
      <p className="m-0 mt-2.5 text-text-secondary">
        {isLoading ? 'Loading learning journeys…' : `${matches.length} matching learning journeys`}
      </p>
      <div className="h-3" />
      {matches.length === 0 && !isLoading && (
        <p className="m-0 p-6">No learning journeys match your search and selected filters.</p>
      )}
      <div
        ref={gridRef}
        className="grid w-full items-start gap-3"
        style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
      >
        {shown.map((journey) => (
          <JourneyCard
            key={journey.journeyId}
            journey={journey}
            onClick={() => onOpenJourney(journey.journeyId)}
          />
        ))}
      </div>
      {matches.length > pageSize && (
        <div className="flex flex-wrap items-center gap-2.5 pt-3">
          <span>
            Showing {(current - 1) * pageSize + 1}–{(current - 1) * pageSize + shown.length} of{' '}
            {matches.length}
          </span>
          <IconButton
            icon="chevron_left"
            label="Previous journey page"
            className="text-[#44474e]"
            disabled={current <= 1}
            onClick={() => setPage(current - 1)}
          />
          <span>
            Page {current} of {pages}
          </span>
          <IconButton
            icon="chevron_right"
            label="Next journey page"
            className="text-[#44474e]"
            disabled={current >= pages}
            onClick={() => setPage(current + 1)}
          />
        </div>
      )}
    </div>
  )
}

/** The course card, with the journey's course count and a Disabled tag when it is switched off. */
export function JourneyCard({ journey, onClick }: { journey: JourneyReport; onClick: () => void }) {
  const title = journey.title || 'Learning journey'
  const rate = Math.min(100, Math.max(0, Math.trunc(journey.completionRate)))
  return (
    <button
      type="button"
      onClick={onClick}
      className="block w-full cursor-pointer overflow-hidden rounded-[14px] border border-[#dde6f1] bg-white p-[18px] text-left hover:shadow-[inset_0_0_0_999px_rgb(0_0_0/0.04)] focus-visible:outline-2 focus-visible:outline-brand-blue-light"
    >
      <div className="flex items-center">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-brand-blue-100 text-primary-blue">
          <Icon name="track_changes" size={22} />
        </span>
        <span className="ml-3 min-w-0 flex-1">
          <span className="line-clamp-2 text-[17px] font-extrabold">{title}</span>
          <span className="block text-xs text-text-secondary">
            {journey.stepCount} {journey.stepCount === 1 ? 'course' : 'courses'}
            {journey.journeyStatus === 'disabled' && ' · Disabled'}
          </span>
        </span>
        <Icon name="chevron_right" size={21} className="shrink-0 text-text-secondary" />
      </div>
      <div className="mt-[17px] flex items-center">
        <ProgressBar
          value={rate / 100}
          height={8}
          radius={8}
          color={colors.accentBlue}
          trackColor={colors.brandBlue100}
          className="flex-1"
        />
        <span className="ml-3 font-extrabold text-primary-blue">{rate}%</span>
      </div>
      <div className="mt-[18px] flex">
        <Stat value={journey.assigned} label="assigned" />
        <Stat value={journey.completed} label="completed" />
        <Stat value={journey.overdue} label="overdue" color={colors.accentRed} />
      </div>
    </button>
  )
}

function Stat({ value, label, color }: { value: number; label: string; color?: string }) {
  return (
    <span className="flex min-w-0 flex-1 flex-col">
      <span className="text-[19px] font-extrabold" style={{ color: color ?? colors.textBlack }}>
        {Math.trunc(value)}
      </span>
      <span className="text-xs text-text-secondary">{label}</span>
    </span>
  )
}
