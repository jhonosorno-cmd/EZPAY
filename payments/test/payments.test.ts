import { describe, expect, it } from 'vitest'
import { OpError } from '../src/errors.js'
import { Cipher } from '../src/crypto.js'
import { PaymentsService } from '../src/domain/service.js'
import { Store } from '../src/store/db.js'
import { activeGrant, cop, KEY, LAURA, makeEnv, MARTA } from './fakes.js'

const rejects = (p: Promise<unknown>, code: string, status?: number) =>
  expect(p).rejects.toMatchObject({ code, ...(status ? { status } : {}) })
const quote = (env: ReturnType<typeof makeEnv>, grantId: string, v: number) =>
  env.svc.createQuote({ grantId, receiver: LAURA, receiveAmount: cop(v) })
const opCreates = (env: ReturnType<typeof makeEnv>) => env.op.calls.filter((c) => c === 'createOutgoingPayment').length

describe('quotes', () => {
  it('creates a quote with the real debit and exceedsRemaining=false', async () => {
    const env = makeEnv()
    env.op.quoteDebit = () => cop(20_15)
    const g = await activeGrant(env, 200_00)
    const q = await quote(env, g, 20_00)
    expect(q).toMatchObject({ debitAmount: cop(20_15), receiveAmount: cop(20_00), exceedsRemaining: false })
    expect(q.quoteId).toMatch(/^q_/)
    expect(JSON.stringify(q)).not.toContain('rs.test')
  })
  it('exceedsRemaining is exact at the boundary', async () => {
    const env = makeEnv()
    env.op.quoteDebit = () => cop(20_15)
    const a = await activeGrant(env, 20_15)
    expect((await quote(env, a, 20_00)).exceedsRemaining).toBe(false)
    const b = await activeGrant(env, 20_14)
    expect((await quote(env, b, 20_00)).exceedsRemaining).toBe(true)
  })
  it('INVALID_RECEIVER on asset mismatch or unknown receiver', async () => {
    const env = makeEnv()
    env.op.wallets[LAURA] = { ...env.op.wallets[LAURA]!, assetCode: 'USD' }
    const g = await activeGrant(env)
    await rejects(quote(env, g, 10_00), 'INVALID_RECEIVER', 400)
    await rejects(env.svc.createQuote({ grantId: g, receiver: 'https://ilp.test/x', receiveAmount: cop(1) }), 'INVALID_RECEIVER')
  })
  it('GRANT_INVALID for a pending grant', async () => {
    const env = makeEnv()
    const { grantId } = await env.svc.createGrant({ userId: 'u', walletAddress: MARTA, finishUri: 'x', limit: { debitAmount: cop(100) } })
    await rejects(quote(env, grantId, 10), 'GRANT_INVALID', 401)
  })
  it('does not retry the write when OP fails', async () => {
    const env = makeEnv()
    const g = await activeGrant(env)
    env.op.failNext.createQuote = new OpError('network')
    await rejects(quote(env, g, 10), 'UPSTREAM_ERROR', 502)
    expect(env.op.calls.filter((c) => c === 'createQuote')).toHaveLength(1)
  })
})

describe('payments', () => {
  it('pays within budget and updates remaining', async () => {
    const env = makeEnv()
    env.op.quoteDebit = () => cop(20_15)
    const g = await activeGrant(env, 200_00)
    const q = await quote(env, g, 20_00)
    const r = await env.svc.pay('k1', { quoteId: q.quoteId })
    expect(r.status).toBe(201)
    expect(r.body).toMatchObject({ status: 'PROCESSING', debitAmount: cop(20_15) })
    expect((await env.svc.getGrant(g)).remaining).toEqual(cop(179_85))
  })
  it('requires Idempotency-Key', async () => {
    const env = makeEnv()
    await rejects(env.svc.pay(undefined, { quoteId: 'q' }), 'IDEMPOTENCY_KEY_REQUIRED', 400)
  })
  it('same key + same quote returns the identical response, one payment', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 60_00)
    const a = await env.svc.pay('k', { quoteId: q.quoteId })
    const b = await env.svc.pay('k', { quoteId: q.quoteId })
    expect(b).toEqual(a)
    expect(env.op.payments).toHaveLength(1)
    expect((await env.svc.getGrant(g)).remaining).toEqual(cop(40_00))
  })
  it('concurrent retries create a single payment', async () => {
    const env = makeEnv()
    env.op.createDelayMs = 30
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    const [a, b] = await Promise.all([env.svc.pay('k', { quoteId: q.quoteId }), env.svc.pay('k', { quoteId: q.quoteId })])
    expect(a).toEqual(b)
    expect(env.op.payments).toHaveLength(1)
  })
  it('422 when the key is reused for another quote', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    const q1 = await quote(env, g, 10_00)
    const q2 = await quote(env, g, 10_00)
    await env.svc.pay('k', { quoteId: q1.quoteId })
    await rejects(env.svc.pay('k', { quoteId: q2.quoteId }), 'IDEMPOTENCY_KEY_REUSED', 422)
    expect(env.op.payments).toHaveLength(1)
  })
  it('409 PAYMENT_IN_PROGRESS when the first attempt is slow', async () => {
    const env = makeEnv()
    env.op.createDelayMs = 700
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    const first = env.svc.pay('k', { quoteId: q.quoteId })
    await rejects(env.svc.pay('k', { quoteId: q.quoteId }), 'PAYMENT_IN_PROGRESS', 409)
    await first
    expect(env.op.payments).toHaveLength(1)
  })
  it('uncertain result: 502, other key gets 404, retry finds the existing payment', async () => {
    const env = makeEnv()
    env.op.createBehavior = ['timeout-created']
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    await rejects(env.svc.pay('k', { quoteId: q.quoteId }), 'UPSTREAM_ERROR', 502)
    await rejects(env.svc.pay('k2', { quoteId: q.quoteId }), 'QUOTE_NOT_FOUND', 404)
    const r = await env.svc.pay('k', { quoteId: q.quoteId })
    expect(r.status).toBe(201)
    expect(env.op.payments).toHaveLength(1)
    expect(opCreates(env)).toBe(1)
  })
  it('uncertain result where the payment was lost: retried once after searching', async () => {
    const env = makeEnv()
    env.op.createBehavior = ['timeout-lost']
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    await rejects(env.svc.pay('k', { quoteId: q.quoteId }), 'UPSTREAM_ERROR')
    const r = await env.svc.pay('k', { quoteId: q.quoteId })
    expect(r.status).toBe(201)
    expect(env.op.calls).toContain('findOutgoingPaymentByQuote')
    expect(env.op.payments).toHaveLength(1)
  })
  it('QUOTE_NOT_FOUND for a quote already paid with another key', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    await env.svc.pay('k1', { quoteId: q.quoteId })
    await rejects(env.svc.pay('k2', { quoteId: q.quoteId }), 'QUOTE_NOT_FOUND', 404)
    expect(env.op.payments).toHaveLength(1)
  })
  it('QUOTE_EXPIRED locally without calling OP', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    env.op.now += 6 * 60_000
    await rejects(env.svc.pay('k', { quoteId: q.quoteId }), 'QUOTE_EXPIRED', 409)
    expect(opCreates(env)).toBe(0)
  })
  it('QUOTE_EXPIRED when the server says invalid quote', async () => {
    const env = makeEnv()
    env.op.createBehavior = ['invalid_quote']
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    const r = await env.svc.pay('k', { quoteId: q.quoteId })
    expect(r).toMatchObject({ status: 409, body: { error: { code: 'QUOTE_EXPIRED' } } })
    expect(env.op.payments).toHaveLength(0)
  })
})

describe('budget', () => {
  it('LIMIT_EXCEEDED locally without calling OP to pay', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 10_00)
    const q = await quote(env, g, 15_00)
    expect(q.exceedsRemaining).toBe(true)
    await rejects(env.svc.pay('k', { quoteId: q.quoteId }), 'LIMIT_EXCEEDED', 403)
    expect(opCreates(env)).toBe(0)
  })
  it('server 403 with exhausted cap -> LIMIT_EXCEEDED; with room -> GRANT_INVALID', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    const q1 = await quote(env, g, 30_00)
    env.op.createBehavior = ['forbidden']
    env.op.spentSequence = [null, cop(80_00)] // el chequeo previo pasa; al recalcular tras el 403 el tope está agotado
    const spentFirst = await env.svc.pay('k1', { quoteId: q1.quoteId })
    expect(spentFirst).toMatchObject({ status: 403, body: { error: { code: 'LIMIT_EXCEEDED' } } })

    const q2 = await quote(env, g, 5_00)
    env.op.createBehavior = ['forbidden']
    env.op.serverSpent = null
    const r2 = await env.svc.pay('k2', { quoteId: q2.quoteId })
    expect(r2).toMatchObject({ status: 401, body: { error: { code: 'GRANT_INVALID' } } })
  })
  it('spent = max(server, local)', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 50_00)
    await env.svc.pay('k', { quoteId: q.quoteId })
    env.op.serverSpent = cop(30_00)
    expect((await env.svc.getGrant(g)).spent).toEqual(cop(50_00))
    env.op.serverSpent = cop(70_00)
    expect((await env.svc.getGrant(g)).spent).toEqual(cop(70_00))
  })
  it('exact integer arithmetic: 0.10 + 0.20 + 19.99', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    for (const [i, v] of [10, 20, 19_99].entries()) {
      const q = await quote(env, g, v)
      await env.svc.pay('k' + i, { quoteId: q.quoteId })
    }
    expect((await env.svc.getGrant(g)).spent.value).toBe('2029')
  })
  it('a FAILED payment does not consume budget', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 50_00)
    const r = await env.svc.pay('k', { quoteId: q.quoteId })
    env.op.payments[0]!.failed = true
    await env.svc.getPayment((r.body as any).paymentId)
    expect((await env.svc.getGrant(g)).spent).toEqual(cop(0))
  })
})

describe('tokens', () => {
  it('rotates a token that is about to expire and pays', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    env.op.now += 11 * 60_000 // el token emitido hace 11 min
    const q2 = await env.svc.createQuote({ grantId: g, receiver: LAURA, receiveAmount: cop(10_00) })
    const r = await env.svc.pay('k', { quoteId: q2.quoteId })
    expect(r.status).toBe(201)
    expect(env.op.calls).toContain('rotateToken')
    void q
  })
  it('revoked token -> GRANT_INVALID after one rotate attempt', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    env.op.createBehavior = ['unauthorized']
    env.op.rotateFails = true
    const r = await env.svc.pay('k', { quoteId: q.quoteId })
    expect(r).toMatchObject({ status: 401, body: { error: { code: 'GRANT_INVALID' } } })
    expect(env.op.calls.filter((c) => c === 'rotateToken')).toHaveLength(1)
  })
  it('401 on create -> rotate once and retry succeeds', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    env.op.createBehavior = ['unauthorized']
    const r = await env.svc.pay('k', { quoteId: q.quoteId })
    expect(r.status).toBe(201)
  })
})

describe('payment status', () => {
  it('COMPLETED when sent >= debit, PROCESSING otherwise, 404 unknown', async () => {
    const env = makeEnv()
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    const id = ((await env.svc.pay('k', { quoteId: q.quoteId })).body as any).paymentId
    expect((await env.svc.getPayment(id)).status).toBe('PROCESSING')
    env.op.payments[0]!.sentAmount = cop(10_00)
    expect((await env.svc.getPayment(id)).status).toBe('COMPLETED')
    await rejects(env.svc.getPayment('p_nope'), 'PAYMENT_NOT_FOUND', 404)
  })
})

describe('restarts', () => {
  it('state and idempotency survive a restart; reserved keys are released', async () => {
    const path = `/tmp/ezpay-test-${process.pid}-${Date.now()}.db`
    const env = makeEnv({ path })
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 30_00)
    const first = await env.svc.pay('K', { quoteId: q.quoteId })
    env.store.reserveKey('R', q.quoteId, 0) // clave reservada que nunca envió
    env.store.close()

    const store2 = new Store(path, new Cipher(KEY))
    const svc2 = new PaymentsService(store2, env.op, { now: () => env.op.now })
    svc2.recover()
    expect((await svc2.getGrant(g)).remaining).toEqual(cop(70_00))
    expect(await svc2.pay('K', { quoteId: q.quoteId })).toEqual(first)
    expect(env.op.payments).toHaveLength(1)
    expect(store2.getKey('R')).toBeNull()
  })
  it('a SENT key becomes UNKNOWN and searches OP before creating', async () => {
    const path = `/tmp/ezpay-test-${process.pid}-${Date.now()}-b.db`
    const env = makeEnv({ path })
    env.op.createBehavior = ['timeout-created']
    const g = await activeGrant(env, 100_00)
    const q = await quote(env, g, 10_00)
    await env.svc.pay('K', { quoteId: q.quoteId }).catch(() => {})
    env.store.setKeyState('K', 'SENT') // como si el proceso hubiera caído antes de saber el resultado
    env.store.close()
    const store2 = new Store(path, new Cipher(KEY))
    const svc2 = new PaymentsService(store2, env.op, { now: () => env.op.now })
    svc2.recover()
    expect((await svc2.pay('K', { quoteId: q.quoteId })).status).toBe(201)
    expect(env.op.payments).toHaveLength(1)
  })
})

describe('secrets', () => {
  it('tokens are not stored in plaintext', async () => {
    const path = `/tmp/ezpay-test-${process.pid}-${Date.now()}-c.db`
    const env = makeEnv({ path })
    await activeGrant(env)
    env.store.db.exec('PRAGMA wal_checkpoint(TRUNCATE)')
    const { readFileSync } = await import('node:fs')
    const raw = readFileSync(path).toString('latin1')
    expect(raw).not.toContain('ACCESS-TOKEN-SECRET')
    expect(raw).not.toContain('CONTINUE-TOKEN-SECRET')
  })
})
