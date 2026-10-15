/**
 * Query keys that the shell refreshes. Feature code must use these roots so that
 * tab activation and "Refresh All Data" reach the right queries.
 */
export const trainerKeys = {
  files: ['files'] as const,
  courses: ['courses'] as const,
  course: (courseId: string) => ['courses', 'detail', courseId] as const,
  assignableCourses: ['assignment', 'courses'] as const,
  assignment: ['assignment'] as const,
  performance: ['performance'] as const,
}
