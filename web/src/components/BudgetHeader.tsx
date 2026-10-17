import type { Budget } from "../api/types"
import { formatAmount, percentLeft } from "../lib/money"

// Como "Your balance" / "Withdrawal $X of $Y" del diseño, con el presupuesto de GET /api/budget.
// Contrato B: limit = { debitAmount, interval? }. Solo ACTIVE muestra montos.
export function BudgetHeader({ budget }: { budget: Budget | null }) {
  const active = budget?.status === "ACTIVE" ? budget : null
  // Sin grant, Python responde PENDING con límite 0 (como el esqueleto de Pagos): eso es "sin presupuesto".
  const pending = budget?.status === "PENDING" && budget.limit.debitAmount.value !== "0"
  return (
    <header>
      <div className="topbar"><p className="brand">EZPAY</p></div>
      <section className="budget" aria-label="Presupuesto">
        {active ? (
          <>
            <p className="budget-label">Te quedan</p>
            <p className="budget-amount">$&nbsp;{formatAmount(active.remaining)}</p>
            <p className="budget-of">de $&nbsp;{formatAmount(active.limit.debitAmount)}</p>
            <div className="bar" aria-hidden="true">
              <span style={{ width: `${percentLeft(active.remaining, active.limit.debitAmount)}%` }} />
            </div>
          </>
        ) : (
          <>
            <p className="budget-label">Tu presupuesto</p>
            <p className="budget-none">
              {pending ? "Esperando que lo apruebes en tu billetera" : "Todavía no autorizaste un presupuesto"}
            </p>
          </>
        )}
      </section>
    </header>
  )
}
