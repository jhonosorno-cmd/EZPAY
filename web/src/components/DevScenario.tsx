import { useState } from "react"
import { setPreferNext } from "../api/client"

// Solo con `npm run dev:prism`: elige qué ejemplo de openapi/contract-b.yaml devuelve el mock de Prism
// en la próxima petición (header `Prefer`). No existe en el build de producción.
const SCENARIOS: { group: string; items: [label: string, prefer: string][] }[] = [
  { group: "/turns (estados)", items: [
    ["AWAITING_COMMAND", "code=200, example=awaiting-command"],
    ["AWAITING_CONFIRMATION", "code=200, example=awaiting-confirmation"],
    ["AWAITING_PIN", "code=200, example=awaiting-pin"],
    ["AWAITING_PIN (reintento)", "code=200, example=awaiting-pin-retry"],
    ["AWAITING_RECIPIENT_CHOICE", "code=200, example=awaiting-recipient-choice"],
    ["AWAITING_AUTHORIZATION", "code=200, example=awaiting-authorization"],
    ["PAYMENT_PENDING", "code=200, example=payment-pending"],
    ["COMPLETED", "code=200, example=completed"],
    ["REJECTED", "code=200, example=rejected"],
  ] },
  { group: "/turns (errores)", items: [
    ["400 INVALID_AUDIO", "code=400, example=invalid-audio"],
    ["400 AUDIO_TOO_LONG", "code=400, example=audio-too-long"],
    ["400 AUDIO_OR_TEXT_REQUIRED", "code=400, example=audio-or-text-required"],
    ["404 SESSION_NOT_FOUND", "code=404, example=session-not-found"],
    ["500 INTERNAL_ERROR", "code=500, example=internal-error"],
  ] },
  { group: "/enrollment", items: [
    ["GET no registrada", "code=200, example=not-enrolled"],
    ["GET registrada", "code=200, example=enrolled"],
    ["POST 400 INVALID_AUDIO", "code=400, example=invalid-audio"],
    ["POST 400 INCONSISTENT_SAMPLES", "code=400, example=inconsistent-samples"],
    ["POST 400 CONSENT_REQUIRED", "code=400, example=consent-required"],
  ] },
  { group: "/budget", items: [
    ["POST 400 INVALID_AMOUNT", "code=400, example=invalid-amount"],
    ["502 UPSTREAM_ERROR", "code=502, example=upstream-error"],
  ] },
]

export function DevScenario() {
  const [open, setOpen] = useState(false)
  const [next, setNext] = useState<string | null>(null)
  const pick = (label: string, prefer: string) => {
    setPreferNext(prefer, () => setNext(null)) // el chip se borra cuando la petición lo usa
    setNext(label)
    setOpen(false)
  }
  return (
    <div className="dev">
      {next && <span className="dev-chip">Próxima: {next}</span>}
      <button className="dev-btn" onClick={() => setOpen(!open)} aria-label="Escenario del mock">🧪</button>
      {open && (
        <div className="dev-menu">
          <p className="dev-title">Mock de Prism · próxima respuesta</p>
          {SCENARIOS.map((g) => (
            <div key={g.group}>
              <p className="dev-group">{g.group}</p>
              {g.items.map(([label, prefer]) => (
                <button key={label} onClick={() => pick(label, prefer)}>{label}</button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
