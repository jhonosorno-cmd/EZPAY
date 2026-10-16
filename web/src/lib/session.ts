// sessionStorage puede fallar (modo privado, almacenamiento bloqueado): nunca rompe la app.
const KEY = "ezpay.sessionId"
const REASON = "ezpay.handoffReason"

const get = (k: string) => { try { return sessionStorage.getItem(k) } catch { return null } }
const set = (k: string, v: string | null) => {
  try { v === null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v) } catch { /* sin almacenamiento */ }
}

export const loadSessionId = () => get(KEY)
export const saveSessionId = (id: string | null) => set(KEY, id)
export type HandoffReason = "budget" | "excess"
export const loadHandoffReason = () => get(REASON) as HandoffReason | null
export const saveHandoffReason = (r: HandoffReason | null) => set(REASON, r)
