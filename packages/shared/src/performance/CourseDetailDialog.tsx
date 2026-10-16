// Dart: frontend/lib/features/performance/course_detail_dialog.dart:1-406 and the dialog route in
// performance_report_portal.dart:793-811 (_showCourse).
import * as RadixDialog from '@radix-ui/react-dialog'
import { useRef, useState } from 'react'
import { errorMessage } from '../api/client'
import {
  parseCourseDetailReport,
  type CourseModuleReport,
  type CourseReport,
} from '../models/performance'
import { Button, IconButton } from '../ui/Button'
import { Icon, type IconName } from '../ui/icons/Icon'
import { ProgressBar } from '../ui/ProgressBar'
import { Spinner } from '../ui/Spinner'
import { AccessGuard } from './AccessGuard'
import { useReport, useReportQuery } from './context'
import { colors, score } from './format'
import { scopeParams, without } from './state'
import { useElementWidth } from './useElementWidth'

/**
 * The course detail dialog. `courseId == null` means closed. The body mounts per course, keeps the
 * report context key from open time and sits inside AccessGuard, so the request runs only while
 * the context is unchanged.
 */
export function CourseDetailDialog({
  courseId,
  onClose,
}: {
  courseId: string | null
  onClose: () => void
}) {
  return (
    <RadixDialog.Root open={courseId != null} onOpenChange={(open) => !open && onClose()}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/54" />
        {courseId != null && <GuardedCourse key={courseId} courseId={courseId} onClose={onClose} />}
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}

function GuardedCourse({ courseId, onClose }: { courseId: string; onClose: () => void }) {
  const { contextKey } = useReport()
  const [expected] = useState(contextKey)
  return (
    <AccessGuard expected={expected} onClose={onClose}>
      <CourseDialogContent courseId={courseId} onClose={onClose} />
    </AccessGuard>
  )
}

function CourseDialogContent({ courseId, onClose }: { courseId: string; onClose: () => void }) {
  const { state, dispatch } = useReport()
  const detail = useReportQuery(
    'courses/' + courseId,
    without(scopeParams(state), 'course_id'),
    parseCourseDetailReport,
  )
  // Same focus return as ui/Dialog.tsx: the dialog opens from state, not from a Radix Trigger.
  const opener = useRef<HTMLElement | null>(null)
  // _showCourse onViewEmployees: close, then course filter, assignment list and Employees tab.
  const viewEmployees = () => {
    onClose()
    dispatch({ type: 'viewEmployeesOf', courseId })
  }

  let body
  if (detail.error) {
    body = <StateMessage detail={errorMessage(detail.error)} onClose={onClose} />
  } else if (!detail.data) {
    body = (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    )
  } else {
    body = (
      <CourseContent
        course={detail.data.course}
        modules={detail.data.modules}
        onClose={onClose}
        onViewEmployees={viewEmployees}
      />
    )
  }
  return (
    <RadixDialog.Content
      onOpenAutoFocus={() => {
        opener.current =
          document.activeElement instanceof HTMLElement ? document.activeElement : null
      }}
      onCloseAutoFocus={(event) => {
        const target = opener.current
        opener.current = null
        if (target?.isConnected) {
          event.preventDefault()
          target.focus()
        }
      }}
      aria-describedby={undefined}
      className="fixed top-1/2 left-1/2 z-40 flex h-[min(800px,calc(100%-32px))] w-[min(1040px,calc(100%-32px))] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-3xl bg-white focus:outline-none"
    >
      {(detail.error || !detail.data) && (
        <RadixDialog.Title className="sr-only">Course detail</RadixDialog.Title>
      )}
      {body}
    </RadixDialog.Content>
  )
}

function CourseContent({
  course,
  modules,
  onClose,
  onViewEmployees,
}: {
  course: CourseReport
  modules: CourseModuleReport[]
  onClose: () => void
  onViewEmployees: () => void
}) {
  const bodyRef = useRef<HTMLDivElement>(null)
  const width = useElementWidth(bodyRef)
  const stacked = width < 690
  // _CourseSummary's own LayoutBuilder: 215 wide beside the path, the full width when stacked.
  const summary = (
    <CourseSummary
      course={course}
      compact={stacked && width >= 290}
      onViewEmployees={onViewEmployees}
    />
  )
  return (
    <>
      <div className="flex shrink-0 items-start bg-linear-to-br from-[#eaf4fc] to-white pt-[22px] pr-[18px] pb-[22px] pl-7">
        <div className="min-w-0 flex-1">
          <p className="m-0 text-[11px] font-extrabold tracking-[1.4px] text-brand-blue-700">
            COURSE DETAIL
          </p>
          <RadixDialog.Title className="m-0 mt-2 text-[27px] font-extrabold text-text-black">
            {course.courseName || 'Course'}
          </RadixDialog.Title>
        </div>
        <IconButton
          icon="close"
          label="Close course detail"
          className="text-[#44474e]!"
          onClick={onClose}
        />
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-6">
        <div ref={bodyRef}>
          {stacked ? (
            <div className="flex flex-col items-start">
              <div className="w-full">{summary}</div>
              <div className="h-[22px]" />
              <ModulePath modules={modules} />
            </div>
          ) : (
            <div className="flex items-start">
              <div className="w-[215px] shrink-0">{summary}</div>
              <div className="w-[26px] shrink-0" />
              <div className="min-w-0 flex-1">
                <ModulePath modules={modules} />
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

function CourseSummary({
  course,
  compact,
  onViewEmployees,
}: {
  course: CourseReport
  compact: boolean
  onViewEmployees: () => void
}) {
  const rate = Math.min(100, Math.max(0, course.completionRate))
  const ring = <Ring rate={rate} size={compact ? 94 : 126} />
  const stats = [
    { label: 'Assigned', value: course.assigned, color: colors.primaryBlue },
    { label: 'Completed', value: course.completed, color: colors.accentGreen },
    { label: 'Overdue', value: course.overdue, color: colors.accentRed },
  ]
  return (
    <div className="flex flex-col items-start rounded-[15px] border border-[#dde6f1] bg-[#f8fbfe] p-[18px]">
      {compact ? (
        <div className="flex w-full items-center">
          {ring}
          <div className="w-[18px] shrink-0" />
          <div className="min-w-0 flex-1">
            {stats.map((stat) => (
              <p key={stat.label} className="m-0 py-[3px] font-bold" style={{ color: stat.color }}>
                {stat.value} {stat.label.toLowerCase()}
              </p>
            ))}
          </div>
        </div>
      ) : (
        <>
          <div className="flex w-full justify-center">{ring}</div>
          <div className="h-5" />
          {stats.map((stat) => (
            <div key={stat.label} className="py-[7px]">
              <p className="m-0 text-[22px] font-extrabold" style={{ color: stat.color }}>
                {stat.value}
              </p>
              <p className="m-0 text-text-secondary">{stat.label.toLowerCase()}</p>
            </div>
          ))}
        </>
      )}
      <div className="h-[18px]" />
      <Button icon="people_outline" className="w-full" onClick={onViewEmployees}>
        View employees
      </Button>
    </div>
  )
}

/** The determinate CircularProgressIndicator (stroke 9, inset 4) with the rate in the middle. */
function Ring({ rate, size }: { rate: number; size: number }) {
  const radius = (size - 8) / 2
  const circumference = 2 * Math.PI * radius
  return (
    <div
      className="relative flex shrink-0 items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg
        role="progressbar"
        aria-label="Course completion"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={rate}
        width={size}
        height={size}
        className="absolute inset-0 -rotate-90"
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colors.brandBlue100}
          strokeWidth={9}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colors.accentBlue}
          strokeWidth={9}
          strokeDasharray={`${(circumference * rate) / 100} ${circumference}`}
        />
      </svg>
      <div className="relative flex flex-col items-center">
        <span className="text-[27px] font-extrabold text-text-black">{rate}%</span>
        <span className="text-[11px] text-text-secondary">complete</span>
      </div>
    </div>
  )
}

function ModulePath({ modules }: { modules: CourseModuleReport[] }) {
  return (
    <div className="flex w-full flex-col items-start">
      <h3 className="m-0 text-xl font-extrabold text-text-black">Module outcomes</h3>
      <p className="m-0 mt-1 text-xs text-text-secondary">
        {modules.length} modules in this course
      </p>
      <div className="h-4" />
      {modules.length === 0 && (
        <p className="m-0 text-text-secondary">No module outcomes are available for this course.</p>
      )}
      {modules.map((module, index) => (
        <ModuleStep
          key={module.moduleId || index}
          module={module}
          isLast={index === modules.length - 1}
        />
      ))}
    </div>
  )
}

function ModuleStep({ module, isLast }: { module: CourseModuleReport; isLast: boolean }) {
  const { assigned, watched } = module
  const rate = assigned === 0 ? 0 : Math.min(1, Math.max(0, watched / assigned))
  const hasQuiz = module.numQuestions > 0
  return (
    <div className="flex w-full items-stretch">
      <div className="flex w-[34px] shrink-0 flex-col items-center">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-blue text-base font-extrabold text-white">
          {module.moduleNumber}
        </span>
        {!isLast && <span className="w-0.5 flex-1 bg-brand-blue-100" />}
      </div>
      <div className="w-3 shrink-0" />
      <div className="mb-3 min-w-0 flex-1 rounded-[13px] border border-[#dde6f1] bg-white p-4">
        <p className="m-0 text-base font-extrabold text-text-black">{module.title || 'Module'}</p>
        <div className="mt-2.5 flex items-center">
          <Icon name="play_circle_outline" size={17} color={colors.primaryBlue} />
          <span className="ml-[5px] text-xs text-text-secondary">
            {watched}/{assigned} watched
          </span>
        </div>
        <ProgressBar
          value={rate}
          height={6}
          radius={6}
          color={colors.accentBlue}
          trackColor={colors.brandBlue100}
          className="mt-1.5"
          label={`${module.title || 'Module'} watched`}
        />
        <div className="mt-3 flex flex-wrap gap-x-2.5 gap-y-2">
          <ModuleMeta
            icon={hasQuiz ? 'quiz_outlined' : 'remove_circle_outline'}
            label={hasQuiz ? `${module.passed} passed` : 'No quiz'}
            color={hasQuiz ? colors.accentGreen : colors.textSecondary}
          />
          <ModuleMeta icon="replay_outlined" label={`${module.attempts} attempts`} />
          <ModuleMeta icon="bar_chart_rounded" label={`Average ${score(module.averageScore)}`} />
        </div>
      </div>
    </div>
  )
}

/** `color` set means bold text (Dart: w700 when a color is given). */
function ModuleMeta({ icon, label, color }: { icon: IconName; label: string; color?: string }) {
  const shown = color ?? colors.textSecondary
  return (
    <span className="inline-flex items-center">
      <Icon name={icon} size={15} color={shown} />
      <span
        className={color == null ? 'ml-1 text-[11px]' : 'ml-1 text-[11px] font-bold'}
        style={{ color: shown }}
      >
        {label}
      </span>
    </span>
  )
}

function StateMessage({ detail, onClose }: { detail: string; onClose: () => void }) {
  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="flex flex-col items-center p-6">
        <Icon name="error_outline" size={36} color={colors.accentRed} />
        <p className="m-0 mt-3 font-extrabold">Could not load course detail</p>
        <p className="m-0 mt-1.5 text-center">{detail}</p>
        <Button variant="text" onClick={onClose}>
          Close
        </Button>
      </div>
    </div>
  )
}
