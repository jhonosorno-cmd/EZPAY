// web-voice-io: TTS del navegador (Web Speech API), voz en español.
let unlocked = false
let speaking = false
const listeners = new Set<(s: boolean) => void>()
const setSpeaking = (s: boolean) => { speaking = s; listeners.forEach((l) => l(s)) }

export const isSpeaking = () => speaking
export function onSpeakingChange(l: (s: boolean) => void) { listeners.add(l); return () => { listeners.delete(l) } }

function pickVoice(): SpeechSynthesisVoice | undefined {
  const voices = speechSynthesis.getVoices()
  return voices.find((v) => v.lang === "es-CO") ?? voices.find((v) => v.lang.startsWith("es-419"))
    ?? voices.find((v) => v.lang.startsWith("es"))
}

/** Los navegadores bloquean el audio hasta un gesto. Llamar desde un onClick. */
export function unlockAudio() {
  if (unlocked || typeof speechSynthesis === "undefined") return
  speechSynthesis.speak(new SpeechSynthesisUtterance(""))
  unlocked = true
}
export const isAudioUnlocked = () => unlocked

export function speak(text: string): Promise<void> {
  if (typeof speechSynthesis === "undefined" || !text) return Promise.resolve()
  return new Promise((resolve) => {
    speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    const voice = pickVoice()
    if (voice) u.voice = voice
    u.lang = voice?.lang ?? "es-CO"
    u.rate = 0.9 // un poco más lento para la usuaria
    const done = () => { setSpeaking(false); resolve() }
    u.onend = done
    u.onerror = done
    setSpeaking(true)
    speechSynthesis.speak(u)
  })
}

export function stopSpeaking() {
  if (typeof speechSynthesis !== "undefined") speechSynthesis.cancel()
  setSpeaking(false)
}
