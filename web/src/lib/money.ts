import type { Amount } from "../api/types"

// CONV-1: nunca number/parseFloat con dinero. Todo opera sobre el string `value` y BigInt.
export function formatAmount({ value, assetScale }: Amount): string {
  const digits = value.replace(/^0+(?=\d)/, "").padStart(assetScale + 1, "0")
  const int = digits.slice(0, digits.length - assetScale)
  const rawFrac = assetScale > 0 ? digits.slice(-assetScale) : ""
  const frac = /^0*$/.test(rawFrac) ? "" : rawFrac // se omiten solo si todos son cero: "10,50", no "10,5"
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ".")
  return frac ? `${grouped},${frac}` : grouped
}

/** Costo = debitado − recibido. null si no hay costo o si las monedas difieren (nunca se combinan). */
export function costOf(debit: Amount, receive: Amount): Amount | null {
  if (debit.assetCode !== receive.assetCode || debit.assetScale !== receive.assetScale) return null
  const diff = BigInt(debit.value) - BigInt(receive.value)
  return diff > 0n ? { ...debit, value: diff.toString() } : null
}

/** Parte entera y centavos por separado, para mostrar los centavos en superíndice. */
export function splitAmount(a: Amount): { int: string; frac: string | null } {
  const [int, frac] = formatAmount(a).split(",")
  return { int: int!, frac: frac ?? null }
}

/** Porcentaje restante (0–100, hacia abajo) para la barra. Es un porcentaje, no dinero. */
export function percentLeft(remaining: Amount, limit: Amount): number {
  const l = BigInt(limit.value)
  if (l === 0n) return 0
  return Number((BigInt(remaining.value) * 100n) / l)
}
