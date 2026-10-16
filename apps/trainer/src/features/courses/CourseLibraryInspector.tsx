import { ApiError, apiRequest, errorDetail } from '@lms/shared/api/client'
import { useLmsAccess } from '@lms/shared/auth/lmsAccess'
import { dartString, isRecord, parseCourse, type JsonRecord } from '@lms/shared/models'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import { ProgressBar } from '@lms/shared/ui/ProgressBar'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { setPendingLinkedReport } from '../../shell/linkedReport'
import { trainerKeys } from '../../shell/queryKeys'
import { useTrainerSearch, useUpdateTrainerSearch } from '../../shell/search'
import { TrainingView } from '../training/TrainingView'
import { UnderlineDropdown } from './UnderlineDropdown'

const PAGE_SIZE = 25
const LOCKED_ACTIONS = ['Edit', 'Regenerate', 'Assign', 'Disable', 'Delete'] as const

type StatusFilter = '' | 'draft' | 'ready' | 'published'
const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: '', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'ready', label: 'Ready' },
  { value: 'published', label: 'Published' },
]

/** Dart string interpolation of a JSON value. A missing value prints "null", as in Flutter. */
const text = (value: unknown): string => (value == null ? 'null' : dartString(value))
const asRecord = (value: unknown): JsonRecord => (isRecord(value) ? value : {})
const errorText = (failure: unknown) =>
  failure instanceof Error ? failure.message : String(failure)

interface Detail {
  course: JsonRecord
  assignment: JsonRecord
}

/**
 * Read-only "All Courses" library (CourseLibraryInspector). It lists every creator's courses 25 at
 * a time. A course opens with its blueprint, assignment settings, and the read-only training view.
 * The open course is `libraryCourse` in the URL, so reload and the back button keep it.
 */
export function CourseLibraryInspector() {
  const { access, refetch: refreshAccess } = useLmsAccess()
  const queryClient = useQueryClient()
  const updateSearch = useUpdateTrainerSearch()
  const openCourseId = useTrainerSearch().libraryCourse
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<StatusFilter>('')
  const [offset, setOffset] = useState(0)
  const [items, setItems] = useState<JsonRecord[]>([])
  const [total, setTotal] = useState(0)
  const [listBusy, setListBusy] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  // Only the newest list request may change the list state.
  const request = useRef(0)

  const get = async (path: string): Promise<JsonRecord> => {
    try {
      return asRecord(await apiRequest(`/api/${path}`))
    } catch (failure) {
      if (failure instanceof ApiError && [401, 403, 404].includes(failure.status)) {
        void refreshAccess()
      }
      if (failure instanceof ApiError && failure.status > 0) {
        throw new Error(errorDetail(failure.body) ?? 'Unable to load course', { cause: failure })
      }
      throw failure
    }
  }

  // Fetches one page. It changes state only after the reply, so the first load can run in an effect.
  const fetchPage = async (serial: number, pageOffset: number, pageStatus: StatusFilter) => {
    const query = new URLSearchParams({
      scope: 'all',
      limit: String(PAGE_SIZE),
      offset: String(pageOffset),
    })
    if (pageStatus) query.set('status', pageStatus)
    if (search.trim()) query.set('search', search.trim())
    try {
      const page = await get(`trainer/course-library?${query.toString()}`)
      if (serial !== request.current) return
      setItems(Array.isArray(page.items) ? page.items.filter(isRecord) : [])
      setTotal(typeof page.total === 'number' ? Math.trunc(page.total) : 0)
      setListBusy(false)
    } catch (failure) {
      if (serial !== request.current) return
      setListBusy(false)
      setListError(errorText(failure))
    }
  }

  // The Blueprint and Courses tabs share the URL, so one query serves both inspectors.
  const detailQuery = useQuery({
    queryKey: ['library', access?.employee_id, access?.permissions_version, openCourseId],
    queryFn: async (): Promise<Detail> => {
      const path = `courses/${encodeURIComponent(openCourseId ?? '')}`
      const [course, assignment] = await Promise.all([get(path), get(`${path}/assignment`)])
      return { course, assignment }
    },
    enabled: openCourseId != null,
    // Each open fetches again, as in Flutter. A failure is shown at once, not retried.
    staleTime: 0,
    retry: false,
  })
  const detail = openCourseId == null ? undefined : detailQuery.data
  const detailError =
    openCourseId != null && detailQuery.isError ? errorText(detailQuery.error) : null
  const busy = listBusy || (openCourseId != null && detailQuery.isFetching)
  const error = detailError ?? listError

  // A second click on a course that failed to open tries again, as in Flutter.
  const open = (courseId: string) => {
    if (courseId === openCourseId) void detailQuery.refetch()
    else updateSearch({ libraryCourse: courseId })
  }

  const showList = () => {
    if (openCourseId != null) updateSearch({ libraryCourse: undefined })
  }

  const load = (next: { offset?: number; status?: StatusFilter } = {}) => {
    const serial = ++request.current
    setListBusy(true)
    setListError(null)
    showList()
    setItems([])
    void fetchPage(serial, next.offset ?? offset, next.status ?? status)
  }

  const changePage = (nextOffset: number) => {
    setOffset(nextOffset)
    load({ offset: nextOffset })
  }

  useEffect(() => {
    const counter = request
    void fetchPage(++counter.current, 0, '')
    return () => {
      counter.current++
    }
    // The first page loads once. Later loads come from the controls.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const viewPerformance = (courseId: string) => {
    setPendingLinkedReport({ courseId, status: null })
    void queryClient.invalidateQueries({ queryKey: trainerKeys.performance })
    updateSearch({ tab: 'performance' })
  }

  return (
    <div className="h-full overflow-y-auto p-6 [scrollbar-width:none]">
      <div className="flex flex-wrap items-center gap-3">
        <SearchField
          value={search}
          onChange={setSearch}
          onSubmit={() => {
            setOffset(0)
            load({ offset: 0 })
          }}
        />
        <UnderlineDropdown
          label="Course status"
          value={status}
          options={STATUS_OPTIONS}
          onChange={(next) => {
            setStatus(next)
            setOffset(0)
            load({ offset: 0, status: next })
          }}
        />
        <OutlinedPill icon="refresh" disabled={busy} onClick={() => load()}>
          Refresh
        </OutlinedPill>
        <span>{total} courses</span>
      </div>
      {busy && <ProgressBar label="Loading course library" />}
      {error != null && <p className="m-0 p-4 text-accent-red">{error}</p>}
      {detail == null ? (
        <>
          <ul className="m-0 list-none p-0" aria-label="Course library">
            {items.map((item) => (
              <li key={text(item.course_id)} className="p-1">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => open(text(item.course_id))}
                  className="flex h-[59px] w-full items-center gap-4 rounded-xl bg-[#f4f3fa] pr-6 pl-4 text-left shadow-[0_1px_1px_rgb(0_0_0/0.16),0_0_1px_rgb(0_0_0/0.06)] enabled:hover:bg-[#e9e8ef] focus-visible:outline-2 focus-visible:outline-brand-blue-light"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-[15px] leading-[22.5px] text-[#1a1b21]">
                      {text(item.course_name)}
                    </span>
                    <span className="block text-[#44474f]">
                      {`Created by ${text(item.creator_name ?? item.trainer_id)} · ${text(item.status)} · ${text(item.generation_status ?? 'Not generated')}`}
                    </span>
                  </span>
                  <Icon name="visibility_outlined" size={24} className="text-[#44474f]" />
                </button>
              </li>
            ))}
          </ul>
          <div className="flex">
            <PageButton
              disabled={busy || offset === 0}
              onClick={() => changePage(offset - PAGE_SIZE)}
            >
              Previous
            </PageButton>
            <PageButton
              disabled={busy || offset + PAGE_SIZE >= total}
              onClick={() => changePage(offset + PAGE_SIZE)}
            >
              Next
            </PageButton>
          </div>
        </>
      ) : (
        <CourseDetail detail={detail} onBack={showList} onViewPerformance={viewPerformance} />
      )}
    </div>
  )
}

function CourseDetail({
  detail,
  onBack,
  onViewPerformance,
}: {
  detail: Detail
  onBack: () => void
  onViewPerformance: (courseId: string) => void
}) {
  const { course, assignment } = detail
  const reason = course.read_only_reason
  const rule = asRecord(assignment.rule)
  const generation = isRecord(course.generation) ? course.generation : null
  const modules = Array.isArray(course.modules) ? course.modules.filter(isRecord) : []
  return (
    <>
      <button
        type="button"
        onClick={onBack}
        className="flex h-9 w-full items-center justify-center gap-2 rounded-full px-3 font-dm text-sm font-bold text-primary-blue hover:bg-primary-blue/8 focus-visible:outline-2 focus-visible:outline-brand-blue-light"
      >
        <Icon name="arrow_back" size={18} />
        Back to library
      </button>
      <h2 className="m-0 font-manrope text-2xl leading-[30px] font-extrabold tracking-normal text-text-black">
        {text(course.course_name)}
      </h2>
      <p className="m-0">Created by {text(course.creator_name ?? course.trainer_id)}</p>
      <p className="m-0 mt-3">
        {reason == null ? 'Manage your own course from My Courses.' : dartString(reason)}
      </p>
      {course.can_manage !== true && (
        <div className="flex flex-wrap gap-2">
          {LOCKED_ACTIONS.map((label) => (
            <Tooltip key={label} content={text(reason)}>
              <span className="inline-flex" tabIndex={0}>
                <OutlinedPill disabled>{label}</OutlinedPill>
              </span>
            </Tooltip>
          ))}
        </div>
      )}
      <OutlinedPill
        icon="analytics_outlined"
        className="mt-4 w-full"
        onClick={() => onViewPerformance(text(course.course_id))}
      >
        View Performance
      </OutlinedPill>
      <InfoCard>
        <p className="m-0 font-bold">Blueprint</p>
        <p className="m-0">{text(course.course_description)}</p>
        <p className="m-0">{text(course.course_objective)}</p>
        {modules.map((module, index) => (
          <Expansion key={index} title={text(module.title)}>
            <p className="m-0 p-3 whitespace-pre-wrap">{text(module.source_text ?? '')}</p>
          </Expansion>
        ))}
      </InfoCard>
      <InfoCard>
        <p className="m-0 font-bold">Assignment settings (read-only)</p>
        <p className="m-0">Deadline: {text(rule.deadline_days ?? 7)} days</p>
        <p className="m-0">Status: {rule.is_active === true ? 'Active' : 'Disabled'}</p>
        <p className="m-0">
          Include: {rule.include_all === true ? 'All active employees' : 'Selected employee groups'}
        </p>
        <p className="m-0">Matched learners: {text(assignment.match_count ?? 0)}</p>
      </InfoCard>
      {generation && (
        <Expansion title="Generation status">
          <p className="m-0">Status: {text(generation.status)}</p>
          <p className="m-0">Stage: {text(generation.current_checkpoint ?? '')}</p>
          {generation.error != null && <p className="m-0">{text(generation.error)}</p>}
        </Expansion>
      )}
      <div className="h-[640px] overflow-hidden">
        <TrainingView readOnly course={parseCourse(course)} />
      </div>
    </>
  )
}

/** Material 3 Card: tinted surface, radius 12, elevation 1, 4 px margin. */
function InfoCard({ children }: { children: ReactNode }) {
  return (
    // Padding, not margin, so the 4 px gaps of two cards add up to 8 px.
    <div className="p-1">
      <div className="rounded-xl bg-[#f4f3fa] p-4 shadow-[0_1px_1px_rgb(0_0_0/0.16),0_0_1px_rgb(0_0_0/0.06)]">
        {children}
      </div>
    </div>
  )
}

/**
 * Material ExpansionTile: a 48 px header row. When open, 1 px outline dividers frame the
 * tile, the icon turns primary blue and the children show.
 */
function Expansion({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <div className={clsx('border-y', open ? 'border-[#757780]' : 'border-transparent')}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className="flex h-12 w-full items-center gap-4 pr-6 pl-4 text-left text-[#1a1b21] hover:bg-black/4 focus-visible:outline-2 focus-visible:outline-brand-blue-light"
      >
        <span className="min-w-0 flex-1 text-[15px] leading-[22.5px]">{title}</span>
        <Icon
          name="expand_more"
          size={24}
          className={clsx(
            'transition-transform',
            open ? 'rotate-180 text-primary-blue' : 'text-[#44474f]',
          )}
        />
      </button>
      {open && (
        // Flutter centers each child box; the text inside it keeps start alignment.
        <div id={id} className="flex flex-col items-center">
          {children}
        </div>
      )}
    </div>
  )
}

/** App OutlinedButton: pill, #DDE3EA border, 36 px high, 22 px side padding. */
function OutlinedPill({
  icon,
  disabled,
  onClick,
  className,
  children,
}: {
  icon?: IconName
  disabled?: boolean
  onClick?: () => void
  className?: string
  children: ReactNode
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={clsx(
        'inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-full border border-input-border px-[21px] font-dm text-sm font-bold whitespace-nowrap text-text-black',
        'focus-visible:outline-2 focus-visible:outline-brand-blue-light enabled:hover:bg-text-black/4',
        'disabled:pointer-events-none disabled:text-[#1a1b21]/38',
        className,
      )}
    >
      {icon && <Icon name={icon} size={18} />}
      {children}
    </button>
  )
}

function PageButton({
  disabled,
  onClick,
  children,
}: {
  disabled: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="inline-flex h-9 min-w-11 items-center justify-center rounded-full px-3 font-dm text-sm font-bold text-primary-blue enabled:hover:bg-primary-blue/8 focus-visible:outline-2 focus-visible:outline-brand-blue-light disabled:text-[#1a1b21]/38"
    >
      {children}
    </button>
  )
}

/** Outlined text field with a search icon and a floating "Find a course" label. Enter searches. */
function SearchField({
  value,
  onChange,
  onSubmit,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
}) {
  const id = useId()
  return (
    <div className="group relative h-12 w-[300px] shrink-0">
      <input
        id={id}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') onSubmit()
        }}
        className="peer h-full w-full rounded-lg border border-input-border bg-white pr-3 pl-[43px] text-[15px] text-text-black focus:border-brand-blue-light focus:ring-[0.4px] focus:ring-brand-blue-light focus:outline-none [&::-webkit-search-cancel-button]:appearance-none"
      />
      <Icon
        name="search"
        size={24}
        color="#4a4c55"
        className="pointer-events-none absolute top-3 left-2"
      />
      <label
        htmlFor={id}
        className={clsx(
          'pointer-events-none absolute left-[43px] text-text-secondary transition-all',
          value
            ? '-top-2 bg-white px-1 text-xs leading-4'
            : 'top-3 text-[15px] leading-6 peer-focus:-top-2 peer-focus:bg-white peer-focus:px-1 peer-focus:text-xs peer-focus:leading-4 peer-focus:text-brand-blue-light',
        )}
      >
        Find a course
      </label>
    </div>
  )
}
