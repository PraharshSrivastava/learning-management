// Who gets the journey: the same employee pickers and filters as the Assign tab, with a live count.
import { errorMessage } from '@lms/shared/api/client'
import type { AssignmentOptions, SavedAssignmentGroup } from '@lms/shared/models'
import { Dialog } from '@lms/shared/ui/Dialog'
import { Spinner } from '@lms/shared/ui/Spinner'
import { useState } from 'react'
import { ActionButton, ChoiceChip, SearchBox, Switch } from '../assignments/controls'
import { todayInKolkata } from '../assignments/dates'
import { splitDirect, withDirectIds, withOtherGroups } from '../assignments/directEmployees'
import { GroupList, OutlinedNumberField } from '../assignments/groups'
import { EmployeePicks, MoreCriteria } from '../assignments/RuleView'
import type { JourneyRule, PreviewEmployee } from './api'

const pluralEmployees = (count: number) => `${count} employee${count === 1 ? '' : 's'}`

export interface MatchPreviewState {
  pending: boolean
  error: unknown
  matchCount: number
  employees: PreviewEmployee[]
}

export function JourneyAudience({
  rule,
  options,
  savedGroups,
  preview,
  onChange,
}: {
  rule: JourneyRule
  options: AssignmentOptions
  savedGroups: SavedAssignmentGroup[]
  preview: MatchPreviewState
  onChange: (rule: JourneyRule) => void
}) {
  const setRule = (patch: Partial<JourneyRule>) => onChange({ ...rule, ...patch })
  const include = splitDirect(rule.includeGroups)
  const exclude = splitDirect(rule.excludeGroups)
  return (
    <div className="flex flex-col gap-5">
      <MatchCount preview={preview} />
      <label className="assign-switch-row">
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-[#19273e]">All active employees</span>
          <span className="block text-xs text-[#5b6980]">
            Start from everyone, then apply exclusions.
          </span>
        </span>
        <Switch
          checked={rule.includeAll}
          label="All active employees"
          onChange={(includeAll) => setRule({ includeAll })}
        />
      </label>
      {!rule.includeAll && (
        <div>
          <EmployeePicks
            title="Selected employees"
            empty="No employees selected yet. Add employees, or include a department or saved group below."
            action="Add employees"
            confirm={(n) => (n ? `Add ${pluralEmployees(n)}` : 'Add employees')}
            employees={options.employees}
            ids={include.employeeIds}
            onChange={(ids) =>
              setRule({
                includeGroups: withDirectIds(rule.includeGroups, ids, 'Selected employees'),
              })
            }
          />
          <MoreCriteria
            label="Departments, mailing lists and saved groups"
            count={include.others.length}
          >
            <GroupList
              label="Include"
              pickerTitle="Add employee"
              allowEmployees={false}
              groups={include.others}
              savedGroups={savedGroups.filter((g) => g.groupType === 'include')}
              options={options}
              onChange={(others) =>
                setRule({ includeGroups: withOtherGroups(rule.includeGroups, others) })
              }
            />
          </MoreCriteria>
        </div>
      )}
      <div className="assign-subsection" role="group" aria-label="Exclusions">
        <EmployeePicks
          title="Excluded employees"
          empty="No one is excluded."
          action="Exclude employees"
          confirm={(n) => (n ? `Exclude ${pluralEmployees(n)}` : 'Exclude employees')}
          employees={options.employees}
          ids={exclude.employeeIds}
          onChange={(ids) =>
            setRule({ excludeGroups: withDirectIds(rule.excludeGroups, ids, 'Excluded employees') })
          }
        />
        <MoreCriteria label="Exclusion filters and saved groups" count={exclude.others.length}>
          <GroupList
            label="Exclude"
            pickerTitle="Exclude employee"
            allowJoinedFilter={false}
            allowEmployees={false}
            groups={exclude.others}
            savedGroups={savedGroups.filter((g) => g.groupType === 'exclude')}
            options={options}
            onChange={(others) =>
              setRule({ excludeGroups: withOtherGroups(rule.excludeGroups, others) })
            }
          />
        </MoreCriteria>
      </div>
      <div>
        <p className="mb-2 text-xs font-semibold text-[#5b6980]">Deadline</p>
        <div className="flex flex-wrap gap-3">
          <ChoiceChip
            selected={rule.deadlineMode === 'relative'}
            onClick={() => setRule({ deadlineMode: 'relative' })}
          >
            Days after it opens
          </ChoiceChip>
          <ChoiceChip
            selected={rule.deadlineMode === 'fixed'}
            onClick={() => setRule({ deadlineMode: 'fixed' })}
          >
            Specific date
          </ChoiceChip>
        </div>
        <div className="mt-3">
          {rule.deadlineMode === 'relative' ? (
            <div className="w-[260px] max-w-full">
              <OutlinedNumberField
                label="Days to finish the journey"
                value={rule.deadlineDays}
                onChange={(days) => setRule({ deadlineDays: Math.max(1, days ?? 1) })}
              />
            </div>
          ) : (
            <input
              type="date"
              aria-label="Journey deadline date"
              className="rounded-lg border border-input-border bg-white px-3 py-2 text-sm"
              min={todayInKolkata()}
              value={rule.deadlineDate ?? ''}
              onChange={(event) => setRule({ deadlineDate: event.target.value || null })}
            />
          )}
          <p className="pt-2 text-xs text-[#5b6980]">
            {rule.deadlineMode === 'relative'
              ? 'Counted from the day the journey opens for each person. Each course gets the journey deadline.'
              : 'Due by the end of this date (Asia/Kolkata). Each course gets the journey deadline.'}
          </p>
        </div>
      </div>
    </div>
  )
}

/** The number of people the current, unsaved selection matches, with a list to check them. */
function MatchCount({ preview }: { preview: MatchPreviewState }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const query = search.trim().toLowerCase()
  const shown = preview.employees.filter(
    (e) =>
      !query ||
      [e.name, e.employeeId, e.department, e.jobTitle].some((v) => v.toLowerCase().includes(query)),
  )
  return (
    <div
      className="flex flex-wrap items-center gap-2 rounded-lg bg-[#f2f6fc] px-3 py-2.5 text-sm text-[#19273e]"
      aria-live="polite"
    >
      {preview.pending ? (
        <Spinner label="Counting employees" />
      ) : preview.error != null ? (
        <span className="text-accent-red">{errorMessage(preview.error)}</span>
      ) : (
        <>
          <span className="min-w-0 flex-1">
            <b>{pluralEmployees(preview.matchCount)}</b> match this selection. Observers are never
            counted.
          </span>
          {preview.matchCount > 0 && (
            <ActionButton variant="text" onClick={() => setOpen(true)}>
              View list
            </ActionButton>
          )}
        </>
      )}
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={`${pluralEmployees(preview.matchCount)} match`}
        width={560}
        actions={
          <ActionButton variant="filled" onClick={() => setOpen(false)}>
            Close
          </ActionButton>
        }
      >
        <SearchBox value={search} onChange={setSearch} placeholder="Search this list" />
        <ul aria-label="Matching employees" className="mt-3">
          {shown.map((employee) => (
            <li
              key={employee.employeeId}
              className="flex items-center gap-3 border-b border-[#dcdfe7] py-2 last:border-0"
            >
              <span className="min-w-0 flex-1">
                <span className="block text-sm text-[#191c20]">{employee.name}</span>
                <span className="block text-xs text-[#44474e]">
                  {[employee.department, employee.jobTitle].filter(Boolean).join(' • ')}
                </span>
              </span>
              <span className="text-xs text-[#44474e]">{employee.employeeId}</span>
            </li>
          ))}
        </ul>
        {preview.matchCount > preview.employees.length && (
          <p className="mt-3 text-xs">
            Showing the first {preview.employees.length} of {preview.matchCount}.
          </p>
        )}
      </Dialog>
    </div>
  )
}
