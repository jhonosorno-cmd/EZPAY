// ÚNICO módulo que importa @interledger/open-payments.
import {
  createAuthenticatedClient,
  isFinalizedGrant,
  isPendingGrant,
  OpenPaymentsClientError,
  type AuthenticatedClient,
} from '@interledger/open-payments'
import { OpError } from '../errors.js'
import type { Amount } from '../money.js'
import type { AccessToken, OpPayment, OpenPaymentsPort, WalletInfo } from '../ports.js'

type Cfg = { walletAddress: string; keyId: string; privateKey: string; timeoutMs: number }

const INCOMING_TTL_MS = 10 * 60_000 // tiene que superar los 5 min de la quote
const TOKEN_CACHE_MARGIN_MS = 30_000

const amt = (a: { value: string; assetCode: string; assetScale: number }): Amount => ({
  value: a.value, assetCode: a.assetCode, assetScale: a.assetScale,
})

/** Traduce errores del SDK/red a OpError. Se decide por status y contexto, no por el texto. */
function mapError(e: unknown): OpError {
  if (e instanceof OpError) return e
  if (e instanceof OpenPaymentsClientError) {
    const s = e.status
    if (s === 401) return new OpError('unauthorized')
    if (s === 403) return new OpError('forbidden')
    if (s === 404) return new OpError('not_found')
    if (s === 400) return new OpError('invalid_quote') // el llamador decide si aplica (solo se usa al pagar)
    if (s !== undefined && s >= 500) return new OpError('server')
    if (s === undefined) return new OpError('network')
    return new OpError('other')
  }
  const name = (e as { name?: string })?.name
  if (name === 'TimeoutError' || name === 'AbortError') return new OpError('timeout')
  return new OpError('network')
}

export class SdkOpenPayments implements OpenPaymentsPort {
  private constructor(private readonly c: AuthenticatedClient, private readonly timeoutMs: number) {}
  private readonly tokenCache = new Map<string, { value: string; expiresAt: number }>()

  static async create(cfg: Cfg) {
    const client = await createAuthenticatedClient({
      walletAddressUrl: cfg.walletAddress, privateKey: cfg.privateKey, keyId: cfg.keyId, logLevel: 'silent', requestTimeoutMs: cfg.timeoutMs,
    })
    return new SdkOpenPayments(client, cfg.timeoutMs)
  }

  private async call<T>(fn: () => Promise<T>): Promise<T> {
    let timer: NodeJS.Timeout | undefined
    try {
      return await Promise.race([
        fn(),
        new Promise<never>((_, rej) => { timer = setTimeout(() => rej(new OpError('timeout')), this.timeoutMs) }),
      ])
    } catch (e) {
      throw mapError(e)
    } finally {
      clearTimeout(timer)
    }
  }

  async getWallet(url: string): Promise<WalletInfo> {
    const w = await this.call(() => this.c.walletAddress.get({ url }))
    return { id: w.id, authServer: w.authServer, resourceServer: w.resourceServer, assetCode: w.assetCode, assetScale: w.assetScale }
  }

  async requestGrant(a: Parameters<OpenPaymentsPort['requestGrant']>[0]) {
    const g = await this.call(() =>
      this.c.grant.request({ url: a.wallet.authServer }, {
        access_token: {
          access: [{
            type: 'outgoing-payment', actions: ['create', 'read', 'list'], identifier: a.wallet.id,
            limits: { debitAmount: a.limit.debitAmount, ...(a.limit.interval ? { interval: a.limit.interval } : {}) },
          }],
        },
        interact: { start: ['redirect'], finish: { method: 'redirect', uri: a.finishUri, nonce: a.clientNonce } },
      }),
    )
    if (!isPendingGrant(g) || !g.interact.finish) throw new OpError('other')
    return {
      interactUrl: g.interact.redirect, interactNonce: g.interact.finish,
      continueUri: g.continue.uri, continueToken: g.continue.access_token.value,
    }
  }

  async continueGrant(a: Parameters<OpenPaymentsPort['continueGrant']>[0]): Promise<AccessToken> {
    let g
    try {
      g = await this.call(() => this.c.grant.continue({ url: a.continueUri, accessToken: a.continueToken }, { interact_ref: a.interactRef }))
    } catch (e) {
      // [VERIFICAR E3] cómo responde la wallet cuando el usuario rechazó
      if (e instanceof OpError && ['unauthorized', 'forbidden', 'invalid_quote', 'not_found'].includes(e.kind)) throw new OpError('forbidden')
      throw e
    }
    if (!isFinalizedGrant(g) || !g.access_token) throw new OpError('forbidden')
    return this.toToken(g.access_token)
  }

  private toToken(t: { value: string; manage: string; expires_in?: number }): AccessToken {
    return { value: t.value, manageUrl: t.manage, expiresAt: new Date(Date.now() + (t.expires_in ?? 600) * 1000) }
  }

  /** [VERIFICAR] se revoca el token vía la manage URL; la cancelación GNAP completa usa el continue URI. */
  async cancelGrant(a: { manageUrl: string; accessToken: string }) {
    await this.call(() => this.c.token.revoke({ url: a.manageUrl, accessToken: a.accessToken }))
  }

  async rotateToken(a: { manageUrl: string; accessToken: string }) {
    const t = await this.call(() => this.c.token.rotate({ url: a.manageUrl, accessToken: a.accessToken }))
    return this.toToken(t.access_token)
  }

  /** Token no interactivo (incoming-payment del receptor o quote del emisor), con caché. */
  private async nonInteractive(authServer: string, kind: 'incoming-payment' | 'quote', walletId?: string): Promise<string> {
    const k = `${authServer}|${kind}`
    const hit = this.tokenCache.get(k)
    if (hit && hit.expiresAt - TOKEN_CACHE_MARGIN_MS > Date.now()) return hit.value
    const access = kind === 'incoming-payment'
      ? [{ type: 'incoming-payment' as const, actions: ['create' as const, 'read' as const, 'list' as const] }]
      : [{ type: 'quote' as const, actions: ['create' as const, 'read' as const] }]
    void walletId
    const g = await this.call(() => this.c.grant.request({ url: authServer }, { access_token: { access } }))
    if (!isFinalizedGrant(g) || !g.access_token) throw new OpError('other')
    const t = this.toToken(g.access_token)
    this.tokenCache.set(k, { value: t.value, expiresAt: t.expiresAt.getTime() })
    return t.value
  }

  async createQuote(a: Parameters<OpenPaymentsPort['createQuote']>[0]) {
    const inToken = await this.nonInteractive(a.receiver.authServer, 'incoming-payment')
    const incoming = await this.call(() =>
      this.c.incomingPayment.create({ url: a.receiver.resourceServer, accessToken: inToken }, {
        walletAddress: a.receiver.id, incomingAmount: a.receiveAmount, expiresAt: new Date(Date.now() + INCOMING_TTL_MS).toISOString(),
      }),
    )
    const qToken = await this.nonInteractive(a.sender.authServer, 'quote')
    const q = await this.call(() =>
      this.c.quote.create({ url: a.sender.resourceServer, accessToken: qToken }, {
        method: 'ilp', walletAddress: a.sender.id, receiver: incoming.id,
      }),
    )
    return {
      url: q.id, debitAmount: amt(q.debitAmount), receiveAmount: amt(q.receiveAmount),
      expiresAt: q.expiresAt ? new Date(q.expiresAt) : new Date(Date.now() + 300_000),
    }
  }

  private toPayment(p: { id: string; failed: boolean; debitAmount: Amount; sentAmount: Amount }): OpPayment {
    return { url: p.id, failed: p.failed, debitAmount: amt(p.debitAmount), sentAmount: amt(p.sentAmount) }
  }

  async createOutgoingPayment(a: Parameters<OpenPaymentsPort['createOutgoingPayment']>[0]) {
    const p = await this.call(() =>
      this.c.outgoingPayment.create({ url: a.sender.resourceServer, accessToken: a.accessToken }, { walletAddress: a.sender.id, quoteId: a.quoteUrl }),
    )
    return this.toPayment(p)
  }

  async findOutgoingPaymentByQuote(a: Parameters<OpenPaymentsPort['findOutgoingPaymentByQuote']>[0]) {
    const page = await this.call(() =>
      this.c.outgoingPayment.list({ url: a.sender.resourceServer, walletAddress: a.sender.id, accessToken: a.accessToken }, { first: 50, 'wallet-address': a.sender.id }),
    )
    const hit = page.result.find((p) => p.quoteId === a.quoteUrl)
    return hit ? this.toPayment(hit) : null
  }

  async getOutgoingPayment(a: { url: string; accessToken: string }) {
    return this.toPayment(await this.call(() => this.c.outgoingPayment.get({ url: a.url, accessToken: a.accessToken })))
  }

  async getGrantSpent(a: { sender: WalletInfo; accessToken: string }) {
    const r = await this.call(() =>
      this.c.outgoingPayment.getGrantSpentAmounts({ url: a.sender.resourceServer.replace(/\/$/, ''), accessToken: a.accessToken }),
    )
    return r.spentDebitAmount ? amt(r.spentDebitAmount) : null
  }
}
