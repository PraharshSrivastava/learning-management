import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import clsx from 'clsx'
import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from 'react'

interface CompactButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'filled' | 'outlined'
  icon?: IconName
  iconSize?: number
  /** Outlined button with the brand-blue-100 fill (the active builder toolbar tab). */
  active?: boolean
}

/**
 * AppTheme FilledButton and OutlinedButton at desktop density: pill, 36 px high, DM Sans 14 bold.
 * The shared Button is 44 px high, which is the mobile size.
 */
export function CompactButton({
  variant = 'filled',
  icon,
  iconSize = 18,
  active = false,
  className,
  children,
  type = 'button',
  ...rest
}: CompactButtonProps) {
  return (
    <button
      type={type}
      className={clsx(
        'inline-flex min-h-9 min-w-11 items-center justify-center gap-2 rounded-full font-dm text-sm leading-[18px] font-bold tracking-normal transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light disabled:cursor-not-allowed',
        variant === 'filled'
          ? 'bg-primary-blue text-white hover:bg-[#0a3d8a] disabled:bg-surface-disabled disabled:text-gray'
          : clsx(
              // Flutter paints the side inside the padding, so an inset ring replaces the border.
              'text-text-black inset-ring inset-ring-input-border disabled:text-gray',
              active ? 'bg-brand-blue-100' : 'bg-transparent hover:bg-[#f2f5f9]',
            ),
        className,
      )}
      {...rest}
    >
      {icon && <Icon name={icon} size={iconSize} />}
      {children}
    </button>
  )
}

/** Builder field label: Barlow 13 semibold gray, 7 px above the field, 12 px after it. */
export function FieldLabel({
  htmlFor,
  label,
  children,
}: {
  htmlFor: string
  label: string
  children: ReactNode
}) {
  return (
    <div className="mb-3">
      <label
        htmlFor={htmlFor}
        className="mb-[7px] block font-barlow text-[13px] leading-[19.5px] font-semibold text-gray"
      >
        {label}
      </label>
      {children}
    </div>
  )
}

// Flutter dense outline input at desktop density: 34 px high, 22 px lines, radius 8.
// M3 bodyLarge adds 0.5 px letter spacing.
const inputBase =
  'block w-full rounded-lg border border-input-border bg-white px-[13px] py-[5px] font-dm text-[15px] leading-[22px] tracking-[0.5px] text-text-black ' +
  'placeholder:text-gray focus:border-brand-blue-light focus:shadow-[0_0_0_0.4px_var(--color-brand-blue-light)] focus:outline-none'

export function BuilderInput({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={clsx(inputBase, 'h-[34px]', className)} {...rest} />
}

/**
 * Flutter scrolls the text inside the content padding, so the border and the padding stay clear
 * when the text scrolls. The border and the padding are on a wrapper for the same result. The
 * 8 px scrollbar gutter takes 8 px of the 13 px right padding and is always kept, so the text is as
 * wide as in Flutter, with or without a scrollbar.
 */
export function BuilderTextArea({
  className,
  rows = 3,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <div
      className={clsx(
        'rounded-lg border border-input-border bg-white py-[5px] pr-[5px] pl-[13px]',
        'focus-within:border-brand-blue-light focus-within:shadow-[0_0_0_0.4px_var(--color-brand-blue-light)]',
        className,
      )}
    >
      <textarea
        rows={rows}
        className={clsx(
          'block w-full resize-none bg-transparent font-dm text-[15px] leading-[22px] tracking-[0.5px] text-text-black placeholder:text-gray focus:outline-none',
          // Flutter desktop Scrollbar: an 8 px light thumb with round ends and no track or arrows.
          '[scrollbar-gutter:stable] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-button]:hidden',
          '[&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-[#e4e4e5]',
        )}
        {...rest}
      />
    </div>
  )
}

interface BuilderSelectProps {
  id?: string
  value: string
  options: readonly { value: string; label: string }[]
  onChange: (value: string) => void
  className?: string
}

/**
 * DropdownButtonFormField closed look: titleMedium text, ellipsis, and a gray arrow. The option
 * list is the native one, not a copy of the Material menu.
 */
export function BuilderSelect({ id, value, options, onChange, className }: BuilderSelectProps) {
  return (
    <div className={clsx('relative h-9 w-full', className)}>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={clsx(
          'block size-full cursor-pointer appearance-none truncate rounded-lg bg-white pr-9 pl-[15px] inset-ring inset-ring-input-border',
          'font-manrope text-lg leading-[24.3px] font-bold tracking-[0.15px] text-primary-blue',
          'focus-visible:shadow-[0_0_0_0.4px_var(--color-brand-blue-light)] focus-visible:outline-none focus-visible:inset-ring-brand-blue-light',
        )}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <Icon
        name="arrow_drop_down"
        size={24}
        color="#616161"
        className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2"
      />
    </div>
  )
}

/** CheckboxListTile (dense, leading box, desktop density): 40 px row, 18 px box. */
export function CheckboxRow({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="group flex h-10 cursor-pointer items-center">
      <span className="relative flex size-10 shrink-0 items-center justify-center">
        <input
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          className="peer absolute inset-0 size-full cursor-pointer appearance-none rounded-full hover:bg-primary-blue/8 focus-visible:bg-primary-blue/12 focus-visible:outline-none"
        />
        <span
          aria-hidden
          className={clsx(
            'pointer-events-none relative flex size-[18px] items-center justify-center rounded-[2px]',
            checked ? 'bg-primary-blue' : 'border-2 border-[#44474e]',
          )}
        >
          {checked && (
            <svg viewBox="0 0 18 18" width={18} height={18} fill="none">
              <path d="M4 9.2l3.3 3.3L14 5.8" stroke="white" strokeWidth={2} />
            </svg>
          )}
        </span>
      </span>
      {/* ListTile titles inherit the bodyLarge letter spacing (0.5 px). */}
      <span className="ml-3 font-barlow text-[13px] leading-[19.5px] font-medium tracking-[0.5px] text-[#1a1b20]">
        {label}
      </span>
    </label>
  )
}

/** Builder status pill: error red, active blue, or inactive gray. */
export function StatusPill({
  text,
  active = false,
  error = false,
}: {
  text: string
  active?: boolean
  error?: boolean
}) {
  return (
    <span
      role="status"
      className={clsx(
        'shrink-0 rounded-full px-2.5 py-1.5 font-barlow text-[11px] leading-4 font-semibold whitespace-nowrap',
        error
          ? 'bg-accent-red/10 text-accent-red'
          : active
            ? 'bg-brand-blue-100 text-primary-blue'
            : 'bg-light-gray text-gray',
      )}
    >
      {text}
    </span>
  )
}
