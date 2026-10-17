import type { Amount, Budget, Contact, Enrollment, ErrorBody, ErrorCode, GrantCallback, TurnResponse } from "./types"

const BASE = "/api" // CONV-5 / web-conversation: solo el Contrato B, vía proxy
const TIMEOUT_MS = 35_000 // un turno de pago puede tardar ~25 s

export class ApiError extends Error {
  constructor(public status: number, public code: string) {
    super(code) // se decide por `code`, nunca por el message del servidor (CONV-2)
  }
}

// Catálogo propio en español (CONV-6): un mensaje por cada ErrorCode de contract-b.yaml.
// Record<ErrorCode, …> hace que TypeScript avise si el contrato agrega un código sin mensaje.
const MESSAGES: Record<ErrorCode, string> = {
  CONSENT_REQUIRED: "Necesito tu permiso para registrar tu voz.",
  SAMPLES_REQUIRED: "Faltan grabaciones. Empecemos el registro de nuevo.",
  INVALID_AUDIO: "No pude escuchar bien. ¿Lo intentas de nuevo?",
  INCONSISTENT_SAMPLES: "Las tres grabaciones tienen que ser de la misma persona. Probemos otra vez.",
  AUDIO_OR_TEXT_REQUIRED: "No recibí tu mensaje. Intenta de nuevo.",
  AUDIO_TOO_LONG: "Eso fue muy largo. Dilo en una frase corta.",
  SESSION_NOT_FOUND: "Empecemos de nuevo.",
  INVALID_AMOUNT: "Ese monto no es válido.",
  UPSTREAM_ERROR: "No pude comunicarme con tu billetera. Intenta en un momento.",
  INTERNAL_ERROR: "Algo falló de nuestro lado. Intenta de nuevo.",
  INVALID_REQUEST: "Algo falló. Intenta de nuevo.",
  INVALID_WALLET: "No encontré esa billetera, o no está en pesos. Revisa la dirección.",
  INVALID_CONTACT: "El nombre debe tener solo letras.",
  CONTACT_EXISTS: "Ya tienes ese contacto.",
  CONTACT_NOT_FOUND: "Ese contacto ya no existe.",
}
export const FALLBACK_MESSAGE = "Algo falló. Intenta de nuevo"
export const isKnownCode = (code: string): code is ErrorCode => code in MESSAGES
export const messageFor = (code: string) => (isKnownCode(code) ? MESSAGES[code] : FALLBACK_MESSAGE)

// Solo en desarrollo: pide un ejemplo concreto al mock de Prism (`Prefer: code=…, example=…`).
let preferNext: string | null = null
let onPreferUsed: (() => void) | null = null
export const setPreferNext = (prefer: string | null, onUsed?: () => void) => {
  preferNext = prefer
  onPreferUsed = onUsed ?? null
}

async function call<T>(path: string, init: RequestInit): Promise<T> {
  const requestId = crypto.randomUUID() // CONV-3: uno nuevo por acción
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>), "X-Request-Id": requestId }
  if (import.meta.env.DEV && preferNext) { headers.Prefer = preferNext; preferNext = null; onPreferUsed?.() }
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers, signal: AbortSignal.timeout(TIMEOUT_MS) })
  } catch {
    throw new ApiError(0, "NETWORK_ERROR")
  }
  const body = (await res.json().catch(() => null)) as (Partial<TurnResponse> & Partial<ErrorBody>) | null
  if (!res.ok) throw new ApiError(res.status, body?.error?.code ?? "UNKNOWN")
  // Solo id y state: nunca el cuerpo (PRIV-4)
  console.log(`[ezpay] ${requestId} ${path} ->`, body?.state ?? res.status)
  return body as T
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
})

export function postTurn(input: { text?: string; audio?: Blob; sessionId?: string | null }) {
  const form = new FormData()
  if (input.sessionId) form.set("sessionId", input.sessionId)
  if (input.text !== undefined) form.set("text", input.text)
  if (input.audio) form.set("audio", input.audio, audioFileName(input.audio))
  return call<TurnResponse>("/turns", { method: "POST", body: form })
}

/** Turno automático único de PAYMENT_PENDING (B-2, decisión D-1b, x-proposed). */
export function postVerifyPending(sessionId: string | null) {
  const form = new FormData()
  if (sessionId) form.set("sessionId", sessionId)
  form.set("kind", "verify_pending")
  return call<TurnResponse>("/turns", { method: "POST", body: form })
}

export const postGrantCallback = (cb: GrantCallback) => call<TurnResponse>("/grant-callback", json(cb))

export const postBudget = (debitAmount: Amount, interval?: string) =>
  call<{ interactUrl: string }>("/budget", json(interval ? { debitAmount, interval } : { debitAmount }))

export const getBudget = () => call<Budget>("/budget", { method: "GET" })

/** Tres muestras en un único POST, con consent=true (B-5, PRIV-2). */
export function postEnrollment(samples: Blob[]) {
  const form = new FormData()
  samples.forEach((s, i) => form.append("audio", s, audioFileName(s, `sample-${i + 1}`)))
  form.set("consent", "true")
  return call<Enrollment>("/enrollment", { method: "POST", body: form })
}

export const getEnrollment = () => call<Enrollment>("/enrollment", { method: "GET" })

// Agenda (extensión x-proposed del Contrato B): Python valida la wallet contra Open Payments.
export const getContacts = () => call<{ contacts: Contact[] }>("/contacts", { method: "GET" })
export const addContact = (name: string, walletAddress: string) =>
  call<Contact>("/contacts", json({ name, walletAddress }))
export const deleteContact = (alias: string) =>
  call<null>(`/contacts/${encodeURIComponent(alias)}`, { method: "DELETE" })

// Chrome graba webm/opus y Safari mp4: la extensión le dice a Python qué decodificar.
function audioFileName(blob: Blob, base = "command") {
  const ext = blob.type.includes("mp4") ? "mp4" : blob.type.includes("ogg") ? "ogg" : "webm"
  return `${base}.${ext}`
}
