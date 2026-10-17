import type { Payment } from "../api/types"
import { formatAmount } from "../lib/money"
import { receiverName } from "../lib/recent"

export function RecentPayments({ items }: { items: Payment[] }) {
  if (!items.length) return null
  return (
    <section className="recent" aria-label="Envíos recientes">
      <h2>Envíos recientes</h2>
      <ul>
        {items.map((p) => (
          <li key={p.paymentId}>
            <span>{receiverName(p.receiver)}</span>
            <span className="amt">−&nbsp;$&nbsp;{formatAmount(p.receiveAmount)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
