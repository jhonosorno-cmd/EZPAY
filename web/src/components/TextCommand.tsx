import { useState } from "react"

// Camino alterno (H1 y respaldo del micrófono). Un comando escrito siempre lleva a PIN (lo decide Python).
export function TextCommand({ disabled, onSend }: { disabled: boolean; onSend: (t: string) => void }) {
  const [text, setText] = useState("")
  return (
    <form
      className="text-command"
      onSubmit={(e) => {
        e.preventDefault()
        if (!text.trim()) return
        onSend(text.trim())
        setText("")
      }}
    >
      <input value={text} onChange={(e) => setText(e.target.value)} disabled={disabled}
        placeholder="O escríbelo aquí" aria-label="Escribe tu mensaje" />
      <button disabled={disabled || !text.trim()}>Enviar</button>
    </form>
  )
}
