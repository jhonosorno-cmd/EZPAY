// Contrato B (docs/contratos-http-v1.md). PAYMENT_PENDING es un cambio propuesto (B-2), aún sin ratificar.
export type Amount = { value: string; assetCode: string; assetScale: number }

export type TurnState =
  | "AWAITING_COMMAND"
  | "AWAITING_CONFIRMATION"
  | "AWAITING_PIN"
  | "AWAITING_RECIPIENT_CHOICE"
  | "AWAITING_AUTHORIZATION"
  | "PAYMENT_PENDING"
  | "COMPLETED"
  | "REJECTED"

export type Payment = { paymentId: string; receiver: string; debitAmount: Amount; receiveAmount: Amount }

export type TurnResponse = {
  sessionId: string
  state: TurnState | (string & {}) // el cliente tolera estados desconocidos
  say: string
  transcript: string | null
  interactUrl: string | null
  options: { alias: string; name: string }[] | null
  payment: Payment | null
}

export type ErrorBody = { error: { code: string; message: string } }

export type GrantCallback = { interactRef?: string; hash?: string; result?: string }
