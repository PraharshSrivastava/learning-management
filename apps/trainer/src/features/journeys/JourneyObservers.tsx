// Journey Observers: people who follow the whole journey, every course in it, for the employees
// or departments they watch. Edited with the rest of the journey and saved by the same button.
import type { Employee } from '@lms/shared/models'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { ActionButton, InputChip } from '../assignments/controls'
import {
  EmployeeMultiPickerDialog,
  EmployeePickerDialog,
  MultiSelectDialog,
} from '../assignments/pickers'
import { fetchObserverDepartments, type JourneyObserver } from './api'

type Dialog =
  | { kind: 'observer' }
  | { kind: 'employees'; index: number }
  | { kind: 'departments'; index: number }
  | null

/** An observer who watches no one cannot be saved. */
export const observersIncomplete = (observers: JourneyObserver[]) =>
  observers.some((o) => o.employeeIds.length === 0 && o.departmentIds.length === 0)

export function JourneyObservers({
  value,
  onChange,
  employees,
}: {
  value: JourneyObserver[]
  onChange: (observers: JourneyObserver[]) => void
  employees: Employee[]
}) {
  const [dialog, setDialog] = useState<Dialog>(null)
  const departments = useQuery({
    queryKey: ['observer', 'departments'],
    queryFn: fetchObserverDepartments,
  })
  const departmentList = departments.data ?? []
  const nameOf = (id: string) => employees.find((e) => e.employeeId === id)?.name ?? id
  const departmentName = (id: string) => departmentList.find((d) => d.id === id)?.name ?? id

  const setAt = (index: number, patch: Partial<JourneyObserver>) =>
    onChange(value.map((item, i) => (i === index ? { ...item, ...patch } : item)))

  const current = dialog && dialog.kind !== 'observer' ? value[dialog.index] : undefined
  return (
    <div className="flex flex-col gap-3">
      {value.length === 0 && <p className="text-sm text-[#5b6980]">No journey observers yet.</p>}
      {value.map((observer, index) => (
        <section
          key={observer.observerEmployeeId}
          aria-label={`Observer ${nameOf(observer.observerEmployeeId)}`}
          className="rounded-lg border border-[#e6e9ef] p-3"
        >
          <div className="flex items-center gap-2">
            <b className="min-w-0 flex-1 truncate text-sm text-[#19273e]">
              {nameOf(observer.observerEmployeeId)}
            </b>
            <ActionButton
              variant="text"
              icon="close"
              aria-label={`Remove observer ${nameOf(observer.observerEmployeeId)}`}
              onClick={() => onChange(value.filter((_, i) => i !== index))}
            />
          </div>
          <p className="mt-1 text-xs text-[#5b6980]">Watches</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {observer.employeeIds.map((id) => (
              <InputChip
                key={id}
                label={nameOf(id)}
                onRemove={() =>
                  setAt(index, { employeeIds: observer.employeeIds.filter((x) => x !== id) })
                }
              />
            ))}
            {observer.departmentIds.map((id) => (
              <InputChip
                key={id}
                label={departmentName(id)}
                onRemove={() =>
                  setAt(index, { departmentIds: observer.departmentIds.filter((x) => x !== id) })
                }
              />
            ))}
            {observer.employeeIds.length === 0 && observer.departmentIds.length === 0 && (
              <span className="text-xs text-accent-red">
                Choose employees or departments to watch.
              </span>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <ActionButton
              variant="text"
              icon="person_add_alt_1"
              onClick={() => setDialog({ kind: 'employees', index })}
            >
              Add employees
            </ActionButton>
            <ActionButton
              variant="text"
              icon="apartment_outlined"
              onClick={() => setDialog({ kind: 'departments', index })}
            >
              Departments
            </ActionButton>
          </div>
        </section>
      ))}
      <div>
        <ActionButton icon="add" onClick={() => setDialog({ kind: 'observer' })}>
          Add observer
        </ActionButton>
      </div>
      <EmployeePickerDialog
        open={dialog?.kind === 'observer'}
        onOpenChange={(open) => !open && setDialog(null)}
        title="Add journey observer"
        employees={employees.filter(
          (e) => !value.some((o) => o.observerEmployeeId === e.employeeId),
        )}
        onPick={(employee) => {
          onChange([
            ...value,
            { observerEmployeeId: employee.employeeId, employeeIds: [], departmentIds: [] },
          ])
          setDialog(null)
        }}
      />
      <EmployeeMultiPickerDialog
        open={dialog?.kind === 'employees'}
        onOpenChange={(open) => !open && setDialog(null)}
        title="Employees this observer watches"
        actionLabel={(n) => (n ? `Watch ${n} employee${n === 1 ? '' : 's'}` : 'Add employees')}
        employees={employees.filter(
          (e) => current != null && !current.employeeIds.includes(e.employeeId),
        )}
        onPick={(picked) => {
          if (dialog?.kind !== 'employees' || !current) return
          setAt(dialog.index, {
            employeeIds: [...current.employeeIds, ...picked.map((e) => e.employeeId)],
          })
        }}
      />
      <MultiSelectDialog
        open={dialog?.kind === 'departments'}
        onOpenChange={(open) => !open && setDialog(null)}
        title="Departments"
        values={departmentList.map((d) => d.name)}
        selected={(current?.departmentIds ?? []).map(departmentName)}
        onApply={(names) => {
          if (dialog?.kind !== 'departments') return
          setAt(dialog.index, {
            departmentIds: departmentList.filter((d) => names.includes(d.name)).map((d) => d.id),
          })
        }}
      />
    </div>
  )
}
