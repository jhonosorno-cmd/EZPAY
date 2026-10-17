import { DatabaseSync } from 'node:sqlite'
import { Cipher } from '../crypto.js'
import type { Amount } from '../money.js'

export type GrantStatus = 'PENDING' | 'ACTIVE' | 'REJECTED' | 'EXPIRED'
export type Grant = {
  id: string; userId: string; walletAddress: string; grantEndpointUri: string
  status: GrantStatus; limit: { debitAmount: Amount; interval?: string }
  clientNonce: string; interactNonce: string; continueUri: string; continueToken: string
  accessToken: string | null; accessTokenExpiresAt: number | null; manageUrl: string | null
  createdAt: number; activatedAt: number | null
}
export type Quote = {
  id: string; grantId: string; opQuoteUrl: string; receiver: string
  debitAmount: Amount; receiveAmount: Amount; expiresAt: number; status: 'CREATED' | 'USED'
}
export type PaymentStatus = 'PROCESSING' | 'COMPLETED' | 'FAILED'
export type Payment = {
  id: string; grantId: string; quoteId: string; opPaymentUrl: string
  debitAmount: Amount; sentAmount: Amount; status: PaymentStatus; createdAt: number
}
export type KeyState = 'RESERVED' | 'SENT' | 'UNKNOWN' | 'DONE'
export type IdemKey = { key: string; quoteId: string; state: KeyState; response: { status: number; body: unknown } | null }

const SCHEMA = `
CREATE TABLE IF NOT EXISTS grants (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, wallet_address TEXT NOT NULL, grant_endpoint_uri TEXT NOT NULL,
  status TEXT NOT NULL, limit_json TEXT NOT NULL, client_nonce TEXT NOT NULL, interact_nonce TEXT NOT NULL,
  continue_uri TEXT NOT NULL, continue_token TEXT NOT NULL, access_token TEXT, access_token_expires_at INTEGER,
  manage_url TEXT, created_at INTEGER NOT NULL, activated_at INTEGER);
CREATE TABLE IF NOT EXISTS quotes (
  id TEXT PRIMARY KEY, grant_id TEXT NOT NULL, op_quote_url TEXT NOT NULL, receiver TEXT NOT NULL,
  debit_amount TEXT NOT NULL, receive_amount TEXT NOT NULL, expires_at INTEGER NOT NULL, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS payments (
  id TEXT PRIMARY KEY, grant_id TEXT NOT NULL, quote_id TEXT NOT NULL, op_payment_url TEXT NOT NULL,
  debit_amount TEXT NOT NULL, sent_amount TEXT NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS idempotency_keys (
  key TEXT PRIMARY KEY, quote_id TEXT NOT NULL, state TEXT NOT NULL, response TEXT, created_at INTEGER NOT NULL);
`

const j = (a: Amount) => JSON.stringify(a)
type Row = Record<string, any>

export class Store {
  readonly db: DatabaseSync
  constructor(path: string, private readonly cipher: Cipher) {
    this.db = new DatabaseSync(path)
    if (path !== ':memory:') this.db.exec('PRAGMA journal_mode=WAL')
    this.db.exec(SCHEMA)
  }
  ping() { this.db.prepare('SELECT 1').get() }
  close() { this.db.close() }
  /** Todo lo que haga `fn` ocurre en una sola transacción síncrona. */
  tx<T>(fn: () => T): T {
    this.db.exec('BEGIN IMMEDIATE')
    try { const r = fn(); this.db.exec('COMMIT'); return r } catch (e) { this.db.exec('ROLLBACK'); throw e }
  }

  // ---- grants
  insertGrant(g: Grant) {
    this.db.prepare(`INSERT INTO grants VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).run(
      g.id, g.userId, g.walletAddress, g.grantEndpointUri, g.status, JSON.stringify(g.limit), g.clientNonce,
      g.interactNonce, g.continueUri, this.cipher.encrypt(g.continueToken),
      g.accessToken ? this.cipher.encrypt(g.accessToken) : null, g.accessTokenExpiresAt, g.manageUrl, g.createdAt, g.activatedAt)
  }
  getGrant(id: string): Grant | null {
    const r = this.db.prepare('SELECT * FROM grants WHERE id=?').get(id) as Row | undefined
    return r ? this.toGrant(r) : null
  }
  updateGrant(id: string, p: Partial<Pick<Grant, 'status' | 'accessToken' | 'accessTokenExpiresAt' | 'manageUrl' | 'activatedAt'>>) {
    const sets: string[] = []; const vals: any[] = []
    if (p.status !== undefined) { sets.push('status=?'); vals.push(p.status) }
    if (p.accessToken !== undefined) { sets.push('access_token=?'); vals.push(p.accessToken ? this.cipher.encrypt(p.accessToken) : null) }
    if (p.accessTokenExpiresAt !== undefined) { sets.push('access_token_expires_at=?'); vals.push(p.accessTokenExpiresAt) }
    if (p.manageUrl !== undefined) { sets.push('manage_url=?'); vals.push(p.manageUrl) }
    if (p.activatedAt !== undefined) { sets.push('activated_at=?'); vals.push(p.activatedAt) }
    if (sets.length) this.db.prepare(`UPDATE grants SET ${sets.join(',')} WHERE id=?`).run(...vals, id)
  }
  private toGrant(r: Row): Grant {
    return {
      id: r.id, userId: r.user_id, walletAddress: r.wallet_address, grantEndpointUri: r.grant_endpoint_uri,
      status: r.status, limit: JSON.parse(r.limit_json), clientNonce: r.client_nonce, interactNonce: r.interact_nonce,
      continueUri: r.continue_uri, continueToken: this.cipher.decrypt(r.continue_token),
      accessToken: r.access_token ? this.cipher.decrypt(r.access_token) : null,
      accessTokenExpiresAt: r.access_token_expires_at, manageUrl: r.manage_url, createdAt: r.created_at, activatedAt: r.activated_at,
    }
  }

  // ---- quotes
  insertQuote(q: Quote) {
    this.db.prepare('INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?)').run(
      q.id, q.grantId, q.opQuoteUrl, q.receiver, j(q.debitAmount), j(q.receiveAmount), q.expiresAt, q.status)
  }
  getQuote(id: string): Quote | null {
    const r = this.db.prepare('SELECT * FROM quotes WHERE id=?').get(id) as Row | undefined
    return r ? { id: r.id, grantId: r.grant_id, opQuoteUrl: r.op_quote_url, receiver: r.receiver,
      debitAmount: JSON.parse(r.debit_amount), receiveAmount: JSON.parse(r.receive_amount), expiresAt: r.expires_at, status: r.status } : null
  }
  setQuoteStatus(id: string, status: Quote['status']) { this.db.prepare('UPDATE quotes SET status=? WHERE id=?').run(status, id) }

  // ---- payments
  insertPayment(p: Payment) {
    this.db.prepare('INSERT INTO payments VALUES (?,?,?,?,?,?,?,?)').run(
      p.id, p.grantId, p.quoteId, p.opPaymentUrl, j(p.debitAmount), j(p.sentAmount), p.status, p.createdAt)
  }
  getPayment(id: string): Payment | null {
    const r = this.db.prepare('SELECT * FROM payments WHERE id=?').get(id) as Row | undefined
    return r ? this.toPayment(r) : null
  }
  paymentsOfGrant(grantId: string): Payment[] {
    return (this.db.prepare('SELECT * FROM payments WHERE grant_id=?').all(grantId) as Row[]).map((r) => this.toPayment(r))
  }
  updatePayment(id: string, p: { status: PaymentStatus; sentAmount: Amount }) {
    this.db.prepare('UPDATE payments SET status=?, sent_amount=? WHERE id=?').run(p.status, j(p.sentAmount), id)
  }
  private toPayment(r: Row): Payment {
    return { id: r.id, grantId: r.grant_id, quoteId: r.quote_id, opPaymentUrl: r.op_payment_url,
      debitAmount: JSON.parse(r.debit_amount), sentAmount: JSON.parse(r.sent_amount), status: r.status, createdAt: r.created_at }
  }

  // ---- idempotency
  /** false si la clave ya existe (la PK hace atómica la reserva). */
  reserveKey(key: string, quoteId: string, now: number): boolean {
    try { this.db.prepare("INSERT INTO idempotency_keys VALUES (?,?,'RESERVED',NULL,?)").run(key, quoteId, now); return true }
    catch (e: any) { if (/UNIQUE|constraint/i.test(String(e?.message))) return false; throw e }
  }
  getKey(key: string): IdemKey | null {
    const r = this.db.prepare('SELECT * FROM idempotency_keys WHERE key=?').get(key) as Row | undefined
    return r ? { key: r.key, quoteId: r.quote_id, state: r.state, response: r.response ? JSON.parse(r.response) : null } : null
  }
  setKeyState(key: string, state: KeyState, response?: IdemKey['response']) {
    this.db.prepare('UPDATE idempotency_keys SET state=?, response=COALESCE(?,response) WHERE key=?')
      .run(state, response ? JSON.stringify(response) : null, key)
  }
  deleteKey(key: string) { this.db.prepare('DELETE FROM idempotency_keys WHERE key=?').run(key) }
  /** Al arrancar: RESERVED se borra (nunca se envió); SENT pasa a UNKNOWN. */
  recoverKeys() {
    this.db.exec("DELETE FROM idempotency_keys WHERE state='RESERVED'")
    this.db.exec("UPDATE idempotency_keys SET state='UNKNOWN' WHERE state='SENT'")
  }
}
