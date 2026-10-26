import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import clsx from 'clsx'
import type { Destination } from './search'

interface DestinationItem {
  icon: IconName
  label: string
}

export const DESTINATIONS: Record<Destination, DestinationItem> = {
  dashboard: { icon: 'dashboard_outlined', label: 'Dashboard' },
  courses: { icon: 'menu_book_outlined', label: 'My Courses' },
  journeys: { icon: 'track_changes', label: 'Learning Journeys' },
  notifications: { icon: 'notifications_outlined', label: 'Notifications' },
  performance: { icon: 'analytics_outlined', label: 'Performance' },
}

interface SidebarProps {
  expanded: boolean
  destinations: Destination[]
  selected: Destination
  onSelect: (destination: Destination) => void
  onToggle: () => void
  className?: string
}

/** Flutter `_LmsNavigation`: gradient rail, 262 px expanded and 76 px collapsed. */
export function Sidebar({
  expanded,
  destinations,
  selected,
  onSelect,
  onToggle,
  className,
}: SidebarProps) {
  return (
    <nav
      aria-label="Main navigation"
      className={clsx(
        'primary-gradient m-3 flex shrink-0 flex-col overflow-hidden rounded-[20px] shadow-[0_8px_18px_rgb(0_49_122/0.18)]',
        expanded ? 'w-[262px]' : 'w-[76px]',
        className,
      )}
    >
      <div
        className={clsx('flex items-center pt-[18px] pr-3 pb-[22px]', expanded ? 'pl-5' : 'pl-3')}
      >
        <div className={clsx('flex h-10 items-center', expanded ? 'w-[154px]' : 'w-10')}>
          <span className="font-inter text-[20px] leading-normal font-bold tracking-[-0.5px] whitespace-nowrap text-white">
            {expanded ? 'PhillipCapital' : 'PC'}
          </span>
        </div>
        {expanded && (
          <ToggleButton
            icon="keyboard_double_arrow_left"
            label="Collapse navigation"
            onClick={onToggle}
          />
        )}
      </div>
      {expanded ? (
        <p className="m-0 px-[22px] pb-5 text-[12px] font-semibold text-[#d0dbf4]">
          Learning Management System
        </p>
      ) : (
        <div className="flex justify-center">
          <ToggleButton
            icon="keyboard_double_arrow_right"
            label="Expand navigation"
            onClick={onToggle}
          />
        </div>
      )}
      <div className="h-px shrink-0 bg-white/30" />
      <div className="h-3.5 shrink-0" />
      <ul className="m-0 list-none p-0">
        {destinations.map((destination) => (
          <li key={destination}>
            <NavigationItem
              {...DESTINATIONS[destination]}
              expanded={expanded}
              selected={selected === destination}
              onClick={() => onSelect(destination)}
            />
          </li>
        ))}
      </ul>
      <div className="flex-1" />
      <div className="p-3.5">
        <div
          className={clsx(
            'flex items-center gap-2.5 rounded-[14px] border border-white/24 bg-white/10 p-3',
            !expanded && 'justify-center',
          )}
        >
          <Icon name="lock_outline" size={18} color="#d0dbf4" />
          {expanded && <span className="text-[12px] text-[#d0dbf4]">Employee learning</span>}
        </div>
      </div>
    </nav>
  )
}

function ToggleButton({
  icon,
  label,
  onClick,
}: {
  icon: IconName
  label: string
  onClick: () => void
}) {
  return (
    <Tooltip content={label}>
      <button
        type="button"
        aria-label={label}
        onClick={onClick}
        className="inline-flex size-10 shrink-0 items-center justify-center rounded-full text-white/70 hover:bg-white/8 focus-visible:outline-2 focus-visible:outline-white"
      >
        <Icon name={icon} size={24} />
      </button>
    </Tooltip>
  )
}

function NavigationItem({
  icon,
  label,
  expanded,
  selected,
  onClick,
}: DestinationItem & { expanded: boolean; selected: boolean; onClick: () => void }) {
  const item = (
    <button
      type="button"
      aria-label={expanded ? undefined : label}
      aria-current={selected ? 'page' : undefined}
      onClick={onClick}
      className={clsx(
        'flex h-12 w-full items-center rounded-full text-left transition-colors focus-visible:outline-2 focus-visible:outline-white',
        expanded ? 'pl-[18px]' : 'justify-center',
        selected ? 'bg-white text-primary-blue' : 'text-white hover:bg-white/8',
      )}
    >
      <Icon name={icon} size={21} color={selected ? undefined : '#d0dbf4'} />
      {expanded && <span className="ml-3.5 font-semibold">{label}</span>}
    </button>
  )
  return (
    <div className={clsx('py-[3px]', expanded ? 'px-3' : 'px-2.5')}>
      {expanded ? item : <Tooltip content={label}>{item}</Tooltip>}
    </div>
  )
}
