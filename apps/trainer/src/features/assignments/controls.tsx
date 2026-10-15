// Local primitives for the Assign tab. Shared UI has no Switch, Checkbox or compact buttons.
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import clsx from 'clsx'
import {
  forwardRef,
  useSyncExternalStore,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from 'react'

type Variant = 'filled' | 'outlined' | 'text'

interface ActionButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  icon?: IconName
  iconSize?: number
}

const variants: Record<Variant, string> = {
  filled:
    'bg-primary-blue px-6 text-white hover:bg-[#0a3d8a] disabled:bg-surface-disabled disabled:text-gray',
  outlined:
    'border border-input-border px-[22px] text-text-black hover:bg-[#f2f5f9] disabled:text-gray',
  text: 'px-3 text-primary-blue hover:bg-brand-blue-50 disabled:text-gray',
}

/** Flutter Filled/Outlined/TextButton at compact desktop density (36 px high). */
export const ActionButton = forwardRef<HTMLButtonElement, ActionButtonProps>(function ActionButton(
  { variant = 'outlined', icon, iconSize = 18, className, children, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={clsx(
        'inline-flex h-9 min-w-11 shrink-0 items-center justify-center gap-2 rounded-full font-dm text-sm leading-none font-bold tracking-normal whitespace-nowrap transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light disabled:cursor-not-allowed',
        variants[variant],
        className,
      )}
      {...rest}
    >
      {icon && <Icon name={icon} size={iconSize} />}
      {children}
    </button>
  )
})

interface SwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  label?: string
  id?: string
}

/** Material 3 Switch (52x32) with the primary-blue scheme. */
export function Switch({ checked, onChange, disabled, label, id }: SwitchProps) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={clsx(
        'group relative inline-flex h-8 w-[52px] shrink-0 items-center rounded-full border-2 transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light disabled:opacity-40',
        checked ? 'border-primary-blue bg-primary-blue' : 'border-[#757780] bg-[#e2e2e9]',
      )}
    >
      <span
        aria-hidden
        className={clsx(
          'absolute top-1/2 -translate-y-1/2 rounded-full transition-all',
          checked ? 'left-[22px] size-6 bg-white' : 'left-[6px] size-4 bg-[#757780]',
        )}
      />
    </button>
  )
}

interface CheckboxRowProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  checked: boolean
  onChange: (checked: boolean) => void
  children: ReactNode
}

/** Flutter CheckboxListTile(dense): label left, 18 px box right. */
export function CheckboxRow({ checked, onChange, children, disabled, ...rest }: CheckboxRowProps) {
  return (
    <label
      className={clsx(
        'flex min-h-12 items-center gap-4 px-4 text-sm text-[#191c20]',
        disabled ? 'opacity-40' : 'cursor-pointer hover:bg-black/4',
      )}
    >
      <span className="min-w-0 flex-1">{children}</span>
      <span className="relative inline-flex size-10 shrink-0 items-center justify-center">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
          className="peer absolute inset-0 size-full cursor-pointer appearance-none rounded-full focus-visible:outline-2 focus-visible:outline-brand-blue-light"
          {...rest}
        />
        <span
          aria-hidden
          className={clsx(
            'pointer-events-none flex size-[18px] items-center justify-center rounded-[2px] border-2',
            checked ? 'border-primary-blue bg-primary-blue text-white' : 'border-[#44474e]',
          )}
        >
          {checked && <Icon name="check" size={14} />}
        </span>
      </span>
    </label>
  )
}

/** Live media query match. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query)
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    () => window.matchMedia(query).matches,
    () => false,
  )
}

type NoticeTone = 'info' | 'success' | 'warning' | 'error'

const noticeTones: Record<NoticeTone, { box: string; icon: IconName }> = {
  info: { box: 'bg-[#edf5ff] border-[#b7e4c7] text-primary-blue', icon: 'info_outline' },
  success: { box: 'bg-[#effaf3] border-[#b7e4c7] text-[#087443]', icon: 'check_circle_outline' },
  warning: { box: 'bg-[#fff8e8] border-[#ffccd5] text-[#805300]', icon: 'warning_amber_rounded' },
  error: { box: 'bg-[#fff1f3] border-[#ffccd5] text-[#a11d33]', icon: 'error_outline' },
}

/** Tone rules from the Flutter _Notice widget. */
export function noticeTone(text: string, isError: boolean): NoticeTone {
  if (isError) return text.includes('Observer') ? 'warning' : 'error'
  return text.includes('successfully') || text.includes('saved.') ? 'success' : 'info'
}

/** Rule-view notice: icon, text and an optional dismiss button. */
export function Notice({
  text,
  isError,
  onDismiss,
}: {
  text: string
  isError: boolean
  onDismiss?: () => void
}) {
  const tone = noticeTones[noticeTone(text, isError)]
  return (
    <div
      role={isError ? 'alert' : 'status'}
      className={clsx('flex items-start gap-2.5 rounded-lg border p-3', tone.box)}
    >
      <Icon name={tone.icon} size={24} className="shrink-0" />
      <p className="min-w-0 flex-1 self-center text-sm whitespace-pre-line">{text}</p>
      {onDismiss && (
        <button
          type="button"
          aria-label="Dismiss message"
          title="Dismiss message"
          onClick={onDismiss}
          className="-my-2 -mr-1 inline-flex size-10 shrink-0 items-center justify-center rounded-full hover:bg-black/6"
        >
          <Icon name="close" size={18} />
        </button>
      )}
    </div>
  )
}

/** Observer panel notice (info or warning). */
export function ObserverNotice({ text, warning }: { text: string; warning: boolean }) {
  return (
    <div
      role={warning ? 'alert' : 'note'}
      className={clsx(
        'mb-2 flex items-center gap-2 rounded-lg border p-3 text-sm',
        warning
          ? 'border-[#f1d99b] bg-[#fff8e8] text-[#805300]'
          : 'border-[#c6ddf8] bg-[#edf5ff] text-[#103b78]',
      )}
    >
      <Icon name={warning ? 'warning_amber_rounded' : 'info_outline'} size={20} />
      <span className="min-w-0 flex-1">{text}</span>
    </div>
  )
}

/** Search box used inside picker dialogs (Flutter TextField with a search prefix). */
export function SearchBox({
  value,
  onChange,
  placeholder,
  autoFocus,
  onClear,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
  autoFocus?: boolean
  onClear?: () => void
}) {
  return (
    <div className="relative">
      <Icon
        name="search"
        size={20}
        className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-[#44474e]"
      />
      <input
        type="search"
        value={value}
        autoFocus={autoFocus}
        aria-label={placeholder}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="h-12 w-full rounded-lg border border-input-border bg-white pr-10 pl-11 text-sm text-text-black placeholder:text-gray focus:border-brand-blue-light focus:outline-none [&::-webkit-search-cancel-button]:hidden"
      />
      {onClear && value && (
        <button
          type="button"
          aria-label="Clear search"
          title="Clear search"
          onClick={onClear}
          className="absolute top-1/2 right-1 inline-flex size-10 -translate-y-1/2 items-center justify-center rounded-full text-[#44474e] hover:bg-black/6"
        >
          <Icon name="close" size={20} />
        </button>
      )}
    </div>
  )
}

/** Flutter InputChip with a delete icon (30 px high, Roboto label). */
export function InputChip({
  label,
  onRemove,
  removeLabel = 'Remove',
  disabled,
}: {
  label: string
  onRemove: () => void
  removeLabel?: string
  disabled?: boolean
}) {
  return (
    <span className="inline-flex h-[30px] items-center gap-2 rounded-full border border-light-gray bg-white pr-2 pl-4 font-roboto text-sm tracking-[0.1px] text-text-black">
      <span className="truncate">{label}</span>
      <button
        type="button"
        disabled={disabled}
        aria-label={`${removeLabel} ${label}`}
        onClick={onRemove}
        className="-mr-0.5 inline-flex size-[22px] items-center justify-center rounded-full text-[#44474e] hover:bg-black/8 disabled:opacity-40"
      >
        <Icon name="close" size={18} />
      </button>
    </span>
  )
}

/** Flutter ChoiceChip or ActionChip (30 px high). Selected chips show a check. */
export function ChoiceChip({
  selected,
  icon,
  children,
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean; icon?: IconName }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={clsx(
        'inline-flex h-[30px] items-center gap-2 rounded-full border font-roboto text-sm tracking-[0.1px] text-text-black transition-colors',
        'focus-visible:outline-2 focus-visible:outline-brand-blue-light disabled:opacity-60',
        selected || icon ? 'pr-4 pl-2' : 'px-4',
        selected
          ? 'border-transparent bg-brand-blue-100'
          : 'border-light-gray bg-white hover:bg-black/4',
        className,
      )}
      {...rest}
    >
      {selected && (
        // Flutter draws a small checkmark inside the 18 px avatar box.
        <span className="-ml-0.5 inline-flex size-[18px] items-center justify-center">
          <Icon name="check" size={12} className="text-primary-blue" />
        </span>
      )}
      {icon && <Icon name={icon} size={18} className="text-primary-blue" />}
      {children}
    </button>
  )
}
