import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError, getBudget, postTurn, postGrantCallback, messageFor } from "./client"

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
  it("GET /api/budget", async () => {
    const body = { status: "ACTIVE", limit: null, spent: null, remaining: null }
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(ok(body))
    vi.spyOn(console, "log").mockImplementation(() => {})
    expect(await getBudget()).toEqual(body)
    expect(f.mock.calls[0]![0]).toBe("/api/budget")
    expect(f.mock.calls[0]![1]!.method).toBe("GET")
  })
})
