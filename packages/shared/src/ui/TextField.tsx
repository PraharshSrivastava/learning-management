import clsx from 'clsx'
import { useId, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from 'react'
import { Icon, type IconName } from './icons/Icon'

const fieldBase =
  'w-full rounded-lg border border-input-border bg-white px-3 text-text-black placeholder:text-gray ' +
  'focus:border-brand-blue-light focus:outline-none focus:ring-[0.4px] focus:ring-brand-blue-light ' +
  'disabled:bg-surface-secondary disabled:text-gray aria-invalid:border-accent-red'

interface FieldShellProps {
  id: string
  label?: ReactNode
  helper?: ReactNode
  error?: ReactNode
  className?: string
  children: ReactNode
}

/** Flutter InputDecoration with a floating label on the outline (AppTheme input theme). */
function FieldShell({ id, label, helper, error, className, children }: FieldShellProps) {
  return (
    <div className={clsx('relative', className)}>
      {children}
      {label && (
        <label
          htmlFor={id}
          className="pointer-events-none absolute -top-2 left-2 bg-white px-1 text-xs leading-4 text-text-secondary"
        >
          {label}
        </label>
      )}
      {(error || helper) && (
        <p
          id={`${id}-help`}
          className={clsx('mt-1 px-3 text-xs', error ? 'text-accent-red' : 'text-text-secondary')}
        >
          {error ?? helper}
        </p>
      )}
    </div>
  )
}

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: ReactNode
  helper?: ReactNode
  error?: ReactNode
  icon?: IconName
  /** `dense` matches Flutter `isDense: true` (40 px). Default is 48 px. */
  dense?: boolean
  fieldClassName?: string
}

export function TextField({
  label,
  helper,
  error,
  icon,
  dense,
  className,
  fieldClassName,
  id,
  ...rest
}: TextFieldProps) {
  const autoId = useId()
  const fieldId = id ?? autoId
  return (
    <FieldShell id={fieldId} label={label} helper={helper} error={error} className={fieldClassName}>
      {icon && (
        <Icon
          name={icon}
          size={20}
          className="pointer-events-none absolute top-[calc(50%)] left-3 -translate-y-1/2 text-[#44474e]"
          style={error || helper ? { top: dense ? 20 : 24 } : undefined}
        />
      )}
      <input
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || helper ? `${fieldId}-help` : undefined}
        className={clsx(fieldBase, dense ? 'h-10' : 'h-12', icon && 'pl-11', className)}
        {...rest}
      />
    </FieldShell>
  )
}

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: ReactNode
  helper?: ReactNode
  error?: ReactNode
  fieldClassName?: string
}

export function TextArea({
  label,
  helper,
  error,
  className,
  fieldClassName,
  id,
  ...rest
}: TextAreaProps) {
  const autoId = useId()
  const fieldId = id ?? autoId
  return (
    <FieldShell id={fieldId} label={label} helper={helper} error={error} className={fieldClassName}>
      <textarea
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || helper ? `${fieldId}-help` : undefined}
        className={clsx(fieldBase, 'py-3', className)}
        {...rest}
      />
    </FieldShell>
  )
}

interface SelectProps<T extends string> {
  label?: ReactNode
  value: T
  options: readonly { value: T; label: string }[] | readonly T[]
  onChange: (value: T) => void
  dense?: boolean
  disabled?: boolean
  className?: string
  id?: string
  'aria-label'?: string
}

/** Flutter DropdownButtonFormField with an outlined border. Uses a native select for keyboard and a11y. */
export function Select<T extends string>({
  label,
  value,
  options,
  onChange,
  dense,
  disabled,
  className,
  id,
  ...aria
}: SelectProps<T>) {
  const autoId = useId()
  const fieldId = id ?? autoId
  const items = options.map((option) =>
    typeof option === 'string' ? { value: option as T, label: option } : option,
  )
  return (
    <FieldShell id={fieldId} label={label} className={className}>
      <select
        id={fieldId}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value as T)}
        className={clsx(fieldBase, 'appearance-none pr-9 pl-4', dense ? 'h-10' : 'h-12')}
        {...aria}
      >
        {items.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
      <span
        aria-hidden
        className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2 border-x-[5px] border-t-[5px] border-x-transparent border-t-[#44474e]"
      />
    </FieldShell>
  )
}
