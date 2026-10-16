// Dart: frontend/lib/features/performance/employee_summary_panel.dart:840-967 (_Metric, _Identity,
// _Completion, _Badge). The summary panel and the employee drawer both use them.
import type { EmployeeReportRow } from '../models/performance'
import { Icon, type IconName } from '../ui/icons/Icon'
import { ProgressBar } from '../ui/ProgressBar'
import { alpha, colors, initials, percent } from './format'

/** `_Identity`: initials avatar, name w800 and department. The drawer header is prominent. */
export function Identity({
  employee,
  prominent = false,
}: {
  employee: EmployeeReportRow
  prominent?: boolean
}) {
  const name = employee.employeeName || 'Employee'
  return (
    <div className="flex items-center gap-2.5">
      <span
        className={
          prominent
            ? 'flex size-14 shrink-0 items-center justify-center rounded-full bg-brand-blue-100 text-lg font-bold text-primary-blue'
            : 'flex size-[42px] shrink-0 items-center justify-center rounded-full bg-brand-blue-100 text-[13px] font-bold text-primary-blue'
        }
      >
        {initials(name)}
      </span>
      <div className="min-w-0 flex-1">
        <p className={prominent ? 'm-0 text-lg font-extrabold' : 'm-0 font-extrabold'}>{name}</p>
        <p className="m-0 text-xs text-text-secondary">{employee.department ?? 'No department'}</p>
      </div>
    </div>
  )
}

/** `_Metric`: icon and count tile. The parent grid sets its width (Wrap with computed widths). */
export function Metric({
  label,
  value,
  icon,
  color = colors.primaryBlue,
}: {
  label: string
  value: number
  icon: IconName
  color?: string
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-[#e2eaf4] p-4">
      <Icon name={icon} size={24} color={color} />
      <div className="min-w-0 flex-1">
        <p className="m-0 text-[11px] text-text-secondary">{label}</p>
        <p className="m-0 text-[23px] font-extrabold">{value}</p>
      </div>
    </div>
  )
}

/** `_Completion`: 7 px bar, green at 100%, with an optional percent label. */
export function Completion({
  rate,
  showLabel = true,
}: {
  rate: number | null
  showLabel?: boolean
}) {
  const value = rate ?? 0
  return (
    <span className="flex items-center gap-2.5">
      <ProgressBar
        className="min-w-0 flex-1"
        value={Math.min(100, Math.max(0, value)) / 100}
        height={7}
        radius={5}
        color={value >= 100 ? colors.green : colors.barBlue}
        trackColor="#e9eef5"
      />
      {showLabel && <span className="text-xs font-bold">{percent(value)}</span>}
    </span>
  )
}

/** `_Badge`: tinted pill, 11 w700. */
export function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span
      className="inline-block rounded-[20px] px-2.5 py-[5px] text-[11px] font-bold"
      style={{ color, backgroundColor: alpha(color, 0.09) }}
    >
      {text}
    </span>
  )
}
