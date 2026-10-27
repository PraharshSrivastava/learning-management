import { hlsVideoAssetUrl, videoAssetUrl } from '@lms/shared/api/client'
import { useHasMediaTicket } from '@lms/shared/api/useMediaTicket'
import {
  hasVideoServiceFailed,
  isVideoServiceActive,
  type Course,
  type CourseModule,
  type VideoGenerationMode,
} from '@lms/shared/models'
import { Dialog } from '@lms/shared/ui/Dialog'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { ProgressBar } from '@lms/shared/ui/ProgressBar'
import { HlsVideoPlayer } from '@lms/shared/video/HlsVideoPlayer'
import clsx from 'clsx'
import { useState } from 'react'
import { useTrainerSearch, useUpdateTrainerSearch } from '../../shell/search'
import { ActionButton } from './ActionButton'
import { ring } from './flutterStyle'
import { QuizSection, type QuizAnswers } from './QuizSection'
import {
  hasVideo,
  quizQuestions,
  slideTitle,
  transcriptSlides,
  videoDownloadFilename,
} from './trainingData'
import { useDownloadVideo } from './useDownloadVideo'
import { useMediaQuery } from './useMediaQuery'
import { useModuleGeneration } from './useModuleGeneration'
import { useVideoGenerationMode } from './videoMode'

const EMPTY_NOTES = 'Learner notes appear here after course generation.'

interface TrainingViewProps {
  course: Course
  /** Course library view of another creator's course. Generation buttons are disabled. */
  readOnly?: boolean
}

/**
 * Trainer view of one course: learning path, module video, notes, transcript, and quiz.
 * The open module is `module` in the URL, so reload and the back button keep it. The read-only
 * library view shows another course inside the page, so it keeps the module in local state.
 */
export function TrainingView({ course, readOnly = false }: TrainingViewProps) {
  // The key resets the module and quiz answers when another course opens.
  return readOnly ? (
    <LocalModuleTraining key={course.courseId} course={course} />
  ) : (
    <UrlModuleTraining key={course.courseId} course={course} />
  )
}

function LocalModuleTraining({ course }: { course: Course }) {
  const [activeIndex, setActiveIndex] = useState(0)
  return (
    <TrainingBody course={course} readOnly activeIndex={activeIndex} onSelect={setActiveIndex} />
  )
}

function UrlModuleTraining({ course }: { course: Course }) {
  const position = useTrainerSearch().module ?? 1
  const updateSearch = useUpdateTrainerSearch()
  return (
    <TrainingBody
      course={course}
      readOnly={false}
      activeIndex={position - 1}
      // Each module change is a history entry, so Back returns to the previous module.
      onSelect={(index) => {
        if (index !== position - 1) updateSearch({ module: index > 0 ? index + 1 : undefined })
      }}
    />
  )
}

interface TrainingBodyProps {
  course: Course
  readOnly: boolean
  activeIndex: number
  onSelect: (index: number) => void
}

function TrainingBody({ course, readOnly, activeIndex, onSelect }: TrainingBodyProps) {
  const isMobile = useMediaQuery('(max-width: 899.98px)')
  const [answers, setAnswers] = useState<QuizAnswers>({ selected: {}, submitted: {} })
  const mode = useVideoGenerationMode()
  const generation = useModuleGeneration(course.courseId, {
    videoActive: course.modules.some((item) => isVideoServiceActive(item.videoService)),
  })

  const module = course.modules[Math.min(activeIndex, course.modules.length - 1)]
  if (!module) return <EmptyCourse />
  const moduleIndex = course.modules.indexOf(module)

  const generationDisabled = readOnly || generation.busy
  const videoDisabled = generationDisabled || generation.videoBusy
  const status = videoStatus(module, generation.videoModules.includes(module.moduleNumber))
  const compile = () => generation.compileVideo(module.moduleNumber)

  const content = (
    <>
      <HeaderSection
        course={course}
        module={module}
        status={status}
        regenerateDisabled={videoDisabled}
        onRegenerate={compile}
      />
      <div className={isMobile ? 'h-4' : 'h-5'} />
      <VideoSection
        module={module}
        mode={mode}
        status={status}
        disabled={videoDisabled}
        onCompile={compile}
      />
      <div className="h-4" />
      <NotesSection module={module} />
      {/* Service videos have burned-in subtitles and no slide scripts to show. */}
      {(mode === 'local' || transcriptSlides(module).length > 0) && (
        <>
          <div className="h-4" />
          <TranscriptSection module={module} />
        </>
      )}
      <div className={isMobile ? 'h-6' : 'h-8'} />
      <hr className="m-0 h-px border-0 bg-light-gray" />
      <div className={isMobile ? 'h-5' : 'h-7'} />
      <QuizPanel
        module={module}
        moduleIndex={moduleIndex}
        answers={answers}
        setAnswers={setAnswers}
        disabled={generationDisabled}
        onGenerate={generation.generateQuiz}
      />
    </>
  )

  if (isMobile) {
    return (
      <div className="h-full overflow-y-auto [scrollbar-width:none]">
        <div className="rounded-lg border border-light-gray bg-[#fafafa] p-4">
          <label className="relative flex items-center">
            <span className="sr-only">Module</span>
            <select
              value={moduleIndex}
              onChange={(event) => onSelect(Number(event.target.value))}
              className="w-full cursor-pointer appearance-none bg-transparent pr-6 font-barlow text-sm font-semibold text-primary-blue outline-none"
            >
              {course.modules.map((item, index) => (
                <option key={index} value={index}>
                  Module {item.moduleNumber}: {item.title}
                </option>
              ))}
            </select>
            <Icon
              name="keyboard_arrow_down"
              size={24}
              color="var(--color-primary-blue)"
              className="pointer-events-none absolute right-0"
            />
          </label>
        </div>
        <div className="h-5" />
        {content}
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0">
      <div className="min-w-0 flex-1 overflow-y-auto pr-6 pb-10 [scrollbar-width:none]">
        {content}
      </div>
      <aside className="flex w-[340px] shrink-0 flex-col border-l border-light-gray pl-5">
        <h2 className="m-0 mb-4 font-barlow text-xs leading-normal font-bold tracking-[1.5px] text-gray">
          COURSE CONTENT
        </h2>
        <ModuleList modules={course.modules} activeIndex={moduleIndex} onSelect={onSelect} />
      </aside>
    </div>
  )
}

function EmptyCourse() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="flex w-full max-w-[500px] flex-col items-center rounded-2xl border border-light-gray bg-white p-8">
        <Icon name="school_outlined" size={64} color="var(--color-gray)" />
        <div className="h-4" />
        <h3 className="m-0 font-inter text-lg font-bold text-primary-blue">No Modules Available</h3>
        <div className="h-2" />
        <p className="m-0 text-center font-barlow text-sm text-gray">
          Please generate the course outline and modules first to start training.
        </p>
      </div>
    </div>
  )
}

/** What the module's current or last video run shows to the trainer. */
interface VideoStatus {
  text: string
  failed: boolean
  /** 0 to 1, or null for an indeterminate bar. */
  progress: number | null
  running: boolean
}

function videoStatus(module: CourseModule, startedHere: boolean): VideoStatus | null {
  const service = module.videoService
  if (service && isVideoServiceActive(service)) {
    const percent = service.progress == null ? '' : ` (${Math.round(service.progress)}%)`
    return {
      text: `Video Generator: ${service.stage ?? service.status}${percent}`,
      failed: false,
      progress: service.progress == null ? null : service.progress / 100,
      running: true,
    }
  }
  if (startedHere) {
    return { text: 'Starting video generation…', failed: false, progress: null, running: true }
  }
  if (service && hasVideoServiceFailed(service)) {
    return {
      text: `Last video run failed: ${service.error ?? service.status}`,
      failed: true,
      progress: null,
      running: false,
    }
  }
  return null
}

function VideoStatusLine({ status }: { status: VideoStatus }) {
  return (
    <div className="flex w-full flex-col gap-2" role="status">
      <p
        className={clsx(
          'm-0 text-center font-barlow text-sm font-semibold',
          status.failed ? 'text-[#b42318]' : 'text-gray',
        )}
      >
        {status.text}
      </p>
      {status.running && (
        <ProgressBar
          value={status.progress}
          color="var(--color-accent-orange)"
          radius={2}
          label="Video generation progress"
        />
      )}
    </div>
  )
}

interface HeaderSectionProps {
  course: Course
  module: CourseModule
  status: VideoStatus | null
  regenerateDisabled: boolean
  onRegenerate: () => void
}

function HeaderSection({
  course,
  module,
  status,
  regenerateDisabled,
  onRegenerate,
}: HeaderSectionProps) {
  const download = useDownloadVideo()
  const [confirming, setConfirming] = useState(false)
  return (
    <header>
      <div className="flex items-center justify-between">
        <span className="rounded bg-primary-blue/8 px-2.5 py-1 font-barlow text-[11px] font-bold tracking-[1px] text-primary-blue">
          MODULE {module.moduleNumber}
        </span>
        {hasVideo(module) && (
          <div className="flex items-center gap-2">
            <ActionButton
              icon="refresh_rounded"
              iconSize={16}
              padding="10px 14px"
              outlined
              className="border border-primary-blue text-primary-blue disabled:border-light-gray disabled:text-gray"
              disabled={regenerateDisabled}
              onClick={() => setConfirming(true)}
            >
              {status?.running ? 'Regenerating…' : 'Regenerate Video'}
            </ActionButton>
            <ActionButton
              icon="download_rounded"
              iconSize={16}
              padding="10px 14px"
              onClick={() =>
                download(
                  videoAssetUrl(module.videoPath ?? ''),
                  videoDownloadFilename(course.courseId, module.moduleNumber, module.title),
                )
              }
            >
              Download Video
            </ActionButton>
          </div>
        )}
      </div>
      {hasVideo(module) && status && (
        <div className="mt-2.5">
          <VideoStatusLine status={status} />
        </div>
      )}
      <h2 className="mt-2.5 mb-0 font-inter text-[22px] font-bold text-text-black">
        {module.title}
      </h2>
      <Dialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Regenerate module video?"
        width={420}
        actions={
          <>
            <ActionButton
              iconSize={16}
              padding="0 16px"
              outlined
              className="text-primary-blue"
              onClick={() => setConfirming(false)}
            >
              Cancel
            </ActionButton>
            <ActionButton
              iconSize={16}
              padding="0 16px"
              onClick={() => {
                setConfirming(false)
                onRegenerate()
              }}
            >
              Regenerate
            </ActionButton>
          </>
        }
      >
        A new video for Module {module.moduleNumber} replaces the current one when it is ready. The
        current video stays available until then.
      </Dialog>
    </header>
  )
}

interface GenerateProps {
  disabled: boolean
}

interface VideoSectionProps extends GenerateProps {
  module: CourseModule
  mode: VideoGenerationMode
  status: VideoStatus | null
  onCompile: () => void
}

function VideoSection({ module, mode, status, disabled, onCompile }: VideoSectionProps) {
  const hasTicket = useHasMediaTicket()
  const videoPath = module.videoPath
  if (!videoPath) {
    const external = mode === 'external'
    const label = !external
      ? 'Compile Module Video'
      : status?.failed
        ? 'Retry Module Video'
        : 'Generate Module Video'
    return (
      <div className="flex h-[400px] flex-col items-center justify-center rounded-2xl border border-light-gray bg-[#fafafa] px-8">
        <Icon name="video_library_outlined" size={56} color="var(--color-gray)" />
        <div className="h-4" />
        <h3 className="m-0 font-inter text-base font-bold text-primary-blue">
          {status?.running
            ? 'Generating Module Video'
            : external
              ? 'No Video Yet'
              : 'No Video Compiled Yet'}
        </h3>
        <div className="h-2" />
        {status ? (
          <div className="w-full max-w-[420px]">
            <VideoStatusLine status={status} />
          </div>
        ) : (
          <p className="m-0 text-center font-barlow text-sm text-gray">
            {external
              ? 'The Video Generator creates this module video from the approved module content.'
              : 'Generate the slides and video compilation first to watch.'}
          </p>
        )}
        <div className="h-6" />
        <ActionButton
          icon="bolt"
          iconSize={16}
          padding="0 24px"
          background="var(--color-accent-orange)"
          disabled={disabled}
          onClick={onCompile}
        >
          {label}
        </ActionButton>
      </div>
    )
  }
  return (
    <div className="h-[450px] overflow-hidden rounded-2xl bg-black shadow-[0_4px_16px_rgb(0_0_0/0.12)]">
      <HlsVideoPlayer
        key={`${videoPath}:${hasTicket}`}
        hlsUrl={hlsVideoAssetUrl(videoPath)}
        fallbackUrl={videoAssetUrl(videoPath)}
      />
    </div>
  )
}

function NotesSection({ module }: { module: CourseModule }) {
  const notes = module.notes.trim() || EMPTY_NOTES
  return (
    <section className="flex items-start rounded-2xl border border-light-gray bg-[#f7fbff] p-[18px] pb-[19px]">
      <Icon name="notes_outlined" size={24} color="var(--color-accent-blue)" />
      <div className="ml-2.5 min-w-0 flex-1">
        <h3 className="m-0 font-inter text-sm font-bold text-primary-blue">Module notes</h3>
        <p className="relative top-0.5 mt-1.5 mb-0 font-barlow text-sm leading-[1.45] whitespace-pre-line text-gray">
          {notes}
        </p>
      </div>
    </section>
  )
}

function TranscriptSection({ module }: { module: CourseModule }) {
  const slides = transcriptSlides(module)
  return (
    // Flutter's Column fills the 360 px max height, so the empty card keeps that height.
    <section
      className={clsx(
        'flex flex-col rounded-2xl border border-light-gray bg-white',
        slides.length === 0 ? 'h-[360px]' : 'max-h-[360px]',
      )}
    >
      <div className="flex items-center px-[18px] pt-3.5 pb-3">
        <Icon name="notes_rounded" size={18} color="var(--color-primary-blue)" />
        {/* The 21 px line box makes the header 47 px high, as Flutter renders it. */}
        <h3 className="relative top-px m-0 ml-2 font-inter text-sm leading-[21px] font-bold text-primary-blue">
          Slide Script / Transcript
        </h3>
      </div>
      <hr className="m-0 h-px border-0 bg-light-gray" />
      {slides.length === 0 ? (
        <p className="m-0 p-5 font-barlow text-sm text-gray">
          No slide narration script is available for this module yet.
        </p>
      ) : (
        <ol className="m-0 flex min-h-0 list-none flex-col gap-2.5 overflow-y-auto p-4 [scrollbar-width:none]">
          {slides.map((slide, index) => (
            <li
              key={index}
              className="shrink-0 rounded-lg border border-light-gray bg-light-gray/25 p-3.5"
            >
              <div className="flex items-center">
                <span
                  className={clsx(
                    'flex size-7 shrink-0 items-center justify-center rounded-full font-barlow text-xs font-bold',
                    slide.isCover
                      ? 'bg-accent-orange/15 text-accent-orange'
                      : 'bg-primary-blue/8 text-primary-blue',
                  )}
                >
                  {index + 1}
                </span>
                <span className="ml-2.5 min-w-0 flex-1 truncate font-inter text-[13px] font-bold text-text-black">
                  {slideTitle(slide, index)}
                </span>
              </div>
              {/* Flutter rounds the text box up to whole pixels, so one line is 20 px high. */}
              <p className="mt-2.5 mb-0 min-h-5 font-barlow text-[13.5px] leading-[1.45] whitespace-pre-line text-text-black">
                {slide.script}
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

interface QuizPanelProps extends GenerateProps {
  module: CourseModule
  moduleIndex: number
  answers: QuizAnswers
  setAnswers: (update: (previous: QuizAnswers) => QuizAnswers) => void
  onGenerate: () => void
}

function QuizPanel({
  module,
  moduleIndex,
  answers,
  setAnswers,
  disabled,
  onGenerate,
}: QuizPanelProps) {
  const questions = quizQuestions(module)
  if (questions.length === 0) {
    return (
      <div className="flex flex-col items-center rounded-xl border border-light-gray bg-[#fafafa] p-8">
        <Icon name="quiz_outlined" size={48} color="var(--color-gray)" />
        <div className="h-3" />
        <h3 className="m-0 font-inter text-[15px] font-bold text-primary-blue">
          No Quiz Available for this Module
        </h3>
        <div className="h-1.5" />
        <p className="m-0 text-center font-barlow text-[13px] text-gray">
          Define the questions count and generate the module quiz to test your learning outcomes.
        </p>
        <div className="h-5" />
        <ActionButton
          icon="auto_awesome"
          iconSize={16}
          padding="0 24px"
          disabled={disabled}
          onClick={onGenerate}
        >
          Generate Quiz Now
        </ActionButton>
      </div>
    )
  }
  return (
    <QuizSection
      moduleIndex={moduleIndex}
      questions={questions}
      answers={answers}
      onSelect={(key, option) =>
        setAnswers((previous) => ({
          ...previous,
          selected: { ...previous.selected, [key]: option },
        }))
      }
      onSubmit={(key) =>
        setAnswers((previous) => ({
          ...previous,
          submitted: { ...previous.submitted, [key]: true },
        }))
      }
      onReset={(keys) =>
        setAnswers((previous) => {
          const selected = { ...previous.selected }
          const submitted = { ...previous.submitted }
          for (const key of keys) {
            delete selected[key]
            delete submitted[key]
          }
          return { selected, submitted }
        })
      }
    />
  )
}

function ModuleList({
  modules,
  activeIndex,
  onSelect,
}: {
  modules: CourseModule[]
  activeIndex: number
  onSelect: (index: number) => void
}) {
  return (
    <ul className="m-0 min-h-0 flex-1 list-none overflow-y-auto p-0 [scrollbar-width:none]">
      {modules.map((item, index) => {
        const selected = index === activeIndex
        const quiz = quizQuestions(item).length > 0
        return (
          <li key={index} className="mb-2">
            <button
              type="button"
              aria-current={selected ? 'true' : undefined}
              onClick={() => onSelect(index)}
              className={clsx(
                'block w-full rounded-lg text-left transition-[background-color,box-shadow,padding] duration-200',
                'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-blue-light',
                selected ? 'bg-primary-blue/6 p-[13.5px]' : 'bg-white p-[13px]',
              )}
              style={{
                boxShadow: selected
                  ? ring(1.5, 'var(--color-primary-blue)')
                  : ring(1, 'var(--color-light-gray)'),
              }}
            >
              <span className="flex items-center">
                <span
                  className={clsx(
                    'relative top-px font-barlow text-[10px] font-bold',
                    selected ? 'text-primary-blue' : 'text-gray',
                  )}
                >
                  MODULE {item.moduleNumber}
                </span>
                <span className="flex-1" />
                {hasVideo(item) ? (
                  <Icon name="play_circle_fill" size={14} color="var(--color-accent-green)" />
                ) : (
                  <Icon name="video_call" size={14} color="var(--color-gray)" />
                )}
                <span className="w-1.5" />
                {quiz ? (
                  <Icon name="assignment_turned_in" size={14} color="var(--color-accent-green)" />
                ) : (
                  <Icon name="assignment_outlined" size={14} color="var(--color-gray)" />
                )}
              </span>
              <span
                className={clsx(
                  'mt-1.5 line-clamp-2 block font-inter text-[13px]',
                  selected ? 'font-bold text-primary-blue' : 'font-semibold text-text-black',
                )}
              >
                {item.title}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
