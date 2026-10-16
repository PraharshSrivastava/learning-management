// Performance Observers section body (Flutter ObserverIncludePanel).
import type { Course, Employee } from '@lms/shared/models'
import { Dialog } from '@lms/shared/ui/Dialog'
import { IconButton } from '@lms/shared/ui/Button'
import { ProgressBar } from '@lms/shared/ui/ProgressBar'
import { useEffect, useState, useSyncExternalStore } from 'react'
import type { ObserverAccess, ObserverDepartment, ObserverSelection, Requester } from './api'
import { ActionButton, CheckboxRow, ObserverNotice } from './controls'
import { ObserverStore } from './observerStore'
import { SearchablePicker } from './SearchablePicker'

interface ObserverPanelProps {
  course: Course
  employees: Employee[]
  refreshGeneration: number
  isAssignmentActive: boolean
  request: Requester
  onDraftObservers: (ids: string[]) => void
}

/** Active employees in scope of one pending selection. */
export function previewCount(
  selection: ObserverSelection,
  departments: ObserverDepartment[],
  employees: Employee[],
): number {
  const names = new Set(
    departments.filter((d) => selection.departmentIds.includes(d.id)).map((d) => d.name),
  )
  return new Set(
    employees
      .filter(
        (e) =>
          e.status === 'active' &&
          (selection.employeeIds.includes(e.employeeId) || names.has(e.department)),
      )
      .map((e) => e.employeeId),
  ).size
}

export function ObserverPanel({
  course,
  employees,
  refreshGeneration,
  isAssignmentActive,
  request,
  onDraftObservers,
}: ObserverPanelProps) {
  // The parent keys this panel by course, trainer and permissions, so one store per mount.
  const [store] = useState(() => new ObserverStore(course.courseId, request, onDraftObservers))
  const state = useSyncExternalStore(store.subscribe, store.getState)
  useEffect(() => store.attach(), [store])
  useEffect(() => store.syncGeneration(refreshGeneration), [store, refreshGeneration])
  const [choosing, setChoosing] = useState<Choosing | null>(null)
  const [confirmReload, setConfirmReload] = useState(false)

  const candidates = employees.filter((e) => e.status === 'active')
  const notPublished = course.status !== 'published' || !isAssignmentActive
  const { busy, dirty, message, selections } = state

  return (
    <div className="pt-2">
      <ObserverNotice
        text="Observers can view performance only. They are not enrolled as learners."
        warning={false}
      />
      {dirty && (
        <ObserverNotice text="Save your changes before applying Observer access." warning />
      )}
      {notPublished && (
        <ObserverNotice text="Publish and assign the course before applying observers." warning />
      )}
      {busy && <ProgressBar label="Loading observers" />}
      {message && <ObserverNotice text={message.text} warning={message.warning} />}
      {dirty && message?.text.includes('changed') && (
        <ActionButton variant="text" disabled={busy} onClick={() => setConfirmReload(true)}>
          Reload saved Observer selections
        </ActionButton>
      )}
      {selections.map((selection, index) => (
        <div key={index} className="flex flex-wrap items-center gap-x-3 gap-y-2 py-2">
          <SearchablePicker
            label="Observer"
            value={selection.observerEmployeeId}
            items={candidates.map((e) => [e.employeeId, e.name] as const)}
            disabled={busy}
            onChange={(id) => store.update(index, { observerEmployeeId: id })}
          />
          <ActionButton
            disabled={busy}
            onClick={() =>
              setChoosing({
                index,
                field: 'departments',
                picked: [...new Set(selection.departmentIds)],
              })
            }
          >
            Departments ({selection.departmentIds.length})
          </ActionButton>
          <ActionButton
            disabled={busy}
            onClick={() =>
              setChoosing({
                index,
                field: 'employees',
                picked: [...new Set(selection.employeeIds)],
              })
            }
          >
            Employees ({selection.employeeIds.length})
          </ActionButton>
          <AccessBadge
            access={
              selection.observerEmployeeId == null
                ? undefined
                : state.effective[selection.observerEmployeeId]
            }
          />
          <span>
            Pending selection: {previewCount(selection, state.departments, employees)} active
            directory employees; reports include only assigned learners on this course.
          </span>
          <IconButton
            icon="close"
            label="Remove observer"
            className="text-[#44474e]"
            disabled={busy}
            onClick={() => store.remove(index)}
          />
        </div>
      ))}
      <div className="flex flex-wrap items-center gap-3">
        <ActionButton
          variant="text"
          icon="add"
          disabled={busy || candidates.length === 0}
          onClick={() => {
            const first = candidates[0]
            if (first) store.add(first.employeeId)
          }}
        >
          Add observer
        </ActionButton>
        <ActionButton disabled={busy} onClick={() => void store.save()}>
          Save Observers
        </ActionButton>
        <ActionButton
          variant="filled"
          disabled={busy || dirty || notPublished}
          onClick={() => void store.save(true)}
        >
          Apply Observers
        </ActionButton>
        <IconButton
          icon="refresh"
          label="Refresh observer configuration"
          className="text-[#44474e]"
          disabled={busy}
          onClick={() => void store.load(true)}
        />
      </div>
      <ScopeDialog
        choosing={choosing}
        employees={candidates}
        departments={state.departments}
        onPick={(picked) => setChoosing((c) => (c ? { ...c, picked } : c))}
        onClose={() => {
          if (choosing) {
            store.update(
              choosing.index,
              choosing.field === 'employees'
                ? { employeeIds: choosing.picked }
                : { departmentIds: choosing.picked },
            )
          }
          setChoosing(null)
        }}
      />
      <Dialog
        open={confirmReload}
        onOpenChange={setConfirmReload}
        title="Reload saved Observer selections?"
        actions={
          <>
            <ActionButton variant="text" onClick={() => setConfirmReload(false)}>
              Keep editing
            </ActionButton>
            <ActionButton
              variant="filled"
              onClick={() => {
                setConfirmReload(false)
                void store.load()
              }}
            >
              Reload saved selections
            </ActionButton>
          </>
        }
      >
        Your unsaved Observer edits will be discarded.
      </Dialog>
    </div>
  )
}

type Field = 'employees' | 'departments'
interface Choosing {
  index: number
  field: Field
  picked: string[]
}

/** Employees or departments to observe. Any close keeps the picks, as in Flutter. */
function ScopeDialog({
  choosing,
  employees,
  departments,
  onPick,
  onClose,
}: {
  choosing: Choosing | null
  employees: Employee[]
  departments: ObserverDepartment[]
  onPick: (picked: string[]) => void
  onClose: () => void
}) {
  const field = choosing?.field
  const picked = choosing?.picked ?? []
  const options =
    field === 'employees'
      ? employees.map((e) => ({ id: e.employeeId, label: `${e.name} (${e.department})` }))
      : departments.map((d) => ({ id: d.id, label: d.name }))
  const allPicked = options.every((o) => picked.includes(o.id))
  return (
    <Dialog
      open={choosing != null}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
      title={field === 'employees' ? 'Employees to observe' : 'Departments to observe'}
      width={568}
      actions={
        <ActionButton variant="text" onClick={onClose}>
          Done
        </ActionButton>
      }
    >
      <div className="flex h-[380px] flex-col">
        {field === 'employees' && (
          // Flutter Wrap in a centered Column: the row is centered and its items align to the top.
          <div className="flex flex-wrap items-start justify-center gap-2">
            <ActionButton
              variant="text"
              icon="done_all"
              disabled={options.length === 0 || allPicked}
              onClick={() => onPick([...new Set([...picked, ...options.map((o) => o.id)])])}
            >
              Select all
            </ActionButton>
            <ActionButton variant="text" disabled={picked.length === 0} onClick={() => onPick([])}>
              Clear all
            </ActionButton>
            <span>{picked.length} selected</span>
          </div>
        )}
        <div className="min-h-0 flex-1 overflow-auto [scrollbar-width:none]">
          {options.map((option) => (
            <CheckboxRow
              key={option.id}
              checked={picked.includes(option.id)}
              onChange={(checked) =>
                onPick(checked ? [...picked, option.id] : picked.filter((id) => id !== option.id))
              }
            >
              {option.label}
            </CheckboxRow>
          ))}
        </div>
      </div>
    </Dialog>
  )
}

function AccessBadge({ access }: { access: ObserverAccess | undefined }) {
  const active = access?.isActive === true
  return (
    <span
      className={
        active
          ? 'rounded-2xl bg-[#eaf5ee] px-2.5 py-1.5 text-xs font-medium text-[#256640]'
          : 'rounded-2xl bg-[#f1f3f6] px-2.5 py-1.5 text-xs font-medium text-[#536174]'
      }
    >
      {active
        ? `Active access: ${access.activeDepartmentIds.length} departments, ${access.activeEmployeeIds.length} selected employees`
        : 'Access not active'}
    </span>
  )
}
