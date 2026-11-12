import type { AnalyticsPerson } from '@lms/shared/auth/session'
import { z } from 'zod'

const text = (fallback: string) =>
  z.preprocess((value) => (value == null ? fallback : String(value)), z.string()).catch(fallback)

const employeeSchema = z
  .object({
    employee_id: text(''),
    name: text(''),
    department: text(''),
    job_title: text(''),
    join_date: text(''),
    status: text('active'),
  })
  .transform((json) => ({
    employeeId: json.employee_id,
    name: json.name,
    department: json.department,
    jobTitle: json.job_title,
    joinDate: json.join_date,
    status: json.status,
  }))

export type Employee = z.output<typeof employeeSchema>

export const parseEmployee = (json: unknown): Employee => employeeSchema.parse(json ?? {})

export const employeeAnalytics = (employee: Employee): AnalyticsPerson => ({
  id: employee.employeeId,
  traits: {
    role: 'employee',
    department: employee.department,
    job_title: employee.jobTitle,
    status: employee.status,
  },
})

export function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
}
