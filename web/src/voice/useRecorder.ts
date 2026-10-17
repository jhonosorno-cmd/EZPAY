import { useCallback, useEffect, useRef, useState } from "react"
import { MAX_RECORDING_MS } from "../config"
import { playCue, primeCue } from "./cue"

// web-voice-io: grabación con MediaRecorder. El audio vive solo en memoria y se entrega una vez (PRIV-1).
// "recording" solo llega cuando el navegador confirma con `onstart`: la usuaria no habla antes de tiempo
// y `durationMs` se mide de `onstart` a `onstop`, sin incluir el retraso de abrir el micrófono.
// `keepOpen` (push-to-talk de la conversación): el stream queda abierto entre grabaciones, con las pistas
// desactivadas (sin captar audio), para que abrir el micrófono no se coma la primera palabra. Se cierra de
// verdad al desmontar o al ocultarse la pestaña. Sin `keepOpen` (enrolamiento) se apaga al detener (PRIV-1).
export type MicStatus = "idle" | "preparing" | "recording" | "denied" | "unsupported"

export function useRecorder(
  onAudio: (audio: Blob, durationMs: number) => void,
  maxMs = MAX_RECORDING_MS,
  keepOpen = false,
) {
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
  const warm = useRef<MediaStream | null>(null) // stream abierto entre grabaciones (solo con keepOpen)

  // Con keepOpen las pistas se desactivan (silencio) en vez de cerrarse; si no, se cierran.
  const idle = useCallback((stream: MediaStream) => {
    if (keepOpen && warm.current === stream) stream.getTracks().forEach((t) => { t.enabled = false })
    else stream.getTracks().forEach((t) => t.stop()) // apaga el micrófono del equipo (PRIV-1)
  }, [keepOpen])

  const close = useCallback(() => {
    warm.current?.getTracks().forEach((t) => t.stop())
    warm.current = null
  }, [])

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
      const reusable = keepOpen && warm.current?.getTracks().every((t) => t.readyState !== "ended")
      if (reusable && warm.current) stream = warm.current
      else {
        close() // pistas terminadas (micrófono desconectado): se pide de nuevo
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        if (keepOpen) warm.current = stream
      }
    } catch {
      busy.current = false
      setStatus("denied")
      return
    }
    if (cancelled.current) {
      idle(stream)
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
      idle(stream)
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
    stream.getTracks().forEach((t) => { t.enabled = true })
    r.start()
  }, [maxMs, status, stop, keepOpen, idle, close])

  useEffect(() => () => { stop(); close() }, [stop, close]) // al desmontar, nunca queda el micrófono encendido

  useEffect(() => { // pestaña oculta: no se deja el micrófono abierto en segundo plano
    if (!keepOpen) return
    const onHide = () => { if (document.hidden) { stop(); close() } }
    document.addEventListener("visibilitychange", onHide)
    return () => document.removeEventListener("visibilitychange", onHide)
  }, [keepOpen, stop, close])

  return { status, start, stop }
}