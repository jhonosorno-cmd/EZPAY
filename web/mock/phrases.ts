// Textos del PIN que dice el mock del Contrato B. Copiados LITERALES del catálogo único de Voz
// (api/voice/phrases.py: PIN_KEYBOARD, PIN_WRONG, PIN_WRONG_ONE, PIN_ATTEMPTS_EXHAUSTED).
// No se reescriben a mano: si cambian, se vuelven a copiar del catálogo.
export const PIN_PROMPT = "Por seguridad, escribe tu PIN en el teclado."

export const pinRetrySay = (n: number): string =>
  n === 1 ? "PIN incorrecto. Te queda 1 intento." : `PIN incorrecto. Te quedan ${n} intentos.`

export const PIN_ATTEMPTS_EXHAUSTED = "No pude verificarte. No envié nada."