/** Performance deep link from notification e-mails: `?view=performance&course_id=...&status=...`. */
export interface LinkedReport {
  courseId: string | null
  status: 'due_soon' | 'overdue' | 'completed' | 'assigned' | null
  /** Opens the Journeys tab with this journey's detail. */
  journeyId?: string | null
}

export function linkedStatus(raw: string | null): LinkedReport['status'] {
  switch (raw) {
    case 'due_soon':
    case 'overdue':
    case 'completed':
      return raw
    case 'assigned':
    case 'reactivated':
    case 'assignment_reminder':
      return 'assigned'
    default:
      return null
  }
}

export function parseLinkedReport(search: string): LinkedReport | null {
  const params = new URLSearchParams(search)
  if (params.get('view') !== 'performance') return null
  return { courseId: params.get('course_id') || null, status: linkedStatus(params.get('status')) }
}

let pending: LinkedReport | null = null

/** Read once at startup. The performance tab takes it when it mounts. */
export function setPendingLinkedReport(report: LinkedReport | null): void {
  pending = report
}

export function takePendingLinkedReport(): LinkedReport | null {
  const report = pending
  pending = null
  return report
}
