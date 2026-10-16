import { errorMessage, hlsVideoAssetUrl, videoAssetUrl } from '@lms/shared/api/client'
import { useHasMediaTicket } from '@lms/shared/api/useMediaTicket'
import type {
  EmployeeCourse,
  PublishedCourseModule,
  QuizSubmissionResult,
} from '@lms/shared/models'
import { Button } from '@lms/shared/ui/Button'
import { Icon } from '@lms/shared/ui/icons/Icon'
import { ProgressBar } from '@lms/shared/ui/ProgressBar'
import { useToast } from '@lms/shared/ui/Toast'
import { Tooltip } from '@lms/shared/ui/Tooltip'
import { HlsVideoPlayer } from '@lms/shared/video/HlsVideoPlayer'
import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { useModuleProgress } from '../dashboard/useEmployeeCourses'
import { useViewportWidth } from '../dashboard/useViewportWidth'
import {
  resumeModuleIndex,
  isQuizUnlocked,
  isVideoUnlocked,
  isVideoWatched,
  moduleStatus,
  passedModuleCount,
  type LocalProgress,
} from './moduleRules'
import { emptyQuizState, QuizSection, type QuizState } from './Quiz'

const DEFAULT_NOTES =
  'Complete the video lesson, then use the quiz to confirm your understanding of this module.'

function without(set: ReadonlySet<number>, value: number): ReadonlySet<number> {
  if (!set.has(value)) return set
  const next = new Set(set)
  next.delete(value)
  return next
}

/** Saved answers of a passed quiz, loaded when a module opens. */
function quizStateFor(course: EmployeeCourse, index: number): QuizState {
  const module = course.publishedModules[index]
  if (!module) return emptyQuizState()
  const progress = course.moduleProgress[String(module.moduleNumber)]
  const saved = progress?.selectedAnswers
  if (!saved || progress.quizPassed !== true) return emptyQuizState()
  return { ...emptyQuizState(), selectedAnswers: { ...saved }, submitted: true }
}

/**
 * Flutter `CoursePlaybackView`. The parent remounts it with `key={courseId}`, so a course change
 * resumes at the first incomplete module. Background updates preserve the current module.
 */
export function CoursePlayback({
  course,
  initialCourse = course,
  onBack,
}: {
  course: EmployeeCourse
  initialCourse?: EmployeeCourse
  onBack: () => void
}) {
  const [activeIndex, setActiveIndex] = useState(() => resumeModuleIndex(initialCourse))
  const [watched, setWatched] = useState<ReadonlySet<number>>(() => new Set())
  const [unsaved, setUnsaved] = useState<ReadonlySet<number>>(() => new Set())
  const [passed, setPassed] = useState<ReadonlySet<number>>(() => new Set())
  const [localScores, setLocalScores] = useState<Record<number, number>>({})
  const [quiz, setQuiz] = useState<QuizState>(() =>
    quizStateFor(initialCourse, resumeModuleIndex(initialCourse)),
  )
  const [result, setResult] = useState<QuizSubmissionResult | null>(null)
  const isMobile = useViewportWidth() < 900
  const quizRef = useRef<HTMLDivElement>(null)
  const scrollToQuiz = useRef(false)
  // True while a quiz is graded. The module stays fixed, so the grade applies to the quiz shown.
  const grading = useRef(false)
  // The last video-completion save of each module. It resolves to true when the save succeeded.
  const videoSaves = useRef(new Map<number, Promise<boolean>>())
  const showToast = useToast()
  const { markVideoWatched, submitQuiz } = useModuleProgress()
  const local: LocalProgress = { watched, passed, unsaved }

  // Flutter scrolls the quiz to 12% from the top after the frame that unlocks it.
  useEffect(() => {
    if (!scrollToQuiz.current) return
    scrollToQuiz.current = false
    const target = quizRef.current
    const scroller = target?.closest<HTMLElement>('[data-scroll-pane]')
    if (!target || !scroller) return
    const offset =
      target.getBoundingClientRect().top -
      scroller.getBoundingClientRect().top -
      scroller.clientHeight * 0.12
    scroller.scrollBy({ top: offset, behavior: 'smooth' })
  })

  const modules = course.publishedModules
  const module = modules[activeIndex]
  if (!module) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center p-8">
          <Icon name="school_outlined" size={64} color="var(--color-gray)" />
          <p className="m-0 mt-4 font-inter text-[18px] font-bold text-primary-blue">
            No Modules Available
          </p>
        </div>
      </div>
    )
  }

  const changeModule = (index: number) => {
    if (grading.current) return
    setActiveIndex(index)
    setQuiz(quizStateFor(course, index))
    setResult(null)
  }

  const handleVideoEnded = (target: PublishedCourseModule) => {
    if (watched.has(target.moduleNumber)) return
    setWatched((current) => new Set(current).add(target.moduleNumber))
    scrollToQuiz.current = true
    showToast('Video completed. Quiz unlocked.', {
      tone: 'learning',
      icon: 'assignment_turned_in_rounded',
      duration: 3000,
    })
    void saveVideo(target.moduleNumber)
  }

  // Flutter swallows a failed save. The learner must know the completion was not saved.
  const saveVideo = (moduleNumber: number) => {
    const save = markVideoWatched(course.courseId, moduleNumber).then(
      () => {
        setUnsaved((current) => without(current, moduleNumber))
        return true
      },
      (error: unknown) => {
        setUnsaved((current) => new Set(current).add(moduleNumber))
        showToast(`Could not save video progress. ${errorMessage(error)}`, { tone: 'error' })
        return false
      },
    )
    videoSaves.current.set(moduleNumber, save)
    return save
  }

  const handleSubmit = async () => {
    if (grading.current) return
    const target = module
    const answers = { ...quiz.selectedAnswers }
    grading.current = true
    setQuiz((current) => ({ ...current, submitted: true }))
    let outcome
    try {
      // The backend grades only after it has the video completion. The cache shows a pending save
      // as done, so the submit waits for that save. A failed save is sent again here.
      const videoSaved = await (videoSaves.current.get(target.moduleNumber) ??
        course.moduleProgress[String(target.moduleNumber)]?.videoWatched === true)
      if (!videoSaved) {
        await markVideoWatched(course.courseId, target.moduleNumber)
        videoSaves.current.set(target.moduleNumber, Promise.resolve(true))
        setUnsaved((current) => without(current, target.moduleNumber))
      }
      outcome = await submitQuiz(course.courseId, target.moduleNumber, answers)
    } catch (error) {
      setQuiz((current) => ({ ...current, submitted: false }))
      showToast(errorMessage(error).replace(/^Exception: /, ''), { tone: 'error' })
      return
    } finally {
      grading.current = false
    }
    setQuiz((current) => ({
      ...current,
      answerResults: { ...outcome.answerResults },
    }))
    if (outcome.passed) {
      setPassed((current) => new Set(current).add(target.moduleNumber))
      setWatched((current) => new Set(current).add(target.moduleNumber))
      setLocalScores((current) => ({ ...current, [target.moduleNumber]: outcome.score }))
    } else {
      // The backend clears the video completion of a failed quiz.
      videoSaves.current.delete(target.moduleNumber)
      setWatched((current) => without(current, target.moduleNumber))
    }
    setResult(outcome)
    scrollToQuiz.current = true
  }

  const closeResult = () => {
    if (result && !result.passed) {
      setQuiz(emptyQuizState())
      setResult(null)
      quizRef.current
        ?.closest<HTMLElement>('[data-scroll-pane]')
        ?.scrollTo({ top: 0, behavior: 'smooth' })
    } else if (activeIndex === modules.length - 1) {
      onBack()
    } else {
      changeModule(activeIndex + 1)
    }
  }

  const progress = course.moduleProgress[String(module.moduleNumber)]
  const alreadyPassed = progress?.quizPassed === true || passed.has(module.moduleNumber)
  const score = localScores[module.moduleNumber] ?? progress?.quizScore ?? null

  const content = (
    <>
      <ModuleHeader module={module} />
      <div className={isMobile ? 'h-4' : 'h-5'} />
      <VideoSection
        course={course}
        module={module}
        watched={isVideoWatched(course, module, local)}
        onEnded={handleVideoEnded}
      />
      {unsaved.has(module.moduleNumber) && (
        <UnsavedVideoNotice onRetry={() => void saveVideo(module.moduleNumber)} />
      )}
      <div className={isMobile ? 'h-4' : 'h-5'} />
      <NotesSection course={course} module={module} />
      <div className={isMobile ? 'h-6' : 'h-8'} />
      <hr className="m-0 h-px border-0 bg-light-gray" />
      <div className={isMobile ? 'h-5' : 'h-7'} />
      <div ref={quizRef}>
        <QuizSection
          module={module}
          unlocked={isQuizUnlocked(course, activeIndex, local)}
          alreadyPassed={alreadyPassed}
          score={score}
          state={quiz}
          onSelect={(questionIndex, answer) =>
            setQuiz((current) => ({
              ...current,
              selectedAnswers: { ...current.selectedAnswers, [questionIndex]: answer },
            }))
          }
          onSubmit={() => void handleSubmit()}
          review={result}
          reviewAction={
            result && !result.passed
              ? 'Rewatch lesson'
              : activeIndex === modules.length - 1
                ? 'Finish course'
                : 'Continue to next module'
          }
          onReviewAction={closeResult}
        />
      </div>
    </>
  )

  return (
    <>
      {isMobile ? (
        <div data-scroll-pane className="h-full overflow-y-auto p-4 [scrollbar-width:none]">
          <WorkspaceHeader course={course} onBack={onBack} />
          <div className="h-5" />
          <ModuleSelect
            course={course}
            activeIndex={activeIndex}
            local={local}
            onChange={changeModule}
          />
          <div className="h-5" />
          {content}
        </div>
      ) : (
        <div className="flex h-full flex-col">
          <WorkspaceHeader course={course} onBack={onBack} />
          <div className="flex min-h-0 flex-1">
            <div
              data-scroll-pane
              className="min-w-0 flex-1 overflow-y-auto px-7 pt-7 pb-11 [scrollbar-width:none]"
            >
              {content}
            </div>
            <aside className="flex w-[330px] shrink-0 flex-col border-l border-[#e6e9ef] bg-white pt-6 pr-3.5 pb-5 pl-[18px]">
              <h2 className="m-0 text-[16px] font-bold">Course content</h2>
              <p className="m-0 mt-1 text-[13px] text-[#667085]">{modules.length} modules</p>
              <div className="h-[18px]" />
              <ModuleList
                course={course}
                activeIndex={activeIndex}
                local={local}
                onChange={changeModule}
              />
            </aside>
          </div>
        </div>
      )}
    </>
  )
}

function WorkspaceHeader({ course, onBack }: { course: EmployeeCourse; onBack: () => void }) {
  const total = course.publishedModules.length
  const passed = passedModuleCount(course)
  const progress = total === 0 ? 0 : passed / total
  return (
    <div className="flex shrink-0 items-center border-b border-[#e6e9ef] bg-white px-7 py-4">
      <Tooltip content="Back to dashboard">
        <button
          type="button"
          aria-label="Back to dashboard"
          onClick={onBack}
          className="inline-flex size-10 shrink-0 items-center justify-center rounded-full text-[#44474e] hover:bg-[#44474e]/8 focus-visible:outline-2 focus-visible:outline-brand-blue-light"
        >
          <Icon name="arrow_back" />
        </button>
      </Tooltip>
      <div className="ml-2.5 min-w-0 flex-1">
        <h1 className="m-0 truncate text-[18px] font-bold">{course.courseName}</h1>
        <p className="m-0 mt-[3px] text-[13px] text-[#667085]">
          {passed} of {total} modules completed
        </p>
      </div>
      <div className="flex w-40 shrink-0 flex-col items-end">
        <span className="font-bold text-primary-blue">{Math.round(progress * 100)}%</span>
        <ProgressBar
          value={progress}
          height={6}
          radius={4}
          trackColor="#e6e9ef"
          className="mt-[7px]"
          label="Course progress"
        />
      </div>
    </div>
  )
}

function ModuleHeader({ module }: { module: PublishedCourseModule }) {
  return (
    <div>
      <span className="inline-block rounded bg-primary-blue/8 px-2.5 py-1 font-barlow text-[11px] font-bold tracking-[1px] text-primary-blue">
        MODULE {module.moduleNumber}
      </span>
      <h2 className="m-0 mt-2.5 font-inter text-[22px] font-bold text-text-black">
        {module.title}
      </h2>
    </div>
  )
}

function VideoSection({
  course,
  module,
  watched,
  onEnded,
}: {
  course: EmployeeCourse
  module: PublishedCourseModule
  watched: boolean
  onEnded: (module: PublishedCourseModule) => void
}) {
  const hasTicket = useHasMediaTicket()
  if (!module.videoPath) {
    return (
      <div className="flex h-[400px] items-center justify-center rounded-2xl border border-light-gray bg-[#fafafa]">
        Video unavailable.
      </div>
    )
  }
  return (
    <div className="overflow-hidden rounded-2xl bg-black shadow-[0_4px_16px_rgb(0_0_0/0.12)]">
      <div className="aspect-video">
        <HlsVideoPlayer
          key={`${course.courseId}_${module.moduleNumber}_${watched}_${hasTicket}`}
          hlsUrl={hlsVideoAssetUrl(module.videoPath)}
          fallbackUrl={videoAssetUrl(module.videoPath)}
          enforceLinearPlayback
          initiallyCompleted={watched}
          onEnded={watched ? undefined : () => onEnded(module)}
        />
      </div>
    </div>
  )
}

/** A failed completion save. Without a quiz, this retry is the only way to save the completion. */
function UnsavedVideoNotice({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="mt-3 flex items-center gap-3 rounded-[10px] border border-accent-red/30 bg-accent-red/6 py-2 pr-2 pl-4"
    >
      <Icon name="error_outline" size={20} color="var(--color-accent-red)" />
      <p className="m-0 flex-1 text-[14px] text-text-black">Video progress was not saved.</p>
      <Button variant="text" onClick={onRetry}>
        Retry
      </Button>
    </div>
  )
}

function NotesSection({
  course,
  module,
}: {
  course: EmployeeCourse
  module: PublishedCourseModule
}) {
  const notes = module.notes.trim() || course.courseDescription.trim() || DEFAULT_NOTES
  return (
    <div className="flex items-start gap-3.5 rounded-[10px] border border-[#e1e7ef] bg-white p-5">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent-blue/12 text-accent-blue">
        <Icon name="notes_outlined" />
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="m-0 text-[16px] font-bold">Notes</h3>
        <p className="m-0 mt-1.5 text-[14px] leading-[1.55] whitespace-pre-line text-[#475467]">
          {notes}
        </p>
      </div>
    </div>
  )
}

interface ModuleNavProps {
  course: EmployeeCourse
  activeIndex: number
  local: LocalProgress
  onChange: (index: number) => void
}

function ModuleList({ course, activeIndex, local, onChange }: ModuleNavProps) {
  return (
    <ol
      aria-label="Course modules"
      className="m-0 min-h-0 flex-1 list-none overflow-y-auto p-0 [scrollbar-width:none]"
    >
      {course.publishedModules.map((module, index) => {
        const selected = index === activeIndex
        const unlocked = isVideoUnlocked(course, index, local)
        const status = moduleStatus(course, module, unlocked, local)
        return (
          <li key={module.moduleNumber} className="mb-2">
            <button
              type="button"
              disabled={!unlocked}
              aria-current={selected ? 'step' : undefined}
              onClick={() => onChange(index)}
              className={clsx(
                'flex w-full items-center rounded-lg p-3 text-left transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-brand-blue-light disabled:cursor-default',
                selected
                  ? 'border-[1.5px] border-primary-blue bg-primary-blue/6'
                  : 'border border-light-gray bg-white enabled:hover:bg-[#f7f8fa]',
              )}
            >
              <Tooltip content={status.label}>
                <span
                  className="flex size-[34px] shrink-0 items-center justify-center rounded-full"
                  style={{ backgroundColor: status.background }}
                >
                  <Icon name={status.icon} size={20} color={status.color} />
                </span>
              </Tooltip>
              <span
                className="ml-3 flex min-w-0 flex-1 flex-col"
                style={{ opacity: unlocked ? 1 : 0.62 }}
              >
                <span
                  className={clsx(
                    'font-barlow text-[10px] font-bold',
                    selected ? 'text-primary-blue' : 'text-[#667085]',
                  )}
                >
                  MODULE {module.moduleNumber}
                </span>
                <span
                  className={clsx(
                    'mt-1 line-clamp-2 font-inter text-[13px]',
                    selected ? 'font-bold text-primary-blue' : 'font-semibold text-text-black',
                  )}
                >
                  {module.title}
                </span>
                <span
                  className="mt-[5px] text-[11px] font-semibold"
                  style={{ color: status.color }}
                >
                  {status.label}
                </span>
              </span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}

/** Flutter mobile dropdown. Locked modules are disabled. */
function ModuleSelect({ course, activeIndex, local, onChange }: ModuleNavProps) {
  return (
    <div className="relative rounded-lg border border-light-gray bg-[#fafafa] p-4">
      <select
        aria-label="Module"
        value={activeIndex}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full appearance-none bg-transparent pr-8 font-barlow text-[14px] font-semibold text-primary-blue outline-none"
      >
        {course.publishedModules.map((module, index) => (
          <option
            key={module.moduleNumber}
            value={index}
            disabled={!isVideoUnlocked(course, index, local)}
          >
            Module {module.moduleNumber}: {module.title}
          </option>
        ))}
      </select>
      <Icon
        name="keyboard_arrow_down"
        color="var(--color-primary-blue)"
        className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2"
      />
    </div>
  )
}
