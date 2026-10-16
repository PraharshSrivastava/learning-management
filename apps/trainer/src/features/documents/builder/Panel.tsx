import clsx from 'clsx'
import type { ReactNode } from 'react'
import { StatusPill } from '../controls'

/** Builder panel card. `label` names the region for screen readers. */
export function Panel({
  label,
  className,
  children,
}: {
  label: string
  className?: string
  children: ReactNode
}) {
  return (
    <section
      aria-label={label}
      className={clsx('card flex min-h-0 flex-col overflow-hidden', className)}
    >
      {children}
    </section>
  )
}

/** Panel header: Inter 17 bold title and a status pill, 14 px padding, bottom border. */
export function PanelHeader({
  title,
  status,
  active = false,
  error = false,
}: {
  title: string
  status: string
  active?: boolean
  error?: boolean
}) {
  return (
    <div className="flex shrink-0 items-start border-b border-light-gray p-3.5">
      <h3 className="m-0 min-w-0 flex-1 font-inter text-[17px] leading-[25.5px] font-bold tracking-[0.25px] text-text-black">
        {title}
      </h3>
      <StatusPill text={status} active={!error && active} error={error} />
    </div>
  )
}
