// Flujo del registro de voz (enrollment-ui + casos de uso preliminares de ML 2).
// Las muestras viven solo en memoria hasta el único POST /api/enrollment (PRIV-1).
export const SAMPLES = 3
export const MIN_SAMPLE_MS = 3_000 // enrollment-ui: entre 3 y 15 s

type Phase = "ready" | "recording" | "review" | "confirm-repeat"

export type EnrollmentState = {
  step: "consent" | "sample" | "sending" | "done"
  accepted: boolean
  index: number // frase actual, 0..2
  phase: Phase
  pending: Blob | null // la grabación que se está revisando
  samples: Blob[]
  tooShort: boolean
  error: string | null // último ErrorCode del servidor
}

export type EnrollmentAction =
  | { type: "TOGGLE_CONSENT" }
  | { type: "CONTINUE" }
  | { type: "START" }
  | { type: "RECORDED"; blob: Blob; durationMs: number }
  | { type: "ASK_REPEAT" }
  | { type: "CANCEL_REPEAT" }
  | { type: "CONFIRM_REPEAT" }
  | { type: "USE" }
  | { type: "SUCCESS" }
  | { type: "FAILED"; code: string }

export const initialEnrollment: EnrollmentState = {
  step: "consent", accepted: false, index: 0, phase: "ready", pending: null, samples: [], tooShort: false, error: null,
}

const restartSamples = (s: EnrollmentState, error: string | null): EnrollmentState =>
  ({ ...s, step: "sample", index: 0, phase: "ready", pending: null, samples: [], tooShort: false, error })

export function enrollmentReducer(s: EnrollmentState, a: EnrollmentAction): EnrollmentState {
  switch (a.type) {
    case "TOGGLE_CONSENT":
      return s.step === "consent" ? { ...s, accepted: !s.accepted } : s
    case "CONTINUE":
      return s.step === "consent" && s.accepted ? restartSamples(s, null) : s
    case "START":
      return s.step === "sample" && s.phase === "ready" ? { ...s, phase: "recording", tooShort: false, error: null } : s
    case "RECORDED":
      if (s.phase !== "recording") return s
      if (a.durationMs < MIN_SAMPLE_MS) return { ...s, phase: "ready", tooShort: true }
      return { ...s, phase: "review", pending: a.blob }
    case "ASK_REPEAT":
      return s.phase === "review" ? { ...s, phase: "confirm-repeat" } : s
    case "CANCEL_REPEAT":
      return s.phase === "confirm-repeat" ? { ...s, phase: "review" } : s
    case "CONFIRM_REPEAT":
      return s.phase === "confirm-repeat" ? { ...s, phase: "ready", pending: null } : s
    case "USE": {
      if (s.phase !== "review" || !s.pending) return s
      const samples = [...s.samples, s.pending]
      if (samples.length === SAMPLES) return { ...s, step: "sending", samples, pending: null }
      return { ...s, index: s.index + 1, phase: "ready", pending: null, samples }
    }
    case "SUCCESS":
      return { ...initialEnrollment, step: "done", accepted: true } // las muestras se sueltan
    case "FAILED":
      if (a.code === "CONSENT_REQUIRED") return { ...initialEnrollment, error: a.code }
      if (a.code === "SAMPLES_REQUIRED") console.error("[ezpay] SAMPLES_REQUIRED: error de programación")
      return restartSamples(s, a.code)
  }
}
