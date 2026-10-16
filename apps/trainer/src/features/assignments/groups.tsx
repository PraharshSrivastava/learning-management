// Include and exclude group editors (Flutter _GroupList, _AssignmentGroupCard,
// _EmployeeSelector, _MultiSelectDropdown).
import {
  emptyAssignmentGroup,
  hasAttributeFilters,
  hasEmployeeSelection,
  hasMixedSelection,
  type AssignmentGroup,
  type AssignmentOptions,
  type Employee,
  type SavedAssignmentGroup,
} from '@lms/shared/models'
import { IconButton } from '@lms/shared/ui/Button'
import { useState } from 'react'
import { ActionButton, ChoiceChip, InputChip } from './controls'
import { EmployeePickerDialog, MultiSelectDialog, SavedGroupPickerDialog } from './pickers'

/** Digits-only text to a number, or null when empty. */
export const digitsToNumber = (text: string): number | null => {
  const digits = text.replace(/\D/g, '')
  return digits === '' ? null : Number.parseInt(digits, 10)
}

interface GroupListProps {
  groups: AssignmentGroup[]
  savedGroups: SavedAssignmentGroup[]
  options: AssignmentOptions
  allowJoinedFilter?: boolean
  /** Employee picker title: "Add employee" for include groups, "Exclude employee" for exclusions. */
  pickerTitle: string
  label: string
  onChange: (groups: AssignmentGroup[]) => void
}

export function GroupList({
  groups,
  savedGroups,
  options,
  allowJoinedFilter = true,
  pickerTitle,
  label,
  onChange,
}: GroupListProps) {
  const [savedOpen, setSavedOpen] = useState(false)
  return (
    <div className="flex flex-col items-start">
      {groups.map((group, index) => (
        <div key={index} className="mb-3 w-full">
          <GroupCard
            index={index}
            label={label}
            group={group}
            options={options}
            allowJoinedFilter={allowJoinedFilter}
            pickerTitle={pickerTitle}
            onChange={(next) => onChange(groups.map((item, i) => (i === index ? next : item)))}
            onDelete={() => onChange(groups.filter((_, i) => i !== index))}
          />
        </div>
      ))}
      <div className="flex flex-wrap gap-x-2.5 gap-y-2">
        <ActionButton
          icon="add"
          iconSize={18}
          onClick={() =>
            onChange([...groups, emptyAssignmentGroup({ name: `Group ${groups.length + 1}` })])
          }
        >
          Add group
        </ActionButton>
        {savedGroups.length > 0 && (
          <ActionButton icon="bookmark_add_outlined" onClick={() => setSavedOpen(true)}>
            Use saved group
          </ActionButton>
        )}
      </div>
      <SavedGroupPickerDialog
        open={savedOpen}
        onOpenChange={setSavedOpen}
        savedGroups={savedGroups}
        onPick={(saved) => onChange([...groups, saved.group])}
      />
    </div>
  )
}

interface GroupCardProps {
  index: number
  label: string
  group: AssignmentGroup
  options: AssignmentOptions
  allowJoinedFilter: boolean
  pickerTitle: string
  onChange: (group: AssignmentGroup) => void
  onDelete: () => void
}

function GroupCard({
  index,
  label,
  group,
  options,
  allowJoinedFilter,
  pickerTitle,
  onChange,
  onDelete,
}: GroupCardProps) {
  const mixed = hasMixedSelection(group)
  const showEmployees = !hasAttributeFilters(group) || mixed
  const showAttributes = !hasEmployeeSelection(group) || mixed
  const displayName = group.name.trim() ? group.name : `Group ${index + 1}`
  return (
    <section
      aria-label={`${label} group ${index + 1}`}
      className="rounded-lg border border-[#e6e9ef] p-3.5"
    >
      <div className="flex items-center gap-2">
        <input
          aria-label="Group name"
          placeholder="Group name"
          value={displayName}
          onChange={(event) => onChange({ ...group, name: event.target.value })}
          className="h-[37px] min-w-0 flex-1 rounded-lg border border-input-border bg-white px-4 text-[15px] font-medium text-text-black placeholder:text-gray focus:border-[1.4px] focus:border-brand-blue-light focus:outline-none"
        />
        <IconButton icon="delete_outline" label="Remove group" onClick={onDelete} />
      </div>
      {mixed && (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-[#f5c451] bg-[#fff8e6] p-3 text-sm font-medium text-[#7a4f01]"
        >
          This saved group mixes specific employees with filters. Clear one side before saving.
        </div>
      )}
      {showEmployees && (
        <EmployeeSelector
          title="Specific employees"
          actionLabel="Add employee"
          pickerTitle={pickerTitle}
          employees={options.employees}
          selectedIds={group.employeeIds}
          onChange={(employeeIds) => onChange({ ...group, employeeIds })}
        />
      )}
      {showAttributes && (
        <>
          {showEmployees && <p className="my-3 font-medium text-[#667085]">or</p>}
          <MultiSelectField
            title="Departments"
            values={options.departments}
            selected={group.departments}
            onChange={(departments) => onChange({ ...group, departments })}
          />
          <div className="h-4" />
          <MultiSelectField
            title="Mailing lists"
            values={options.mailingLists}
            selected={group.mailingLists}
            onChange={(mailingLists) => onChange({ ...group, mailingLists })}
          />
          {allowJoinedFilter && (
            <div className="mt-4 w-[280px]">
              <OutlinedNumberField
                label="Joined less than days ago"
                value={group.joinedLessThanDaysAgo}
                onChange={(joinedLessThanDaysAgo) => onChange({ ...group, joinedLessThanDaysAgo })}
              />
            </div>
          )}
        </>
      )}
    </section>
  )
}

/** Dense outlined digits-only field with a floating label (Flutter OutlineInputBorder, isDense). */
export function OutlinedNumberField({
  label,
  value,
  onChange,
  onBlur,
  disabled,
}: {
  label: string
  value: number | null | string
  onChange: (value: number | null) => void
  onBlur?: () => void
  disabled?: boolean
}) {
  const [text, setText] = useState(value == null ? '' : String(value))
  const [prev, setPrev] = useState(value)
  // Follow outside changes (for example a reload) without fighting local typing.
  if (prev !== value) {
    setPrev(value)
    if (digitsToNumber(text) !== (value == null || value === '' ? null : Number(value))) {
      setText(value == null ? '' : String(value))
    }
  }
  return (
    <label className="relative block">
      <input
        inputMode="numeric"
        value={text}
        disabled={disabled}
        placeholder=" "
        onBlur={onBlur}
        onChange={(event) => {
          const next = event.target.value.replace(/\D/g, '')
          setText(next)
          onChange(digitsToNumber(next))
        }}
        className="peer h-[38px] w-full rounded-lg border border-input-border bg-white px-[15px] text-[15px] text-text-black focus:border-[1.4px] focus:border-brand-blue-light focus:outline-none disabled:bg-surface-secondary disabled:text-gray"
      />
      <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-[15px] text-text-secondary transition-all peer-not-placeholder-shown:top-0 peer-not-placeholder-shown:left-3 peer-not-placeholder-shown:bg-white peer-not-placeholder-shown:px-1 peer-not-placeholder-shown:text-xs peer-not-placeholder-shown:tracking-normal peer-focus:top-0 peer-focus:left-3 peer-focus:bg-white peer-focus:px-1 peer-focus:text-xs peer-focus:tracking-normal peer-focus:text-brand-blue-light">
        {label}
      </span>
    </label>
  )
}

interface EmployeeSelectorProps {
  title: string
  actionLabel: string
  pickerTitle: string
  employees: Employee[]
  selectedIds: string[]
  onChange: (ids: string[]) => void
}

function EmployeeSelector({
  title,
  actionLabel,
  pickerTitle,
  employees,
  selectedIds,
  onChange,
}: EmployeeSelectorProps) {
  const [open, setOpen] = useState(false)
  // Chips follow the directory order, as in Flutter. Unknown ids come last so they can be removed.
  const known = employees.filter((e) => selectedIds.includes(e.employeeId))
  const unknown = selectedIds.filter((id) => !employees.some((e) => e.employeeId === id))
  const remove = (id: string) => onChange(selectedIds.filter((item) => item !== id))
  return (
    <div>
      <p className="font-medium text-text-black">{title}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {known.map((e) => (
          <InputChip
            key={e.employeeId}
            label={`${e.name} (${e.employeeId})`}
            onRemove={() => remove(e.employeeId)}
          />
        ))}
        {unknown.map((id) => (
          <InputChip key={id} label={`Unavailable employee (${id})`} onRemove={() => remove(id)} />
        ))}
        <ChoiceChip icon="person_add_alt_1" onClick={() => setOpen(true)}>
          {actionLabel}
        </ChoiceChip>
      </div>
      <EmployeePickerDialog
        open={open}
        onOpenChange={setOpen}
        title={pickerTitle}
        employees={employees.filter(
          (e) => e.status === 'active' && !selectedIds.includes(e.employeeId),
        )}
        onPick={(employee) => onChange([...selectedIds, employee.employeeId])}
      />
    </div>
  )
}

interface MultiSelectFieldProps {
  title: string
  values: string[]
  selected: string[]
  onChange: (values: string[]) => void
}

function MultiSelectField({ title, values, selected, onChange }: MultiSelectFieldProps) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <p className="font-medium text-text-black">{title}</p>
      <ActionButton
        className="mt-2"
        icon="arrow_drop_down_circle_outlined"
        disabled={values.length === 0}
        onClick={() => setOpen(true)}
      >
        {selected.length === 0 ? `Select ${title.toLowerCase()}` : `${selected.length} selected`}
      </ActionButton>
      {selected.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {selected.map((value) => (
            <InputChip
              key={value}
              label={value}
              onRemove={() => onChange(selected.filter((item) => item !== value))}
            />
          ))}
        </div>
      )}
      <MultiSelectDialog
        open={open}
        onOpenChange={setOpen}
        title={title}
        values={values}
        selected={selected}
        onApply={onChange}
      />
    </div>
  )
}
