import { AppError } from './errors.js'

export type Amount = { value: string; assetCode: string; assetScale: number }

const invalid = (msg: string) => new AppError(400, 'INVALID_AMOUNT', msg)

/** Valida la forma de un Amount del contrato. `value` es solo dígitos y mayor que cero. */
export function parseAmount(raw: unknown, field = 'amount'): Amount {
  if (typeof raw !== 'object' || raw === null) throw invalid(`${field} is required`)
  const { value, assetCode, assetScale } = raw as Record<string, unknown>
  if (typeof value !== 'string' || !/^\d+$/.test(value)) throw invalid(`${field}.value must be a digits-only string`)
  if (typeof assetCode !== 'string' || assetCode.length === 0) throw invalid(`${field}.assetCode is required`)
  if (typeof assetScale !== 'number' || !Number.isInteger(assetScale) || assetScale < 0)
    throw invalid(`${field}.assetScale must be a non-negative integer`)
  if (BigInt(value) <= 0n) throw invalid(`${field}.value must be greater than zero`)
  return { value: BigInt(value).toString(), assetCode, assetScale }
}

export const zero = (like: Amount): Amount => ({ ...like, value: '0' })

function assertSame(a: Amount, b: Amount) {
  if (a.assetCode !== b.assetCode || a.assetScale !== b.assetScale)
    throw new Error('amount asset mismatch') // bug interno -> 500
}

export function add(a: Amount, b: Amount): Amount {
  assertSame(a, b)
  return { ...a, value: (BigInt(a.value) + BigInt(b.value)).toString() }
}

/** a - b, nunca negativo. */
export function sub(a: Amount, b: Amount): Amount {
  assertSame(a, b)
  const r = BigInt(a.value) - BigInt(b.value)
  return { ...a, value: (r < 0n ? 0n : r).toString() }
}

export function cmp(a: Amount, b: Amount): number {
  assertSame(a, b)
  const x = BigInt(a.value)
  const y = BigInt(b.value)
  return x === y ? 0 : x > y ? 1 : -1
}

export const max = (a: Amount, b: Amount) => (cmp(a, b) >= 0 ? a : b)
