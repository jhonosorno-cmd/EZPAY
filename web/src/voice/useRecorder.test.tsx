import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { useRecorder } from "./useRecorder"
import { playCue } from "./cue"

vi.mock("./cue", () => ({ primeCue: vi.fn(), playCue: vi.fn() }))

// Recorder simulado: `start()` no dispara `onstart` por sí solo; la prueba lo hace a mano.
class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = []
  state = "inactive"
  mimeType = "audio/webm"
  onstart: (() => void) | null = null
  onstop: (() => void) | null = null
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  constructor(public stream: { getTracks: () => FakeTrack[] }) {
    FakeMediaRecorder.instances.push(this)
  }
  start() { this.state = "recording" }
  stop() { this.state = "inactive"; this.onstop?.() }
}

type Deferred<T> = { promise: Promise<T>; resolve: (v: T) => void }

const deferred = <T,>(): Deferred<T> => {
  let resolve!: (v: T) => void
  return { promise: new Promise<T>((r) => (resolve = r)), resolve }
}

type FakeTrack = { stop: ReturnType<typeof vi.fn>; enabled: boolean; readyState: string }

const fakeStream = () => {
  const tracks: FakeTrack[] = [vi.fn(), vi.fn()].map((stop) => ({ stop, enabled: true, readyState: "live" }))
  return { getTracks: () => tracks }
}

beforeEach(() => {
  vi.useFakeTimers()
  FakeMediaRecorder.instances = []
  vi.stubGlobal("MediaRecorder", FakeMediaRecorder as unknown as typeof MediaRecorder)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const userMedia = (impl: () => Promise<MediaStream>) =>
  vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia: vi.fn(impl) }, vibrate: undefined })

const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve() }) }

describe("useRecorder", () => {
  it("1: toque con getUserMedia pendiente queda en preparing, nunca recording", async () => {
    const g = deferred<MediaStream>()
    userMedia(() => g.promise)
    const { result } = renderHook(() => useRecorder(vi.fn()))
    await act(async () => { void result.current.start() })
    await flush()
    expect(result.current.status).toBe("preparing")
  })

  it("2: tras r.start() y sin onstart sigue en preparing", async () => {
    const stream = fakeStream()
    userMedia(() => Promise.resolve(stream as unknown as MediaStream))
    const { result } = renderHook(() => useRecorder(vi.fn()))
    await act(async () => { void result.current.start() })
    await flush()
    expect(result.current.status).toBe("preparing")
  })

  it("3: onstart pasa a recording y llama a playCue", async () => {
    userMedia(() => Promise.resolve(fakeStream() as unknown as MediaStream))
    const { result } = renderHook(() => useRecorder(vi.fn()))
    await act(async () => { void result.current.start() })
    await flush()
    await act(async () => { FakeMediaRecorder.instances[0]!.onstart?.() })
    expect(result.current.status).toBe("recording")
    expect(playCue).toHaveBeenCalled()
  })

  it("4: durationMs se mide desde onstart, no desde el toque", async () => {
    const stream = fakeStream()
    userMedia(() => new Promise<MediaStream>((resolve) => {
      setTimeout(() => resolve(stream as unknown as MediaStream), 400)
    }))
    const onAudio = vi.fn()
    const { result } = renderHook(() => useRecorder(onAudio))
    await act(async () => { void result.current.start() })
    await act(async () => { vi.advanceTimersByTime(400); await Promise.resolve() })
    await act(async () => { FakeMediaRecorder.instances[0]!.onstart?.() })
    await act(async () => { vi.advanceTimersByTime(3000) })
    await act(async () => { result.current.stop() })
    expect(onAudio).toHaveBeenCalledTimes(1)
    expect(onAudio.mock.calls[0]![1]).toBe(3000)
  })

  it("5: al parar se detienen todas las pistas", async () => {
    const stream = fakeStream()
    userMedia(() => Promise.resolve(stream as unknown as MediaStream))
    const { result } = renderHook(() => useRecorder(vi.fn()))
    await act(async () => { void result.current.start() })
    await flush()
    await act(async () => { FakeMediaRecorder.instances[0]!.onstart?.() })
    await act(async () => { result.current.stop() })
    for (const t of stream.getTracks()) expect(t.stop).toHaveBeenCalled()
  })

  it("6: stop durante preparing detiene pistas, no entrega audio y vuelve a idle", async () => {
    const stream = fakeStream()
    userMedia(() => Promise.resolve(stream as unknown as MediaStream))
    const onAudio = vi.fn()
    const { result } = renderHook(() => useRecorder(onAudio))
    await act(async () => { void result.current.start() })
    await flush()
    await act(async () => { result.current.stop() })
    expect(onAudio).not.toHaveBeenCalled()
    expect(result.current.status).toBe("idle")
    for (const t of stream.getTracks()) expect(t.stop).toHaveBeenCalled()
  })

  it("7: doble start mientras prepara abre getUserMedia una sola vez", async () => {
    const stream = fakeStream()
    const g = vi.fn(() => Promise.resolve(stream as unknown as MediaStream))
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia: g }, vibrate: undefined })
    const { result } = renderHook(() => useRecorder(vi.fn()))
    await act(async () => { void result.current.start(); void result.current.start() })
    await flush()
    expect(g).toHaveBeenCalledTimes(1)
  })

  it("8: el tope de 15 s se cuenta desde onstart", async () => {
    userMedia(() => Promise.resolve(fakeStream() as unknown as MediaStream))
    const onAudio = vi.fn()
    const { result } = renderHook(() => useRecorder(onAudio, 15_000))
    await act(async () => { void result.current.start() })
    await flush()
    await act(async () => { vi.advanceTimersByTime(2_000) }) // 2 s preparando no cuentan
    await act(async () => { FakeMediaRecorder.instances[0]!.onstart?.() })
    await act(async () => { vi.advanceTimersByTime(14_999) })
    expect(onAudio).not.toHaveBeenCalled()
    await act(async () => { vi.advanceTimersByTime(1) })
    expect(onAudio).toHaveBeenCalledTimes(1)
  })

  it("9: en DEV registra la latencia en ms y nunca un Blob", async () => {
    userMedia(() => Promise.resolve(fakeStream() as unknown as MediaStream))
    const info = vi.spyOn(console, "info").mockImplementation(() => {})
    const { result } = renderHook(() => useRecorder(vi.fn()))
    await act(async () => { void result.current.start() })
    await flush()
    await act(async () => { FakeMediaRecorder.instances[0]!.onstart?.() })
    expect(info).toHaveBeenCalledWith("[ezpay] mic-start-latency", expect.any(Number))
    for (const call of info.mock.calls) for (const a of call) expect(a).not.toBeInstanceOf(Blob)
  })

  it("10: permiso negado pasa a denied", async () => {
    userMedia(() => Promise.reject(new Error("denied")))
    const { result } = renderHook(() => useRecorder(vi.fn()))
    await act(async () => { void result.current.start() })
    await flush()
    expect(result.current.status).toBe("denied")
  })

  // Micrófono abierto entre grabaciones (keepOpen): la primera palabra ya no se pierde al abrirlo.
  describe("keepOpen", () => {
    const record = async (result: { current: ReturnType<typeof useRecorder> }, n: number) => {
      await act(async () => { void result.current.start() })
      await flush()
      await act(async () => { FakeMediaRecorder.instances[n]!.onstart?.() })
    }

    it("11: al parar deja las pistas abiertas pero desactivadas (sin captar audio)", async () => {
      const stream = fakeStream()
      userMedia(() => Promise.resolve(stream as unknown as MediaStream))
      const { result } = renderHook(() => useRecorder(vi.fn(), 15_000, true))
      await record(result, 0)
      expect(stream.getTracks().every((t) => t.enabled)).toBe(true)
      await act(async () => { result.current.stop() })
      for (const t of stream.getTracks()) {
        expect(t.stop).not.toHaveBeenCalled()
        expect(t.enabled).toBe(false)
      }
    })

    it("12: la segunda grabación reutiliza el stream: getUserMedia se llama una sola vez", async () => {
      const stream = fakeStream()
      const g = vi.fn(() => Promise.resolve(stream as unknown as MediaStream))
      vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia: g }, vibrate: undefined })
      const onAudio = vi.fn()
      const { result } = renderHook(() => useRecorder(onAudio, 15_000, true))
      await record(result, 0)
      await act(async () => { result.current.stop() })
      await record(result, 1)
      expect(g).toHaveBeenCalledTimes(1)
      expect(stream.getTracks().every((t) => t.enabled)).toBe(true)
      await act(async () => { result.current.stop() })
      expect(onAudio).toHaveBeenCalledTimes(2)
    })

    it("13: stop durante preparing no entrega audio y deja el stream desactivado, no cerrado", async () => {
      const stream = fakeStream()
      userMedia(() => Promise.resolve(stream as unknown as MediaStream))
      const onAudio = vi.fn()
      const { result } = renderHook(() => useRecorder(onAudio, 15_000, true))
      await act(async () => { void result.current.start() })
      await flush()
      await act(async () => { result.current.stop() })
      expect(onAudio).not.toHaveBeenCalled()
      expect(result.current.status).toBe("idle")
      for (const t of stream.getTracks()) {
        expect(t.stop).not.toHaveBeenCalled()
        expect(t.enabled).toBe(false)
      }
    })

    it("14: al desmontar se detienen todas las pistas", async () => {
      const stream = fakeStream()
      userMedia(() => Promise.resolve(stream as unknown as MediaStream))
      const { result, unmount } = renderHook(() => useRecorder(vi.fn(), 15_000, true))
      await record(result, 0)
      await act(async () => { result.current.stop() })
      unmount()
      for (const t of stream.getTracks()) expect(t.stop).toHaveBeenCalled()
    })

    it("15: si la pestaña se oculta se cierra el micrófono y la siguiente grabación lo reabre", async () => {
      const stream = fakeStream()
      const g = vi.fn(() => Promise.resolve(stream as unknown as MediaStream))
      vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia: g }, vibrate: undefined })
      const { result } = renderHook(() => useRecorder(vi.fn(), 15_000, true))
      await record(result, 0)
      await act(async () => { result.current.stop() })
      Object.defineProperty(document, "hidden", { configurable: true, value: true })
      await act(async () => { document.dispatchEvent(new Event("visibilitychange")) })
      for (const t of stream.getTracks()) expect(t.stop).toHaveBeenCalled()
      Object.defineProperty(document, "hidden", { configurable: true, value: false })
      await record(result, 1)
      expect(g).toHaveBeenCalledTimes(2)
    })

    it("16: un stream con pistas terminadas (micrófono desconectado) se vuelve a pedir", async () => {
      const first = fakeStream()
      const second = fakeStream()
      const g = vi.fn().mockResolvedValueOnce(first).mockResolvedValueOnce(second)
      vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia: g }, vibrate: undefined })
      const { result } = renderHook(() => useRecorder(vi.fn(), 15_000, true))
      await record(result, 0)
      await act(async () => { result.current.stop() })
      for (const t of first.getTracks()) t.readyState = "ended"
      await record(result, 1)
      expect(g).toHaveBeenCalledTimes(2)
    })

    it("17: sin keepOpen (enrolamiento) sigue apagando el micrófono al parar", async () => {
      const stream = fakeStream()
      userMedia(() => Promise.resolve(stream as unknown as MediaStream))
      const { result } = renderHook(() => useRecorder(vi.fn()))
      await record(result, 0)
      await act(async () => { result.current.stop() })
      for (const t of stream.getTracks()) expect(t.stop).toHaveBeenCalled()
    })
  })
})
