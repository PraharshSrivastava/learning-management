// Trainer assignment models (Dart: frontend models.dart AssignmentRule, AssignmentGroup,
// SavedAssignmentGroup, AssignmentOptions; assignment_providers.dart payloads).
import { z } from 'zod'
import {
  boolNotFalse,
  int,
  isRecord,
  list,
  optInt,
  optStr,
  reparse,
  str,
  strList,
  type JsonRecord,
} from './parse'
import { employeeSchema } from './people'

export const assignmentGroupSchema = z
  .object({
    saved_group_id: optStr(),
    name: str(),
    employee_ids: strList(),
    departments: strList(),
    mailing_lists: strList(),
    job_titles: strList(),
    joined_less_than_days_ago: optInt(),
  })
  .transform((j) => ({
    savedGroupId: j.saved_group_id,
    name: j.name,
    employeeIds: j.employee_ids,
    departments: j.departments,
    mailingLists: j.mailing_lists,
    jobTitles: j.job_titles,
    joinedLessThanDaysAgo: j.joined_less_than_days_ago,
  }))
export type AssignmentGroup = z.output<typeof assignmentGroupSchema>
export const parseAssignmentGroup = (json: unknown): AssignmentGroup =>
  assignmentGroupSchema.parse(json)

// Dart AssignmentGroup() constructor with defaults.
export const emptyAssignmentGroup = (patch: Partial<AssignmentGroup> = {}): AssignmentGroup => ({
  savedGroupId: null,
  name: '',
  employeeIds: [],
  departments: [],
  mailingLists: [],
  jobTitles: [],
  joinedLessThanDaysAgo: null,
  ...patch,
})

export const isGroupEmpty = (g: AssignmentGroup) =>
  g.employeeIds.length === 0 &&
  g.departments.length === 0 &&
  g.mailingLists.length === 0 &&
  g.jobTitles.length === 0 &&
  g.joinedLessThanDaysAgo == null

export const hasEmployeeSelection = (g: AssignmentGroup) => g.employeeIds.length > 0

export const hasAttributeFilters = (g: AssignmentGroup) =>
  g.departments.length > 0 ||
  g.mailingLists.length > 0 ||
  g.jobTitles.length > 0 ||
  g.joinedLessThanDaysAgo != null

export const hasMixedSelection = (g: AssignmentGroup) =>
  hasEmployeeSelection(g) && hasAttributeFilters(g)

// Dart AssignmentGroup.toJson: saved_group_id and name only when set.
export function assignmentGroupToJson(g: AssignmentGroup): JsonRecord {
  const name = g.name.trim()
  return {
    ...(g.savedGroupId != null ? { saved_group_id: g.savedGroupId } : {}),
    ...(name.length > 0 ? { name } : {}),
    employee_ids: g.employeeIds,
    departments: g.departments,
    mailing_lists: g.mailingLists,
    job_titles: g.jobTitles,
    joined_less_than_days_ago: g.joinedLessThanDaysAgo,
  }
}

export type SavedGroupType = 'include' | 'exclude'

// Body for POST/PUT of a saved group (assignment_providers.dart, persist step).
// The name falls back to "Employee selection group N" or "Employee exclusion group N".
export function savedGroupPayload(g: AssignmentGroup, groupType: SavedGroupType, index: number) {
  const trimmed = g.name.trim()
  const name =
    trimmed.length > 0
      ? trimmed
      : `${groupType === 'include' ? 'Employee selection' : 'Employee exclusion'} group ${index + 1}`
  return {
    name,
    group_type: groupType,
    employee_ids: g.employeeIds,
    departments: g.departments,
    mailing_lists: g.mailingLists,
    job_titles: g.jobTitles,
    joined_less_than_days_ago: g.joinedLessThanDaysAgo,
  }
}

export const savedAssignmentGroupSchema = z
  .record(z.string(), z.unknown())
  .transform((raw, ctx) => {
    const group = reparse(assignmentGroupSchema, raw, ctx)
    return {
      savedGroupId: raw.saved_group_id == null ? '' : String(raw.saved_group_id),
      trainerId: raw.trainer_id == null ? '' : String(raw.trainer_id),
      name: raw.name == null ? '' : String(raw.name),
      groupType: raw.group_type == null ? 'include' : String(raw.group_type),
      group,
    }
  })
export type SavedAssignmentGroup = z.output<typeof savedAssignmentGroupSchema>
export const parseSavedAssignmentGroup = (json: unknown): SavedAssignmentGroup =>
  savedAssignmentGroupSchema.parse(json)

export const assignmentRuleSchema = z
  .object({
    include_all: boolNotFalse(),
    include_groups: list(assignmentGroupSchema),
    exclude_groups: list(assignmentGroupSchema),
    // Legacy flat fields, used when the group lists are empty.
    include_employee_ids: strList(),
    include_departments: strList(),
    include_mailing_lists: strList(),
    include_job_titles: strList(),
    joined_less_than_days_ago: optInt(),
    exclude_employee_ids: strList(),
    exclude_departments: strList(),
    exclude_mailing_lists: strList(),
    exclude_job_titles: strList(),
    deadline_days: int(7),
    deadline_mode: str('relative'),
    deadline_date: optStr(),
    is_active: boolNotFalse(),
  })
  .transform((j) => {
    const nonEmpty = (g: AssignmentGroup) => (isGroupEmpty(g) ? [] : [g])
    return {
      includeAll: j.include_all,
      includeGroups:
        j.include_groups.length > 0
          ? j.include_groups
          : nonEmpty(
              emptyAssignmentGroup({
                employeeIds: j.include_employee_ids,
                departments: j.include_departments,
                mailingLists: j.include_mailing_lists,
                jobTitles: j.include_job_titles,
                joinedLessThanDaysAgo: j.joined_less_than_days_ago,
              }),
            ),
      excludeGroups:
        j.exclude_groups.length > 0
          ? j.exclude_groups
          : nonEmpty(
              emptyAssignmentGroup({
                employeeIds: j.exclude_employee_ids,
                departments: j.exclude_departments,
                mailingLists: j.exclude_mailing_lists,
                jobTitles: j.exclude_job_titles,
              }),
            ),
      deadlineDays: j.deadline_days,
      deadlineMode: j.deadline_mode,
      deadlineDate: j.deadline_date,
      isActive: j.is_active,
    }
  })
export type AssignmentRule = z.output<typeof assignmentRuleSchema>
export const parseAssignmentRule = (json: unknown): AssignmentRule =>
  assignmentRuleSchema.parse(json)

// Dart AssignmentRule() constructor defaults (note deadlineMode 'fixed', unlike fromJson).
export const defaultAssignmentRule = (): AssignmentRule => ({
  includeAll: true,
  includeGroups: [],
  excludeGroups: [],
  deadlineDays: 7,
  deadlineMode: 'fixed',
  deadlineDate: null,
  isActive: true,
})

// Dart AssignmentRule.toJson. is_active is never sent.
export function assignmentRuleToJson(rule: AssignmentRule): JsonRecord {
  return {
    include_all: rule.includeAll,
    include_groups: rule.includeGroups.map(assignmentGroupToJson),
    exclude_groups: rule.excludeGroups.map(assignmentGroupToJson),
    deadline_days: rule.deadlineDays,
    deadline_mode: rule.deadlineMode,
    deadline_date: rule.deadlineMode === 'fixed' ? rule.deadlineDate : null,
  }
}

// Editor load rule: a rule never saved or published opens with a fixed deadline.
// Saved relative deadlines (including legacy records) keep their meaning.
export function ruleForEditor(rawRule: unknown): AssignmentRule {
  const rule = parseAssignmentRule(rawRule)
  const record: JsonRecord = isRecord(rawRule) ? rawRule : {}
  return record.updated_at == null && record.published_at == null
    ? { ...rule, deadlineMode: 'fixed' }
    : rule
}

export const assignmentOptionsSchema = z
  .object({
    employees: list(employeeSchema),
    departments: strList(),
    mailing_lists: strList(),
    job_titles: strList(),
  })
  .transform((j) => ({
    employees: j.employees,
    departments: j.departments,
    mailingLists: j.mailing_lists,
    jobTitles: j.job_titles,
  }))
export type AssignmentOptions = z.output<typeof assignmentOptionsSchema>
export const parseAssignmentOptions = (json: unknown): AssignmentOptions =>
  assignmentOptionsSchema.parse(json)
