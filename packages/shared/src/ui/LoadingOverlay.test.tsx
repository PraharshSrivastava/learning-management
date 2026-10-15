import { render, screen } from '@testing-library/react'
import { LoadingOverlay, overlayContent } from './LoadingOverlay'

it.each([
  ['Publishing assignment...', 'Publishing assignment'],
  ['Generating entire course', 'Generating course content'],
  ['Running Qwen modular extraction', 'Creating your course outline'],
  ['Generating quiz slides', 'Generating quizzes'],
  ['Generating slides for module 2', 'Generating slides'],
  ['Generating scripts', 'Generating narration'],
  ['Rendering video', 'Generating video'],
  ['Saving course blueprint modifications...', 'Saving changes'],
])('maps %s to %s', (message, title) => {
  expect(overlayContent(message).title).toBe(title)
})

it('shows the first line of an unknown message', () => {
  render(<LoadingOverlay message={'Doing a thing\nwith details'} />)
  expect(screen.getByRole('alertdialog', { name: 'Working on it' })).toBeInTheDocument()
  expect(screen.getByText('Doing a thing')).toBeInTheDocument()
  expect(screen.getByText('This may take a few minutes.')).toBeInTheDocument()
})
