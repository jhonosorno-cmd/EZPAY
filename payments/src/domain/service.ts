import { randomUUID } from 'node:crypto'
import { AppError, OpError, isUpstream } from '../errors.js'
import { interactHash, safeEqual } from '../crypto.js'
import { type Amount, add, cmp, max, parseAmount, sub, zero } from '../money.js'
import { currentPeriod, parseInterval } from '../interval.js'
import type { OpPayment, OpenPaymentsPort, WalletInfo } from '../ports.js'
import type { Grant, Payment, Quote, Store } from '../store/db.js'

export type HttpResult = { status: number; body: unknown }
export type Clock = () => number

const PENDING_TTL_MS = 10 * 60_000
const TOKEN_REFRESH_MARGIN_MS = 60_000

const err = (status: number, code: string, message = code) => new AppError(status, code, message)
const errResult = (e: AppError): HttpResult => ({ status: e.status, body: { error: { code: e.code, message: e.message } } })
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export type ServiceOptions = { now?: Clock; inProgressWaitMs?: number; inProgressPollMs?: number; log?: (line: Record<string, unknown>) => void }

export class PaymentsService {
  private readonly now: Clock
  private readonly waitMs: number
  private readonly pollMs: number
  private readonly log?: (line: Record<string, unknown>) => void
  private readonly wallets = new Map<string, WalletInfo>()

  constructor(
    private readonly store: Store,
    private readonly op: OpenPaymentsPort,
    opts: ServiceOptions = {},
  ) {
    this.now = opts.now ?? Date.now
    this.waitMs = opts.inProgressWaitMs ?? 2000
    this.pollMs = opts.inProgressPollMs ?? 100
    this.log = opts.log
  }

  // ------------------------------------------------------------------ helpers
  private async wallet(url: string, onMissing: () => AppError): Promise<WalletInfo> {
    const hit = this.wallets.get(url)
    if (hit) return hit
    try {
      const w = await this.op.getWallet(url)
      this.wallets.set(url, w)
      return w
    } catch (e) {
      if (isUpstream(e)) throw err(502, 'UPSTREAM_ERROR', 'Open Payments is unavailable')
      throw onMissing()
    }
  }

  /** Aplica los vencimientos (pendiente > 10 min, repeticiones agotadas) y devuelve el grant al día. */
  private load(id: string): Grant {
    const g = this.store.getGrant(id)
    if (!g) throw err(404, 'GRANT_NOT_FOUND')
    let status = g.status
    if (status === 'PENDING' && this.now() - g.createdAt > PENDING_TTL_MS) status = 'EXPIRED'
    if (status === 'ACTIVE' && g.limit.interval) {
      const iv = parseInterval(g.limit.interval)
      if (iv && currentPeriod(iv, new Date(this.now())).expired) status = 'EXPIRED'
    }
    if (status !== g.status) {
      this.store.updateGrant(id, { status })
      return { ...g, status }
    }
    return g
  }

  private periodStart(g: Grant): number {
    if (!g.limit.interval) return 0
    const iv = parseInterval(g.limit.interval)
    return iv ? currentPeriod(iv, new Date(this.now())).from.getTime() : 0
  }

  /** spent = max(servidor, suma local de PROCESSING y COMPLETED del período). */
  private async spent(g: Grant, sender?: WalletInfo, token?: string): Promise<Amount> {
    const base = zero(g.limit.debitAmount)
    const from = this.periodStart(g)
    const local = this.store
      .paymentsOfGrant(g.id)
      .filter((p) => p.status !== 'FAILED' && p.createdAt >= from)
      .reduce((acc, p) => add(acc, p.debitAmount), base)
    if (!sender || !token) return local
    try {
      const remote = await this.op.getGrantSpent({ sender, accessToken: token })
      return remote ? max(local, remote) : local
    } catch {
      this.log?.({ level: 'warn', event: 'spent_fallback' })
      return local
    }
  }

  private async view(g: Grant) {
    const limit = g.limit.debitAmount
    let spent = zero(limit)
    if (g.status === 'ACTIVE') {
      const sender = await this.wallet(g.walletAddress, () => err(502, 'UPSTREAM_ERROR')).catch(() => undefined)
      spent = await this.spent(g, sender, g.accessToken ?? undefined)
    }
    return { limit, spent, remaining: sub(limit, spent) }
  }

  /** Token vigente; rota si le quedan < 60 s. El token nuevo se guarda antes de usarlo. */
  private async token(g: Grant, force = false): Promise<string> {
    if (!g.accessToken) throw err(401, 'GRANT_INVALID')
    const dueSoon = g.accessTokenExpiresAt !== null && g.accessTokenExpiresAt - this.now() < TOKEN_REFRESH_MARGIN_MS
    if (!force && !dueSoon) return g.accessToken
    if (!g.manageUrl) throw err(401, 'GRANT_INVALID')
    try {
      const t = await this.op.rotateToken({ manageUrl: g.manageUrl, accessToken: g.accessToken })
      this.store.updateGrant(g.id, { accessToken: t.value, manageUrl: t.manageUrl, accessTokenExpiresAt: t.expiresAt.getTime() })
      g.accessToken = t.value
      g.manageUrl = t.manageUrl
      g.accessTokenExpiresAt = t.expiresAt.getTime()
      return t.value
    } catch (e) {
      if (isUpstream(e)) throw err(502, 'UPSTREAM_ERROR', 'Open Payments is unavailable')
      throw err(401, 'GRANT_INVALID')
    }
  }

  private active(g: Grant) {
    if (g.status !== 'ACTIVE') throw err(401, 'GRANT_INVALID')
  }

  // ------------------------------------------------------------------ grants
  async createGrant(body: any) {
    const b = body ?? {}
    if (typeof b.userId !== 'string' || !b.userId) throw err(400, 'INVALID_REQUEST', 'userId is required')
    if (typeof b.walletAddress !== 'string' || !b.walletAddress) throw err(400, 'INVALID_REQUEST', 'walletAddress is required')
    if (typeof b.finishUri !== 'string' || !b.finishUri) throw err(400, 'INVALID_REQUEST', 'finishUri is required')
    if (typeof b.limit !== 'object' || b.limit === null || typeof b.limit.debitAmount !== 'object' || b.limit.debitAmount === null)
      throw err(400, 'INVALID_REQUEST', 'limit.debitAmount object is required')
    const debitAmount = parseAmount(b.limit.debitAmount, 'limit.debitAmount')
    const interval = b.limit?.interval
    if (interval !== undefined && (typeof interval !== 'string' || !parseInterval(interval)))
      throw err(400, 'INVALID_AMOUNT', 'limit.interval is not a supported ISO 8601 repeating interval')

    const wallet = await this.wallet(b.walletAddress, () => err(400, 'INVALID_WALLET', 'wallet address could not be resolved'))
    const clientNonce = randomUUID()
    let r
    try {
      r = await this.op.requestGrant({ wallet, limit: { debitAmount, ...(interval ? { interval } : {}) }, finishUri: b.finishUri, clientNonce })
    } catch (e) {
      throw isUpstream(e) ? err(502, 'UPSTREAM_ERROR') : err(500, 'INTERNAL_ERROR')
    }
    const id = 'g_' + randomUUID().replaceAll('-', '').slice(0, 12)
    this.store.insertGrant({
      id, userId: b.userId, walletAddress: b.walletAddress, grantEndpointUri: wallet.authServer, status: 'PENDING',
      limit: { debitAmount, ...(interval ? { interval } : {}) }, clientNonce, interactNonce: r.interactNonce,
      continueUri: r.continueUri, continueToken: r.continueToken, accessToken: null, accessTokenExpiresAt: null,
      manageUrl: null, createdAt: this.now(), activatedAt: null,
    })
    return { grantId: id, status: 'PENDING', interactUrl: r.interactUrl }
  }

  async continueGrant(id: string, body: any) {
    const g = this.load(id)
    if (g.status !== 'PENDING') throw err(409, 'GRANT_NOT_PENDING')
    const { interactRef, hash } = body ?? {}
    if (typeof interactRef !== 'string' || typeof hash !== 'string') throw err(400, 'INVALID_HASH')
    const expected = interactHash(g.clientNonce, g.interactNonce, interactRef, g.grantEndpointUri)
    if (!safeEqual(expected, hash)) throw err(400, 'INVALID_HASH')
    try {
      const t = await this.op.continueGrant({ continueUri: g.continueUri, continueToken: g.continueToken, interactRef })
      this.store.updateGrant(id, {
        status: 'ACTIVE', accessToken: t.value, manageUrl: t.manageUrl, accessTokenExpiresAt: t.expiresAt.getTime(), activatedAt: this.now(),
      })
    } catch (e) {
      if (e instanceof AppError) throw e
      if (e instanceof OpError && e.kind === 'forbidden') {
        this.store.updateGrant(id, { status: 'REJECTED' })
        throw err(403, 'GRANT_REJECTED')
      }
      throw isUpstream(e) ? err(502, 'UPSTREAM_ERROR') : err(500, 'INTERNAL_ERROR')
    }
    const v = await this.view(this.load(id))
    return { grantId: id, status: 'ACTIVE', limit: g.limit, remaining: v.remaining }
  }

  async getGrant(id: string) {
    const g = this.load(id)
    const v = await this.view(g)
    return { grantId: id, status: g.status, limit: v.limit === g.limit.debitAmount ? g.limit : g.limit, spent: v.spent, remaining: v.remaining }
  }

  async cancelGrant(id: string): Promise<void> {
    const g = this.store.getGrant(id)
    if (!g) throw err(404, 'GRANT_NOT_FOUND')
    if (g.status === 'EXPIRED') return
    this.store.updateGrant(id, { status: 'EXPIRED' }) // aunque el cancel falle, no se usa de nuevo
    if (g.continueUri && g.continueToken) {
      try {
        await this.op.cancelGrant({ continueUri: g.continueUri, continueToken: g.continueToken })
      } catch {
        throw err(502, 'UPSTREAM_ERROR', 'could not cancel the grant in Open Payments')
      }
    }
  }

  // ------------------------------------------------------------------ quotes
  async createQuote(body: any) {
    const b = body ?? {}
    if (typeof b.grantId !== 'string' || !b.grantId) throw err(400, 'INVALID_REQUEST', 'grantId is required')
    const receiveAmount = parseAmount(b.receiveAmount, 'receiveAmount')
    if (typeof b.receiver !== 'string' || !b.receiver) throw err(400, 'INVALID_RECEIVER', 'receiver is required')
    const g = this.load(b.grantId)
    this.active(g)

    const receiver = await this.wallet(b.receiver, () => err(400, 'INVALID_RECEIVER', 'receiver could not be resolved'))
    if (receiver.assetCode !== receiveAmount.assetCode || receiver.assetScale !== receiveAmount.assetScale)
      throw err(400, 'INVALID_RECEIVER', 'receiver asset does not match receiveAmount')
    const sender = await this.wallet(g.walletAddress, () => err(400, 'INVALID_WALLET'))

    let q
    try {
      q = await this.op.createQuote({ sender, receiver, receiveAmount })
    } catch (e) {
      throw isUpstream(e) ? err(502, 'UPSTREAM_ERROR') : err(500, 'INTERNAL_ERROR')
    }
    const id = 'q_' + randomUUID().replaceAll('-', '').slice(0, 12)
    this.store.insertQuote({
      id, grantId: g.id, opQuoteUrl: q.url, receiver: b.receiver, debitAmount: q.debitAmount,
      receiveAmount: q.receiveAmount, expiresAt: q.expiresAt.getTime(), status: 'CREATED',
    })
    const spent = await this.spent(g, sender, g.accessToken ?? undefined)
    const remaining = sub(g.limit.debitAmount, spent)
    return {
      quoteId: id, debitAmount: q.debitAmount, receiveAmount: q.receiveAmount,
      expiresAt: q.expiresAt.toISOString(), exceedsRemaining: cmp(q.debitAmount, remaining) > 0,
    }
  }

  // ------------------------------------------------------------------ payments
  async pay(key: string | undefined, body: any): Promise<HttpResult> {
    if (!key) throw err(400, 'IDEMPOTENCY_KEY_REQUIRED')
    const quoteId = body?.quoteId
    if (typeof quoteId !== 'string' || !quoteId) throw err(400, 'INVALID_REQUEST', 'quoteId is required')

    // La reserva es síncrona (PK): ocurre antes de cualquier await.
    if (!this.store.reserveKey(key, quoteId, this.now())) return this.existingKey(key, quoteId)

    let ctx
    try {
      ctx = await this.prepare(quoteId)
    } catch (e) {
      this.store.deleteKey(key) // falló antes de enviar: se puede reintentar
      throw e
    }
    this.store.tx(() => {
      this.store.setKeyState(key, 'SENT')
      this.store.setQuoteStatus(quoteId, 'USED')
    })
    return this.send(key, ctx)
  }

  private async prepare(quoteId: string) {
    const quote = this.store.getQuote(quoteId)
    if (!quote || quote.status !== 'CREATED') throw err(404, 'QUOTE_NOT_FOUND')
    if (quote.expiresAt <= this.now()) throw err(409, 'QUOTE_EXPIRED')
    const grant = this.load(quote.grantId)
    this.active(grant)
    const sender = await this.wallet(grant.walletAddress, () => err(400, 'INVALID_WALLET'))
    let token = await this.token(grant)
    const spent = await this.spent(grant, sender, token)
    if (cmp(quote.debitAmount, sub(grant.limit.debitAmount, spent)) > 0) throw err(403, 'LIMIT_EXCEEDED')
    token = grant.accessToken ?? token
    return { quote, grant, sender, token }
  }

  private async existingKey(key: string, quoteId: string): Promise<HttpResult> {
    const deadline = Date.now() + this.waitMs
    for (;;) {
      const k = this.store.getKey(key)
      if (!k) return this.pay(key, { quoteId }) // se borró tras fallar antes de enviar
      if (k.quoteId !== quoteId) throw err(422, 'IDEMPOTENCY_KEY_REUSED')
      if (k.state === 'DONE' && k.response) return k.response
      if (k.state === 'UNKNOWN') return this.resolveUnknown(key, quoteId)
      if (Date.now() >= deadline) throw err(409, 'PAYMENT_IN_PROGRESS')
      await sleep(this.pollMs)
    }
  }

  private async resolveUnknown(key: string, quoteId: string): Promise<HttpResult> {
    const quote = this.store.getQuote(quoteId)
    if (!quote) throw err(404, 'QUOTE_NOT_FOUND')
    const grant = this.load(quote.grantId)
    this.active(grant)
    const sender = await this.wallet(grant.walletAddress, () => err(400, 'INVALID_WALLET'))
    const token = await this.token(grant)
    let found: OpPayment | null
    try {
      found = await this.op.findOutgoingPaymentByQuote({ sender, accessToken: token, quoteUrl: quote.opQuoteUrl })
    } catch (e) {
      throw isUpstream(e) ? err(502, 'UPSTREAM_ERROR') : err(500, 'INTERNAL_ERROR')
    }
    if (found) return this.record(key, quote, grant, found)
    return this.send(key, { quote, grant, sender, token })
  }

  /** Crea el pago en Open Payments. Desde acá la quote ya está USED y la clave en SENT. */
  private async send(key: string, c: { quote: Quote; grant: Grant; sender: WalletInfo; token: string }): Promise<HttpResult> {
    const { quote, grant, sender } = c
    let token = c.token
    let rotated = false
    for (;;) {
      try {
        const p = await this.op.createOutgoingPayment({ sender, accessToken: token, quoteUrl: quote.opQuoteUrl })
        return this.record(key, quote, grant, p)
      } catch (e) {
        if (e instanceof AppError) throw e
        if (!(e instanceof OpError)) {
          this.store.setKeyState(key, 'UNKNOWN')
          throw err(500, 'INTERNAL_ERROR', 'unexpected error')
        }
        if (e.kind === 'unauthorized' && !rotated) {
          rotated = true
          try { token = await this.token(grant, true) } catch (re) { return this.fail(key, re as AppError) }
          continue
        }
        if (e.kind === 'unauthorized') return this.fail(key, err(401, 'GRANT_INVALID'))
        if (e.kind === 'invalid_quote') return this.fail(key, err(409, 'QUOTE_EXPIRED'))
        if (e.kind === 'forbidden') {
          const spent = await this.spent(grant, sender, token)
          const fits = cmp(quote.debitAmount, sub(grant.limit.debitAmount, spent)) <= 0
          if (!fits) return this.fail(key, err(403, 'LIMIT_EXCEEDED'))
          if (!rotated) {
            rotated = true
            try { token = await this.token(grant, true) } catch (re) { return this.fail(key, re as AppError) }
            continue
          }
          return this.fail(key, err(401, 'GRANT_INVALID'))
        }
        // timeout / red / 5xx: resultado incierto
        this.store.setKeyState(key, 'UNKNOWN')
        throw err(502, 'UPSTREAM_ERROR', 'payment result is uncertain; retry with the same Idempotency-Key')
      }
    }
  }

  private fail(key: string, e: AppError): HttpResult {
    const r = errResult(e)
    this.store.setKeyState(key, 'DONE', r)
    return r
  }

  private record(key: string, quote: Quote, grant: Grant, p: OpPayment): HttpResult {
    const id = 'p_' + randomUUID().replaceAll('-', '').slice(0, 12)
    const status = derive(p)
    const payment: Payment = {
      id, grantId: grant.id, quoteId: quote.id, opPaymentUrl: p.url, debitAmount: p.debitAmount ?? quote.debitAmount,
      sentAmount: p.sentAmount, status, createdAt: this.now(),
    }
    const r: HttpResult = {
      status: 201,
      body: { paymentId: id, status, debitAmount: payment.debitAmount, sentAmount: payment.sentAmount },
    }
    this.store.tx(() => {
      this.store.insertPayment(payment)
      this.store.setKeyState(key, 'DONE', r)
    })
    return r
  }

  async getPayment(id: string) {
    const p = this.store.getPayment(id)
    if (!p) throw err(404, 'PAYMENT_NOT_FOUND')
    const grant = this.store.getGrant(p.grantId)
    if (grant?.accessToken && p.status === 'PROCESSING') {
      let op: OpPayment | null = null
      for (let i = 0; i < 2 && !op; i++) {
        try { op = await this.op.getOutgoingPayment({ url: p.opPaymentUrl, accessToken: grant.accessToken }) } catch { /* un reintento */ }
      }
      if (op) {
        const status = derive({ ...op, debitAmount: p.debitAmount })
        this.store.updatePayment(id, { status, sentAmount: op.sentAmount })
        return { paymentId: id, status, sentAmount: op.sentAmount }
      }
    }
    return { paymentId: id, status: p.status, sentAmount: p.sentAmount }
  }

  /** Al arrancar el proceso. */
  recover() { this.store.recoverKeys() }
}

function derive(p: OpPayment): Payment['status'] {
  if (p.failed) return 'FAILED'
  return cmp(p.sentAmount, p.debitAmount) >= 0 && BigInt(p.debitAmount.value) > 0n ? 'COMPLETED' : 'PROCESSING'
}
