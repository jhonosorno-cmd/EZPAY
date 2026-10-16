import { describe, expect, it } from "vitest"
import { costOf, formatAmount, percentLeft, splitAmount } from "./money"

const cop = (value: string) => ({ value, assetCode: "COP", assetScale: 2 })

describe("formatAmount (CONV-1, es-CO)", () => {
  it("monto en pesos", () => expect(formatAmount(cop("2000000"))).toBe("20.000"))
  it("monto con centavos", () => expect(formatAmount(cop("1050"))).toBe("10,50"))
  it("menos de un peso", () => expect(formatAmount(cop("5"))).toBe("0,05"))
  it("cero", () => expect(formatAmount(cop("0"))).toBe("0"))
  it("millones", () => expect(formatAmount(cop("123456789000"))).toBe("1.234.567.890"))
  it("escala 0", () => expect(formatAmount({ value: "1500", assetCode: "COP", assetScale: 0 })).toBe("1.500"))
  it("no pierde precisión por encima de 2^53", () =>
    expect(formatAmount(cop("900719925474099300"))).toBe("9.007.199.254.740.993"))
})

describe("costOf", () => {
  it("diferencia entre debitado y recibido", () =>
    expect(costOf(cop("2015000"), cop("2000000"))).toEqual(cop("15000")))
  it("sin costo → null", () => expect(costOf(cop("2000000"), cop("2000000"))).toBeNull())
  it("monedas distintas → null (nunca se combinan)", () =>
    expect(costOf(cop("2015000"), { value: "2000000", assetCode: "USD", assetScale: 2 })).toBeNull())
})

describe("splitAmount (centavos en superíndice)", () => {
  it("sin decimales", () => expect(splitAmount(cop("2000000"))).toEqual({ int: "20.000", frac: null }))
  it("con decimales", () => expect(splitAmount(cop("1050"))).toEqual({ int: "10", frac: "50" }))
})

describe("percentLeft (barra del presupuesto)", () => {
  it("mitad", () => expect(percentLeft(cop("10000000"), cop("20000000"))).toBe(50))
  it("redondea hacia abajo", () => expect(percentLeft(cop("18992500"), cop("20000000"))).toBe(94))
  it("límite cero", () => expect(percentLeft(cop("0"), cop("0"))).toBe(0))
})
