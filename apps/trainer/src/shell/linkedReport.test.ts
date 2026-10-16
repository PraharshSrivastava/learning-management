import { linkedStatus, parseLinkedReport } from './linkedReport'

describe('linked performance report', () => {
  it('maps notification statuses like the Flutter dashboard', () => {
    expect(linkedStatus('due_soon')).toBe('due_soon')
    expect(linkedStatus('overdue')).toBe('overdue')
    expect(linkedStatus('completed')).toBe('completed')
    expect(linkedStatus('reactivated')).toBe('assigned')
    expect(linkedStatus('assignment_reminder')).toBe('assigned')
    expect(linkedStatus('assigned')).toBe('assigned')
    expect(linkedStatus('started')).toBeNull()
    expect(linkedStatus(null)).toBeNull()
  })

  it('reads only view=performance links', () => {
    expect(parseLinkedReport('?view=performance&course_id=c1&status=overdue')).toEqual({
      courseId: 'c1',
      status: 'overdue',
    })
    expect(parseLinkedReport('?view=performance')).toEqual({ courseId: null, status: null })
    expect(parseLinkedReport('?view=courses&course_id=c1')).toBeNull()
  })
})
