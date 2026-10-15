// Lenient parse helpers that mirror the Dart fromJson idioms.
// A wrong-typed optional field falls back to the default and never throws.
import { z } from 'zod'

export type JsonRecord = Record<string, unknown>

export function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

// Dart Object.toString() for JSON values (null -> "null"). Containers are approximate.
export function dartString(value: unknown): string {
  if (typeof value === 'string') return value
  if (value !== null && typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// x?.toString() ?? fallback
export const str = (fallback = '') =>
  z.unknown().transform((v) => (v == null ? fallback : dartString(v)))

// x?.toString() (String?)
export const optStr = () => z.unknown().transform((v) => (v == null ? null : dartString(v)))

// x as String? ?? fallback (non-strings fall back instead of throwing)
export const onlyStr = (fallback = '') =>
  z.unknown().transform((v) => (typeof v === 'string' ? v : fallback))

// x as String? (non-strings become null)
export const optOnlyStr = () => z.unknown().transform((v) => (typeof v === 'string' ? v : null))

// (x as num?)?.toInt() ?? fallback
export const int = (fallback = 0) =>
  z
    .unknown()
    .transform((v) => (typeof v === 'number' && Number.isFinite(v) ? Math.trunc(v) : fallback))

// (x as num?)?.toInt()
export const optInt = () =>
  z.unknown().transform((v) => (typeof v === 'number' && Number.isFinite(v) ? Math.trunc(v) : null))

// (x as num?)?.toDouble() ?? fallback
export const num = (fallback = 0) =>
  z.unknown().transform((v) => (typeof v === 'number' && Number.isFinite(v) ? v : fallback))

// (x as num?)?.toDouble()
export const optNum = () =>
  z.unknown().transform((v) => (typeof v === 'number' && Number.isFinite(v) ? v : null))

// x == true
export const bool = () => z.unknown().transform((v) => v === true)

// x != false
export const boolNotFalse = () => z.unknown().transform((v) => v !== false)

// x as bool?
export const optBool = () => z.unknown().transform((v) => (typeof v === 'boolean' ? v : null))

// (x as List? ?? []).map((e) => e.toString()).toList()
export const strList = () =>
  z.unknown().transform((v) => (Array.isArray(v) ? v.map((item) => dartString(item)) : []))

// x as List? ?? []
export const unknownList = () =>
  z.unknown().transform((v): unknown[] => (Array.isArray(v) ? v : []))

// x as Map<String, dynamic>? (non-maps become null)
export const optRecord = () =>
  z.unknown().transform((v): JsonRecord | null => (isRecord(v) ? v : null))

// x as Map<String, dynamic>? ?? {}
export const record = () => z.unknown().transform((v): JsonRecord => (isRecord(v) ? v : {}))

// (x as List? ?? []).map(Item.fromJson). Bad items throw, as the Dart hard cast does.
export const list = <T extends z.ZodType>(item: T) =>
  z.preprocess((v) => (Array.isArray(v) ? v : []), z.array(item))

// Nested object: x as Map? ?? {}, then parsed by the schema.
export const nested = <T extends z.ZodType>(schema: T) =>
  z.preprocess((v) => (isRecord(v) ? v : {}), schema)

// Report helper _int: num -> toInt, else int.tryParse('$v') ?? 0
export const looseInt = () =>
  z.unknown().transform((v) => {
    if (typeof v === 'number') return Number.isFinite(v) ? Math.trunc(v) : 0
    const text = dartString(v)
    return /^[+-]?\d+$/.test(text) ? Number.parseInt(text, 10) : 0
  })

// Map<int, String> from a map with numeric string keys (int.tryParse key, value.toString()).
export function indexedMap(value: unknown, nullAsEmpty: boolean): Record<number, string> {
  const result: Record<number, string> = {}
  if (isRecord(value)) {
    for (const [key, item] of Object.entries(value)) {
      if (!/^[+-]?\d+$/.test(key)) continue
      result[Number.parseInt(key, 10)] = item == null && nullAsEmpty ? '' : dartString(item)
    }
  }
  return result
}

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/

// Approximates DateTime.tryParse. Date-only and zone-less values are local time.
export function parseDartDate(value: string | null | undefined): Date | null {
  if (value == null) return null
  const text = value.trim()
  let date: Date
  if (DATE_ONLY.test(text)) {
    const [y, m, d] = text.split('-').map(Number)
    date = new Date(y!, m! - 1, d!)
  } else {
    date = new Date(text.replace(/^(\d{4}-\d{2}-\d{2}) /, '$1T'))
  }
  return Number.isNaN(date.getTime()) ? null : date
}

// Re-parse a value inside a transform and forward any issues (keeps ZodError semantics).
export function reparse<T extends z.ZodType>(
  schema: T,
  value: unknown,
  ctx: z.RefinementCtx,
): z.output<T> {
  const result = schema.safeParse(value)
  if (!result.success) {
    ctx.addIssue({ code: 'custom', message: result.error.message, input: value })
    return z.NEVER
  }
  return result.data
}
