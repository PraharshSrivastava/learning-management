// Assignment rule editor for one course (Flutter AssignmentRuleView).
import { useLmsAccess } from '@lms/shared/auth/lmsAccess'
import { useSession } from '@lms/shared/auth/session'
import type { AssignmentRule, Course, Employee } from '@lms/shared/models'
import { Dialog } from '@lms/shared/ui/Dialog'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import { ProgressBar } from '@lms/shared/ui/ProgressBar'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import clsx from 'clsx'
import { useState, useSyncExternalStore, type ReactNode } from 'react'
import type { Trainer } from '../../auth/trainer'
import { CourseActionsMenu } from '../courses/CourseActionsMenu'
import { PREVIEW_PAGE_SIZE, type Requester } from './api'
import { ActionButton, ChoiceChip, InputChip, Notice, Switch } from './controls'
import { deadlineRange, isDeadlineInRange } from './dates'
import { splitDirect, withDirectIds, withOtherGroups } from './directEmployees'
import { GroupList, OutlinedNumberField } from './groups'
import { LifecycleBadge } from './LifecycleBadge'
import { ObserverPanel } from './ObserverPanel'
import { EmployeeMultiPickerDialog } from './pickers'
import type { AssignmentState, AssignmentWorkspace } from './workspace'

interface RuleViewProps {
  course: Course
  workspace: AssignmentWorkspace
  request: Requester
  /** Reloads course lists and reports after a course action. */
  onCourseChanged: (deleted: boolean) => Promise<void>
}

const publishLabel = (course: Course) =>
  course.lifecycleState === 'active'
    ? 'Update Assignments'
    : course.lifecycleState === 'disabled'
      ? 'Enable'
      : 'Publish & Assign'

export function publishConfirmText(state: AssignmentState): string {
  const { rule } = state
  const deadline =
    rule.deadlineMode === 'fixed'
      ? (rule.deadlineDate ?? 'not selected')
      : `${rule.deadlineDays} days after assignment`
  return `${state.matchCount} employees match the selection. Deadline: ${deadline}. Excluded employees lose access; completed results and progress are retained. Review the selected deadline. Apply Observers separately after this operation.`
}

export function RuleView({ course, workspace, request, onCourseChanged }: RuleViewProps) {
  const state = useSyncExternalStore(workspace.subscribe, workspace.getState)
  const { person } = useSession<Trainer>()
  const { access } = useLmsAccess()
  const [confirm, setConfirm] = useState<{ label: string; text: string } | null>(null)
  const [confirmReload, setConfirmReload] = useState(false)
  const { rule } = state
  const busy = state.isLoading || state.isSaving || state.isPublishing
  const archived = course.lifecycleState === 'archived'
  const update = (next: AssignmentRule) => workspace.updateRule(next)

  const confirmPublish = async () => {
    await workspace.fetchEmployeePreview()
    const s = workspace.getState()
    if (s.loadedCourseId !== course.courseId) return
    if (s.previewStale || s.isLoading || s.isPublishing) return
    setConfirm({ label: publishLabel(course), text: publishConfirmText(s) })
  }

  return (
    // `inert` blocks keyboard input too, so no edit lands during a save (Flutter AbsorbPointer).
    <div className="assign-workspace" inert={busy} aria-busy={busy}>
      <header className="assign-heading">
        <div className="min-w-0 flex-1">
          <p className="assign-kicker">Assign course</p>
          <h2 className="assign-title">{course.courseName}</h2>
          <p className="assign-meta">
            <span>{course.courseDifficulty || 'Difficulty not set'}</span>
            <LifecycleBadge course={course} />
            <span>
              {course.moduleCount} module{course.moduleCount === 1 ? '' : 's'}
            </span>
          </p>
        </div>
        <div className="assign-actions" role="toolbar" aria-label="Assignment actions">
          <ActionButton
            icon="save_outlined"
            disabled={archived || busy}
            onClick={() => void workspace.save(course.courseId)}
            className="assign-button"
          >
            {state.isSaving ? 'Saving…' : 'Save Rule'}
          </ActionButton>
          <Tooltip content="Reload employees, groups and options">
            <ActionButton
              icon="refresh"
              aria-label="Refresh assignment data"
              disabled={archived || busy}
              onClick={() => void workspace.refreshOptionsAndGroups()}
              className="assign-button"
            >
              Refresh
            </ActionButton>
          </Tooltip>
          {/* The publish button is this course's Enable, so the lifecycle control omits it. */}
          <CourseActionsMenu
            course={course}
            directSingle
            exclude={['Enable']}
            onChanged={(action) => onCourseChanged(action === 'Delete')}
          />
          <ActionButton
            variant="filled"
            icon="send_outlined"
            disabled={archived || busy}
            onClick={() => void confirmPublish()}
            className="assign-button assign-primary"
          >
            {state.isPublishing ? 'Publishing…' : publishLabel(course)}
          </ActionButton>
        </div>
      </header>
      {archived && (
        <Notice
          text="This course requires an availability update. Refresh or contact your administrator."
          isError={false}
        />
      )}
      <div className={clsx(archived && 'pointer-events-none')} inert={archived}>
        {!rule.isActive && (
          <div className="mb-4">
            <Notice
              text="Employee access is disabled. Review the selections and deadline, then Enable. Apply Observers separately."
              isError={false}
            />
          </div>
        )}
        {state.error != null && (
          <div className="mb-4">
            <Notice text={state.error} isError />
            {state.error.includes('changed') && (
              <ActionButton variant="text" icon="refresh" onClick={() => setConfirmReload(true)}>
                Reload saved employee rule
              </ActionButton>
            )}
          </div>
        )}
        {state.message != null && (
          <div className="mb-4">
            <Notice
              text={state.message}
              isError={false}
              onDismiss={() => workspace.dismissMessage()}
            />
          </div>
        )}
        <div className="assign-grid">
          <div className="assign-column">
            <Section
              title="Target employees"
              icon="people_outline"
              description="Choose who receives this course. Saving the rule does not enroll anyone until you publish."
            >
              <TargetEmployees rule={rule} state={state} update={update} />
            </Section>
            <PreviewCard state={state} workspace={workspace} />
          </div>
          <div className="assign-column">
            <Section
              title="Completion deadline"
              icon="calendar_month_outlined"
              description="When assigned employees should finish."
            >
              <Deadline
                rule={rule}
                disabled={state.isLoading}
                onChange={(next) => {
                  // Ignore a pick that lands after the course changed.
                  if (workspace.getState().loadedCourseId === course.courseId) update(next)
                }}
              />
            </Section>
            <Section
              title="Performance observers"
              icon="visibility_outlined"
              description="Observers see performance reports only and are not enrolled as learners."
            >
              <ObserverPanel
                key={`${course.courseId}:${person?.trainerId}:${access?.permissions_version}`}
                course={course}
                employees={state.options.employees}
                refreshGeneration={state.refreshGeneration}
                isAssignmentActive={rule.isActive}
                request={request}
                onDraftObservers={(ids) => workspace.updateDraftObservers(ids)}
              />
            </Section>
          </div>
        </div>
      </div>
      <Dialog
        open={confirm != null}
        onOpenChange={(open) => {
          if (!open) setConfirm(null)
        }}
        title={`${confirm?.label ?? ''}?`}
        actions={
          <>
            <ActionButton variant="text" onClick={() => setConfirm(null)}>
              Cancel
            </ActionButton>
            <ActionButton
              variant="filled"
              onClick={() => {
                setConfirm(null)
                if (workspace.getState().loadedCourseId === course.courseId) {
                  void workspace.publish(course.courseId, course.lifecycleRevision)
                }
              }}
            >
              {confirm?.label}
            </ActionButton>
          </>
        }
      >
        {confirm?.text}
      </Dialog>
      <Dialog
        open={confirmReload}
        onOpenChange={setConfirmReload}
        title="Reload saved employee rule?"
        actions={
          <>
            <ActionButton variant="text" onClick={() => setConfirmReload(false)}>
              Keep editing
            </ActionButton>
            <ActionButton
              variant="filled"
              onClick={() => {
                setConfirmReload(false)
                void workspace.reloadSavedRule(course.courseId)
              }}
            >
              Reload saved rule
            </ActionButton>
          </>
        }
      >
        Your unsaved employee selections and deadline edits will be discarded. Observer edits will
        be retained.
      </Dialog>
    </div>
  )
}

function Section({
  title,
  icon,
  description,
  className,
  children,
}: {
  title: string
  icon: IconName
  description?: string
  className?: string
  children: ReactNode
}) {
  return (
    <section aria-label={title} className={clsx('assign-panel', className)}>
      <header className="assign-panel-head">
        <span className="assign-panel-icon">
          <Icon name={icon} size={18} />
        </span>
        <div className="min-w-0">
          <h3>{title}</h3>
          {description && <p>{description}</p>}
        </div>
      </header>
      {children}
    </section>
  )
}

const pluralEmployees = (count: number) => `${count} employee${count === 1 ? '' : 's'}`

function TargetEmployees({
  rule,
  state,
  update,
}: {
  rule: AssignmentRule
  state: AssignmentState
  update: (rule: AssignmentRule) => void
}) {
  const include = splitDirect(rule.includeGroups)
  const exclude = splitDirect(rule.excludeGroups)
  return (
    <div className="flex flex-col gap-5">
      <label className="assign-switch-row">
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-[#19273e]">All active employees</span>
          <span className="block text-xs text-[#5b6980]">
            Start from everyone, then apply exclusions.
          </span>
        </span>
        <Switch
          checked={rule.includeAll}
          label="All active employees"
          onChange={(includeAll) => update({ ...rule, includeAll })}
        />
      </label>
      {!rule.includeAll && (
        <div>
          <EmployeePicks
            title="Selected employees"
            empty="No employees selected yet. Add employees, or include a department or saved group below."
            action="Add employees"
            confirm={(n) => (n ? `Add ${pluralEmployees(n)}` : 'Add employees')}
            employees={state.options.employees}
            ids={include.employeeIds}
            onChange={(ids) =>
              update({
                ...rule,
                includeGroups: withDirectIds(rule.includeGroups, ids, 'Selected employees'),
              })
            }
          />
          <MoreCriteria
            label="Departments, mailing lists and saved groups"
            count={include.others.length}
          >
            <GroupList
              label="Include"
              pickerTitle="Add employee"
              allowEmployees={false}
              groups={include.others}
              savedGroups={state.savedGroups.filter((g) => g.groupType === 'include')}
              options={state.options}
              onChange={(others) =>
                update({ ...rule, includeGroups: withOtherGroups(rule.includeGroups, others) })
              }
            />
          </MoreCriteria>
        </div>
      )}
      <div className="assign-subsection" role="group" aria-label="Exclusions">
        <EmployeePicks
          title="Excluded employees"
          empty="No one is excluded."
          action="Exclude employees"
          confirm={(n) => (n ? `Exclude ${pluralEmployees(n)}` : 'Exclude employees')}
          employees={state.options.employees}
          ids={exclude.employeeIds}
          onChange={(ids) =>
            update({
              ...rule,
              excludeGroups: withDirectIds(rule.excludeGroups, ids, 'Excluded employees'),
            })
          }
        />
        <MoreCriteria label="Exclusion filters and saved groups" count={exclude.others.length}>
          <GroupList
            label="Exclude"
            pickerTitle="Exclude employee"
            allowJoinedFilter={false}
            allowEmployees={false}
            groups={exclude.others}
            savedGroups={state.savedGroups.filter((g) => g.groupType === 'exclude')}
            options={state.options}
            onChange={(others) =>
              update({ ...rule, excludeGroups: withOtherGroups(rule.excludeGroups, others) })
            }
          />
        </MoreCriteria>
      </div>
    </div>
  )
}

/** Individually chosen employees: chips in directory order, with the multi-select picker. */
export function EmployeePicks({
  title,
  empty,
  action,
  confirm,
  employees,
  ids,
  onChange,
}: {
  title: string
  empty: string
  action: string
  confirm: (count: number) => string
  employees: Employee[]
  ids: string[]
  onChange: (ids: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  // Chips follow the directory order. Unknown ids come last so they can still be removed.
  const known = employees.filter((e) => ids.includes(e.employeeId))
  const unknown = ids.filter((id) => !employees.some((e) => e.employeeId === id))
  const remove = (id: string) => onChange(ids.filter((item) => item !== id))
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-[#19273e]">
          {title} <span className="assign-count">{ids.length}</span>
        </p>
        <ActionButton
          icon="person_add_alt_1"
          className="assign-button"
          onClick={() => setOpen(true)}
        >
          {action}
        </ActionButton>
      </div>
      {ids.length === 0 ? (
        <p className="mt-2 text-xs text-[#5b6980]">{empty}</p>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          {known.map((e) => (
            <InputChip
              key={e.employeeId}
              label={`${e.name} (${e.employeeId})`}
              onRemove={() => remove(e.employeeId)}
            />
          ))}
          {unknown.map((id) => (
            <InputChip
              key={id}
              label={`Unavailable employee (${id})`}
              onRemove={() => remove(id)}
            />
          ))}
        </div>
      )}
      <EmployeeMultiPickerDialog
        open={open}
        onOpenChange={setOpen}
        title={action}
        actionLabel={confirm}
        employees={employees.filter((e) => e.status === 'active' && !ids.includes(e.employeeId))}
        onPick={(picked) => onChange([...ids, ...picked.map((e) => e.employeeId)])}
      />
    </div>
  )
}

/** Supplementary criteria, collapsed until needed or already in use. */
export function MoreCriteria({
  label,
  count,
  children,
}: {
  label: string
  count: number
  children: ReactNode
}) {
  const [open, setOpen] = useState(count > 0)
  return (
    <div className="mt-4">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="assign-disclosure"
      >
        <Icon name="expand_more" size={18} className={open ? 'rotate-180' : undefined} />
        {label}
        {count > 0 && <span className="assign-count">{count}</span>}
      </button>
      {open && <div className="mt-3">{children}</div>}
    </div>
  )
}

function Deadline({
  rule,
  disabled,
  onChange,
}: {
  rule: AssignmentRule
  disabled: boolean
  onChange: (rule: AssignmentRule) => void
}) {
  return (
    <div>
      <div className="flex flex-wrap gap-3">
        <ChoiceChip
          selected={rule.deadlineMode === 'relative'}
          disabled={disabled}
          onClick={() => onChange({ ...rule, deadlineMode: 'relative' })}
        >
          Days after assignment
        </ChoiceChip>
        <ChoiceChip
          selected={rule.deadlineMode === 'fixed'}
          disabled={disabled}
          onClick={() => onChange({ ...rule, deadlineMode: 'fixed' })}
        >
          Specific date
        </ChoiceChip>
      </div>
      <div className="mt-3">
        {rule.deadlineMode === 'relative' ? (
          <div className="w-[260px]">
            <OutlinedNumberField
              label="Due days after assignment"
              value={rule.deadlineDays}
              onChange={(days) => onChange({ ...rule, deadlineDays: days ?? 1 })}
            />
          </div>
        ) : (
          <DeadlineDate
            value={rule.deadlineDate}
            disabled={disabled}
            onChange={(deadlineDate) => onChange({ ...rule, deadlineDate })}
          />
        )}
        {rule.deadlineMode === 'fixed' && (
          <p className="pt-2">Due by the end of this date (Asia/Kolkata).</p>
        )}
      </div>
    </div>
  )
}

/** Native date input. Partly typed or out-of-range dates stay local until blur, then revert. */
function DeadlineDate({
  value,
  disabled,
  onChange,
}: {
  value: string | null
  disabled: boolean
  onChange: (value: string) => void
}) {
  const { min, max } = deadlineRange()
  const [text, setText] = useState(value ?? '')
  const [shown, setShown] = useState(value)
  if (shown !== value) {
    setShown(value)
    setText(value ?? '')
  }
  const invalid = text !== '' && !isDeadlineInRange(text)
  return (
    <input
      type="date"
      aria-label="Completion date"
      aria-invalid={invalid || undefined}
      value={text}
      min={min}
      max={max}
      disabled={disabled}
      onChange={(event) => {
        const next = event.target.value
        setText(next)
        if (isDeadlineInRange(next)) {
          setShown(next)
          onChange(next)
        }
      }}
      onBlur={() => setText(value ?? '')}
      className="h-9 rounded-lg border border-input-border bg-white px-3 text-sm text-text-black focus:border-brand-blue-light focus:outline-none disabled:bg-surface-secondary disabled:text-gray aria-invalid:border-accent-red"
    />
  )
}

function PreviewCard({
  state,
  workspace,
}: {
  state: AssignmentState
  workspace: AssignmentWorkspace
}) {
  const [search, setSearch] = useState(state.previewSearch)
  const loading = state.isPreviewLoading
  return (
    <Section
      title="Assignment preview"
      icon="list_alt_outlined"
      description="Check your employees before publishing."
      className="assign-preview"
    >
      {state.blockedEmployeeCount > 0 && (
        <p className="py-2 text-[#805300]">
          {state.blockedEmployeeCount} matching employees are also Observers. Resolve these
          conflicts before publishing.
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-2">
        <ChoiceChip
          selected={state.previewView === 'matching'}
          disabled={state.isLoading}
          onClick={() => void workspace.fetchEmployeePreview({ view: 'matching', page: 1 })}
        >
          Matching employees ({state.matchCount})
        </ChoiceChip>
        <ChoiceChip
          selected={state.previewView === 'assigned'}
          disabled={state.isLoading}
          onClick={() => void workspace.fetchEmployeePreview({ view: 'assigned', page: 1 })}
        >
          Assigned employees ({state.totalAssignedCount})
        </ChoiceChip>
      </div>
      <div className="relative mt-3 w-[360px] max-w-full">
        <Icon
          name="search"
          size={18}
          className="pointer-events-none absolute top-1/2 left-[11px] -translate-y-1/2 text-[#44474e]"
        />
        <input
          type="search"
          aria-label="Search employees"
          placeholder="Search employees"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') void workspace.fetchEmployeePreview({ search, page: 1 })
          }}
          className="h-10 w-full rounded-lg border border-input-border bg-white pr-3 pl-11 text-[15px] text-text-black placeholder:text-text-secondary focus:border-[1.4px] focus:border-brand-blue-light focus:outline-none [&::-webkit-search-cancel-button]:hidden"
        />
      </div>
      {loading && <ProgressBar label="Loading preview" />}
      {state.previewStale && (
        <p className="py-2 text-[#805300]">Preview needs refreshing. Your edits are preserved.</p>
      )}
      <div className="h-2" />
      {!loading && state.previewEmployees.length === 0 && <p>No employees to display.</p>}
      {state.previewEmployees.length > 0 && (
        <ul aria-label="Preview employees">
          {state.previewEmployees.map((employee) => (
            <li key={employee.employeeId} className="flex min-h-[53px] items-center gap-4 py-1">
              <span className="min-w-0 flex-1">
                <span className="block text-sm leading-5 text-[#191c20]">{employee.name}</span>
                <span className="block text-xs leading-4 text-[#44474e]">
                  {employee.department} • {employee.jobTitle}
                </span>
              </span>
              <span className="text-xs text-[#44474e]">{employee.employeeId}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <span>
          {state.previewTotal} employees • Page {state.previewPage}
        </span>
        <ActionButton
          variant="text"
          disabled={loading || state.previewPage <= 1}
          onClick={() => void workspace.fetchEmployeePreview({ page: state.previewPage - 1 })}
        >
          Previous
        </ActionButton>
        <ActionButton
          variant="text"
          disabled={loading || state.previewPage * PREVIEW_PAGE_SIZE >= state.previewTotal}
          onClick={() => void workspace.fetchEmployeePreview({ page: state.previewPage + 1 })}
        >
          Next
        </ActionButton>
      </div>
    </Section>
  )
}
