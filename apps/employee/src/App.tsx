import { HubGate } from '@lms/shared/auth/HubGate'
import { SessionProvider, useSession } from '@lms/shared/auth/session'
import { ToastProvider } from '@lms/shared/ui/Toast'
import { TooltipProvider } from '@lms/shared/ui/Tooltip'
import { EmployeeLoginPage } from './auth/EmployeeLoginPage'
import { parseEmployee, type Employee } from './auth/employee'
import { EmployeeDashboard } from './dashboard/EmployeeDashboard'

function EmployeeAuthGate() {
  const { person } = useSession<Employee>()
  return person ? <EmployeeDashboard /> : <EmployeeLoginPage />
}

export function App() {
  return (
    <HubGate title="Employee learning access">
      {(session) => (
        <SessionProvider<Employee>
          initialPerson={session.person ? parseEmployee(session.person) : null}
        >
          <TooltipProvider>
            <ToastProvider>
              <EmployeeAuthGate />
            </ToastProvider>
          </TooltipProvider>
        </SessionProvider>
      )}
    </HubGate>
  )
}
