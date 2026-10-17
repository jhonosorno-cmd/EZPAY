import { describe, expect, it } from "vitest"
import { CONSENT_CHECK, CONSENT_POINTS, PHRASES } from "./content"

// Los textos son definitivos de ML 2 (verificacion-ml2/textos-enrolamiento.md). Se copian tal cual.
describe("enrollment-ui: textos de ML 2", () => {
  it("no queda ningún marcador pendiente", () => {
    const all = [CONSENT_CHECK, ...CONSENT_POINTS, ...PHRASES].join(" ")
    expect(all).not.toContain("PENDIENTE")
    expect(all).not.toContain("[PENDIENTE ML 2]")
  })

  it("hay 3 frases", () => expect(PHRASES).toHaveLength(3))

  it("el consentimiento menciona el servicio externo", () =>
    expect(CONSENT_CHECK).toContain("servicio externo"))

  it("algún punto menciona el PIN como alternativa", () =>
    expect(CONSENT_POINTS.some((p) => p.includes("PIN"))).toBe(true))
})