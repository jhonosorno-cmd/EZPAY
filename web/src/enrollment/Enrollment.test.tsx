import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Enrollment } from "./Enrollment"
import { useRecorder } from "../voice/useRecorder"
import { CONSENT_CHECK } from "./content"

vi.mock("../voice/useRecorder")
vi.mock("../voice/tts", () => ({
  speak: vi.fn(),
  stopSpeaking: vi.fn(),
  unlockAudio: vi.fn(),
  isSpeaking: () => false,
  onSpeakingChange: () => () => {},
}))
vi.mock("../api/client", () => ({
  ApiError: class extends Error {},
  messageFor: (c: string) => c,
  postEnrollment: vi.fn(async () => ({ enrolled: true })),
}))

describe("Enrollment", () => {
  afterEach(() => cleanup())

  it("consentimiento, continuar e iniciar grabación", async () => {
    const start = vi.fn()
    vi.mocked(useRecorder).mockReturnValue({ status: "idle", start, stop: vi.fn() } as never)
    render(<Enrollment onClose={() => {}} />)
    screen.getByLabelText(CONSENT_CHECK).click()
    screen.getByRole("button", { name: "Continuar" }).click()
    const init = await screen.findByText("● Iniciar grabación")
    init.click()
    expect(start).toHaveBeenCalled()
  })

  it("con el micrófono preparándose el botón está deshabilitado y no muestra Habla ahora", async () => {
    vi.mocked(useRecorder).mockImplementation(() => ({ status: "preparing", start: vi.fn(), stop: vi.fn() } as never))
    render(<Enrollment onClose={() => {}} />)
    screen.getByLabelText(CONSENT_CHECK).click()
    screen.getByRole("button", { name: "Continuar" }).click()
    ;(await screen.findByText("● Iniciar grabación")).click()
    const b = (await screen.findByRole("button", { name: "Preparando el micrófono…" })) as HTMLButtonElement
    expect(b.disabled).toBe(true)
    expect(screen.queryByText("Habla ahora")).toBeNull()
  })

  it("Habla ahora aparece solo cuando el navegador confirmó con onstart", async () => {
    vi.mocked(useRecorder).mockImplementation(() => ({ status: "recording", start: vi.fn(), stop: vi.fn() } as never))
    render(<Enrollment onClose={() => {}} />)
    screen.getByLabelText(CONSENT_CHECK).click()
    screen.getByRole("button", { name: "Continuar" }).click()
    ;(await screen.findByText("● Iniciar grabación")).click()
    const b = await screen.findByRole("button", { name: "■ Detener grabación" })
    expect(b).toBeDefined()
    expect(screen.getByText("Habla ahora")).toBeDefined()
  })
})