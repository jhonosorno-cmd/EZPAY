import { useEffect, useState } from "react"
import { useRecorder } from "../voice/useRecorder"
import { isSpeaking, onSpeakingChange, stopSpeaking, unlockAudio } from "../voice/tts"

const MicIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
  </svg>
)

// Push-to-talk: se mantiene presionado para hablar. Nunca graba mientras habla el TTS.
export function MicButton({ disabled, onAudio }: { disabled: boolean; onAudio: (a: Blob) => void }) {
  const { status, start, stop } = useRecorder(onAudio)
  const [ttsOn, setTtsOn] = useState(isSpeaking())
  useEffect(() => onSpeakingChange(setTtsOn), [])

  if (status === "unsupported") return <p className="mic-note">Este navegador no puede grabar. Escribe tu mensaje.</p>
  if (status === "denied") return <p className="mic-note">No tengo permiso para el micrófono. Puedes escribir tu mensaje.</p>

  const down = () => {
    unlockAudio()
    if (ttsOn) { stopSpeaking(); return } // primer toque: callar el TTS; el siguiente graba
    void start()
  }
  return (
    <button
      className={`mic ${status === "recording" ? "recording" : ""}`}
      disabled={disabled}
      onPointerDown={down}
      onPointerUp={stop}
      onPointerLeave={stop}
      onContextMenu={(e) => e.preventDefault()}
      aria-label="Mantén presionado para hablar"
    >
      <MicIcon />
      {status === "recording" ? "Te escucho… suelta para enviar" : ttsOn ? "Toca para callar" : "Mantén presionado y habla"}
    </button>
  )
}
