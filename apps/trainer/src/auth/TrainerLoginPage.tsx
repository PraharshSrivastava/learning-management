import { apiRequest, errorMessage } from '@lms/shared/api/client'
import { useSession } from '@lms/shared/auth/session'
import { Spinner } from '@lms/shared/ui/Spinner'
import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { parseTrainer, type Trainer } from './trainer'

async function fetchTrainers(): Promise<Trainer[]> {
  const data = await apiRequest('/api/auth/local/trainers')
  return Array.isArray(data) ? data.map(parseTrainer) : []
}

/** Local dev login: pick a synced trainer. Shown when the Hub session has no trainer record. */
export function TrainerLoginPage() {
  const { signIn } = useSession<Trainer>()
  const trainers = useQuery({ queryKey: ['local-trainers'], queryFn: fetchTrainers, staleTime: 0 })
  const login = useMutation({
    mutationFn: async (trainer: Trainer) => {
      const data = (await apiRequest('/api/auth/local/trainer-login', {
        json: { trainer_id: trainer.trainerId },
      })) as { token?: unknown; trainer?: unknown } | null
      if (!data?.trainer) throw new Error('Could not log in trainer.')
      return {
        trainer: parseTrainer(data.trainer),
        token: data.token != null ? String(data.token) : null,
      }
    },
    onSuccess: ({ trainer, token }) => signIn(trainer, token),
  })
  const error = login.error ?? trainers.error

  return (
    <main className="page-gradient flex min-h-full items-center justify-center">
      <div className="w-full max-w-[760px] p-6">
        <header className="flex items-center gap-4">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-primary-blue font-extrabold text-white">
            PC
          </div>
          <div>
            <h1 className="font-inter text-[26px] leading-tight font-extrabold text-text-black">
              Trainer access
            </h1>
            <p className="mt-1 text-[#667085]">
              Select a synced employee to test trainer access locally.
            </p>
          </div>
        </header>
        <div className="mt-6">
          {trainers.isPending ? (
            <Spinner className="mx-auto block" />
          ) : (
            <ul className="flex flex-wrap gap-3" aria-label="Trainers">
              {trainers.data?.map((trainer) => {
                const busy = login.isPending && login.variables?.trainerId === trainer.trainerId
                return (
                  <li key={trainer.trainerId} className="w-[235px] p-1">
                    <button
                      type="button"
                      disabled={login.isPending}
                      aria-busy={busy || undefined}
                      onClick={() => login.mutate(trainer)}
                      className={clsx(
                        'relative w-full rounded-[10px] border border-[#e6e9ef] bg-[#f4f3fa] p-4 text-left transition-colors',
                        'hover:bg-[#ebeaf3] focus-visible:outline-2 focus-visible:outline-brand-blue-light',
                        'disabled:cursor-wait',
                      )}
                    >
                      <span className="block font-barlow text-[17px] leading-snug font-extrabold text-primary-blue">
                        {trainer.name}
                      </span>
                      <span className="mt-1.5 block text-[#667085]">{trainer.status}</span>
                      <span className="mt-1 block truncate text-xs text-[#98a2b3]">
                        {trainer.trainerId}
                      </span>
                      {busy && (
                        <Spinner size={18} strokeWidth={2} className="absolute top-4 right-4" />
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
          {trainers.data?.length === 0 && (
            <p className="text-[#667085]">No synced trainers are available.</p>
          )}
          {error && (
            <p className="mt-4 text-accent-red" role="alert">
              {errorMessage(error)}
            </p>
          )}
        </div>
      </div>
    </main>
  )
}
