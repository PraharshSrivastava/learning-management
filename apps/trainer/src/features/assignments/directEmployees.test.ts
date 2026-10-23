import { emptyAssignmentGroup } from '@lms/shared/models'
import { describe, expect, it } from 'vitest'
import { directGroupIndex, splitDirect, withDirectIds, withOtherGroups } from './directEmployees'

const filters = emptyAssignmentGroup({ name: 'Finance', departments: ['Finance'] })
const saved = emptyAssignmentGroup({ name: 'Saved', savedGroupId: 's1', employeeIds: ['e9'] })
const direct = emptyAssignmentGroup({ name: 'Selected employees', employeeIds: ['e1'] })

describe('direct employee selection', () => {
  it('finds the plain employee group and never a saved group or a filter group', () => {
    expect(directGroupIndex([filters, saved, direct])).toBe(2)
    expect(directGroupIndex([filters, saved])).toBe(-1)
    expect(splitDirect([filters, direct])).toEqual({ employeeIds: ['e1'], others: [filters] })
  })

  it('creates, updates in place, deduplicates and removes the direct group', () => {
    const created = withDirectIds([filters], ['e2', 'e2'], 'Selected employees')
    expect(created).toEqual([
      emptyAssignmentGroup({ name: 'Selected employees', employeeIds: ['e2'] }),
      filters,
    ])
    expect(withDirectIds([filters, direct], ['e1', 'e3'], 'x')[1]!.employeeIds).toEqual([
      'e1',
      'e3',
    ])
    expect(withDirectIds([filters, direct], [], 'x')).toEqual([filters])
    expect(withDirectIds([filters], [], 'x')).toEqual([filters])
  })

  it('keeps the direct group when the other groups change', () => {
    expect(withOtherGroups([filters, direct], [saved])).toEqual([direct, saved])
    expect(withOtherGroups([filters], [saved])).toEqual([saved])
  })
})
