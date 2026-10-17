import { beforeEach, describe, expect, it } from "vitest"
import { addRecent, loadRecent } from "./recent"

const p = (id: string) => ({
  paymentId: id, receiver: "https://ilp.interledger-test.dev/laura",
  debitAmount: { value: "2015000", assetCode: "COP", assetScale: 2 },
  receiveAmount: { value: "2000000", assetCode: "COP", assetScale: 2 },
})

beforeEach(() => sessionStorage.clear())

describe("envíos recientes", () => {
  it("el más nuevo primero", () => {
    addRecent(p("a")); addRecent(p("b"))
    expect(loadRecent().map((x) => x.paymentId)).toEqual(["b", "a"])
  })
  it("no duplica el mismo pago (el callback puede re-aplicar el turno)", () => {
    addRecent(p("a")); addRecent(p("a"))
    expect(loadRecent()).toHaveLength(1)
  })
  it("guarda como mucho 5", () => {
    for (const id of "abcdefg") addRecent(p(id))
    expect(loadRecent()).toHaveLength(5)
  })
})
