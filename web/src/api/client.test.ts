import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError, getBudget, getEnrollment, postEnrollment, postTurn, postGrantCallback, messageFor } from "./client"

const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200 })
const fail = (status: number, code: string, message = "x") =>
  new Response(JSON.stringify({ error: { code, message } }), { status })

afterEach(() => vi.restoreAllMocks())

describe("postTurn", () => {
  it("manda text, sessionId y un X-Request-Id nuevo por llamada", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(async () => ok({ sessionId: "s_1", state: "AWAITING_COMMAND" }))
    await postTurn({ text: "hola", sessionId: "s_0" })
    await postTurn({ text: "hola" })
    const [url, init] = f.mock.calls[0]!
    expect(url).toBe("/api/turns")
    const form = (init as RequestInit).body as FormData
    expect(form.get("text")).toBe("hola")
    expect(form.get("sessionId")).toBe("s_0")
    const ids = f.mock.calls.map((c) => ((c[1] as RequestInit).headers as Record<string, string>)["X-Request-Id"])
    expect(ids[0]).toBeTruthy()
    expect(ids[0]).not.toBe(ids[1])
    expect((f.mock.calls[1]![1]!.body as FormData).has("sessionId")).toBe(false)
  })

  it("decide por error.code, no por message", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(fail(400, "INVALID_AUDIO", "texto raro"))
    const e = await postTurn({ text: "x" }).catch((x) => x)
    expect(e).toBeInstanceOf(ApiError)
    expect(e.code).toBe("INVALID_AUDIO")
    expect(messageFor("INVALID_AUDIO")).toBe("No pude escuchar bien. ¿Lo intentas de nuevo?")
  })

  it("código desconocido → mensaje genérico", () =>
    expect(messageFor("NOPE")).toBe("Algo falló. Intenta de nuevo"))

  it("no escribe el cuerpo en la consola (PRIV-4)", async () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {})
    vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ sessionId: "s", state: "AWAITING_PIN", say: "secreto" }))
    await postTurn({ text: "1234" })
    expect(JSON.stringify(log.mock.calls)).not.toContain("1234")
  })
})

describe("postGrantCallback", () => {
  it("reenvía solo lo que vino, sin descartar ni validar", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok({ sessionId: "s", state: "REJECTED" }))
    await postGrantCallback({ result: "grant_rejected" })
    expect(JSON.parse(f.mock.calls[0]![1]!.body as string)).toEqual({ result: "grant_rejected" })
  })
})

describe("getBudget", () => {
  it("GET /api/budget con la forma del contrato (limit = { debitAmount, interval })", async () => {
    const cop = (value: string) => ({ value, assetCode: "COP", assetScale: 2 })
    const body = { status: "ACTIVE", limit: { debitAmount: cop("20000000"), interval: "R52/2026-10-16T00:00:00Z/P1W" },
      spent: cop("2015000"), remaining: cop("17985000") }
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(body))
    vi.spyOn(console, "log").mockImplementation(() => {})
    expect(await getBudget()).toEqual(body)
    expect(f.mock.calls[0]![0]).toBe("/api/budget")
    expect(f.mock.calls[0]![1]!.method).toBe("GET")
  })
})

describe("catálogo de errores", () => {
  it("cada código del contrato tiene su mensaje en español", () => {
    const codes = ["CONSENT_REQUIRED", "SAMPLES_REQUIRED", "INVALID_AUDIO", "INCONSISTENT_SAMPLES",
      "AUDIO_OR_TEXT_REQUIRED", "AUDIO_TOO_LONG", "SESSION_NOT_FOUND", "INVALID_AMOUNT", "UPSTREAM_ERROR", "INTERNAL_ERROR"]
    for (const c of codes) expect(messageFor(c), c).not.toBe("Algo falló. Intenta de nuevo")
  })
})

describe("enrollment (B-5)", () => {
  it("POST con tres campos audio y consent=true", async () => {
    vi.spyOn(console, "log").mockImplementation(() => {})
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ enrolled: true }), { status: 201 }))
    const blobs = [new Blob(["a"]), new Blob(["b"]), new Blob(["c"])]
    expect(await postEnrollment(blobs)).toEqual({ enrolled: true })
    const [url, init] = f.mock.calls[0]!
    expect(url).toBe("/api/enrollment")
    const form = init!.body as FormData
    expect(form.getAll("audio")).toHaveLength(3)
    expect(form.get("consent")).toBe("true")
  })
  it("GET /api/enrollment", async () => {
    vi.spyOn(console, "log").mockImplementation(() => {})
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ enrolled: false })))
    expect(await getEnrollment()).toEqual({ enrolled: false })
  })
})
