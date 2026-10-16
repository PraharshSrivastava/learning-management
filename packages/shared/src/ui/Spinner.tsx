interface SpinnerProps {
  size?: number
  strokeWidth?: number
  color?: string
  className?: string
  label?: string
}

/** Indeterminate circular progress, like Flutter's CircularProgressIndicator (36 px, stroke 4). */
export function Spinner({
  size = 36,
  strokeWidth = 4,
  color = 'var(--color-primary-blue)',
  className,
  label = 'Loading',
}: SpinnerProps) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  return (
    <svg
      role="progressbar"
      aria-label={label}
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      style={{ animation: 'lms-spin 1.4s linear infinite', flexShrink: 0 }}
    >
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={`${circumference * 0.3} ${circumference}`}
        style={{ animation: 'lms-dash 1.4s ease-in-out infinite' }}
      />
    </svg>
  )
}
