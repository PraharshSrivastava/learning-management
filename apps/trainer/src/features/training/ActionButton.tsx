import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import clsx from 'clsx'
import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from 'react'

interface ActionButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'style'> {
  icon?: IconName
  iconSize: number
  /** Fill color of the enabled button. */
  background?: string
  outlined?: boolean
  padding: string
  /** Classes for the disabled look. Default is the Material 3 disabled button. */
  disabledClassName?: string
  style?: CSSProperties
  children: ReactNode
}

/**
 * Flutter ElevatedButton and OutlinedButton as used by the training portal: radius 6, 36 px
 * minimum height, DM Sans 14 bold, no letter spacing. Disabled colors are the Material 3 defaults.
 */
export function ActionButton({
  icon,
  iconSize,
  background = 'var(--color-primary-blue)',
  outlined = false,
  padding,
  disabledClassName = 'disabled:bg-[#1a1b20]/12 disabled:text-[#1a1b20]/38',
  className,
  style,
  children,
  type = 'button',
  ...rest
}: ActionButtonProps) {
  return (
    <button
      type={type}
      className={clsx(
        'inline-flex min-h-9 min-w-11 items-center leading-4 justify-center gap-2 rounded-[6px] font-dm text-sm font-bold tracking-normal whitespace-nowrap transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light',
        'disabled:cursor-not-allowed',
        !outlined &&
          'bg-(--action-bg) text-white hover:brightness-110 disabled:hover:brightness-100',
        !outlined && disabledClassName,
        className,
      )}
      style={
        { padding, '--action-bg': outlined ? undefined : background, ...style } as CSSProperties
      }
      {...rest}
    >
      {icon && <Icon name={icon} size={iconSize} />}
      {children}
    </button>
  )
}
