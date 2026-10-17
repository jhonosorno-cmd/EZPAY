// Señal corta de "Habla ahora": vibración si existe; si no, un tono muy corto y suave.
// Suena al llegar `onstart` del MediaRecorder. Es silenciosa para el oído en 60 ms y no
// cuenta como voz útil para el recorte de silencios del backend.
let ctx: AudioContext | null = null

/** Crea o reanuda el AudioContext dentro del gesto del usuario, para que pueda sonar después. */
export function primeCue(): void {
  const AC = window.AudioContext ?? (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!AC) return
  if (!ctx) ctx = new AC()
  if (ctx.state === "suspended") void ctx.resume()
}

/** Señal al confirmar el navegador: vibra 40 ms si hay vibración; si no, tono de 60 ms a 880 Hz. */
export function playCue(): void {
  if (typeof navigator.vibrate === "function") {
    navigator.vibrate(40)
    return
  }
  if (!ctx) return
  const t = ctx.currentTime
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.frequency.value = 880
  gain.gain.setValueAtTime(0.0001, t)
  gain.gain.exponentialRampToValueAtTime(0.05, t + 0.01)
  gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.06)
  osc.connect(gain).connect(ctx.destination)
  osc.start(t)
  osc.stop(t + 0.07)
}