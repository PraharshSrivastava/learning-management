import { cleanup, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { setCourseFilter } from '../courses/courseQueries'
import { accessJson, courseJson, renderCourses } from '../courses/test/renderCourses'
import { stubBrowser, stubFetch } from '../documents/test/renderDocuments'
import { CoursesTab } from './CoursesTab'

beforeEach(() => {
  stubBrowser()
  setCourseFilter('all')
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('shows the course detail load error, not an empty course', async () => {
  stubFetch((url) => {
    if (url.pathname === '/api/lms/me') return accessJson()
    if (url.pathname === '/api/courses') return [courseJson({ modules: [] })]
    return new Response('{"detail":"Forbidden"}', { status: 403 })
  })
  renderCourses(CoursesTab, { url: '/?tab=courses&course=c1' })
  expect(await screen.findByText('Error loading course')).toBeInTheDocument()
  expect(screen.queryByText('No Modules Available')).not.toBeInTheDocument()
})
