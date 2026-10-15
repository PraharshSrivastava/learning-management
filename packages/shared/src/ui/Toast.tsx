import clsx from 'clsx'
import { createContext, use, useCallback, useRef, useState, type ReactNode } from 'react'
import { Icon, type IconName } from './icons/Icon'

// 'learning' is the white employee success snack bar (_showLearningSuccessSnackBar).
export type ToastTone = 'neutral' | 'success' | 'error' | 'learning'

export interface ToastOptions {
  tone?: ToastTone
  /** Leading icon, used by the learner success toast. */
  icon?: IconName
  /** Milliseconds. Flutter SnackBar default is 4000. */
  duration?: number
}

interface ToastItem extends Required<Omit<ToastOptions, 'icon'>> {
  id: number
  message: string
  icon: IconName | undefined
}

type ShowToast = (message: string, options?: ToastOptions) => void

const ToastContext = createContext<ShowToast | null>(null)

const tones: Record<ToastTone, string> = {
  neutral: 'bg-[#2e3036] text-[#f0f0f7]',
  success: 'bg-accent-green text-white',
  error: 'bg-accent-red text-white',
  learning: 'border border-[#d6e8e2] bg-white font-semibold text-[#101828]',
}

/**
 * Flutter SnackBar replacement. A new toast replaces the current one, as
 * ScaffoldMessenger does when callers hide the current snack bar first.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastItem | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const nextId = useRef(0)
  const show = useCallback<ShowToast>((message, options = {}) => {
    clearTimeout(timer.current)
    const item: ToastItem = {
      id: ++nextId.current,
      message,
      tone: options.tone ?? 'neutral',
      icon: options.icon,
      duration: options.duration ?? 4000,
    }
    setToast(item)
    timer.current = setTimeout(
      () => setToast((current) => (current?.id === item.id ? null : current)),
      item.duration,
    )
  }, [])
  return (
    <ToastContext value={show}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex justify-center p-6"
        role="status"
        aria-live="polite"
      >
        {toast && (
          <div
            key={toast.id}
            className={clsx(
              'pointer-events-auto flex min-h-12 w-full items-center gap-3 px-4 py-3.5 text-sm',
              toast.tone === 'learning'
                ? 'rounded-lg shadow-[0_5px_10px_rgb(0_0_0/0.2)]'
                : 'max-w-[640px] rounded shadow-[0_4px_12px_rgb(0_0_0/0.25)]',
              tones[toast.tone],
            )}
          >
            {toast.icon &&
              (toast.tone === 'learning' ? (
                <span className="flex size-[34px] shrink-0 items-center justify-center rounded-full bg-[#e7f7f0] text-[#087e5b]">
                  <Icon name={toast.icon} size={20} />
                </span>
              ) : (
                <Icon name={toast.icon} size={20} />
              ))}
            <span className="flex-1 whitespace-pre-line">{toast.message}</span>
            {toast.tone !== 'learning' && (
              <button
                type="button"
                aria-label="Dismiss"
                className="-my-2 -mr-2 rounded-full p-2 opacity-80 hover:opacity-100"
                onClick={() => setToast(null)}
              >
                <Icon name="close" size={18} />
              </button>
            )}
          </div>
        )}
      </div>
    </ToastContext>
  )
}

export function useToast(): ShowToast {
  const show = use(ToastContext)
  if (!show) throw new Error('useToast must be used inside ToastProvider')
  return show
}
