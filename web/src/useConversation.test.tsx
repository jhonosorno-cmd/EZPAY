import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { useConversation } from "./useConversation"

const turn = (state: string, extra = {}) =>
  new Response(JSON.stringify({ sessionId: "s_1", state, say: "x", transcript: null, interactUrl: null, options: null, payment: null, ...extra }))

beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(console, "log").mockImplementation(() => {})
  sessionStorage.clear()
})
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks() })

const sentBodies = (f: ReturnType<typeof vi.spyOn>) =>
  f.mock.calls.map((c: any[]) => Object.fromEntries((c[1].body as FormData).entries()))

describe("useConversation", () => {
  it("un turno a la vez: el doble toque manda una sola petición", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(async () => turn("AWAITING_PIN"))
    const { result } = renderHook(() => useConversation({ speak: async () => {} }))
    await act(async () => { result.current.sendText("envíale 20 mil"); result.current.sendText("envíale 20 mil") })
    expect(f).toHaveBeenCalledTimes(1)
  })

  it("guarda y reenvía el sessionId", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(async () => turn("AWAITING_CONFIRMATION"))
    const { result } = renderHook(() => useConversation({ speak: async () => {} }))
    await act(async () => { await result.current.sendText("hola") })
    await act(async () => { await result.current.sendText("sí") })
    expect(sentBodies(f)[1]).toMatchObject({ sessionId: "s_1", text: "sí" })
    expect(sessionStorage.getItem("ezpay.sessionId")).toBe("s_1")
  })

  it("PAYMENT_PENDING: una sola verificación a los 20 s con kind=verify_pending (B-2, D-1b)", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(async () => turn("PAYMENT_PENDING"))
    const { result } = renderHook(() => useConversation({ speak: async () => {} }))
    await act(async () => { await result.current.sendText("sí") })
    await act(async () => { await vi.advanceTimersByTimeAsync(20_000) })
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })
    expect(f).toHaveBeenCalledTimes(2)
    expect(sentBodies(f)[1]).toEqual({ sessionId: "s_1", kind: "verify_pending" })
  })

  it("PAYMENT_PENDING: si la usuaria habla antes, se cancela la verificación", async () => {
    const f = vi.spyOn(globalThis, "fetch")
      .mockImplementationOnce(async () => turn("PAYMENT_PENDING"))
      .mockImplementation(async () => turn("AWAITING_PIN"))
    const { result } = renderHook(() => useConversation({ speak: async () => {} }))
    await act(async () => { await result.current.sendText("sí") })
    await act(async () => { await result.current.sendText("envíale 10 mil") })
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })
    expect(f).toHaveBeenCalledTimes(2)
  })

  it("SESSION_NOT_FOUND borra la sesión y vuelve al inicio", async () => {
    sessionStorage.setItem("ezpay.sessionId", "viejo")
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "SESSION_NOT_FOUND", message: "" } }), { status: 404 }))
    const { result } = renderHook(() => useConversation({ speak: async () => {} }))
    await act(async () => { await result.current.sendText("hola") })
    expect(sessionStorage.getItem("ezpay.sessionId")).toBeNull()
    expect(result.current.view.state).toBe("AWAITING_COMMAND")
  })

  it("estado desconocido vuelve al inicio", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => turn("ALGO_NUEVO"))
    const { result } = renderHook(() => useConversation({ speak: async () => {} }))
    await act(async () => { await result.current.sendText("hola") })
    expect(result.current.view.state).toBe("AWAITING_COMMAND")
  })

  it("ante un error no queda la transcripción del turno anterior", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockImplementationOnce(async () => turn("PAYMENT_PENDING", { transcript: "sí" }))
      .mockResolvedValue(new Response(JSON.stringify({ error: { code: "INVALID_AUDIO", message: "" } }), { status: 400 }))
    const { result } = renderHook(() => useConversation({ speak: async () => {} }))
    await act(async () => { await result.current.sendText("sí") })
    await act(async () => { await result.current.sendText("x") })
    expect(result.current.view.transcript).toBeNull()
    expect(result.current.view.say).toBe("No pude escuchar bien. ¿Lo intentas de nuevo?")
  })
})
