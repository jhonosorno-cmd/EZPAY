import type { Amount, ErrorBody, GrantCallback, TurnResponse } from "./types"

const BASE = "/api" // CONV-5 / web-conversation: solo el Contrato B, vía proxy
const TIMEOUT_MS = 35_000 // un turno de pago puede tardar ~25 s

export class ApiError extends Error {
  constructor(public status: number, public code: string) {
    super(code) // se decide por `code`, nunca por el message del servidor (CONV-2)
  }
}

// Catálogo propio en español (CONV-6). Los códigos de /turns son del cambio propuesto B-3.
const MESSAGES: Record<string, string> = {
  INVALID_AUDIO: "No pude escuchar bien. ¿Lo intentas de nuevo?",
  AUDIO_TOO_LONG: "Eso fue muy largo. Dilo en una frase corta.",
  SESSION_NOT_FOUND: "Empecemos de nuevo.",
  CONSENT_REQUIRED: "Necesito tu permiso para registrar tu voz.",
}
export const FALLBACK_MESSAGE = "Algo falló. Intenta de nuevo"
export const messageFor = (code: string) => MESSAGES[code] ?? FALLBACK_MESSAGE

async function call<T>(path: string, init: RequestInit): Promise<T> {
  const requestId = crypto.randomUUID() // CONV-3: uno nuevo por acción
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { ...(init.headers as Record<string, string>), "X-Request-Id": requestId },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    })
  } catch {
    throw new ApiError(0, "NETWORK_ERROR")
  }
  const body = (await res.json().catch(() => null)) as (TurnResponse & Partial<ErrorBody>) | null
  if (!res.ok) throw new ApiError(res.status, body?.error?.code ?? "UNKNOWN")
  // Solo id y state: nunca el cuerpo (PRIV-4)
  console.log(`[ezpay] ${requestId} ${path} ->`, body && "state" in body ? body.state : res.status)
  return body as T
}

export function postTurn(input: { text?: string; audio?: Blob; sessionId?: string | null }) {
  const form = new FormData()
  if (input.sessionId) form.set("sessionId", input.sessionId)
  if (input.text !== undefined) form.set("text", input.text)
  if (input.audio) form.set("audio", input.audio, "command.webm")
  return call<TurnResponse>("/turns", { method: "POST", body: form })
}

export function postGrantCallback(cb: GrantCallback) {
  return call<TurnResponse>("/grant-callback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cb),
  })
}

export function postBudget(debitAmount: { value: string; assetCode: string; assetScale: number }) {
  return call<{ interactUrl: string }>("/budget", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ debitAmount }),
  })
}

export type Budget = { status: string; limit: Amount | null; spent: Amount | null; remaining: Amount | null }
export const getBudget = () => call<Budget>("/budget", { method: "GET" })
