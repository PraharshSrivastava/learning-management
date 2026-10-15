import { apiRequest, errorMessage } from '@lms/shared/api/client'
import { useSession } from '@lms/shared/auth/session'
import { Button, IconButton } from '@lms/shared/ui/Button'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import { Spinner } from '@lms/shared/ui/Spinner'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useDeferredValue, useMemo, useState } from 'react'
import { initials, parseEmployee, type Employee } from './employee'

async function fetchEmployees(): Promise<Employee[]> {
  const data = await apiRequest('/api/employees')
  return Array.isArray(data) ? data.map(parseEmployee) : []
}

/** Local dev login: pick a synced employee. Shown when the Hub session has no employee record. */
export function EmployeeLoginPage() {
  const { signIn } = useSession<Employee>()
  const [query, setQuery] = useState('')
  const [department, setDepartment] = useState('All')
  const deferredQuery = useDeferredValue(query)
  const employees = useQuery({
    queryKey: ['local-employees'],
    queryFn: fetchEmployees,
    staleTime: 0,
  })
  const login = useMutation({
    mutationFn: async (employee: Employee) => {
      const data = (await apiRequest('/api/auth/local/employee-login', {
        json: { employee_id: employee.employeeId },
      })) as { token?: unknown; employee?: unknown } | null
      if (!data?.employee) throw new Error('Login failed')
      return {
        employee: parseEmployee(data.employee),
        token: data.token != null ? String(data.token) : null,
      }
    },
    onSuccess: ({ employee, token }) => signIn(employee, token),
  })

  const all = useMemo(() => employees.data ?? [], [employees.data])
  const departments = useMemo(
    () => ['All', ...new Set(all.map((employee) => employee.department))],
    [all],
  )
  const visible = useMemo(() => {
    const needle = deferredQuery.toLowerCase()
    return all.filter((employee) => {
      const haystack =
        `${employee.name} ${employee.employeeId} ${employee.department} ${employee.jobTitle}`.toLowerCase()
      return (
        (!needle || haystack.includes(needle)) &&
        (department === 'All' || employee.department === department)
      )
    })
  }, [all, deferredQuery, department])
  const error = login.error ?? employees.error

  return (
    <main className="page-gradient h-full overflow-auto">
      <div className="mx-auto flex min-h-full max-w-[1180px] flex-col p-6">
        <header className="flex items-center gap-3.5">
          <div className="primary-gradient flex size-11 shrink-0 items-center justify-center rounded-[14px] font-extrabold text-white">
            PC
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl leading-tight font-extrabold text-[#101828]">
              Employee learning access
            </h1>
            <p className="mt-[3px] text-[#667085]">Select a synced employee for local testing.</p>
          </div>
          <IconButton
            icon="refresh"
            label="Refresh employees"
            className="text-[#44474e]"
            disabled={employees.isFetching}
            onClick={() => void employees.refetch()}
          />
        </header>

        <div className="card mt-6 flex items-center gap-3 p-4">
          <label className="relative flex-1">
            <span className="sr-only">Search employees</span>
            <Icon
              name="search"
              size={20}
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-[#44474e]"
            />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by name, employee ID, department, or job title"
              className="h-10 w-full rounded-lg border border-input-border bg-white pr-3 pl-11 text-[15px] placeholder:text-gray focus:border-brand-blue-light focus:outline-none focus:ring-[0.4px] focus:ring-brand-blue-light"
            />
          </label>
          <label className="relative w-[220px]">
            <span className="absolute -top-2 left-3 bg-white px-1 text-xs text-text-secondary">
              Department
            </span>
            <select
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
              className="h-10 w-full appearance-none rounded-lg border border-input-border bg-white pr-9 pl-4 text-base text-text-black focus:border-brand-blue-light focus:outline-none"
            >
              {departments.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <span className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2 border-x-[5px] border-t-[5px] border-x-transparent border-t-[#44474e]" />
          </label>
        </div>

        {error && (
          <div
            className="mt-3.5 rounded-lg border border-[#f3d19c] bg-[#fff7e8] p-3 text-[#704a00]"
            role="alert"
          >
            {errorMessage(error)}
          </div>
        )}

        <div className="mt-[18px] flex flex-1 flex-col">
          {employees.isPending ? (
            <Spinner className="m-auto" />
          ) : visible.length === 0 ? (
            <p className="m-auto text-[#667085]">No employees match the current filters.</p>
          ) : (
            <ul className="grid grid-cols-1 gap-3.5 min-[728px]:grid-cols-2 min-[1088px]:grid-cols-3">
              {visible.map((employee) => (
                <EmployeeCard
                  key={employee.employeeId}
                  employee={employee}
                  busy={login.isPending}
                  opening={login.isPending && login.variables?.employeeId === employee.employeeId}
                  onSelect={() => login.mutate(employee)}
                />
              ))}
            </ul>
          )}
        </div>
      </div>
    </main>
  )
}

function EmployeeCard({
  employee,
  busy,
  opening,
  onSelect,
}: {
  employee: Employee
  busy: boolean
  opening: boolean
  onSelect: () => void
}) {
  return (
    <li className="flex h-[210px] flex-col rounded-2xl border border-light-gray bg-white p-4">
      <div className="flex items-center gap-3">
        <span
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-brand-blue-100 text-base font-extrabold text-primary-blue"
          aria-hidden
        >
          {initials(employee.name)}
        </span>
        <div className="min-w-0">
          <p className="truncate text-base font-extrabold">{employee.name}</p>
          <p className="mt-0.5 text-xs text-[#667085]">{employee.employeeId}</p>
        </div>
      </div>
      <div className="mt-3.5 flex flex-col gap-[7px]">
        <MetaLine icon="apartment_outlined" text={employee.department} />
        <MetaLine icon="badge_outlined" text={employee.jobTitle} />
        <MetaLine icon="calendar_today_outlined" text={`Joined ${employee.joinDate}`} />
      </div>
      <Button
        className="mt-auto self-end"
        icon="login"
        loading={opening}
        disabled={busy}
        onClick={onSelect}
        aria-label={`Open session for ${employee.name}`}
      >
        Open session
      </Button>
    </li>
  )
}

function MetaLine({ icon, text }: { icon: IconName; text: string }) {
  return (
    <div className="flex items-center gap-2 text-[13px] text-[#344054]">
      <Icon name={icon} size={16} color="#667085" />
      <span className="truncate">{text}</span>
    </div>
  )
}
