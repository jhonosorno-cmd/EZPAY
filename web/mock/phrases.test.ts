import { describe, expect, it } from "vitest"
import { PIN_ATTEMPTS_EXHAUSTED, PIN_PROMPT, pinRetrySay } from "./phrases"

// Los textos se copian literales de api/voice/phrases.py (catálogo único de Voz).
describe("mock: textos de PIN", () => {
  it("pinRetrySay(2) usa el plural", () =>
    expect(pinRetrySay(2)).toBe("PIN incorrecto. Te quedan 2 intentos."))

  it("pinRetrySay(1) usa el singular del catálogo", () =>
    expect(pinRetrySay(1)).toBe("PIN incorrecto. Te queda 1 intento."))

  it("PIN_PROMPT es el del catálogo", () =>
    expect(PIN_PROMPT).toBe("Por seguridad, escribe tu PIN en el teclado."))

  it("el tercer fallo usa PIN_ATTEMPTS_EXHAUSTED", () =>
    expect(PIN_ATTEMPTS_EXHAUSTED).toBe("No pude verificarte. No envié nada."))
})