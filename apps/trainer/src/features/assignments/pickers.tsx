// Picker dialogs for the group editor (Flutter _MultiSelectDialog, _EmployeePickerDialog,
// _SavedGroupPickerDialog). Content mounts only while open, so search resets on each open.
import type { AssignmentGroup, Employee, SavedAssignmentGroup } from '@lms/shared/models'
import { Dialog } from '@lms/shared/ui/Dialog'
import { useState, type ReactNode } from 'react'
import { ActionButton, CheckboxRow, SearchBox } from './controls'

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

/** Text summary of a saved group's criteria. */
export function savedGroupSummary(group: AssignmentGroup): string {
  const parts: string[] = []
  if (group.employeeIds.length > 0) parts.push(plural(group.employeeIds.length, 'employee'))
  if (group.departments.length > 0) parts.push(plural(group.departments.length, 'department'))
  if (group.mailingLists.length > 0) parts.push(plural(group.mailingLists.length, 'mailing list'))
  if (group.joinedLessThanDaysAgo != null) {
    parts.push(`joined under ${group.joinedLessThanDaysAgo} days`)
  }
  return parts.length === 0 ? 'No criteria yet' : parts.join(' • ')
}

/** Fixed-size dialog body, like Flutter SizedBox(width, height). */
function Body({ height, children }: { height: number; children: ReactNode }) {
  return (
    <div className="flex flex-col" style={{ height }}>
      {children}
    </div>
  )
}

/** Clickable two-line list row (Flutter ListTile). */
export function ListRow({
  title,
  subtitle,
  trailing,
  onClick,
}: {
  title: ReactNode
  subtitle?: ReactNode
  trailing?: ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-14 w-full items-center gap-4 px-4 py-2 text-left hover:bg-black/4 focus-visible:bg-black/6 focus-visible:outline-none"
    >
      <span className="min-w-0 flex-1">
        <span className="block text-base text-[#191c20]">{title}</span>
        {subtitle && <span className="block text-sm text-[#44474e]">{subtitle}</span>}
      </span>
      {trailing}
    </button>
  )
}

interface MultiSelectDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  values: string[]
  selected: string[]
  onApply: (values: string[]) => void
}

export function MultiSelectDialog(props: MultiSelectDialogProps) {
  return (
    <Dialog
      open={props.open}
      onOpenChange={props.onOpenChange}
      title={`Select ${props.title.toLowerCase()}`}
      width={568}
    >
      {props.open && <MultiSelectBody {...props} />}
    </Dialog>
  )
}

function MultiSelectBody({
  title,
  values,
  selected,
  onApply,
  onOpenChange,
}: MultiSelectDialogProps) {
  const [picked, setPicked] = useState(selected)
  const [query, setQuery] = useState('')
  const filtered = values.filter((value) => value.toLowerCase().includes(query.toLowerCase()))
  return (
    <>
      <Body height={460}>
        <SearchBox
          value={query}
          onChange={setQuery}
          placeholder={`Search ${title.toLowerCase()}`}
        />
        <div className="mt-3 min-h-0 flex-1 overflow-auto [scrollbar-width:none]">
          {filtered.map((value) => (
            <CheckboxRow
              key={value}
              dense
              checked={picked.includes(value)}
              onChange={(checked) =>
                setPicked((current) =>
                  checked ? [...current, value] : current.filter((item) => item !== value),
                )
              }
            >
              {value}
            </CheckboxRow>
          ))}
        </div>
      </Body>
      <div className="mt-6 flex justify-end gap-2">
        <ActionButton variant="text" onClick={() => onOpenChange(false)}>
          Cancel
        </ActionButton>
        <ActionButton variant="text" onClick={() => setPicked([])}>
          Clear
        </ActionButton>
        <ActionButton
          variant="filled"
          onClick={() => {
            onApply(picked)
            onOpenChange(false)
          }}
        >
          Apply
        </ActionButton>
      </div>
    </>
  )
}

interface EmployeePickerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  employees: Employee[]
  onPick: (employee: Employee) => void
}

export function EmployeePickerDialog(props: EmployeePickerProps) {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange} title={props.title} width={568}>
      {props.open && <EmployeePickerBody {...props} />}
    </Dialog>
  )
}

function EmployeePickerBody({ employees, onPick, onOpenChange }: EmployeePickerProps) {
  const [query, setQuery] = useState('')
  const needle = query.toLowerCase()
  const filtered = employees.filter((e) =>
    `${e.name} ${e.employeeId} ${e.department} ${e.jobTitle} ${e.mailingLists.join(' ')}`
      .toLowerCase()
      .includes(needle),
  )
  return (
    <Body height={460}>
      <SearchBox value={query} onChange={setQuery} placeholder="Search employees" />
      <div className="mt-3 min-h-0 flex-1 overflow-auto">
        {filtered.map((employee) => (
          <ListRow
            key={employee.employeeId}
            title={employee.name}
            subtitle={`${employee.employeeId} • ${employee.department}`}
            onClick={() => {
              onPick(employee)
              onOpenChange(false)
            }}
          />
        ))}
      </div>
    </Body>
  )
}

interface SavedGroupPickerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  savedGroups: SavedAssignmentGroup[]
  onPick: (group: SavedAssignmentGroup) => void
}

export function SavedGroupPickerDialog(props: SavedGroupPickerProps) {
  return (
    <Dialog
      open={props.open}
      onOpenChange={props.onOpenChange}
      title="Use saved group"
      width={568}
      actions={
        <ActionButton variant="text" onClick={() => props.onOpenChange(false)}>
          Cancel
        </ActionButton>
      }
    >
      {props.open && <SavedGroupPickerBody {...props} />}
    </Dialog>
  )
}

function SavedGroupPickerBody({ savedGroups, onPick, onOpenChange }: SavedGroupPickerProps) {
  const [query, setQuery] = useState('')
  const filtered = savedGroups.filter((saved) =>
    `${saved.name} ${saved.group.departments.join(' ')} ${saved.group.mailingLists.join(' ')}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  )
  return (
    <Body height={420}>
      <SearchBox value={query} onChange={setQuery} placeholder="Search saved groups" />
      <div className="mt-3 min-h-0 flex-1 divide-y divide-light-gray overflow-auto">
        {filtered.map((saved) => (
          <ListRow
            key={saved.savedGroupId}
            title={saved.name}
            subtitle={savedGroupSummary(saved.group)}
            onClick={() => {
              onPick(saved)
              onOpenChange(false)
            }}
          />
        ))}
      </div>
    </Body>
  )
}
