import { describe, expect, it } from "vitest"
import { enrollmentReducer, initialEnrollment, type EnrollmentState } from "./enrollmentFlow"

const blob = () => new Blob(["x"])
const run = (...actions: Parameters<typeof enrollmentReducer>[1][]) =>
  actions.reduce<EnrollmentState>(enrollmentReducer, initialEnrollment)

const recordOk = (ms = 5000) => [
  { type: "START" } as const,
  { type: "RECORDED", blob: blob(), durationMs: ms } as const,
]

describe("enrollment-ui: consentimiento (PRIV-2)", () => {
  it("empieza sin aceptar", () => expect(initialEnrollment).toMatchObject({ step: "consent", accepted: false }))
  it("sin aceptar no se puede pasar a grabar", () =>
    expect(run({ type: "CONTINUE" }).step).toBe("consent"))
  it("aceptando, pasa a la primera muestra", () =>
    expect(run({ type: "TOGGLE_CONSENT" }, { type: "CONTINUE" })).toMatchObject({ step: "sample", index: 0, phase: "ready" }))
})

describe("enrollment-ui: tres muestras", () => {
  const ready = [{ type: "TOGGLE_CONSENT" }, { type: "CONTINUE" }] as const

  it("una muestra de menos de 3 s se rechaza y se vuelve a grabar", () => {
    const s = run(...ready, ...recordOk(2000))
    expect(s).toMatchObject({ step: "sample", index: 0, phase: "ready", tooShort: true })
    expect(s.samples).toHaveLength(0)
  })

  it("después de grabar se puede revisar: reproducir, repetir o usar", () =>
    expect(run(...ready, ...recordOk()).phase).toBe("review"))

  it("repetir pide confirmación y, si se confirma, vuelve a grabar la misma frase", () => {
    const asked = run(...ready, ...recordOk(), { type: "ASK_REPEAT" })
    expect(asked.phase).toBe("confirm-repeat")
    const back = enrollmentReducer(asked, { type: "CANCEL_REPEAT" })
    expect(back.phase).toBe("review")
    const again = enrollmentReducer(asked, { type: "CONFIRM_REPEAT" })
    expect(again).toMatchObject({ index: 0, phase: "ready", pending: null })
  })

  it("usar pasa a la frase siguiente y, con la tercera, a enviar", () => {
    const s = run(...ready,
      ...recordOk(), { type: "USE" },
      ...recordOk(), { type: "USE" },
      ...recordOk(), { type: "USE" })
    expect(s.step).toBe("sending")
    expect(s.samples).toHaveLength(3)
  })
})

describe("enrollment-ui: resultado (CONV-2)", () => {
  const sending = run({ type: "TOGGLE_CONSENT" }, { type: "CONTINUE" },
    ...recordOk(), { type: "USE" }, ...recordOk(), { type: "USE" }, ...recordOk(), { type: "USE" })

  it("éxito", () => expect(enrollmentReducer(sending, { type: "SUCCESS" }).step).toBe("done"))

  it("CONSENT_REQUIRED vuelve al consentimiento", () =>
    expect(enrollmentReducer(sending, { type: "FAILED", code: "CONSENT_REQUIRED" })).toMatchObject({ step: "consent", accepted: false }))

  for (const code of ["INVALID_AUDIO", "INCONSISTENT_SAMPLES", "SAMPLES_REQUIRED", "UPSTREAM_ERROR"]) {
    it(`${code} repite las tres muestras y no guarda nada`, () => {
      const s = enrollmentReducer(sending, { type: "FAILED", code })
      expect(s).toMatchObject({ step: "sample", index: 0, phase: "ready", error: code })
      expect(s.samples).toHaveLength(0)
    })
  }
})
