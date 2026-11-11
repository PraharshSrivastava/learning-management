import clsx from 'clsx'

export interface SwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  label?: string
  id?: string
  /**
   * "default" is the Material 3 52x32 switch. "compact" (40x24) fits a 36 px toolbar control.
   * "labelled" (52x24) fits the same toolbar and writes ON or OFF inside the track.
   */
  size?: 'default' | 'compact' | 'labelled'
}

const EASE = 'duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]'

/** Material 3 Switch with the primary-blue scheme. */
export function Switch({ checked, onChange, disabled, label, id, size = 'default' }: SwitchProps) {
  if (size === 'labelled') {
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
          'relative inline-flex h-6 w-[52px] shrink-0 items-center rounded-full transition-colors',
          EASE,
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light disabled:opacity-40',
          checked ? 'bg-primary-blue' : 'bg-[#e2e8f0]',
        )}
      >
        <span
          aria-hidden
          className={clsx(
            'absolute top-1/2 left-2 -translate-y-1/2 text-[10px] leading-none font-semibold tracking-[0.3px] text-white transition-opacity',
            EASE,
            checked ? 'opacity-100' : 'opacity-0',
          )}
        >
          ON
        </span>
        <span
          aria-hidden
          className={clsx(
            'absolute top-1/2 right-[7px] -translate-y-1/2 text-[10px] leading-none font-semibold tracking-[0.3px] text-text-secondary transition-opacity',
            EASE,
            checked ? 'opacity-0' : 'opacity-100',
          )}
        >
          OFF
        </span>
        <span
          aria-hidden
          className={clsx(
            'absolute top-1/2 size-5 -translate-y-1/2 rounded-full bg-white shadow-[0_1px_2px_rgb(0_0_0/0.18)] transition-[left]',
            EASE,
            checked ? 'left-[30px]' : 'left-0.5',
          )}
        />
      </button>
    )
  }

  const compact = size === 'compact'
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
        'group relative inline-flex shrink-0 items-center rounded-full border-2 transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light disabled:opacity-40',
        compact ? 'h-6 w-10' : 'h-8 w-[52px]',
        checked ? 'border-primary-blue bg-primary-blue' : 'border-[#757780] bg-[#e2e2e9]',
      )}
    >
      <span
        aria-hidden
        className={clsx(
          'absolute top-1/2 -translate-y-1/2 rounded-full transition-all',
          compact
            ? checked
              ? 'left-[17px] size-[18px] bg-white'
              : 'left-[3px] size-3 bg-[#757780]'
            : checked
              ? 'left-[22px] size-6 bg-white'
              : 'left-[6px] size-4 bg-[#757780]',
        )}
      />
    </button>
  )
}
