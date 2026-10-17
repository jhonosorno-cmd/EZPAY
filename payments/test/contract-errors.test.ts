import { describe, expect, it } from 'vitest'
import request from 'supertest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { parse } from 'yaml'
import { interactHash } from '../src/crypto.js'
import { createApp } from '../src/http/app.js'
import { LAURA, MARTA, activeGrant, cop, makeEnv } from './fakes.js'

const contractPath = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'openapi', 'contract-a.yaml')
const contract: { components: { schemas: { ErrorCode: { enum: string[] } } } } = parse(readFileSync(contractPath, 'utf8'))
const CONTRACT_CODES: readonly string[] = contract.components.schemas.ErrorCode.enum

function build() {
  const env = makeEnv()
  const app = createApp({ svc: env.svc, ping: () => env.store.ping(), log: () => {} })
  return { ...env, app }
}

const grantBody = (extra: Record<string, unknown> = {}) => ({
  userId: 'demo-user',
  walletAddress: MARTA,
  finishUri: 'http://localhost:5173/grant-callback',
  limit: { debitAmount: cop(100_00) },
  ...extra,
})

const pendingGrant = async (env: ReturnType<typeof build>) => {
  const g = await env.svc.createGrant(grantBody())
  const stored = env.store.getGrant(g.grantId)!
  const hash = interactHash(stored.clientNonce, stored.interactNonce, 'REF', stored.grantEndpointUri)
  return { grantId: g.grantId, hash }
}

describe('cases Contract A does not cover map to existing codes (decision D-10a)', () => {
  it('unknown route -> 500 INTERNAL_ERROR', async () => {
    const { app } = build()
    const r = await request(app).get('/v1/does-not-exist')
    expect(r.status).toBe(500)
    expect(r.body.error.code).toBe('INTERNAL_ERROR')
  })
  it('malformed JSON -> 500 INTERNAL_ERROR', async () => {
    const { app } = build()
    const r = await request(app).post('/v1/grants').set('content-type', 'application/json').send('{bad')
    expect(r.status).toBe(500)
    expect(r.body.error.code).toBe('INTERNAL_ERROR')
  })
  it('missing userId, walletAddress, finishUri, limit or limit.debitAmount -> 500 INTERNAL_ERROR', async () => {
    const { app } = build()
    for (const body of [
      grantBody({ userId: undefined }),
      grantBody({ walletAddress: undefined }),
      grantBody({ finishUri: undefined }),
      grantBody({ limit: undefined }),
      grantBody({ limit: {} }),
      grantBody({ limit: '100.00' }),
    ]) {
      const r = await request(app).post('/v1/grants').send(body)
      expect(r.status, JSON.stringify(body)).toBe(500)
      expect(r.body.error.code).toBe('INTERNAL_ERROR')
    }
  })
  it('unsupported interval -> 400 INVALID_AMOUNT', async () => {
    const { app } = build()
    const r = await request(app).post('/v1/grants').send(grantBody({ limit: { debitAmount: cop(100_00), interval: 'R1/2026-10-16T00:00:00Z/P1M' } }))
    expect(r.status).toBe(400)
    expect(r.body.error.code).toBe('INVALID_AMOUNT')
  })
})

describe('every emitted error code is in the Contract A enum', () => {
  it('battery of failures emits only contract codes', async () => {
    const env = build()
    const { app, op, store } = env

    const emit = async (p: Promise<{ status: number; body: any }>) => {
      const r = await p
      return r.body?.error?.code as string | undefined
    }

    const http = request(app)
    const codes: (string | undefined)[] = []
    codes.push(await emit(http.get('/v1/grants/g_nope') as any))
    codes.push(await emit(http.post('/v1/grants').send(grantBody({ userId: undefined })) as any))
    codes.push(await emit(http.post('/v1/grants').send(grantBody({ limit: { debitAmount: { ...cop(1), value: '1.5' } } })) as any))
    codes.push(await emit(http.post('/v1/grants').send(grantBody({ walletAddress: 'https://ilp.test/nobody' })) as any))
    codes.push(await emit(http.post('/v1/grants').send(grantBody({ limit: { debitAmount: cop(100_00), interval: 'R1/2026-10-16T00:00:00Z/P1M' } })) as any))

    const rejectedEnv = build()
    rejectedEnv.op.rejectOnContinue = true
    const rej = await pendingGrant(rejectedEnv)
    codes.push(await emit(request(rejectedEnv.app).post(`/v1/grants/${rej.grantId}/continue`).send({ interactRef: 'REF', hash: rej.hash }) as any))

    const bad = await pendingGrant(env)
    codes.push(await emit(http.post(`/v1/grants/${bad.grantId}/continue`).send({ interactRef: 'REF', hash: 'TAMPERED' }) as any))
    codes.push(await emit(http.post('/v1/grants/g_nope/continue').send({ interactRef: 'REF', hash: 'x' }) as any))

    const quoteBody = { grantId: 'g_unknown', receiver: LAURA, receiveAmount: cop(1) }
    codes.push(await emit(http.post('/v1/quotes').send(quoteBody) as any))
    const pending = await pendingGrant(env)
    const activeId = await activeGrant(env)
    codes.push(await emit(http.post(`/v1/grants/${activeId}/continue`).send({ interactRef: 'REF', hash: 'x' }) as any))
    codes.push(await emit(http.post('/v1/quotes').send({ grantId: pending.grantId, receiver: LAURA, receiveAmount: cop(1) }) as any))
    codes.push(await emit(http.post('/v1/quotes').send({ grantId: activeId, receiver: 'https://ilp.test/none', receiveAmount: cop(1) }) as any))

    codes.push(await emit(http.post('/v1/payments').send({ quoteId: 'q_nope' }) as any))
    codes.push(await emit(http.post('/v1/payments').set('Idempotency-Key', 'k').send({ quoteId: 'q_nope' }) as any))

    codes.push(await emit(http.delete('/v1/grants/g_nope') as any))
    codes.push(await emit(http.get('/v1/payments/p_nope') as any))
    codes.push(await emit(http.get('/v1/nope') as any))

    op.failNext.createOutgoingPayment = new (await import('../src/errors.js')).OpError('timeout')
    const g = await env.svc.createGrant(grantBody())
    const s = store.getGrant(g.grantId)!
    const h = interactHash(s.clientNonce, s.interactNonce, 'REF', s.grantEndpointUri)
    await env.svc.continueGrant(g.grantId, { interactRef: 'REF', hash: h })
    const q = await env.svc.createQuote({ grantId: g.grantId, receiver: LAURA, receiveAmount: cop(1) })
    codes.push(await emit(http.post('/v1/payments').set('Idempotency-Key', 'k-up').send({ quoteId: q.quoteId }) as any))

    const filtered = codes.filter((c) => c !== undefined)
    expect(filtered.length).toBeGreaterThanOrEqual(14)
    for (const code of filtered) expect(CONTRACT_CODES, `code ${code} is not in the Contract A enum`).toContain(code)
    for (const expected of ['INTERNAL_ERROR', 'INVALID_AMOUNT', 'INVALID_WALLET', 'INVALID_RECEIVER', 'INVALID_HASH', 'GRANT_REJECTED', 'GRANT_NOT_FOUND', 'GRANT_NOT_PENDING', 'GRANT_INVALID', 'IDEMPOTENCY_KEY_REQUIRED', 'QUOTE_NOT_FOUND', 'PAYMENT_NOT_FOUND', 'UPSTREAM_ERROR'])
      expect(filtered, `the battery never exercised ${expected}`).toContain(expected)
  })
})