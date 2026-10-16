// Dart: JoinedDaysReportFilter in frontend/lib/features/performance/report_filter_row.dart:56-99
// and its use in performance_report_portal.dart:317-326.
import { useId, useState } from 'react'
import { Icon } from '../ui/icons/Icon'
import { useReport } from './context'

/**
 * "Joined within days" box. Enter applies `joinedLessThanDaysAgo` (empty text clears it). The
 * portal clears the text on Clear all, course availability and view changes, which all bump
 * `employeeResetVersion`.
 */
export function JoinedDaysFilter({ width }: { width: number }) {
  const { state, dispatch } = useReport()
  const id = useId()
  const [text, setText] = useState('')
  const [resetVersion, setResetVersion] = useState(state.employeeResetVersion)
  if (resetVersion !== state.employeeResetVersion) {
    setResetVersion(state.employeeResetVersion)
    setText('')
  }

  const submit = () => {
    // Dart int.tryParse: null for empty or too large text.
    const days = text === '' ? null : Number(text)
    dispatch({
      type: 'filter',
      filter: {
        ...state.filter,
        joinedLessThanDaysAgo: days != null && Number.isSafeInteger(days) ? days : null,
      },
    })
  }

  return (
    <div
      style={{ width }}
      className="flex h-[60px] shrink-0 items-center gap-2.5 rounded-xl border border-[#d2e0f0] bg-white px-3.5 py-2"
    >
      <Icon name="event_outlined" size={19} className="text-primary-blue" />
      <div className="flex min-w-0 flex-1 flex-col justify-center">
        <label
          htmlFor={id}
          className="truncate text-[11px] leading-[14px] font-medium text-text-secondary"
        >
          Joined within days
        </label>
        <input
          id={id}
          value={text}
          inputMode="numeric"
          enterKeyHint="done"
          placeholder="Enter days"
          onChange={(event) => setText(event.target.value.replace(/\D/g, ''))}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return
            submit()
            // TextInputAction.done unfocuses the field after submit.
            event.currentTarget.blur()
          }}
          className="h-[18px] w-full min-w-0 border-0 bg-transparent p-0 text-[13px] leading-[18px] font-bold text-primary-blue placeholder:text-primary-blue placeholder:opacity-100 focus:outline-none"
        />
      </div>
    </div>
  )
}
