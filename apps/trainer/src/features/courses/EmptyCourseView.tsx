import { Icon } from '@lms/shared/ui/icons/Icon'

/** Right pane when no course is selected. */
export function EmptyCourseView() {
  return (
    <div className="card flex h-full flex-col items-center justify-center">
      <Icon name="collections_bookmark_rounded" size={64} className="text-gray/40" />
      <h2 className="m-0 mt-4 font-inter text-lg font-bold text-primary-blue">
        No Course Selected
      </h2>
      <p className="m-0 mt-2 font-barlow text-sm text-gray">
        Select a course from the list on the left to view its syllabus outline.
      </p>
    </div>
  )
}
