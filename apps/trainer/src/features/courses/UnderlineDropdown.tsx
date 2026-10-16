import { Icon } from '@lms/shared/ui/icons/Icon'
import clsx from 'clsx'
import { useId } from 'react'

interface UnderlineDropdownProps<T extends string> {
  /** Accessible name of the select. */
  label: string
  value: T
  options: readonly { value: T; label: string }[]
  onChange: (value: T) => void
  /** Fill the parent width (isExpanded). Otherwise the width fits the longest option. */
  expanded?: boolean
  className?: string
}

/**
 * Flutter DropdownButton: titleMedium text, a 24 px arrow, and a hairline 8 px above the bottom of
 * the 48 px box. A transparent native select sits on top for the keyboard and screen readers.
 */
export function UnderlineDropdown<T extends string>({
  label,
  value,
  options,
  onChange,
  expanded = false,
  className,
}: UnderlineDropdownProps<T>) {
  const id = useId()
  return (
    <div className={clsx('relative h-12 shrink-0', expanded ? 'block' : 'inline-block', className)}>
      <span
        aria-hidden
        className="grid h-full items-center pr-6 pb-px font-manrope text-lg leading-[24.3px] font-bold tracking-normal whitespace-nowrap text-primary-blue"
      >
        {options.map((option) => (
          // Every option takes the same cell, so the box is as wide as the longest one.
          <span
            key={option.value}
            className={clsx('[grid-area:1/1]', option.value !== value && 'invisible')}
          >
            {option.label}
          </span>
        ))}
      </span>
      <Icon
        name="arrow_drop_down"
        size={24}
        color="#616161"
        className="pointer-events-none absolute top-3 right-0"
      />
      <span aria-hidden className="absolute inset-x-0 bottom-2 h-0.5 bg-[#dedede]" />
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
        className="absolute inset-0 w-full cursor-pointer appearance-none opacity-0"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}
