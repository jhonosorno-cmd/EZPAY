import { useCallback, useEffect, useRef, useState } from "react"
import { MAX_RECORDING_MS } from "../config"
import { playCue, primeCue } from "./cue"

// web-voice-io: grabación con MediaRecorder. El audio vive solo en memoria y se entrega una vez (PRIV-1).
// "recording" solo llega cuando el navegador confirma con `onstart`: la usuaria no habla antes de tiempo
// y `durationMs` se mide de `onstart` a `onstop`, sin incluir el retraso de abrir el micrófono.
export type MicStatus = "idle" | "preparing" | "recording" | "denied" | "unsupported"

export function useRecorder(onAudio: (audio: Blob, durationMs: number) => void, maxMs = MAX_RECORDING_MS) {
  const [status, setStatus] = useState<MicStatus>(
    typeof MediaRecorder === "undefined" ? "unsupported" : "idle",
  )
  const rec = useRef<MediaRecorder | null>(null)
  const startedAt = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const busy = useRef(false) // evita abrir el micrófono dos veces con un doble toque
  const cancelled = useRef(false)
  const confirmed = useRef(false) // llegó `onstart`
  const onAudioRef = useRef(onAudio)
  onAudioRef.current = onAudio

  const stop = useCallback(() => {
    if (!confirmed.current) cancelled.current = true // aún preparando: cancelar, no entregar
    clearTimeout(timer.current)
    if (rec.current?.state === "recording") rec.current.stop()
  }, [])

  const start = useCallback(async () => {
    if (busy.current || status === "unsupported") return
    busy.current = true
    cancelled.current = false
    confirmed.current = false
    const t0 = Date.now()
    setStatus("preparing")
    primeCue() // síncrono, dentro del gesto: el AudioContext puede sonar después
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      busy.current = false
      setStatus("denied")
      return
    }
    if (cancelled.current) {
      stream.getTracks().forEach((t) => t.stop())
      busy.current = false
      setStatus("idle")
      return
    }
    const chunks: Blob[] = []
    const r = new MediaRecorder(stream)
    r.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data) }
    r.onstart = () => {
      confirmed.current = true
      startedAt.current = Date.now()
      setStatus("recording")
      playCue()
      if (import.meta.env.DEV) console.info("[ezpay] mic-start-latency", startedAt.current - t0)
      timer.current = setTimeout(stop, maxMs) // tope de duración, contado desde `onstart`
    }
    r.onstop = () => {
      stream.getTracks().forEach((t) => t.stop()) // apaga el micrófono del equipo (PRIV-1)
      const took = confirmed.current
      busy.current = false
      rec.current = null
      confirmed.current = false
      if (!took) { // se canceló antes de `onstart`: no se entrega audio
        setStatus("idle")
        chunks.length = 0
        return
      }
      setStatus("idle")
      onAudioRef.current(new Blob(chunks, { type: r.mimeType }), Date.now() - startedAt.current)
      chunks.length = 0
    }
    rec.current = r
    r.start()
  }, [maxMs, status, stop])

  useEffect(() => stop, [stop]) // al desmontar, nunca queda el micrófono encendido

  return { status, start, stop }
}