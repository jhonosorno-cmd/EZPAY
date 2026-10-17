import { useCallback, useEffect, useRef, useState } from "react"
import { MAX_RECORDING_MS } from "../config"

// web-voice-io: grabación con MediaRecorder. El audio vive solo en memoria y se entrega una vez (PRIV-1).
// Quien llama decide qué hacer con una grabación corta: el comando la ignora, el registro pide repetir.
export type MicStatus = "idle" | "recording" | "denied" | "unsupported"

export function useRecorder(onAudio: (audio: Blob, durationMs: number) => void, maxMs = MAX_RECORDING_MS) {
  const [status, setStatus] = useState<MicStatus>(
    typeof MediaRecorder === "undefined" ? "unsupported" : "idle",
  )
  const rec = useRef<MediaRecorder | null>(null)
  const startedAt = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const onAudioRef = useRef(onAudio)
  onAudioRef.current = onAudio

  const stop = useCallback(() => {
    clearTimeout(timer.current)
    if (rec.current?.state === "recording") rec.current.stop()
  }, [])

  const start = useCallback(async () => {
    if (rec.current || status === "unsupported") return
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setStatus("denied")
      return
    }
    const chunks: Blob[] = []
    const r = new MediaRecorder(stream)
    r.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data) }
    r.onstop = () => {
      stream.getTracks().forEach((t) => t.stop()) // apaga el micrófono del equipo
      setStatus("idle")
      onAudioRef.current(new Blob(chunks, { type: r.mimeType }), Date.now() - startedAt.current)
      chunks.length = 0
      rec.current = null
    }
    rec.current = r
    startedAt.current = Date.now()
    r.start()
    setStatus("recording")
    timer.current = setTimeout(stop, maxMs) // tope de duración
  }, [maxMs, status, stop])

  useEffect(() => stop, [stop]) // al desmontar, nunca queda el micrófono encendido

  return { status, start, stop }
}
