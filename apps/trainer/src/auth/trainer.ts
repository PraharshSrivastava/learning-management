import type { AnalyticsPerson } from '@lms/shared/auth/session'
import { z } from 'zod'

const text = z.preprocess((value) => (value == null ? '' : String(value)), z.string()).catch('')

const trainerSchema = z
  .object({ trainer_id: text, name: text, status: text })
  .transform((json) => ({ trainerId: json.trainer_id, name: json.name, status: json.status }))

export type Trainer = z.output<typeof trainerSchema>

export const parseTrainer = (json: unknown): Trainer => trainerSchema.parse(json ?? {})

export const trainerAnalytics = (trainer: Trainer): AnalyticsPerson => ({
  id: trainer.trainerId,
  traits: { role: 'trainer', status: trainer.status },
})
