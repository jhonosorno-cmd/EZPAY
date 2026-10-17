import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { BudgetHeader } from "./BudgetHeader"
import type { Budget } from "../api/types"

const cop = (value: string) => ({ value, assetCode: "COP", assetScale: 2 })
// Ejemplo de GET /api/budget en openapi/contract-b.yaml
const contractExample: Budget = {
  status: "ACTIVE",
  limit: { debitAmount: cop("20000000"), interval: "R52/2026-10-16T00:00:00Z/P1W" },
  spent: cop("2015000"),
  remaining: cop("17985000"),
}

afterEach(cleanup)

describe("BudgetHeader", () => {
  it("muestra lo que queda y el tope, con la forma del contrato", () => {
    render(<BudgetHeader budget={contractExample} />)
    expect(screen.getByText("$ 179.850")).toBeTruthy()
    expect(screen.getByText("de $ 200.000")).toBeTruthy()
  })
  it("un presupuesto que no está ACTIVE no muestra montos", () => {
    render(<BudgetHeader budget={{ ...contractExample, status: "PENDING" }} />)
    expect(screen.queryByText("$ 179.850")).toBeNull()
  })
  it("PENDING con límite 0 es que todavía no hay presupuesto (no que espere la wallet)", () => {
    const none = { ...contractExample, status: "PENDING" as const, limit: { debitAmount: cop("0") } }
    render(<BudgetHeader budget={none} />)
    expect(screen.getByText(/no autorizaste un presupuesto/)).toBeTruthy()
  })
  it("sin respuesta del backend", () => {
    render(<BudgetHeader budget={null} />)
    expect(screen.getByText(/no autorizaste un presupuesto/)).toBeTruthy()
  })
})
