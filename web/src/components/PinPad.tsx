import { useState } from "react"
import { speak } from "../voice/tts"

// El PIN nunca se guarda, nunca va a la consola ni se lee en voz alta: cada tecla dice "punto".
export function PinPad({ disabled, onSubmit }: { disabled: boolean; onSubmit: (pin: string) => void }) {
  const [pin, setPin] = useState("")
  const press = (d: string) => {
    if (pin.length >= 6) return
    setPin(pin + d)
    void speak("punto")
  }
  const submit = () => {
    if (!pin) return
    onSubmit(pin)
    setPin("") // queda vacío después de enviarlo
  }
  return (
    <section className="pin" aria-label="Teclado de PIN">
      <div className="pin-dots" aria-label={`${pin.length} números escritos`}>{"●".repeat(pin.length) || " "}</div>
      <div className="pin-grid">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
          <button key={d} disabled={disabled} onClick={() => press(d)}>{d}</button>
        ))}
        <button disabled={disabled || !pin} onClick={() => setPin(pin.slice(0, -1))} aria-label="Borrar">⌫</button>
        <button disabled={disabled} onClick={() => press("0")}>0</button>
        <button className="pin-send" disabled={disabled || !pin} onClick={submit}>Enviar</button>
      </div>
    </section>
  )
}
