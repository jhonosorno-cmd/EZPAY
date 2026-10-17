import { describe, expect, it } from "vitest"
import { readCallbackParams } from "./callback"

describe("readCallbackParams (wallet-handoff)", () => {
  it("aprobación", () =>
    expect(readCallbackParams("?interact_ref=abc&hash=xyz")).toEqual({ interactRef: "abc", hash: "xyz" }))
  it("rechazo", () =>
    expect(readCallbackParams("?result=grant_rejected")).toEqual({ result: "grant_rejected" }))
  it("sin parámetros igual se envía (Python responde REJECTED)", () =>
    expect(readCallbackParams("")).toEqual({}))
})
