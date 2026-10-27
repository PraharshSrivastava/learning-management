import type { IconName } from './icons/Icon'
import { Icon } from './icons/Icon'
import { Spinner } from './Spinner'

interface OverlayContent {
  icon: IconName
  title: string
  message: string
  expectation: string
}

/** Maps a progress message to overlay copy. Order matters: the first keyword match wins. */
export function overlayContent(rawMessage: string): OverlayContent {
  const lower = rawMessage.toLowerCase()
  if (lower.includes('publishing assignment')) {
    return {
      icon: 'publish_outlined',
      title: 'Publishing assignment',
      message: 'We are assigning this course to the selected employee groups.',
      expectation: 'Publishing may take up to 2 minutes.',
    }
  }
  if (lower.includes('module videos')) {
    return {
      icon: 'school_outlined',
      title: 'Generating course content',
      message:
        'We are preparing quizzes and notes while the Video Generator produces each module video.',
      expectation:
        'Each module video takes several minutes; a large course may take up to 60 minutes.',
    }
  }
  if (lower.includes('course content') || lower.includes('entire course')) {
    return {
      icon: 'school_outlined',
      title: 'Generating course content',
      message: 'We are preparing quizzes, slides, narration, and videos for this course.',
      expectation: 'This may take a while, up to 60 minutes.',
    }
  }
  if (
    lower.includes('course outline') ||
    lower.includes('modular extraction') ||
    lower.includes('qwen')
  ) {
    return {
      icon: 'auto_stories_outlined',
      title: 'Creating your course outline',
      message: 'We are reading the document and shaping it into a course blueprint.',
      expectation: 'This may take up to 5 minutes.',
    }
  }
  if (lower.includes('quiz')) {
    return {
      icon: 'quiz_outlined',
      title: 'Generating quizzes',
      message: 'We are creating assessment questions for the selected module.',
      expectation: 'This may take up to 5 minutes.',
    }
  }
  if (lower.includes('slide')) {
    return {
      icon: 'slideshow_outlined',
      title: 'Generating slides',
      message: 'We are turning module content into a presentation deck.',
      expectation: 'This may take up to 5 minutes.',
    }
  }
  if (lower.includes('narration') || lower.includes('script')) {
    return {
      icon: 'record_voice_over_outlined',
      title: 'Generating narration',
      message: 'We are preparing the speaking notes and audio for this module.',
      expectation: 'This may take up to 5 minutes.',
    }
  }
  if (lower.includes('video')) {
    return {
      icon: 'ondemand_video_outlined',
      title: 'Generating video',
      message: 'We are creating the module video from the prepared course material.',
      expectation: 'This may take up to 5 minutes.',
    }
  }
  if (lower.includes('saving')) {
    return {
      icon: 'save_outlined',
      title: 'Saving changes',
      message: 'We are updating the course blueprint.',
      expectation: 'This should only take a moment.',
    }
  }
  return {
    icon: 'hourglass_top_outlined',
    title: 'Working on it',
    message: rawMessage.split('\n')[0] ?? '',
    expectation: 'This may take a few minutes.',
  }
}

/** Blocking progress card shown over the whole app while a long backend job runs. */
export function LoadingOverlay({ message, detail }: { message: string; detail?: string | null }) {
  const content = overlayContent(message)
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/52"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="lms-overlay-title"
      aria-describedby="lms-overlay-message"
    >
      <div className="w-full max-w-[420px] rounded-[18px] bg-white p-7 shadow-[0_18px_40px_rgb(0_0_0/0.22)]">
        <div className="mx-auto flex size-[58px] items-center justify-center rounded-2xl bg-brand-blue-100">
          <div className="relative flex size-12 items-center justify-center">
            <Spinner
              size={48}
              strokeWidth={3.8}
              className="absolute inset-0"
              label={content.title}
            />
            <Icon name={content.icon} size={22} color="var(--color-primary-blue)" />
          </div>
        </div>
        <h2
          id="lms-overlay-title"
          className="mt-[22px] text-center font-manrope text-xl font-extrabold leading-tight text-[#101828]"
        >
          {content.title}
        </h2>
        <p
          id="lms-overlay-message"
          className="mt-2 text-center font-dm text-sm font-medium leading-[1.4] text-[#475467]"
          aria-live="polite"
        >
          {content.message}
        </p>
        <div className="mt-[18px] flex items-center gap-2 rounded-lg border border-[#e6e9ef] bg-[#f5f7fa] px-3 py-2.5">
          <Icon name="schedule_outlined" size={18} color="var(--color-primary-blue)" />
          <span className="font-dm text-[13px] font-bold text-[#344054]">
            {content.expectation}
          </span>
        </div>
        {detail && (
          <p
            className="mt-3 mb-0 text-center font-dm text-[13px] font-semibold leading-normal whitespace-pre-line text-[#475467]"
            aria-live="polite"
          >
            {detail}
          </p>
        )}
      </div>
    </div>
  )
}
