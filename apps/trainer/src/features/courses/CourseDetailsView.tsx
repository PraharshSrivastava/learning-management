import { assetUrl, videoAssetUrl } from '@lms/shared/api/client'
import { useHasMediaTicket } from '@lms/shared/api/useMediaTicket'
import type { Course, CourseImage } from '@lms/shared/models'
import { Icon, type IconName } from '@lms/shared/ui/icons/Icon'
import { Spinner } from '@lms/shared/ui/Spinner'
import { useToast } from '@lms/shared/ui/Toast'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import clsx from 'clsx'
import {
  useId,
  useRef,
  useState,
  type CSSProperties,
  type DragEvent,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import { videoDownloadFilename } from '../training/trainingData'
import { useDownloadVideo } from '../training/useDownloadVideo'
import { CourseActionsMenu } from './CourseActionsMenu'
import {
  DIFFICULTIES,
  blueprintDraft,
  blueprintPayload,
  editorSignature,
  generateButtonState,
  moduleNumberForImage,
  moveItem,
  newModuleDraft,
  type BlueprintDraft,
  type Difficulty,
  type ModuleDraft,
} from './courseLogic'
import { updateErrorMessage, useUpdateCourse } from './courseQueries'
import { useFullCourseGeneration } from './useFullCourseGeneration'

interface CourseDetailsViewProps {
  course: Course
  /** Detail load error. Shown in place of the endless spinner. */
  detailError?: string | null
}

/** Blueprint tab detail pane: archived notice, loading state, or the blueprint editor. */
export function CourseDetailsView({ course, detailError = null }: CourseDetailsViewProps) {
  if (course.lifecycleState === 'archived') return <ArchivedCourseView course={course} />
  if (isDetailPending(course)) return <CourseDetailPending detailError={detailError} />
  // A new course or a changed server copy resets the form, as didUpdateWidget did.
  return <BlueprintEditor key={editorSignature(course)} course={course} />
}

/** The sidebar summary has modules, but the course details have not loaded yet. */
export function isDetailPending(course: Course): boolean {
  return course.modules.length === 0 && course.moduleCount > 0
}

/** Detail pane while the course details load, or the load error. */
export function CourseDetailPending({ detailError }: { detailError: string | null }) {
  return (
    <div className="card flex h-full items-center justify-center p-6">
      {detailError ? (
        <div role="alert" className="flex flex-col items-center text-center">
          <Icon name="error_outline_rounded" size={32} className="text-accent-red" />
          <p className="m-0 mt-2 font-barlow leading-[21px] font-bold">Error loading course</p>
          <p className="m-0 mt-1 text-xs leading-[16.8px] text-gray">{detailError}</p>
        </div>
      ) : (
        <Spinner label="Loading course" />
      )}
    </div>
  )
}

/** Legacy branch for a course in the archived state. */
function ArchivedCourseView({ course }: { course: Course }) {
  return (
    <div className="card h-full overflow-y-auto p-6">
      <div className="flex items-center">
        <h2 className="m-0 min-w-0 flex-1 font-manrope text-2xl leading-[30px] font-extrabold text-text-black">
          {course.courseName}
        </h2>
        <CourseActionsMenu course={course} />
      </div>
      <p className="m-0 mt-3">
        This course requires an availability update. Refresh or contact your administrator. Learning
        records are preserved.
      </p>
      <p className="m-0 mt-5">{course.courseDescription}</p>
      <p className="m-0 mt-3">{course.courseObjective}</p>
      {course.modules.map((module) => (
        <div key={module.moduleNumber} className="px-4 py-2">
          <p className="m-0 text-[15px] leading-[22.5px]">{module.title}</p>
          <p className="m-0 text-text-secondary">{module.sourceText}</p>
        </div>
      ))}
    </div>
  )
}

function BlueprintEditor({ course }: { course: Course }) {
  const [draft, setDraft] = useState<BlueprintDraft>(() => blueprintDraft(course))
  const [nameInvalid, setNameInvalid] = useState(false)
  const update = useUpdateCourse()
  const generation = useFullCourseGeneration()
  const toast = useToast()
  const generate = generateButtonState(course, draft.modules.length, generation.running)

  const patch = (fields: Partial<BlueprintDraft>) =>
    setDraft((current) => ({ ...current, ...fields }))
  const setModules = (change: (modules: ModuleDraft[]) => ModuleDraft[]) =>
    setDraft((current) => ({ ...current, modules: change(current.modules) }))

  const save = async (showSuccessMessage: boolean): Promise<boolean> => {
    // Flutter validated only the name, without a trim.
    if (draft.name === '') {
      setNameInvalid(true)
      return false
    }
    setNameInvalid(false)
    try {
      await update.mutateAsync({ courseId: course.courseId, payload: blueprintPayload(draft) })
    } catch (error) {
      toast(updateErrorMessage(error), { tone: 'error' })
      return false
    }
    if (showSuccessMessage) toast('Course blueprint successfully saved!', { tone: 'success' })
    return true
  }

  const startGeneration = async () => {
    if (generate.resume) {
      generation.start(course.courseId, true)
      return
    }
    // A new run uses the saved blueprint, so the form is saved first.
    if (await save(false)) generation.start(course.courseId, false)
  }

  const generateButton = (
    <PillButton
      icon={generate.icon}
      background={generate.complete ? '#616161' : 'var(--color-accent-orange)'}
      disabled={!generate.enabled}
      onClick={() => void startGeneration()}
    >
      {generate.label}
    </PillButton>
  )

  return (
    <form
      noValidate
      className="card flex h-full flex-col overflow-hidden"
      onSubmit={(event) => {
        event.preventDefault()
        void save(true)
      }}
    >
      <div className="shrink-0 primary-gradient p-6">
        <div className="flex items-start">
          <span className="font-barlow text-[11px] leading-[16.5px] font-bold tracking-[2px] text-white/70">
            COURSE BLUEPRINT
          </span>
          <div className="ml-4 flex min-w-0 flex-1 flex-wrap items-start justify-end gap-2">
            <CourseActionsMenu course={course} foregroundColor="white" />
            <button
              type="button"
              onClick={() => {
                setDraft(blueprintDraft(course))
                setNameInvalid(false)
              }}
              className="inline-flex h-9 min-w-11 items-center justify-center rounded-full px-3 font-dm text-sm font-bold tracking-[0.1px] text-white hover:bg-white/8 focus-visible:outline-2 focus-visible:outline-white"
            >
              Reset
            </button>
            {generate.tooltip ? (
              <Tooltip content={generate.tooltip}>{generateButton}</Tooltip>
            ) : (
              generateButton
            )}
            <PillButton icon="save" background="var(--color-accent-green)" type="submit">
              Save Changes
            </PillButton>
          </div>
        </div>
        <NameField value={draft.name} invalid={nameInvalid} onChange={(name) => patch({ name })} />
        <div className="mt-4 flex gap-6">
          <HeaderField label="Difficulty">
            {(id) => (
              <div className="relative">
                <select
                  id={id}
                  value={draft.difficulty}
                  onChange={(event) => patch({ difficulty: event.target.value as Difficulty })}
                  className="block h-6 w-full cursor-pointer appearance-none border-b border-white/38 bg-transparent pr-6 font-barlow text-sm leading-[23px] font-bold tracking-normal text-white outline-none focus:border-white [&>option]:bg-primary-blue"
                >
                  {DIFFICULTIES.map((difficulty) => (
                    <option key={difficulty} value={difficulty}>
                      {difficulty}
                    </option>
                  ))}
                </select>
                <Icon
                  name="arrow_drop_down"
                  size={24}
                  color="#616161"
                  className="pointer-events-none absolute top-0 right-0"
                />
              </div>
            )}
          </HeaderField>
          <HeaderField label="Language">
            {(id) => (
              <input
                id={id}
                value={draft.language}
                onChange={(event) => patch({ language: event.target.value })}
                className="block h-[21px] w-full border-b border-white/38 bg-transparent font-barlow text-sm leading-5 font-bold tracking-[0.5px] text-white caret-white outline-none selection:bg-white/30 focus:border-white"
              />
            )}
          </HeaderField>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        <SectionHeader icon="description">Course Description</SectionHeader>
        <BodyTextArea
          label="Course Description"
          rows={4}
          value={draft.description}
          placeholder="Enter course description..."
          onChange={(description) => patch({ description })}
        />
        <SectionHeader icon="track_changes" className="mt-6">
          Course Objective
        </SectionHeader>
        <BodyTextArea
          label="Course Objective"
          rows={4}
          value={draft.objective}
          placeholder="Enter course objective..."
          onChange={(objective) => patch({ objective })}
        />
        <SectionHeader icon="group" className="mt-6">
          Target Audience
        </SectionHeader>
        <BodyTextArea
          label="Target Audience"
          rows={2}
          value={draft.audience}
          placeholder="Enter target audience..."
          onChange={(audience) => patch({ audience })}
        />

        <SectionHeader icon="format_list_numbered" className="mt-6">
          Modules Curriculum Outline
        </SectionHeader>
        <ModuleList course={course} modules={draft.modules} setModules={setModules} />
        <button
          type="button"
          onClick={() => setModules((modules) => [...modules, newModuleDraft()])}
          className="inline-flex h-9 items-center gap-2 rounded-[6px] border border-primary-blue px-[14px] font-dm text-sm font-bold text-primary-blue hover:bg-primary-blue/8 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light"
        >
          <Icon name="add" size={16} />
          Add Module
        </button>

        <SectionHeader icon="image_search_rounded" className="mt-8">
          Extracted PDF Images &amp; Captions Verification
        </SectionHeader>
        <div className="mt-3">
          {course.images.length === 0 ? (
            <div className="flex items-center gap-2 rounded-lg border border-light-gray bg-light-gray/50 p-4">
              <Icon name="info_outline" size={24} className="text-gray" />
              <span className="font-barlow text-gray">No images were extracted from this PDF.</span>
            </div>
          ) : (
            <ul className="m-0 grid list-none grid-cols-2 gap-4 p-0">
              {course.images.map((image) => (
                <ImageCard
                  key={image.imageId}
                  image={image}
                  moduleNumber={moduleNumberForImage(draft.modules, image.imageId)}
                />
              ))}
            </ul>
          )}
        </div>
      </div>
    </form>
  )
}

interface PillButtonProps {
  icon: IconName
  background: string
  disabled?: boolean
  type?: 'button' | 'submit'
  onClick?: () => void
  children: ReactNode
}

/** Header ElevatedButton.icon: pill, 36 px high, 14 px icon. */
function PillButton({
  icon,
  background,
  disabled,
  type = 'button',
  onClick,
  children,
}: PillButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className="inline-flex h-9 items-center gap-2 rounded-full bg-(--pill-bg) px-4 font-dm text-sm font-bold whitespace-nowrap tracking-[0.1px] text-white hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white disabled:cursor-not-allowed disabled:bg-[#1a1b20]/12 disabled:text-[#1a1b20]/38 disabled:hover:brightness-100"
      style={{ '--pill-bg': background } as CSSProperties}
    >
      <Icon name={icon} size={14} />
      {children}
    </button>
  )
}

function NameField({
  value,
  invalid,
  onChange,
}: {
  value: string
  invalid: boolean
  onChange: (value: string) => void
}) {
  const id = useId()
  return (
    <div className="mt-4">
      <label htmlFor={id} className="block text-xs leading-[18px] font-bold text-white/70">
        Course Name
      </label>
      <input
        id={id}
        value={value}
        required
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? `${id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
        className={clsx(
          'mt-1 block h-[41px] w-full border-b bg-transparent font-inter text-[22px] leading-[26px] font-bold tracking-[0.5px] text-white caret-white outline-none selection:bg-white/30',
          invalid ? 'border-accent-red' : 'border-white/38 focus:border-white',
        )}
      />
      {invalid && (
        <p id={`${id}-error`} className="m-0 mt-2 text-xs leading-4 text-accent-red">
          Required
        </p>
      )}
    </div>
  )
}

function HeaderField({ label, children }: { label: string; children: (id: string) => ReactNode }) {
  const id = useId()
  return (
    <div className="min-w-0 flex-1">
      <label htmlFor={id} className="mb-1 block text-xs leading-[18px] text-white/70">
        {label}
      </label>
      {children(id)}
    </div>
  )
}

function SectionHeader({
  icon,
  className,
  children,
}: {
  icon: IconName
  className?: string
  children: ReactNode
}) {
  return (
    <h3 className={clsx('m-0 flex items-center gap-2', className)}>
      <Icon name={icon} size={18} className="text-primary-blue" />
      <span className="font-inter text-sm leading-[21px] font-bold tracking-normal text-primary-blue">
        {children}
      </span>
    </h3>
  )
}

function BodyTextArea({
  label,
  rows,
  value,
  placeholder,
  onChange,
}: {
  label: string
  rows: number
  value: string
  placeholder: string
  onChange: (value: string) => void
}) {
  return (
    <textarea
      aria-label={label}
      rows={rows}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
      className="mt-1.5 block w-full resize-none rounded-lg border border-input-border bg-white px-4 py-2 font-barlow text-[15px] leading-[22.5px] tracking-[0.5px] text-text-black placeholder:text-gray focus:border-brand-blue-light focus:ring-[0.4px] focus:ring-brand-blue-light focus:outline-none"
    />
  )
}

interface ModuleListProps {
  course: Course
  modules: ModuleDraft[]
  setModules: (change: (modules: ModuleDraft[]) => ModuleDraft[]) => void
}

/** ReorderableListView: the drag handle at the right edge moves a module. Arrow keys also work. */
function ModuleList({ course, modules, setModules }: ModuleListProps) {
  const [dragging, setDragging] = useState<number | null>(null)
  const items = useRef<(HTMLLIElement | null)[]>([])

  const move = (from: number, to: number) => {
    if (to < 0 || to >= modules.length || from === to) return
    setModules((current) => moveItem(current, from, to))
  }

  const dropIndex = (event: DragEvent<HTMLLIElement>, index: number) => {
    const box = event.currentTarget.getBoundingClientRect()
    return event.clientY > box.top + box.height / 2 ? index + 1 : index
  }

  return (
    <ul className="m-0 mt-2 list-none p-0" aria-label="Modules">
      {modules.map((module, index) => (
        <li
          key={module.key}
          ref={(node) => {
            items.current[index] = node
          }}
          className={clsx('relative pb-4', dragging === index && 'opacity-50')}
          onDragOver={(event) => {
            if (dragging === null) return
            event.preventDefault()
            event.dataTransfer.dropEffect = 'move'
          }}
          onDrop={(event) => {
            if (dragging === null) return
            event.preventDefault()
            const target = dropIndex(event, index)
            move(dragging, target > dragging ? target - 1 : target)
            setDragging(null)
          }}
        >
          <ModuleCard
            course={course}
            module={module}
            index={index}
            onChange={(fields) =>
              setModules((current) =>
                current.map((item) => (item.key === module.key ? { ...item, ...fields } : item)),
              )
            }
            onDelete={() =>
              setModules((current) => current.filter((item) => item.key !== module.key))
            }
          />
          <button
            type="button"
            draggable
            aria-label={`Reorder module ${index + 1}`}
            title="Drag or use the arrow keys to reorder"
            onDragStart={(event) => {
              setDragging(index)
              event.dataTransfer.effectAllowed = 'move'
              event.dataTransfer.setData('text/plain', module.key)
              const item = items.current[index]
              if (item) event.dataTransfer.setDragImage(item, event.nativeEvent.offsetX + 920, 20)
            }}
            onDragEnd={() => setDragging(null)}
            onKeyDown={(event: KeyboardEvent<HTMLButtonElement>) => {
              if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
                event.preventDefault()
                move(index, index + (event.key === 'ArrowUp' ? -1 : 1))
              }
            }}
            className="absolute top-1/2 right-2 flex -translate-y-1/2 cursor-grab text-black/87 focus-visible:outline-2 focus-visible:outline-brand-blue-light"
          >
            <Icon name="drag_handle" size={24} />
          </button>
        </li>
      ))}
    </ul>
  )
}

interface ModuleCardProps {
  course: Course
  module: ModuleDraft
  index: number
  onChange: (fields: Partial<ModuleDraft>) => void
  onDelete: () => void
}

function ModuleCard({ course, module, index, onChange, onDelete }: ModuleCardProps) {
  const download = useDownloadVideo()
  const quizId = useId()
  const original = module.original
  const number = index + 1
  return (
    <div className="rounded-lg border border-light-gray p-3">
      <div className="flex items-center">
        <Icon name="drag_indicator" size={20} className="text-gray" />
        <span className="ml-2 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-blue font-barlow text-xs font-bold text-white">
          {number}
        </span>
        <input
          aria-label={`Module ${number} title`}
          value={module.title}
          placeholder="Module title..."
          onChange={(event) => onChange({ title: event.target.value })}
          className="ml-2.5 h-[31px] min-w-0 flex-1 rounded-lg border border-input-border bg-white px-3.5 font-barlow text-[15px] leading-[22.5px] font-semibold text-text-black placeholder:font-normal placeholder:text-gray focus:border-brand-blue-light focus:ring-[0.4px] focus:ring-brand-blue-light focus:outline-none"
        />
        <Tooltip content="Delete module">
          <button
            type="button"
            aria-label="Delete module"
            onClick={onDelete}
            className="flex size-10 shrink-0 items-center justify-center rounded-full text-accent-red hover:bg-black/4 focus-visible:outline-2 focus-visible:outline-brand-blue-light"
          >
            <Icon name="delete" size={20} />
          </button>
        </Tooltip>
      </div>
      {original?.videoPath && (
        <div className="mt-2.5 flex justify-end">
          <button
            type="button"
            onClick={() =>
              void download(
                videoAssetUrl(original.videoPath ?? ''),
                videoDownloadFilename(course.courseId, original.moduleNumber, original.title),
              )
            }
            className="inline-flex h-9 items-center gap-2 rounded-[6px] bg-primary-blue px-[14px] font-dm text-sm font-bold tracking-[0.1px] text-white hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light"
          >
            <Icon name="download_rounded" size={16} />
            Download Video
          </button>
        </div>
      )}
      <div className="mt-2.5 flex items-center">
        <Icon name="quiz_outlined" size={16} className="text-primary-blue" />
        <label
          htmlFor={quizId}
          className="ml-1.5 font-barlow text-[13px] leading-[19.5px] font-medium text-primary-blue"
        >
          Quiz questions:
        </label>
        <input
          id={quizId}
          inputMode="numeric"
          value={module.numQuestions}
          onChange={(event) => onChange({ numQuestions: event.target.value })}
          className="ml-2 h-6 w-[70px] rounded-lg border border-input-border bg-white px-3 font-barlow text-[13px] leading-[19.5px] font-bold text-text-black focus:border-brand-blue-light focus:ring-[0.4px] focus:ring-brand-blue-light focus:outline-none"
        />
        <span className="ml-2 font-barlow text-xs leading-[18px] text-gray">
          questions (0 to disable)
        </span>
      </div>
      <textarea
        aria-label={`Module ${number} content`}
        value={module.sourceText}
        placeholder="Module content will appear here after generation..."
        onChange={(event) => onChange({ sourceText: event.target.value })}
        // Three to six lines, then it scrolls (minLines 3, maxLines 6).
        className="mt-2.5 block max-h-[131px] min-h-[72px] w-full resize-none rounded-lg border border-input-border bg-light-gray/50 px-3.5 py-1.5 font-barlow text-[13px] leading-[19.5px] text-text-black field-sizing-content placeholder:text-gray focus:border-brand-blue-light focus:ring-[0.4px] focus:ring-brand-blue-light focus:outline-none"
      />
    </div>
  )
}

function ImageCard({ image, moduleNumber }: { image: CourseImage; moduleNumber: number | null }) {
  // The URL changes when the media ticket arrives, so a load that failed without it retries.
  useHasMediaTicket()
  const src = assetUrl(image.filePath)
  const [brokenSrc, setBrokenSrc] = useState<string | null>(null)
  const broken = brokenSrc === src
  const mapped = moduleNumber != null
  return (
    <li className="flex aspect-[1.3] flex-col overflow-hidden rounded-lg border border-light-gray bg-white shadow-[0_2px_4px_rgb(0_0_0/0.02)]">
      <div className="flex min-h-0 flex-1 items-center justify-center bg-light-gray/30">
        {broken ? (
          <Icon name="broken_image" size={24} className="text-gray" />
        ) : (
          <img
            src={src}
            alt={image.caption || 'Extracted image'}
            onError={() => setBrokenSrc(src)}
            className="max-h-full max-w-full object-contain"
          />
        )}
      </div>
      <div className="flex items-start gap-2 bg-white px-2.5 py-2">
        <p className="m-0 line-clamp-2 min-w-0 flex-1 font-barlow text-[12.5px] leading-[18.75px] font-semibold text-text-black">
          {image.caption || 'No Caption Found'}
        </p>
        <span
          className={clsx(
            'shrink-0 rounded-full border px-2 py-[3px] font-barlow text-[11px] leading-[16.5px] font-bold',
            mapped
              ? 'border-primary-blue/25 bg-primary-blue/8 text-primary-blue'
              : 'border-light-gray bg-light-gray text-gray',
          )}
        >
          {mapped ? `Module ${moduleNumber}` : 'Unmapped'}
        </span>
      </div>
    </li>
  )
}
