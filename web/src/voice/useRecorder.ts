import { useCallback, useRef, useState } from "react"
import { MAX_RECORDING_MS, MIN_RECORDING_MS } from "../config"

// web-voice-io: push-to-talk con MediaRecorder. El audio vive solo en memoria y se entrega una vez (PRIV-1).
export type MicStatus = "idle" | "recording" | "denied" | "unsupported"

export function useRecorder(onAudio: (audio: Blob) => void) {
  const [status, setStatus] = useState<MicStatus>(
    typeof MediaRecorder === "undefined" ? "unsupported" : "idle",
  )
  const rec = useRef<MediaRecorder | null>(null)
  const startedAt = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const stop = useCallback(() => {
    clearTimeout(timer.current)
    if (rec.current?.state === "recording") rec.current.stop()
  }, [])

  const start = useCallback(async () => {
    if (status === "recording" || status === "unsupported") return
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
      stream.getTracks().forEach((t) => t.stop())
      setStatus("idle")
      const long = Date.now() - startedAt.current
      if (long >= MIN_RECORDING_MS) onAudio(new Blob(chunks, { type: r.mimeType }))
      chunks.length = 0 // no queda nada en memoria después de enviar
      rec.current = null
    }
    rec.current = r
    startedAt.current = Date.now()
    r.start()
    setStatus("recording")
    timer.current = setTimeout(stop, MAX_RECORDING_MS) // F-5: corta en 15 s
  }, [onAudio, status, stop])

  return { status, start, stop }
}
