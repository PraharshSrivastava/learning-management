import { HubGate } from '@lms/shared/auth/HubGate'
import { SessionProvider, useSession } from '@lms/shared/auth/session'
import { TrainerLoginPage } from './auth/TrainerLoginPage'
import { parseTrainer, type Trainer } from './auth/trainer'
import { OverlayProvider } from './shell/overlay'
import { TrainerShell } from './shell/TrainerShell'

function TrainerAuthGate() {
  const { person } = useSession<Trainer>()
  return person ? <TrainerShell /> : <TrainerLoginPage />
}

export function App() {
  return (
    <HubGate title="Trainer access">
      {(session) => (
        <SessionProvider<Trainer>
          initialPerson={session.person ? parseTrainer(session.person) : null}
        >
          <OverlayProvider>
            <TrainerAuthGate />
          </OverlayProvider>
        </SessionProvider>
      )}
    </HubGate>
  )
}
