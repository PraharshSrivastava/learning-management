import clsx from 'clsx'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Icon, type IconName } from './icons/Icon'

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  selected?: boolean
  icon?: IconName
  /** Shows a remove button, like Flutter InputChip.onDeleted. */
  onRemove?: () => void
  removeLabel?: string
  children: ReactNode
}

/** Pill chip from AppTheme.chipTheme: white, light-gray border, brand-blue-100 when selected. */
export function Chip({
  selected,
  icon,
  onRemove,
  removeLabel = 'Remove',
  children,
  className,
  type = 'button',
  ...rest
}: ChipProps) {
  const body = (
    <>
      {selected && !icon && <Icon name="check" size={18} />}
      {icon && <Icon name={icon} size={18} />}
      <span>{children}</span>
    </>
  )
  const classes = clsx(
    'inline-flex h-8 items-center gap-2 rounded-full border px-3 text-sm font-medium transition-colors',
    selected
      ? 'border-brand-blue-light bg-brand-blue-100 text-primary-blue'
      : 'border-light-gray bg-white text-text-black hover:bg-surface-secondary',
    className,
  )
  if (onRemove) {
    return (
      <span className={clsx(classes, 'pr-1.5')}>
        {body}
        <button
          type="button"
          aria-label={`${removeLabel} ${typeof children === 'string' ? children : ''}`.trim()}
          onClick={onRemove}
          className="rounded-full p-0.5 hover:bg-black/8"
        >
          <Icon name="close" size={16} />
        </button>
      </span>
    )
  }
  return (
    <button
      type={type}
      aria-pressed={selected}
      className={clsx(classes, 'focus-visible:outline-2 focus-visible:outline-brand-blue-light')}
      {...rest}
    >
      {body}
    </button>
  )
}
