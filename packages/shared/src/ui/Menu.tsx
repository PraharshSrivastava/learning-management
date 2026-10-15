import * as RadixMenu from '@radix-ui/react-dropdown-menu'
import clsx from 'clsx'
import type { ReactNode } from 'react'
import { Icon, type IconName } from './icons/Icon'

export interface MenuItem {
  key: string
  label: ReactNode
  icon?: IconName
  danger?: boolean
  disabled?: boolean
  onSelect: () => void
}

interface MenuProps {
  /** The trigger element. It must accept a ref, for example a button. */
  trigger: ReactNode
  items: readonly MenuItem[]
  align?: 'start' | 'end'
}

/** Flutter PopupMenuButton: white surface, radius 4, 48 px rows. */
export function Menu({ trigger, items, align = 'end' }: MenuProps) {
  return (
    <RadixMenu.Root modal={false}>
      <RadixMenu.Trigger asChild>{trigger}</RadixMenu.Trigger>
      <RadixMenu.Portal>
        <RadixMenu.Content
          align={align}
          sideOffset={4}
          className="z-50 min-w-[112px] rounded bg-white py-2 shadow-[0_4px_16px_rgb(0_0_0/0.18)]"
        >
          {items.map((item) => (
            <RadixMenu.Item
              key={item.key}
              disabled={item.disabled}
              onSelect={item.onSelect}
              className={clsx(
                'flex h-12 cursor-pointer items-center gap-3 px-3 text-sm outline-none select-none',
                'data-[disabled]:cursor-default data-[disabled]:opacity-40 data-[highlighted]:bg-black/6',
                item.danger ? 'text-accent-red' : 'text-text-black',
              )}
            >
              {item.icon && <Icon name={item.icon} size={20} />}
              {item.label}
            </RadixMenu.Item>
          ))}
        </RadixMenu.Content>
      </RadixMenu.Portal>
    </RadixMenu.Root>
  )
}
