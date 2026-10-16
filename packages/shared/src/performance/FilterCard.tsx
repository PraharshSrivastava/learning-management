// Dart: frontend/lib/features/performance/performance_report_portal.dart:166-329 (_filters,
// employee_frontend is the same).
import type { PerformanceReportOptions } from '../models/performance'
import { Button } from '../ui/Button'
import { Icon } from '../ui/icons/Icon'
import { Tooltip } from '../ui/Tooltip'
import { useReport } from './context'
import { JoinedDaysFilter } from './JoinedDaysFilter'
import { ReportFilterRow } from './ReportFilterRow'
import { SearchableFilter } from './SearchableFilter'
import { activeFilterCount } from './state'

const courseStatusItems: [string, string][] = [
  ['all', 'All courses'],
  ['active', 'Active'],
  ['disabled', 'Disabled'],
]

/**
 * The "Filter reports" card. Flutter clears the search and joined days text boxes here. In React
 * `courseStatus` and `clearFilters` bump `employeeResetVersion`, and those boxes clear themselves
 * when it changes, so the card only dispatches.
 */
export function FilterCard({ options }: { options: PerformanceReportOptions | undefined }) {
  const { state, dispatch } = useReport()
  const { filter } = state
  const activeCount = activeFilterCount(filter)
  return (
    <section className="rounded-[18px] border border-[#d7e5f5] bg-linear-to-br from-[#f1f7ff] to-white p-[18px] shadow-[0_4px_14px_rgb(20_61_115/0.04)]">
      <div className="flex items-center">
        <div className="flex size-[34px] shrink-0 items-center justify-center rounded-[10px] bg-brand-blue-100 text-primary-blue">
          <Icon name="tune_rounded" size={19} />
        </div>
        <h2 className="m-0 ml-2.5 min-w-0 flex-1 text-[15px] font-extrabold">Filter reports</h2>
        {activeCount > 0 && (
          <span className="rounded-full bg-brand-blue-100 px-[9px] py-[5px] text-[11px] font-bold text-primary-blue">
            {activeCount} active
          </span>
        )}
        <Button
          variant="text"
          icon="filter_alt_off_outlined"
          className="ml-2 pr-4"
          onClick={() => dispatch({ type: 'clearFilters' })}
        >
          Clear all
        </Button>
      </div>
      <div className="mt-3">
        <ReportFilterRow>
          {(width) => (
            <>
              <Tooltip content="Includes active and disabled courses and retained learning records.">
                <div>
                  <SearchableFilter
                    label="Course availability"
                    value={filter.courseStatus === 'archived' ? 'disabled' : filter.courseStatus}
                    width={width}
                    icon="visibility_outlined"
                    allowAll={false}
                    items={courseStatusItems}
                    onChange={(value) => {
                      if (value != null) dispatch({ type: 'courseStatus', status: value })
                    }}
                  />
                </div>
              </Tooltip>
              <SearchableFilter
                label="Course"
                value={filter.courseId}
                width={width}
                icon="menu_book_outlined"
                items={(options?.courses ?? []).map((course) => [
                  course.courseId,
                  course.courseName,
                ])}
                onChange={(value) =>
                  dispatch({ type: 'filter', filter: { ...filter, courseId: value } })
                }
              />
              <SearchableFilter
                label="Department"
                value={filter.department}
                width={width}
                icon="apartment_outlined"
                items={(options?.departments ?? []).map((value) => [value, value])}
                onChange={(value) =>
                  dispatch({ type: 'filter', filter: { ...filter, department: value } })
                }
              />
              <SearchableFilter
                label="Mailing list"
                value={filter.mailingList}
                width={width}
                icon="group_outlined"
                items={(options?.mailingLists ?? []).map((value) => [value, value])}
                onChange={(value) =>
                  dispatch({ type: 'filter', filter: { ...filter, mailingList: value } })
                }
              />
              <JoinedDaysFilter width={width} />
            </>
          )}
        </ReportFilterRow>
      </div>
    </section>
  )
}
