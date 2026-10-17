import { useCallback, useEffect, useRef, useState } from "react"
import { ApiError, isKnownCode, messageFor, postGrantCallback, postTurn, postVerifyPending } from "./api/client"
import type { GrantCallback, TurnResponse, TurnState } from "./api/types"
import { PENDING_CHECK_MS } from "./config"
import { loadSessionId, saveHandoffReason, saveSessionId } from "./lib/session"

const KNOWN: TurnState[] = [
  "AWAITING_COMMAND", "AWAITING_CONFIRMATION", "AWAITING_PIN", "AWAITING_RECIPIENT_CHOICE",
  "AWAITING_AUTHORIZATION", "PAYMENT_PENDING", "COMPLETED", "REJECTED",
]

export type View = {
  state: TurnState
  say: string
  transcript: string | null
  interactUrl: string | null
  options: TurnResponse["options"]
  payment: TurnResponse["payment"]
  challengePhrase: string | null // desafío de voz (B11): la frase que hay que repetir en voz alta
  errorCode: string | null // se muestra en letra pequeña si el código es desconocido
}

const START: View = {
  state: "AWAITING_COMMAND", say: "¿A quién le quieres enviar dinero?",
  transcript: null, interactUrl: null, options: null, payment: null, challengePhrase: null, errorCode: null,
}

export function useConversation({ speak }: { speak: (text: string) => Promise<void> }) {
  const [view, setView] = useState<View>(START)
  const [busy, setBusy] = useState(false)
  const inFlight = useRef(false) // ref, no state: el doble toque llega antes del re-render
  const pendingTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const apply = useCallback((r: TurnResponse) => {
    if (!KNOWN.includes(r.state as TurnState)) {
      // Estado desconocido: se muestra y lee el say, y se vuelve al inicio sin enviar nada
      setView({ ...START, say: r.say })
      void speak(r.say)
      return
    }
    saveSessionId(r.sessionId)
    const state = r.state as TurnState
    if (state === "COMPLETED" || state === "REJECTED") saveHandoffReason(null)
    setView({ state, say: r.say, transcript: r.transcript, interactUrl: r.interactUrl,
      options: r.options, payment: r.payment, challengePhrase: r.challengePhrase ?? null, errorCode: null })
    void speak(r.say)
  }, [speak])

  const fail = useCallback((e: unknown) => {
    const code = e instanceof ApiError ? e.code : "UNKNOWN"
    if (code === "SESSION_NOT_FOUND") {
      saveSessionId(null)
      setView(START)
      void speak(messageFor(code))
      return
    }
    if (code === "AUDIO_OR_TEXT_REQUIRED") {
      console.error("[ezpay] AUDIO_OR_TEXT_REQUIRED: error de programación") // sigue en el estado anterior
      return
    }
    const msg = messageFor(code)
    setView((v) => ({ ...v, say: msg, transcript: null, errorCode: isKnownCode(code) ? null : code }))
    void speak(msg)
  }, [speak])

  const run = useCallback(async (req: () => Promise<TurnResponse>) => {
    if (inFlight.current) return // un turno a la vez
    inFlight.current = true
    clearTimeout(pendingTimer.current) // la usuaria habló: se cancela la verificación automática
    setBusy(true)
    try {
      apply(await req())
    } catch (e) {
      fail(e)
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }, [apply, fail])

  const sendText = useCallback((text: string) =>
    run(() => postTurn({ text, sessionId: loadSessionId() })), [run])
  const sendAudio = useCallback((audio: Blob) =>
    run(() => postTurn({ audio, sessionId: loadSessionId() })), [run])
  const sendCallback = useCallback((cb: GrantCallback) => run(() => postGrantCallback(cb)), [run])

  // PAYMENT_PENDING: un único turno de verificación a los 20 s, sin audio ni texto. Nunca polling.
  const pendingChecked = useRef(false)
  useEffect(() => {
    if (view.state !== "PAYMENT_PENDING") {
      pendingChecked.current = false
      return
    }
    if (pendingChecked.current) return // la respuesta siguió en PAYMENT_PENDING: no se repite
    pendingTimer.current = setTimeout(() => {
      pendingChecked.current = true
      void run(() => postVerifyPending(loadSessionId()))
    }, PENDING_CHECK_MS)
    return () => clearTimeout(pendingTimer.current)
  }, [view, run])

  const restart = useCallback(() => {
    clearTimeout(pendingTimer.current)
    saveSessionId(null)
    saveHandoffReason(null)
    setView(START)
  }, [])

  return { view, busy, sendText, sendAudio, sendCallback, restart, setView }
}
