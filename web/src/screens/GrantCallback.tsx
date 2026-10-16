import { useEffect, useRef } from "react"
import { readCallbackParams } from "../lib/callback"
import type { useConversation } from "../useConversation"

// /grant-callback: reenvía a Python lo que trajo la wallet, una sola vez, y limpia la URL.
export function GrantCallback({ conv, onDone }: { conv: ReturnType<typeof useConversation>; onDone: () => void }) {
  const sent = useRef(false) // StrictMode monta dos veces en desarrollo
  useEffect(() => {
    if (sent.current) return
    sent.current = true
    const params = readCallbackParams(window.location.search)
    window.history.replaceState(null, "", "/") // recargar no reenvía el callback; nada se registra (PRIV-4)
    void conv.sendCallback(params).then(onDone)
  }, [conv, onDone])
  return <main className="welcome"><p className="welcome-text">Volviendo de tu billetera…</p></main>
}
