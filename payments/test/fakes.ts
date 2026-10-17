import { OpError } from '../src/errors.js'
import { Cipher, interactHash } from '../src/crypto.js'
import type { Amount } from '../src/money.js'
import type { OpPayment, OpenPaymentsPort, WalletInfo } from '../src/ports.js'
import { PaymentsService } from '../src/domain/service.js'
import { Store } from '../src/store/db.js'

export const cop = (v: string | number): Amount => ({ value: String(v), assetCode: 'COP', assetScale: 2 })
export const KEY = Buffer.alloc(32, 7).toString('base64')

export const MARTA = 'https://ilp.test/marta'
export const LAURA = 'https://ilp.test/laura'
export const AUTH = 'https://auth.test'

export class FakeOp implements OpenPaymentsPort {
  now = Date.now()
  wallets: Record<string, WalletInfo> = {
    [MARTA]: { id: MARTA, authServer: AUTH, resourceServer: 'https://rs.test', assetCode: 'COP', assetScale: 2 },
    [LAURA]: { id: LAURA, authServer: AUTH, resourceServer: 'https://rs.test', assetCode: 'COP', assetScale: 2 },
  }
  calls: string[] = []
  payments: (OpPayment & { quoteUrl: string })[] = []
  quoteDebit = (a: Amount) => a // por defecto, sin comisión
  serverSpent: Amount | null = null
  /** Respuestas sucesivas de getGrantSpent; al agotarse se usa serverSpent. */
  spentSequence: (Amount | null)[] = []
  createBehavior: Array<'ok' | 'timeout-created' | 'timeout-lost' | 'unauthorized' | 'forbidden' | 'invalid_quote'> = []
  createDelayMs = 0
  rotateFails = false
  failNext: Record<string, OpError> = {}
  tokenSeq = 0
  rejectOnContinue = false
  private n = 0

  private track(name: string) {
    this.calls.push(name)
    const f = this.failNext[name]
    if (f) { delete this.failNext[name]; throw f }
  }
  async getWallet(url: string) {
    this.track('getWallet')
    const w = this.wallets[url]
    if (!w) throw new OpError('not_found')
    return w
  }
  async requestGrant(a: { clientNonce: string }) {
    this.track('requestGrant')
    return { interactUrl: 'https://auth.test/interact/1', interactNonce: 'inonce', continueUri: 'https://auth.test/continue/1', continueToken: 'CONTINUE-TOKEN-SECRET' }
  }
  async continueGrant() {
    this.track('continueGrant')
    if (this.rejectOnContinue) throw new OpError('forbidden')
    return { value: `ACCESS-TOKEN-SECRET-${++this.tokenSeq}`, manageUrl: `https://auth.test/token/${this.tokenSeq}`, expiresAt: new Date(this.now + 600_000) }
  }
  async cancelGrant() { this.track('cancelGrant') }
  async rotateToken() {
    this.track('rotateToken')
    if (this.rotateFails) throw new OpError('unauthorized')
    return { value: `ACCESS-TOKEN-SECRET-${++this.tokenSeq}`, manageUrl: `https://auth.test/token/${this.tokenSeq}`, expiresAt: new Date(this.now + 600_000) }
  }
  async createQuote(a: { receiveAmount: Amount }) {
    this.track('createQuote')
    return { url: `https://rs.test/quotes/${++this.n}`, debitAmount: this.quoteDebit(a.receiveAmount), receiveAmount: a.receiveAmount, expiresAt: new Date(this.now + 300_000) }
  }
  async createOutgoingPayment(a: { quoteUrl: string; accessToken: string }) {
    this.track('createOutgoingPayment')
    if (this.createDelayMs) await new Promise((r) => setTimeout(r, this.createDelayMs))
    const mode = this.createBehavior.shift() ?? 'ok'
    const make = () => {
      const q = this.quotes.get(a.quoteUrl)!
      const p = { url: `https://rs.test/op/${++this.n}`, failed: false, debitAmount: q, sentAmount: cop(0), quoteUrl: a.quoteUrl }
      this.payments.push(p)
      return p
    }
    if (mode === 'timeout-created') { make(); throw new OpError('timeout') }
    if (mode === 'timeout-lost') throw new OpError('timeout')
    if (mode === 'unauthorized') throw new OpError('unauthorized')
    if (mode === 'forbidden') throw new OpError('forbidden')
    if (mode === 'invalid_quote') throw new OpError('invalid_quote')
    return make()
  }
  quotes = new Map<string, Amount>()
  async findOutgoingPaymentByQuote(a: { quoteUrl: string }) {
    this.track('findOutgoingPaymentByQuote')
    return this.payments.find((p) => p.quoteUrl === a.quoteUrl) ?? null
  }
  async getOutgoingPayment(a: { url: string }) {
    this.track('getOutgoingPayment')
    return this.payments.find((p) => p.url === a.url)!
  }
  async getGrantSpent() {
    this.track('getGrantSpent')
    return this.spentSequence.length ? this.spentSequence.shift()! : this.serverSpent
  }
}

// El fake recuerda el débito de cada quote.
export function makeEnv(opts: { now?: () => number; path?: string; log?: (line: Record<string, unknown>) => void } = {}) {
  const op = new FakeOp()
  const origQuote = op.createQuote.bind(op)
  op.createQuote = async (a: any) => {
    const q = await origQuote(a)
    op.quotes.set(q.url, q.debitAmount)
    return q
  }
  const store = new Store(opts.path ?? ':memory:', new Cipher(KEY))
  const svc = new PaymentsService(store, op, { now: opts.now ?? (() => op.now), inProgressWaitMs: 300, inProgressPollMs: 10, log: opts.log })
  return { op, store, svc }
}

/** Crea un grant y lo deja ACTIVE con el hash correcto. */
export async function activeGrant(env: ReturnType<typeof makeEnv>, limit = 20_000_00, interval?: string) {
  const g = await env.svc.createGrant({
    userId: 'demo-user', walletAddress: MARTA, finishUri: 'http://localhost:5173/grant-callback',
    limit: { debitAmount: cop(limit), ...(interval ? { interval } : {}) },
  })
  const stored = env.store.getGrant(g.grantId)!
  const hash = interactHash(stored.clientNonce, stored.interactNonce, 'REF', stored.grantEndpointUri)
  await env.svc.continueGrant(g.grantId, { interactRef: 'REF', hash })
  return g.grantId
}
