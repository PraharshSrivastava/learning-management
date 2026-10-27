// Dart: frontend/lib/features/performance/searchable_report_filter.dart:1-184 and
// ReportFilterStyle in report_filter_row.dart:5-13.
import * as RadixDialog from '@radix-ui/react-dialog'
import clsx from 'clsx'
import { useState, type ReactNode } from 'react'
import { Button } from '../ui/Button'
import { Icon, type IconName } from '../ui/icons/Icon'
import { Tooltip } from '../ui/Tooltip'
import { AccessGuard } from './AccessGuard'
import { useReport } from './context'
import { OVERLAY_LAYER, WINDOW_LAYER } from '../ui/layers'

type FilterItems = ReadonlyArray<readonly [value: string, label: string]>

interface SearchableFilterProps {
  label: string
  value: string | null
  /** [value, label] pairs in display order (the Dart map). */
  items: FilterItems
  icon: IconName
  width: number
  allowAll?: boolean
  onChange: (value: string | null) => void
}

/**
 * SearchableReportFilter. Searches the complete, permission-scoped option list without changing
 * reports until the person selects a result. The picker keeps the report context key from open
 * time: AccessGuard replaces it when the key changes, and a pick applies only while the key is
 * still current.
 */
export function SearchableFilter({
  label,
  value,
  items,
  icon,
  width,
  allowAll = true,
  onChange,
}: SearchableFilterProps) {
  const { contextKey, isCurrent } = useReport()
  // The context key at open time. null means the picker is closed.
  const [expected, setExpected] = useState<string | null>(null)
  const lower = label.toLowerCase()
  const selected =
    value == null
      ? allowAll
        ? 'All'
        : `Choose ${lower}`
      : (items.find(([id]) => id === value)?.[1] ?? `Selected ${label}`)

  const pick = (picked: string | null) => {
    const opened = expected
    setExpected(null)
    if (opened != null && isCurrent(opened)) onChange(picked)
  }

  return (
    <RadixDialog.Root
      open={expected != null}
      onOpenChange={(open) => setExpected(open ? contextKey : null)}
    >
      <Tooltip content={selected}>
        <RadixDialog.Trigger asChild>
          <button
            type="button"
            aria-label={`${label}: ${selected}`}
            style={{ width }}
            className="flex h-[60px] shrink-0 items-center rounded-xl border border-[#d2e0f0] bg-white px-3.5 py-2 text-left text-primary-blue hover:shadow-[inset_0_0_0_999px_rgb(0_49_122/0.08)] focus-visible:shadow-[inset_0_0_0_999px_rgb(0_49_122/0.1)] focus-visible:outline-none active:shadow-[inset_0_0_0_999px_rgb(0_49_122/0.1)]"
          >
            <Icon name={icon} size={19} />
            <span className="ml-2.5 flex min-w-0 flex-1 flex-col justify-center">
              <span className="truncate text-[11px] leading-[14px] font-medium text-text-secondary">
                {label}
              </span>
              <span className="truncate text-[13px] leading-[18px] font-bold">{selected}</span>
            </span>
            <Icon name="expand_more" size={20} />
          </button>
        </RadixDialog.Trigger>
      </Tooltip>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={`fixed inset-0 ${OVERLAY_LAYER} bg-black/54`} />
        {expected != null && (
          <AccessGuard expected={expected} onClose={() => setExpected(null)}>
            <RadixDialog.Content
              aria-describedby={undefined}
              className={`fixed top-1/2 left-1/2 ${WINDOW_LAYER} flex max-h-[calc(100%-48px)] w-[calc(100%-80px)] max-w-[528px] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[28px] bg-[#e8e7ef] p-6 focus:outline-none`}
            >
              <RadixDialog.Title className="m-0 font-manrope text-2xl leading-[30px] font-extrabold tracking-normal text-text-black">
                {`Select ${lower}`}
              </RadixDialog.Title>
              <div className="mt-4 min-h-0 overflow-auto text-sm text-[#44474e]">
                <FilterDialogBody
                  label={label}
                  value={value}
                  items={items}
                  allowAll={allowAll}
                  onPick={pick}
                />
              </div>
              <div className="mt-6 flex justify-end">
                <Button variant="text" onClick={() => setExpected(null)}>
                  Cancel
                </Button>
              </div>
            </RadixDialog.Content>
          </AccessGuard>
        )}
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}

/** `_FilterDialog` content: 480x420 search box, count, "All" row, divider and results. */
function FilterDialogBody({
  label,
  value,
  items,
  allowAll,
  onPick,
}: {
  label: string
  value: string | null
  items: FilterItems
  allowAll: boolean
  onPick: (value: string | null) => void
}) {
  const [query, setQuery] = useState('')
  const lower = label.toLowerCase()
  const words = query.trim().toLowerCase().split(/\s+/)
  const results = items.filter(([id, name]) =>
    words.every((word) => `${name} ${id}`.toLowerCase().includes(word)),
  )
  const check = <Icon name="check" size={24} className="text-primary-blue" />
  return (
    <div className="flex h-[420px] max-w-[480px] flex-col">
      <div className="relative">
        <Icon
          name="search"
          size={24}
          className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-[#44474e]"
        />
        <input
          type="search"
          value={query}
          autoFocus
          aria-label={`Search ${lower}`}
          placeholder={`Search ${lower}`}
          onChange={(event) => setQuery(event.target.value)}
          className="h-12 w-full rounded-lg border border-input-border bg-white pr-12 pl-12 text-sm text-text-black placeholder:text-gray focus:border-brand-blue-light focus:outline-none [&::-webkit-search-cancel-button]:hidden"
        />
        {query && (
          <Tooltip content="Clear search">
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => setQuery('')}
              className="absolute top-1/2 right-1 inline-flex size-10 -translate-y-1/2 items-center justify-center rounded-full text-[#44474e] hover:bg-black/6"
            >
              <Icon name="close" size={24} />
            </button>
          </Tooltip>
        )}
      </div>
      <p className="m-0 mt-2.5 text-xs text-text-secondary">{results.length} matching options</p>
      {allowAll && (
        <OptionRow
          title={`All ${lower} options`}
          trailing={value == null ? check : null}
          onClick={() => onPick(null)}
        />
      )}
      <hr className="m-0 border-0 border-t border-[#c4c6d0]" />
      {results.length === 0 ? (
        <p className="m-auto text-[#191c20]">No matching options.</p>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto">
          {results.map(([id, name]) => (
            <OptionRow
              key={id}
              title={name}
              subtitle={label === 'Course' ? id : undefined}
              trailing={value === id ? check : null}
              onClick={() => onPick(id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

/** M3 ListTile: 56 px one line, 72 px with a subtitle, padding 16 start and 24 end. */
function OptionRow({
  title,
  subtitle,
  trailing,
  onClick,
}: {
  title: string
  subtitle?: string
  trailing: ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        'flex w-full shrink-0 items-center gap-4 py-2 pr-6 pl-4 text-left hover:bg-black/4 focus-visible:bg-black/6 focus-visible:outline-none',
        subtitle == null ? 'min-h-14' : 'min-h-[72px]',
      )}
    >
      <span className="min-w-0 flex-1">
        <span className="block text-base text-[#191c20]">{title}</span>
        {subtitle != null && (
          <span className="block text-[11px] leading-4 text-text-secondary">{subtitle}</span>
        )}
      </span>
      {trailing}
    </button>
  )
}
