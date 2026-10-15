import { act, fireEvent, render, screen } from '@testing-library/react'
import { Chip } from './Chip'
import { ProgressBar } from './ProgressBar'
import { Select, TextField } from './TextField'
import { ToastProvider, useToast } from './Toast'

function ToastButton() {
  const toast = useToast()
  return <button onClick={() => toast('Saved', { tone: 'success', duration: 1000 })}>go</button>
}

describe('shared primitives', () => {
  it('shows a toast and hides it after its duration', () => {
    vi.useFakeTimers()
    render(
      <ToastProvider>
        <ToastButton />
      </ToastProvider>,
    )
    fireEvent.click(screen.getByText('go'))
    expect(screen.getByText('Saved')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(1000))
    expect(screen.queryByText('Saved')).not.toBeInTheDocument()
    vi.useRealTimers()
  })

  it('links a text field label and error', () => {
    render(<TextField label="Title" error="Required" />)
    const input = screen.getByLabelText('Title')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Required')
  })

  it('reports select changes with the option value', () => {
    const onChange = vi.fn()
    render(
      <Select
        label="Scope"
        value="a"
        options={[
          { value: 'a', label: 'A' },
          { value: 'b', label: 'B' },
        ]}
        onChange={onChange}
      />,
    )
    fireEvent.change(screen.getByLabelText('Scope'), { target: { value: 'b' } })
    expect(onChange).toHaveBeenCalledWith('b')
  })

  it('marks a selected chip as pressed', () => {
    render(<Chip selected>Finance</Chip>)
    expect(screen.getByRole('button', { name: 'Finance' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('clamps progress values', () => {
    render(<ProgressBar value={1.4} label="p" />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
  })
})
