import { cleanup, render, screen, fireEvent } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { MicButton } from "./MicButton"
import { useRecorder } from "../voice/useRecorder"

vi.mock("../voice/useRecorder")
vi.mock("../voice/tts", () => ({ isSpeaking: () => false, onSpeakingChange: () => () => {}, stopSpeaking: vi.fn(), unlockAudio: vi.fn(), speak: vi.fn() }))

let status: string
const start = vi.fn()
const stop = vi.fn()

beforeEach(() => {
  vi.mocked(useRecorder).mockImplementation(() => ({ status: status as never, start, stop } as never))
  start.mockClear()
  stop.mockClear()
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

it("en preparing muestra Preparando el micrófono y aria-disabled", () => {
  status = "preparing"
  render(<MicButton disabled={false} onAudio={vi.fn()} />)
  const b = screen.getByRole("button")
  expect(b.textContent).toContain("Preparando el micrófono…")
  expect(b.getAttribute("aria-disabled")).toBe("true")
})

it("tras onstart muestra Habla ahora", () => {
  status = "recording"
  render(<MicButton disabled={false} onAudio={vi.fn()} />)
  const b = screen.getByLabelText("Mantén presionado para hablar")
  expect(b.textContent).toContain("Habla ahora")
})

it("soltar durante preparing llama a stop para cancelar", () => {
  status = "preparing"
  render(<MicButton disabled={false} onAudio={vi.fn()} />)
  const b = screen.getByLabelText("Mantén presionado para hablar")
  fireEvent.pointerDown(b, { pointerId: 1 })
  fireEvent.pointerUp(b, { pointerId: 1 })
  expect(stop).toHaveBeenCalled()
})