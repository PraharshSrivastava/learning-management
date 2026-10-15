import * as RadixDialog from '@radix-ui/react-dialog'
import clsx from 'clsx'
import type { ReactNode } from 'react'

interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  /** Footer buttons, right aligned like Flutter AlertDialog actions. */
  actions?: ReactNode
  children?: ReactNode
  /** Max width in px. Flutter AlertDialog is 280 to 560 wide. */
  width?: number
  /** Blocks Esc and outside clicks, for dialogs with a running request. */
  dismissible?: boolean
  className?: string
}

/** Material 3 AlertDialog: radius 28, padding 24, title 24/32. */
export function Dialog({
  open,
  onOpenChange,
  title,
  actions,
  children,
  width = 560,
  dismissible = true,
  className,
}: DialogProps) {
  const block = (event: Event) => {
    if (!dismissible) event.preventDefault()
  }
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/54" />
        <RadixDialog.Content
          onEscapeKeyDown={block}
          onPointerDownOutside={block}
          onInteractOutside={block}
          aria-describedby={undefined}
          style={{ maxWidth: width }}
          className={clsx(
            'fixed top-1/2 left-1/2 z-40 flex max-h-[calc(100%-48px)] w-[calc(100%-80px)] -translate-x-1/2 -translate-y-1/2 flex-col',
            'rounded-[28px] bg-[#f9f9ff] p-6 shadow-[0_8px_24px_rgb(0_0_0/0.2)] focus:outline-none',
            className,
          )}
        >
          <RadixDialog.Title className="font-dm text-2xl leading-8 text-[#191c20]">
            {title}
          </RadixDialog.Title>
          {children && (
            <div className="mt-4 min-h-0 overflow-auto text-sm text-[#44474e]">{children}</div>
          )}
          {actions && <div className="mt-6 flex justify-end gap-2">{actions}</div>}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}

export const DialogClose = RadixDialog.Close
