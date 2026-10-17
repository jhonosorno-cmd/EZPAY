import { useEffect, useReducer, useRef, useState } from "react"
import { ApiError, messageFor, postEnrollment } from "../api/client"
import { speak, stopSpeaking, unlockAudio } from "../voice/tts"
import { useRecorder } from "../voice/useRecorder"
import { CONSENT_CHECK, CONSENT_POINTS, CONSENT_TITLE, PHRASES } from "./content"
import { enrollmentReducer, initialEnrollment, MIN_SAMPLE_MS, SAMPLES } from "./enrollmentFlow"

const ERROR_SAY: Record<string, string> = {
  INVALID_AUDIO: "No pude escuchar bien las grabaciones. Busca un lugar sin ruido y grabemos las tres otra vez.",
  INCONSISTENT_SAMPLES: "Las tres grabaciones tienen que ser de la misma persona. Grabemos otra vez.",
}

// enrollment-ui: consentimiento → tres frases (tocar para grabar / tocar para parar) → un único POST.
export function Enrollment({ onClose }: { onClose: (enrolled: boolean) => void }) {
  const [s, dispatch] = useReducer(enrollmentReducer, initialEnrollment)
  const rec = useRecorder((blob, durationMs) => dispatch({ type: "RECORDED", blob, durationMs }))
  const playUrl = usePlayback(s.pending)
  const phrase = PHRASES[s.index] ?? ""

  // Lo que se dice en voz alta en cada paso
  useEffect(() => {
    if (s.step === "consent") void speak(`${CONSENT_TITLE}. ${CONSENT_POINTS.join(" ")}`)
    if (s.step === "done") void speak("Tu voz quedó registrada.")
  }, [s.step])
  useEffect(() => {
    if (s.step !== "sample" || s.phase !== "ready") return
    const pre = s.error ? `${ERROR_SAY[s.error] ?? messageFor(s.error)} ` : s.tooShort ? "Fue muy corto. " : ""
    void speak(`${pre}Frase ${s.index + 1} de ${SAMPLES}. Toca grabar y lee en voz alta: ${phrase}`)
  }, [s.step, s.phase, s.index, s.tooShort, s.error, phrase])

  // Envío único de las tres muestras
  useEffect(() => {
    if (s.step !== "sending") return
    postEnrollment(s.samples)
      .then((r) => dispatch(r.enrolled ? { type: "SUCCESS" } : { type: "FAILED", code: "INTERNAL_ERROR" }))
      .catch((e) => dispatch({ type: "FAILED", code: e instanceof ApiError ? e.code : "UNKNOWN" }))
  }, [s.step, s.samples])

  const startRecording = () => {
    unlockAudio()
    stopSpeaking() // nunca grabar mientras habla el TTS
    dispatch({ type: "START" })
    void rec.start()
  }

  return (
    <div className="app">
      <header className="topbar enroll-top">
        <button className="back" onClick={() => onClose(false)} aria-label="Volver">←</button>
        <p className="brand">REGISTRO DE VOZ</p>
        <span />
      </header>
      <main className="content">
        {s.step === "consent" && (
          <section className="panel">
            <h2>{CONSENT_TITLE}</h2>
            <ul className="consent-list">{CONSENT_POINTS.map((p) => <li key={p}>{p}</li>)}</ul>
            {s.error === "CONSENT_REQUIRED" && <p className="warn">Necesito que aceptes para continuar.</p>}
            <label className="check">
              <input type="checkbox" checked={s.accepted} onChange={() => dispatch({ type: "TOGGLE_CONSENT" })} />
              <span>{CONSENT_CHECK}</span>
            </label>
            <button className="pill pill-primary" disabled={!s.accepted} onClick={() => dispatch({ type: "CONTINUE" })}>
              Continuar
            </button>
          </section>
        )}

        {s.step === "sample" && (
          <>
            <div className="steps" aria-label={`Frase ${s.index + 1} de ${SAMPLES}`}>
              {PHRASES.map((_, i) => <span key={i} className={i < s.index ? "done" : i === s.index ? "now" : ""} />)}
            </div>
            <article className="say-card">
              <p className="say-label">Frase {s.index + 1} de {SAMPLES} · léela en voz alta</p>
              <p className="say">“{phrase}”</p>
            </article>
            {s.tooShort && <p className="warn">Fue muy corto. Graba al menos {MIN_SAMPLE_MS / 1000} segundos.</p>}
            {s.error && <p className="warn">{ERROR_SAY[s.error] ?? messageFor(s.error)}</p>}
            {rec.status === "denied" && <p className="warn">No tengo permiso para el micrófono. Actívalo en el navegador.</p>}

            {s.phase === "ready" && (
              <button className="pill pill-primary rec" onClick={startRecording} disabled={rec.status === "unsupported"}>
                ● Iniciar grabación
              </button>
            )}
            {s.phase === "recording" && (
              <button className="pill rec recording" onClick={rec.stop}>■ Detener grabación</button>
            )}
            {s.phase === "review" && (
              <div className="review">
                {playUrl && <PlayButton url={playUrl} />}
                <button className="pill pill-light" onClick={() => dispatch({ type: "ASK_REPEAT" })}>↺ Repetir grabación</button>
                <button className="pill pill-primary" onClick={() => dispatch({ type: "USE" })}>✓ Usar grabación</button>
              </div>
            )}
            {s.phase === "confirm-repeat" && (
              <section className="panel">
                <p className="confirm-q">¿Seguro que quieres grabar esta frase otra vez?</p>
                <div className="row">
                  <button className="pill pill-primary" onClick={() => dispatch({ type: "CONFIRM_REPEAT" })}>Sí, repetir</button>
                  <button className="pill pill-light" onClick={() => dispatch({ type: "CANCEL_REPEAT" })}>No</button>
                </div>
              </section>
            )}
          </>
        )}

        {s.step === "sending" && <article className="say-card"><p className="say">Registrando tu voz…</p></article>}

        {s.step === "done" && (
          <section className="panel center">
            <p className="ok-badge big-ok">✓</p>
            <h2>Tu voz quedó registrada</h2>
            <button className="pill pill-primary" onClick={() => onClose(true)}>Aceptar</button>
          </section>
        )}
      </main>
    </div>
  )
}

function PlayButton({ url }: { url: string }) {
  const audio = useRef<HTMLAudioElement | null>(null)
  const [playing, setPlaying] = useState(false)
  return (
    <>
      <audio ref={audio} src={url} onEnded={() => setPlaying(false)} onPause={() => setPlaying(false)} />
      <button className="pill pill-light" onClick={() => {
        if (!audio.current) return
        if (playing) { audio.current.pause(); return }
        stopSpeaking(); void audio.current.play(); setPlaying(true)
      }}>
        {playing ? "■ Detener" : "▶ Reproducir grabación"}
      </button>
    </>
  )
}

/** URL temporal para escuchar la muestra; se libera al cambiar o desmontar (el audio no se guarda). */
function usePlayback(blob: Blob | null) {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!blob) { setUrl(null); return }
    const u = URL.createObjectURL(blob)
    setUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [blob])
  return url
}
