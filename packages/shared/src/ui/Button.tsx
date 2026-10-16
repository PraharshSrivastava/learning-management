import clsx from 'clsx'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Icon, type IconName } from './icons/Icon'
import { Spinner } from './Spinner'

type Variant = 'primary' | 'secondary' | 'text'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  icon?: IconName
  iconSize?: number
  loading?: boolean
  children?: ReactNode
}

/** Pill buttons from AppTheme: FilledButton (primary), OutlinedButton (secondary), TextButton (text). */
const variants: Record<Variant, string> = {
  primary:
    'bg-primary-blue text-white px-6 hover:bg-[#0a3d8a] disabled:bg-surface-disabled disabled:text-gray',
  secondary:
    'bg-transparent text-text-black border border-input-border px-[22px] hover:bg-[#f2f5f9] disabled:text-gray',
  text: 'bg-transparent text-primary-blue px-3 hover:bg-brand-blue-50 disabled:text-gray',
}

export function Button({
  variant = 'primary',
  icon,
  iconSize = 18,
  loading = false,
  disabled,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={clsx(
        'inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-full font-dm text-sm font-bold transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light disabled:cursor-not-allowed',
        variants[variant],
        className,
      )}
      {...rest}
    >
      {loading ? (
        <Spinner size={iconSize} strokeWidth={2} color="currentColor" />
      ) : (
        icon && <Icon name={icon} size={iconSize} />
      )}
      {children}
    </button>
  )
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: IconName
  /** Tooltip and accessible name. */
  label: string
  size?: number
  tonal?: boolean
}

/** Flutter IconButton: 40 px target, 24 px icon. `tonal` matches IconButton.filledTonal. */
export function IconButton({
  icon,
  label,
  size = 24,
  tonal,
  className,
  type = 'button',
  ...rest
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={clsx(
        'inline-flex size-10 items-center justify-center rounded-full transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light disabled:cursor-not-allowed disabled:opacity-40',
        tonal
          ? 'bg-[#dae2f9] text-[#141b2c] hover:bg-[#cdd6f0]'
          : 'text-primary-blue hover:bg-primary-blue/8',
        className,
      )}
      {...rest}
    >
      <Icon name={icon} size={size} />
    </button>
  )
}
