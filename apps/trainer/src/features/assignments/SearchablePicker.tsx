// Observer picker (Flutter SearchableReportFilter with allowAll false).
import { Dialog } from '@lms/shared/ui/Dialog'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import { useState } from 'react'
import { ActionButton, SearchBox } from './controls'
import { ListRow } from './pickers'

interface SearchablePickerProps {
  label: string
  value: string | null
  /** id to display name, in display order. */
  items: ReadonlyArray<readonly [string, string]>
  disabled?: boolean
  onChange: (value: string) => void
}

export function SearchablePicker({
  label,
  value,
  items,
  disabled,
  onChange,
}: SearchablePickerProps) {
  const [open, setOpen] = useState(false)
  const lower = label.toLowerCase()
  const selected =
    value == null
      ? `Choose ${lower}`
      : (items.find(([id]) => id === value)?.[1] ?? `Selected ${label}`)
  return (
    <>
      <Tooltip content={selected}>
        <button
          type="button"
          disabled={disabled}
          aria-label={`${label}: ${selected}`}
          onClick={() => setOpen(true)}
          className="flex h-[60px] w-[260px] shrink-0 items-center gap-2.5 rounded-xl border border-[#d2e0f0] bg-white px-3.5 py-2 text-left text-primary-blue hover:bg-primary-blue/4 focus-visible:outline-2 focus-visible:outline-brand-blue-light disabled:opacity-40"
        >
          <Icon name="search" size={19} />
          <span className="flex min-w-0 flex-1 flex-col justify-center">
            <span className="text-[11px] leading-[14px] font-medium text-text-secondary">
              {label}
            </span>
            <span className="truncate text-[13px] leading-[18px] font-bold">{selected}</span>
          </span>
          <Icon name="expand_more" size={20} />
        </button>
      </Tooltip>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={`Select ${lower}`}
        width={528}
        actions={
          <ActionButton variant="text" onClick={() => setOpen(false)}>
            Cancel
          </ActionButton>
        }
      >
        {open && (
          <PickerBody
            label={lower}
            value={value}
            items={items}
            onPick={(id) => {
              setOpen(false)
              onChange(id)
            }}
          />
        )}
      </Dialog>
    </>
  )
}

function PickerBody({
  label,
  value,
  items,
  onPick,
}: {
  label: string
  value: string | null
  items: SearchablePickerProps['items']
  onPick: (id: string) => void
}) {
  const [query, setQuery] = useState('')
  const words = query.trim().toLowerCase().split(/\s+/)
  const results = items.filter(([id, name]) =>
    words.every((word) => `${name} ${id}`.toLowerCase().includes(word)),
  )
  return (
    <div className="flex h-[420px] flex-col">
      <SearchBox
        value={query}
        onChange={setQuery}
        onClear={() => setQuery('')}
        placeholder={`Search ${label}`}
        autoFocus
      />
      <p className="mt-2.5 text-xs text-text-secondary">{results.length} matching options</p>
      <hr className="mt-1 border-[#c4c6d0]" />
      {results.length === 0 ? (
        <p className="m-auto text-[#191c20]">No matching options.</p>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto">
          {results.map(([id, name]) => (
            <ListRow
              key={id}
              title={name}
              trailing={
                value === id ? <Icon name="check" size={24} className="text-primary-blue" /> : null
              }
              onClick={() => onPick(id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
