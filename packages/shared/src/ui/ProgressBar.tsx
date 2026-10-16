import clsx from 'clsx'

interface ProgressBarProps {
  /** 0 to 1. Omit for an indeterminate bar. */
  value?: number | null
  color?: string
  trackColor?: string
  height?: number
  radius?: number
  className?: string
  label?: string
}

/** Flutter LinearProgressIndicator (primary-blue on light-gray). */
export function ProgressBar({
  value,
  color = 'var(--color-primary-blue)',
  trackColor = 'var(--color-light-gray)',
  height = 4,
  radius = 0,
  className,
  label,
}: ProgressBarProps) {
  const determinate = value != null
  const percent = determinate ? Math.min(1, Math.max(0, value)) * 100 : 0
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={determinate ? 0 : undefined}
      aria-valuemax={determinate ? 100 : undefined}
      aria-valuenow={determinate ? Math.round(percent) : undefined}
      className={clsx('relative w-full overflow-hidden', className)}
      style={{ height, borderRadius: radius, backgroundColor: trackColor }}
    >
      <div
        className={clsx(
          'absolute inset-y-0 left-0',
          !determinate && 'w-2/5 animate-[lms-indeterminate_1.6s_ease-in-out_infinite]',
        )}
        style={{
          width: determinate ? `${percent}%` : undefined,
          backgroundColor: color,
          borderRadius: radius,
        }}
      />
    </div>
  )
}
