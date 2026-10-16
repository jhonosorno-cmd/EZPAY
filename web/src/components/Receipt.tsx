import type { Payment } from "../api/types"
import { costOf, formatAmount, splitAmount } from "../lib/money"
import { receiverName } from "../lib/recent"

// Como la pantalla "Transfer" del diseño: monto grande con centavos en superíndice.
export function Receipt({ payment }: { payment: Payment }) {
  const cost = costOf(payment.debitAmount, payment.receiveAmount)
  const { int, frac } = splitAmount(payment.receiveAmount)
  return (
    <section className="receipt" aria-label="Recibo">
      <p className="ok-badge">✓ Envío completado</p>
      <p className="receipt-label">Enviaste</p>
      <div className="receipt-box">
        <p className="amount-big">$&nbsp;{int}{frac && <sup>,{frac}</sup>}</p>
      </div>
      <p className="receipt-label">A</p>
      <p className="receipt-to">{receiverName(payment.receiver)}</p>
      {cost && <p className="receipt-cost">Costo del envío: $&nbsp;{formatAmount(cost)}</p>}
    </section>
  )
}
