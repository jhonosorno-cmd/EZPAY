import type { Budget } from "../api/client"
import { formatAmount, percentLeft } from "../lib/money"

// Como "Your balance" / "Withdrawal $X of $Y" del diseño, pero con el presupuesto autorizado en la wallet.
export function BudgetHeader({ budget }: { budget: Budget | null }) {
  const active = budget?.status === "ACTIVE" && budget.remaining && budget.limit
  return (
    <header>
      <div className="topbar"><p className="brand">EZPAY</p></div>
      <section className="budget" aria-label="Presupuesto">
        {active ? (
          <>
            <p className="budget-label">Te quedan</p>
            <p className="budget-amount">$&nbsp;{formatAmount(budget.remaining!)}</p>
            <p className="budget-of">de $&nbsp;{formatAmount(budget.limit!)}</p>
            <div className="bar" aria-hidden="true">
              <span style={{ width: `${percentLeft(budget.remaining!, budget.limit!)}%` }} />
            </div>
          </>
        ) : (
          <>
            <p className="budget-label">Tu presupuesto</p>
            <p className="budget-none">Todavía no autorizaste un presupuesto</p>
          </>
        )}
      </section>
    </header>
  )
}
