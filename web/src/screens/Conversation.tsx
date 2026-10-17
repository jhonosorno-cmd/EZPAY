import { useEffect, useState } from "react"
import { ApiError, getBudget, getEnrollment, messageFor, postBudget } from "../api/client"
import type { Budget, Payment } from "../api/types"
import { DEMO_BUDGET } from "../config"
import { formatAmount } from "../lib/money"
import { addRecent, loadRecent, receiverName } from "../lib/recent"
import { saveHandoffReason } from "../lib/session"
import type { useConversation } from "../useConversation"
import { BudgetHeader } from "../components/BudgetHeader"
import { MicButton } from "../components/MicButton"
import { PinPad } from "../components/PinPad"
import { Receipt } from "../components/Receipt"
import { RecentPayments } from "../components/RecentPayments"
import { TextCommand } from "../components/TextCommand"
import { speak, unlockAudio } from "../voice/tts"

type Conv = ReturnType<typeof useConversation>
const CAN_SPEAK = ["AWAITING_COMMAND", "AWAITING_CONFIRMATION", "AWAITING_RECIPIENT_CHOICE", "PAYMENT_PENDING"]

export function Conversation({ conv, onEnroll }: { conv: Conv; onEnroll: () => void }) {
  const { view, busy, sendText, sendAudio, restart } = conv
  const [budgetUrl, setBudgetUrl] = useState<string | null>(null)
  const [budget, setBudget] = useState<Budget | null>(null)
  const [recent, setRecent] = useState<Payment[]>(loadRecent)
  // enrollment-ui: "Registrar mi voz" solo si no hay huella. Si la ruta falla, se ofrece igual.
  const [enrolled, setEnrolled] = useState<boolean | null>(null)
  const s = view.state

  useEffect(() => {
    getEnrollment().then((r) => setEnrolled(r.enrolled)).catch(() => setEnrolled(false))
  }, [])

  // El presupuesto se relee al cambiar de estado (después de un pago o de volver de la wallet).
  useEffect(() => {
    getBudget().then(setBudget).catch(() => setBudget(null))
  }, [s])

  useEffect(() => {
    if (s === "COMPLETED" && view.payment) setRecent(addRecent(view.payment))
  }, [s, view.payment])

  const goToWallet = (url: string, reason: "budget" | "excess") => {
    saveHandoffReason(reason) // el sessionId ya está guardado; la página se recarga completa al volver
    window.location.assign(url) // solo después del toque, nunca automático
  }

  const askBudget = async () => {
    unlockAudio()
    try {
      const { interactUrl } = await postBudget(DEMO_BUDGET)
      setBudgetUrl(interactUrl)
      void speak("Vas a autorizar un presupuesto en tu billetera. Toca el botón para ir.")
    } catch (e) {
      void speak(messageFor(e instanceof ApiError ? e.code : "UNKNOWN"))
    }
  }

  const walletUrl = s === "AWAITING_AUTHORIZATION" ? view.interactUrl : budgetUrl
  const hasBudget = budget?.status === "ACTIVE"

  return (
    <div className="app">
      <BudgetHeader budget={budget} />

      <main className="content">
        <article className="say-card" aria-live="polite">
          <p className="say-label">EZPAY dice</p>
          <p className="say">{busy ? "Procesando…" : view.say}</p>
          {view.transcript && <p className="transcript">Entendí: “{view.transcript}”</p>}
          {view.errorCode && <p className="error-code">{view.errorCode}</p>}
        </article>

        {walletUrl && (
          <button className="pill pill-primary"
            onClick={() => goToWallet(walletUrl, s === "AWAITING_AUTHORIZATION" ? "excess" : "budget")}>
            Ir a mi billetera →
          </button>
        )}

        {s === "AWAITING_CONFIRMATION" && (
          <div className="row">
            <button className="pill pill-primary" disabled={busy} onClick={() => sendText("sí")}>Sí</button>
            <button className="pill pill-light" disabled={busy} onClick={() => sendText("no")}>No</button>
          </div>
        )}

        {s === "AWAITING_RECIPIENT_CHOICE" && view.options?.map((o) => (
          <button key={o.alias} className="pill pill-light" disabled={busy} onClick={() => sendText(o.alias)}>{o.name}</button>
        ))}

        {s === "AWAITING_PIN" && <PinPad disabled={busy} onSubmit={sendText} />}

        {s === "PAYMENT_PENDING" && (
          <section className="pending" aria-label="Envío en camino">
            <p className="receipt-label">En camino</p>
            {view.payment ? (
              <p className="pending-detail">$&nbsp;{formatAmount(view.payment.receiveAmount)} para {receiverName(view.payment.receiver)}</p>
            ) : (
              <p className="pending-detail">Tu envío va en camino…</p>
            )}
          </section>
        )}

        {s === "COMPLETED" && view.payment && <Receipt payment={view.payment} />}

        {(s === "COMPLETED" || s === "REJECTED") && (
          <button className="pill pill-light" onClick={restart}>Hacer otro envío</button>
        )}

        {(s === "AWAITING_COMMAND" || s === "PAYMENT_PENDING") && <TextCommand disabled={busy} onSend={sendText} />}

        {s === "AWAITING_COMMAND" && !hasBudget && !budgetUrl && (
          <button className="linkish" onClick={askBudget}>Autorizar presupuesto de $&nbsp;{formatAmount(DEMO_BUDGET)}</button>
        )}

        {s === "AWAITING_COMMAND" && enrolled === false && (
          <button className="pill pill-light" onClick={onEnroll}>🎙 Registrar mi voz</button>
        )}

        <RecentPayments items={recent} />
      </main>

      {/* En PIN, wallet o recibo no hay micrófono ("Sin micrófono en el PIN"): el dock no se muestra,
          para no tapar el teclado ni ofrecer una acción que no sirve. */}
      {CAN_SPEAK.includes(s) && (
        <nav className="dock" aria-label="Hablar">
          <div className="dock-inner">
            <MicButton disabled={busy} onAudio={sendAudio} />
          </div>
        </nav>
      )}
    </div>
  )
}
