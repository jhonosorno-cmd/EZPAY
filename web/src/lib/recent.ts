import type { Payment } from "../api/types"

// Envíos de esta sesión del navegador. Sobreviven a la ida a la wallet (sessionStorage), nada más.
const KEY = "ezpay.recent"
const MAX = 5

export function loadRecent(): Payment[] {
  try { return JSON.parse(sessionStorage.getItem(KEY) ?? "[]") as Payment[] } catch { return [] }
}

export function addRecent(p: Payment): Payment[] {
  const list = [p, ...loadRecent().filter((x) => x.paymentId !== p.paymentId)].slice(0, MAX)
  try { sessionStorage.setItem(KEY, JSON.stringify(list)) } catch { /* sin almacenamiento */ }
  return list
}

/** "https://ilp.interledger-test.dev/laura" → "Laura". */
export function receiverName(url: string): string {
  const last = url.replace(/\/+$/, "").split("/").pop() ?? url
  return last.charAt(0).toUpperCase() + last.slice(1)
}
