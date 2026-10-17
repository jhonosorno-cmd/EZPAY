import { useCallback, useState } from "react"
import { useConversation } from "./useConversation"
import { Conversation } from "./screens/Conversation"
import { GrantCallback } from "./screens/GrantCallback"
import { Enrollment } from "./enrollment/Enrollment"
import { Contacts } from "./screens/Contacts"
import { DevScenario } from "./components/DevScenario"
import { isAudioUnlocked, speak, unlockAudio } from "./voice/tts"

const PRISM = import.meta.env.DEV && import.meta.env.VITE_MOCK === "prism"

export function App() {
  return <><Screens />{PRISM && <DevScenario />}</>
}

function Screens() {
  const conv = useConversation({ speak })
  const [route, setRoute] = useState(window.location.pathname)
  const [started, setStarted] = useState(isAudioUnlocked())
  const done = useCallback(() => setRoute("/"), [])

  if (route === "/grant-callback") return <GrantCallback conv={conv} onDone={done} />
  if (route === "/contactos") return <Contacts onClose={() => setRoute("/")} />
  if (route === "/registro") return <Enrollment onClose={() => { setRoute("/"); void speak(conv.view.say) }} />

  // El navegador no deja hablar hasta un gesto: al volver de la wallet, un toque desbloquea y relee el say.
  // Inspirada en la pantalla de login del diseño, pero sin usuario ni contraseña (la wallet autoriza, SEG-1).
  if (!started) {
    return (
      <main className="welcome">
        <h1 className="welcome-brand">EZPAY</h1>
        <hr />
        <p className="welcome-hi">¡Bienvenida!</p>
        <p className="welcome-text">Envía dinero hablando, dentro del presupuesto que autorizaste.</p>
        <button className="welcome-btn" onClick={() => { unlockAudio(); setStarted(true); void speak(conv.view.say) }}>
          EMPEZAR
        </button>
      </main>
    )
  }
  return <Conversation conv={conv} onEnroll={() => setRoute("/registro")} onContacts={() => setRoute("/contactos")} />
}
