// Journey Observers: people who follow the whole journey, every course in it, for the employees
// or departments they watch. Saved separately from the journey, like course Observers.
import { errorMessage } from '@lms/shared/api/client'
import type { Employee } from '@lms/shared/models'
import { Spinner } from '@lms/shared/ui/Spinner'
import { useToast } from '@lms/shared/ui/Toast'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { trainerKeys } from '../../shell/queryKeys'
import { ActionButton, InputChip, Notice } from '../assignments/controls'
import {
  EmployeeMultiPickerDialog,
  EmployeePickerDialog,
  MultiSelectDialog,
} from '../assignments/pickers'
import {
  fetchJourneyObservers,
  fetchObserverDepartments,
  saveJourneyObservers,
  type JourneyObserver,
} from './api'

type Dialog =
  | { kind: 'observer' }
  | { kind: 'employees'; index: number }
  | { kind: 'departments'; index: number }
  | null

export function JourneyObservers({
  journeyId,
  employees,
}: {
  journeyId: string
  employees: Employee[]
}) {
  const key = [...trainerKeys.journeys, 'observers', journeyId]
  const saved = useQuery({ queryKey: key, queryFn: () => fetchJourneyObservers(journeyId) })
  if (saved.isPending) return <Spinner label="Loading observers" />
  if (saved.isError) return <Notice text={errorMessage(saved.error)} isError />
  return (
    <ObserverEditor
      key={JSON.stringify(saved.data)}
      journeyId={journeyId}
      saved={saved.data}
      employees={employees}
    />
  )
}

function ObserverEditor({
  journeyId,
  saved,
  employees,
}: {
  journeyId: string
  saved: JourneyObserver[]
  employees: Employee[]
}) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [draft, setDraft] = useState<JourneyObserver[]>(saved)
  const [dialog, setDialog] = useState<Dialog>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const departments = useQuery({
    queryKey: ['observer', 'departments'],
    queryFn: fetchObserverDepartments,
  })
  const departmentList = departments.data ?? []
  const nameOf = (id: string) => employees.find((e) => e.employeeId === id)?.name ?? id
  const departmentName = (id: string) => departmentList.find((d) => d.id === id)?.name ?? id
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved)
  const incomplete = draft.some((o) => o.employeeIds.length === 0 && o.departmentIds.length === 0)

  const setAt = (index: number, patch: Partial<JourneyObserver>) =>
    setDraft((current) => current.map((item, i) => (i === index ? { ...item, ...patch } : item)))

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      await saveJourneyObservers(journeyId, draft)
      // Observers are never enrolled, so the "who matches" count changes with them.
      void queryClient.invalidateQueries({
        queryKey: [...trainerKeys.journeys, 'preview', journeyId],
      })
      await queryClient.invalidateQueries({
        queryKey: [...trainerKeys.journeys, 'observers', journeyId],
      })
      toast('Journey observers saved.')
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  const current = dialog && dialog.kind !== 'observer' ? draft[dialog.index] : undefined
  return (
    <div className="flex flex-col gap-3" aria-busy={busy}>
      {error != null && <Notice text={error} isError onDismiss={() => setError(null)} />}
      {draft.length === 0 && <p className="text-sm text-[#5b6980]">No journey observers yet.</p>}
      {draft.map((observer, index) => (
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
              onClick={() => setDraft((list) => list.filter((_, i) => i !== index))}
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
      <div className="flex flex-wrap gap-2">
        <ActionButton icon="add" onClick={() => setDialog({ kind: 'observer' })}>
          Add observer
        </ActionButton>
        <ActionButton
          variant="filled"
          icon="save_outlined"
          disabled={!dirty || incomplete || busy}
          onClick={() => void save()}
        >
          {busy ? 'Saving…' : 'Save observers'}
        </ActionButton>
      </div>
      <EmployeePickerDialog
        open={dialog?.kind === 'observer'}
        onOpenChange={(open) => !open && setDialog(null)}
        title="Add journey observer"
        employees={employees.filter(
          (e) => !draft.some((o) => o.observerEmployeeId === e.employeeId),
        )}
        onPick={(employee) => {
          setDraft((list) => [
            ...list,
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
