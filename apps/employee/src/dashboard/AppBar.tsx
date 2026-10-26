import { Icon } from '@lms/shared/ui/icons/Icon'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import clsx from 'clsx'
import type { Employee } from '../auth/employee'
import type { Destination } from './search'
import { DESTINATIONS } from './Sidebar'

interface AppBarProps {
  isCompact: boolean
  active: Destination
  unreadCount: number
  employee: Employee | null
  onMenu: () => void
  onNotifications: () => void
}

/** Flutter `_employeeInitials`: 'PC' when the name is empty. */
export function employeeInitials(name: string | undefined): string {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'PC'
  return parts
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
}

/** Flutter `_DashboardAppBar`. */
export function AppBar({
  isCompact,
  active,
  unreadCount,
  employee,
  onMenu,
  onNotifications,
}: AppBarProps) {
  const profile = [employee?.name || 'Employee', employee?.department, employee?.jobTitle]
    .filter(Boolean)
    .join(' - ')
  const notificationsLabel =
    unreadCount === 0 ? 'Notifications' : `${unreadCount} unread notifications`
  return (
    <header
      className={clsx(
        'flex shrink-0 items-center border-b border-light-gray bg-white/94 px-5',
        isCompact ? 'h-20' : 'h-[72px]',
      )}
    >
      {isCompact && (
        <Tooltip content="Open navigation">
          <button
            type="button"
            aria-label="Open navigation"
            onClick={onMenu}
            className="mr-2 inline-flex size-10 items-center justify-center rounded-full text-primary-blue hover:bg-primary-blue/8"
          >
            <Icon name="menu" />
          </button>
        </Tooltip>
      )}
      <div className="min-w-0 flex-1">
        <p className="m-0 text-[18px] font-bold">Learning Management System</p>
        <p className="m-0 mt-0.5 text-[13px] text-[#667085]">{DESTINATIONS[active].label}</p>
      </div>
      <Tooltip content={notificationsLabel}>
        <button
          type="button"
          aria-label={notificationsLabel}
          onClick={onNotifications}
          className={clsx(
            'relative inline-flex size-10 items-center justify-center rounded-full hover:bg-primary-blue/8',
            unreadCount > 0 ? 'text-primary-blue' : 'text-[#344054]',
          )}
        >
          <Icon name={unreadCount > 0 ? 'notifications' : 'notifications_none'} />
          {unreadCount > 0 && (
            <span className="absolute -top-[5px] -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent-red px-1 text-[11px] leading-none font-medium tracking-normal text-white">
              {unreadCount > 999 ? '999+' : unreadCount}
            </span>
          )}
        </button>
      </Tooltip>
      <Tooltip content={profile}>
        <span
          aria-label={profile}
          role="img"
          className="ml-2 flex size-9 shrink-0 items-center justify-center rounded-full bg-[#e7efff] text-[16px] font-bold text-primary-blue"
        >
          {employeeInitials(employee?.name)}
        </span>
      </Tooltip>
    </header>
  )
}
