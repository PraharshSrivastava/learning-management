// People models (Dart: trainer models.dart Trainer/Employee, employee models.dart Employee).
import { z } from 'zod'
import { str, strList } from './parse'

export const trainerSchema = z
  .object({ trainer_id: str(), name: str(), status: str() })
  .transform((j) => ({ trainerId: j.trainer_id, name: j.name, status: j.status }))
export type Trainer = z.output<typeof trainerSchema>
export const parseTrainer = (json: unknown): Trainer => trainerSchema.parse(json)

// Trainer app employee: has mailing lists, status defaults to ''.
export const employeeSchema = z
  .object({
    employee_id: str(),
    name: str(),
    department: str(),
    mailing_lists: strList(),
    job_title: str(),
    join_date: str(),
    status: str(),
  })
  .transform((j) => ({
    employeeId: j.employee_id,
    name: j.name,
    department: j.department,
    mailingLists: j.mailing_lists,
    jobTitle: j.job_title,
    joinDate: j.join_date,
    status: j.status,
  }))
export type Employee = z.output<typeof employeeSchema>
export const parseEmployee = (json: unknown): Employee => employeeSchema.parse(json)

// Employee app session employee: no mailing lists, status defaults to 'active'.
// Kept apart from Employee because the defaults differ.
export const employeeProfileSchema = z
  .object({
    employee_id: str(),
    name: str(),
    department: str(),
    job_title: str(),
    join_date: str(),
    status: str('active'),
  })
  .transform((j) => ({
    employeeId: j.employee_id,
    name: j.name,
    department: j.department,
    jobTitle: j.job_title,
    joinDate: j.join_date,
    status: j.status,
  }))
export type EmployeeProfile = z.output<typeof employeeProfileSchema>
export const parseEmployeeProfile = (json: unknown): EmployeeProfile =>
  employeeProfileSchema.parse(json)
