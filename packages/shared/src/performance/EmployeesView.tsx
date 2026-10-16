// Dart: frontend/lib/features/performance/performance_report_portal.dart:598-627 (_employees).
import clsx from 'clsx'
import type { ReactNode } from 'react'
import type { AssignmentListReport } from '../models/performance'
import { Icon } from '../ui/icons/Icon'
import { AssignmentsBox } from './AssignmentsBox'
import { useReport } from './context'
import { EmployeeSummaryPanel } from './EmployeeSummaryPanel'
import type { Params } from './state'

/** The Employees tab: "Employee summary" or "Course assignments". */
export function EmployeesView({
  assignments,
  onOpenAssignment,
  onOpenEmployee,
  onExportEmployees,
}: {
  assignments: AssignmentListReport | undefined
  onOpenAssignment: (assignmentId: string) => void
  onOpenEmployee: (employeeId: string) => void
  onExportEmployees: (params: Params) => Promise<void>
}) {
  const { state, dispatch } = useReport()
  const summary = state.employeeSummary
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <ChoiceChip
          selected={summary}
          onClick={() => dispatch({ type: 'employeeSummary', summary: true })}
        >
          Employee summary
        </ChoiceChip>
        <ChoiceChip
          selected={!summary}
          onClick={() => dispatch({ type: 'employeeSummary', summary: false })}
        >
          Course assignments
        </ChoiceChip>
      </div>
      <div className="h-3" />
      {summary ? (
        <EmployeeSummaryPanel onOpenEmployee={onOpenEmployee} onExport={onExportEmployees} />
      ) : (
        <AssignmentsBox assignments={assignments} onOpenAssignment={onOpenAssignment} />
      )}
    </div>
  )
}

/** Material ChoiceChip with the app chip theme. A selected chip shows a check. */
function ChoiceChip({
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
