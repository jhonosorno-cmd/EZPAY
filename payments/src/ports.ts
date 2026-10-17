import type { Amount } from './money.js'

export type WalletInfo = { id: string; authServer: string; resourceServer: string; assetCode: string; assetScale: number }

export type AccessToken = { value: string; manageUrl: string; expiresAt: Date }

export type OpPayment = {
  url: string
  /** FAILED si Open Payments lo marcó como fallido. */
  failed: boolean
  debitAmount: Amount
  sentAmount: Amount
}

/** Único contrato con Open Payments. Solo `src/op/` lo implementa con el SDK. */
export interface OpenPaymentsPort {
  /** Lanza OpError('not_found') si la wallet no existe. */
  getWallet(url: string): Promise<WalletInfo>
  requestGrant(a: {
    wallet: WalletInfo
    limit: { debitAmount: Amount; interval?: string }
    finishUri: string
    clientNonce: string
  }): Promise<{ interactUrl: string; interactNonce: string; continueUri: string; continueToken: string }>
  /** Lanza OpError('forbidden') si el usuario rechazó. */
  continueGrant(a: { continueUri: string; continueToken: string; interactRef: string }): Promise<AccessToken>
  /** Cancela el grant con GNAP grant.cancel (DELETE sobre la continue URI). Lanza OpError si la wallet falla. */
  cancelGrant(a: { continueUri: string; continueToken: string }): Promise<void>
  rotateToken(a: { manageUrl: string; accessToken: string }): Promise<AccessToken>
  createQuote(a: {
    sender: WalletInfo
    receiver: WalletInfo
    receiveAmount: Amount
  }): Promise<{ url: string; debitAmount: Amount; receiveAmount: Amount; expiresAt: Date }>
  createOutgoingPayment(a: { sender: WalletInfo; accessToken: string; quoteUrl: string }): Promise<OpPayment>
  findOutgoingPaymentByQuote(a: { sender: WalletInfo; accessToken: string; quoteUrl: string }): Promise<OpPayment | null>
  getOutgoingPayment(a: { url: string; accessToken: string }): Promise<OpPayment>
  /** null si el servidor no informa el gastado. */
  getGrantSpent(a: { sender: WalletInfo; accessToken: string }): Promise<Amount | null>
}
