import * as RadixTooltip from '@radix-ui/react-tooltip'
import type { ReactNode } from 'react'

/**
 * Flutter Tooltip: dark grey, 12 px text, radius 4. It shows below the target and keeps
 * 10 px from the screen edges. Wrap the app in TooltipProvider once.
 */
export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          side="bottom"
          sideOffset={6}
          collisionPadding={10}
          className="z-[70] max-w-[calc(100vw-20px)] rounded bg-[#616161]/92 px-2 py-1 text-xs text-white"
        >
          {content}
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  )
}

export const TooltipProvider = ({ children }: { children: ReactNode }) => (
  <RadixTooltip.Provider delayDuration={500}>{children}</RadixTooltip.Provider>
)
