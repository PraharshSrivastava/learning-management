// Assignment rule editor for one course (Flutter AssignmentRuleView).
import { useLmsAccess } from '@lms/shared/auth/lmsAccess'
import { useSession } from '@lms/shared/auth/session'
import type { AssignmentRule, Course } from '@lms/shared/models'
import { Dialog } from '@lms/shared/ui/Dialog'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import { ProgressBar } from '@lms/shared/ui/ProgressBar'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import clsx from 'clsx'
import { useState, useSyncExternalStore, type ReactNode } from 'react'
import type { Trainer } from '../../auth/trainer'
import { CourseActionsMenu } from '../courses/CourseActionsMenu'
import { PREVIEW_PAGE_SIZE, type Requester } from './api'
import { ActionButton, ChoiceChip, Notice, Switch } from './controls'
import { deadlineRange, isDeadlineInRange } from './dates'
import { GroupList, OutlinedNumberField } from './groups'
import { ObserverPanel } from './ObserverPanel'
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
    <div className="card overflow-auto p-6" inert={busy} aria-busy={busy}>
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="w-[240px] pt-[5px]">
          <h2 className="font-barlow text-2xl leading-[1.2] font-extrabold text-text-black">
            Assign Course
          </h2>
          <p className="mt-2 text-[#667085]">{course.courseName}</p>
        </div>
        <ActionButton
          icon="save_outlined"
          disabled={archived || busy}
          onClick={() => void workspace.save(course.courseId)}
          className="border-primary-blue text-primary-blue disabled:border-light-gray"
        >
          {state.isSaving ? 'Saving…' : 'Save Rule'}
        </ActionButton>
        <Tooltip content="Refresh assignment data">
          <button
            type="button"
            aria-label="Refresh assignment data"
            disabled={archived || busy}
            onClick={() => void workspace.refreshOptionsAndGroups()}
            className="inline-flex size-10 items-center justify-center rounded-full border border-[#757780] text-[#44474e] hover:bg-black/4 focus-visible:outline-2 focus-visible:outline-brand-blue-light disabled:border-light-gray disabled:text-gray"
          >
            <Icon name="refresh" />
          </button>
        </Tooltip>
        <ActionButton
          variant="filled"
          icon="send_outlined"
          disabled={archived || busy}
          onClick={() => void confirmPublish()}
        >
          {state.isPublishing ? 'Publishing…' : publishLabel(course)}
        </ActionButton>
        <CourseActionsMenu
          course={course}
          onEnable={confirmPublish}
          onChanged={(action) => onCourseChanged(action === 'Delete')}
        />
      </div>
      {archived && (
        <Notice
          text="This course requires an availability update. Refresh or contact your administrator."
          isError={false}
        />
      )}
      <div className={clsx(archived && 'pointer-events-none')} inert={archived}>
        {!rule.isActive && (
          <div className="mt-4">
            <Notice
              text="Employee access is disabled. Review the selections and deadline, then Enable. Apply Observers separately."
              isError={false}
            />
          </div>
        )}
        {state.error != null && (
          <div className="mt-4">
            <Notice text={state.error} isError />
            {state.error.includes('changed') && (
              <ActionButton variant="text" icon="refresh" onClick={() => setConfirmReload(true)}>
                Reload saved employee rule
              </ActionButton>
            )}
          </div>
        )}
        {state.message != null && (
          <div className="mt-4">
            <Notice
              text={state.message}
              isError={false}
              onDismiss={() => workspace.dismissMessage()}
            />
          </div>
        )}
        <div className="mt-6 flex flex-col gap-5">
          <Section title="Target Employees">
            <label className="flex cursor-pointer items-center gap-4 pt-[7px] pr-1 pb-2">
              <span className="min-w-0 flex-1">
                <span className="block text-base leading-6 text-[#191c20]">
                  All active employees
                </span>
                <span className="block text-sm leading-5 text-[#44474e]">
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
              <div className="mt-3">
                <GroupList
                  label="Include"
                  pickerTitle="Add employee"
                  groups={rule.includeGroups}
                  savedGroups={state.savedGroups.filter((g) => g.groupType === 'include')}
                  options={state.options}
                  onChange={(includeGroups) => update({ ...rule, includeGroups })}
                />
              </div>
            )}
          </Section>
          <Section title="Performance Observers">
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
          <Section title="Employee Exclusions">
            <GroupList
              label="Exclude"
              pickerTitle="Exclude employee"
              allowJoinedFilter={false}
              groups={rule.excludeGroups}
              savedGroups={state.savedGroups.filter((g) => g.groupType === 'exclude')}
              options={state.options}
              onChange={(excludeGroups) => update({ ...rule, excludeGroups })}
            />
          </Section>
          <Section title="Completion Deadline">
            <Deadline
              rule={rule}
              disabled={state.isLoading}
              onChange={(next) => {
                // Ignore a pick that lands after the course changed.
                if (workspace.getState().loadedCourseId === course.courseId) update(next)
              }}
            />
          </Section>
          <PreviewCard state={state} workspace={workspace} />
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

const sectionStyle: Record<string, { bg: string; icon: IconName }> = {
  'Target Employees': { bg: '#EDF5FF', icon: 'people_outline' },
  'Performance Observers': { bg: '#EDF5FF', icon: 'visibility_outlined' },
  'Employee Exclusions': { bg: '#FBECEF', icon: 'person_remove_outlined' },
  'Completion Deadline': { bg: '#F0F2F5', icon: 'calendar_month_outlined' },
  'Assignment Preview': { bg: '#EDF5FF', icon: 'list_alt_outlined' },
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const style = sectionStyle[title] ?? { bg: '#EDF5FF', icon: 'people_outline' }
  return (
    <section aria-label={title} className="rounded-2xl border border-light-gray bg-white p-4">
      <div
        className="flex items-center gap-2.5 rounded-[10px] px-3.5 py-3"
        style={{ backgroundColor: style.bg }}
      >
        <Icon name={style.icon} size={21} className="text-primary-blue" />
        <h3 className="text-[17px] leading-[26px] font-medium tracking-normal text-primary-blue">
          {title}
        </h3>
      </div>
      <div className="mt-3.5">{children}</div>
    </section>
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
    <Section title="Assignment Preview">
      <p className="text-[13px] leading-5 font-medium text-[#475467]">
        Check your employees before publishing.
      </p>
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
