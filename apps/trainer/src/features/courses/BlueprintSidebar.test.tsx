import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { stubBrowser, stubFetch } from '../documents/test/renderDocuments'
import { BlueprintTab } from './BlueprintTab'
import { setCourseFilter } from './courseQueries'
import { accessJson, courseJson, renderCourses } from './test/renderCourses'

beforeEach(() => {
  stubBrowser()
  setCourseFilter('all')
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('searches titles within the existing availability filter without losing selection', async () => {
  stubFetch((url) =>
    url.pathname === '/api/lms/me'
      ? accessJson()
      : url.pathname === '/api/courses'
        ? [
            courseJson(),
            courseJson({ course_id: 'c2', course_name: 'Risk guide', lifecycle_state: 'draft' }),
          ]
        : courseJson(),
  )
  renderCourses(BlueprintTab, { url: '/?tab=blueprint&course=c1' })
  const list = await screen.findByRole('list', { name: 'My courses' })
  expect(within(list).getByRole('button', { current: true })).toHaveTextContent(
    'Compliance Essentials',
  )
  fireEvent.change(screen.getByRole('searchbox', { name: 'Search courses' }), {
    target: { value: 'Risk' },
  })
  expect(within(list).getAllByRole('button')).toHaveLength(1)
  expect(within(list).queryByText('Compliance Essentials')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Course availability'), { target: { value: 'active' } })
  expect(screen.getByText('No matching courses')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Course availability'), { target: { value: 'all' } })
  fireEvent.change(screen.getByRole('searchbox', { name: 'Search courses' }), {
    target: { value: '' },
  })
  expect(
    within(screen.getByRole('list', { name: 'My courses' })).getByRole('button', { current: true }),
  ).toHaveTextContent('Compliance Essentials')
})
