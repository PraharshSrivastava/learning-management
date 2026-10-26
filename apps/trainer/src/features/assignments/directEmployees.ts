// Individually picked employees, stored in the rule's existing group structure.
import {
  emptyAssignmentGroup,
  hasAttributeFilters,
  hasEmployeeSelection,
  type AssignmentGroup,
} from '@lms/shared/models'

/** Names of the groups that hold individually picked employees. */
export const DIRECT_GROUP_NAMES = ['Selected employees', 'Excluded employees']

/**
 * The group that holds individually picked employees: the first one with employee ids only that
 * is not a user's saved group. A saved group is shared criteria, so the picker never edits it.
 * Earlier builds saved the picked group under its reserved name, so that name still counts.
 */
export function directGroupIndex(groups: AssignmentGroup[]): number {
  return groups.findIndex(
    (group) =>
      (group.savedGroupId == null || DIRECT_GROUP_NAMES.includes(group.name.trim())) &&
      hasEmployeeSelection(group) &&
      !hasAttributeFilters(group),
  )
}

/** Picked employee ids and the other groups (filters, saved groups) shown separately. */
export function splitDirect(groups: AssignmentGroup[]): {
  employeeIds: string[]
  others: AssignmentGroup[]
} {
  const index = directGroupIndex(groups)
  return index < 0
    ? { employeeIds: [], others: groups }
    : { employeeIds: groups[index]!.employeeIds, others: groups.filter((_, i) => i !== index) }
}

/**
 * Groups with the picked ids replaced. The direct group keeps its position and name; it is
 * created when the first employee is picked and removed when the last one is.
 */
export function withDirectIds(
  groups: AssignmentGroup[],
  employeeIds: string[],
  name: string,
): AssignmentGroup[] {
  const ids = [...new Set(employeeIds)]
  const index = directGroupIndex(groups)
  if (index < 0)
    return ids.length ? [emptyAssignmentGroup({ name, employeeIds: ids }), ...groups] : groups
  if (!ids.length) return groups.filter((_, i) => i !== index)
  return groups.map((group, i) =>
    i === index ? { ...group, employeeIds: ids, savedGroupId: null } : group,
  )
}

/** Groups after the supplementary (non-direct) groups change. */
export function withOtherGroups(
  groups: AssignmentGroup[],
  others: AssignmentGroup[],
): AssignmentGroup[] {
  const index = directGroupIndex(groups)
  return index < 0 ? others : [groups[index]!, ...others]
}
