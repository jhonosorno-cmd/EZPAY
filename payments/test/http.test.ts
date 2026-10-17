import { describe, expect, it } from 'vitest'
import request from 'supertest'
import { createApp, instrument } from '../src/http/app.js'
import { loadConfig } from '../src/config.js'
import { PaymentsService } from '../src/domain/service.js'
import { interactHash } from '../src/crypto.js'
import { LAURA, MARTA, cop, makeEnv } from './fakes.js'

function build() {
  const env = makeEnv()
  const logs: any[] = []
  const svc = new PaymentsService(env.store, instrument(env.op), { now: () => env.op.now })
  const app = createApp({ svc, ping: () => env.store.ping(), log: (l) => logs.push(l) })
  return { ...env, app, logs }
}

describe('http', () => {
  it('health answers without calling Open Payments', async () => {
    const { app, op } = build()
    const r = await request(app).get('/v1/health')
    expect(r.status).toBe(200)
    expect(r.body).toEqual({ ok: true })
    expect(op.calls).toHaveLength(0)
  })
  it('uniform error format and requestId propagation', async () => {
    const { app, logs } = build()
    const r = await request(app).get('/v1/grants/g_nope').set('X-Request-Id', 'abc-123')
    expect(r.status).toBe(404)
    expect(r.body).toEqual({ error: { code: 'GRANT_NOT_FOUND', message: 'GRANT_NOT_FOUND' } })
    expect(logs.at(-1)).toMatchObject({ requestId: 'abc-123', method: 'GET', status: 404 })
  })
  it('400 INVALID_AMOUNT for a numeric value', async () => {
    const { app } = build()
    const r = await request(app).post('/v1/grants').send({
      userId: 'u', walletAddress: MARTA, finishUri: 'x', limit: { debitAmount: { value: 5, assetCode: 'COP', assetScale: 2 } },
    })
    expect(r.status).toBe(400)
    expect(r.body.error.code).toBe('INVALID_AMOUNT')
  })
  it('400 on malformed JSON, 500 without internals on unexpected errors', async () => {
    const { app, op } = build()
    expect((await request(app).post('/v1/grants').set('content-type', 'application/json').send('{bad')).body.error.code).toBe('INTERNAL_ERROR')
    op.getWallet = async () => { throw new TypeError('boom https://secret.example/x TOKEN') }
    const r = await request(app).post('/v1/grants').send({ userId: 'u', walletAddress: MARTA, finishUri: 'x', limit: { debitAmount: cop(1) } })
    expect(r.status).toBe(400) // un fallo no clasificado al resolver la wallet es INVALID_WALLET
    op.requestGrant = async () => { throw new TypeError('boom https://secret.example/x TOKEN') }
    op.getWallet = async () => op.wallets[MARTA]!
    const r2 = await request(app).post('/v1/grants').send({ userId: 'u', walletAddress: MARTA, finishUri: 'x', limit: { debitAmount: cop(1) } })
    expect(r2.status).toBe(500)
    expect(JSON.stringify(r2.body)).not.toMatch(/secret|TOKEN|boom/)
  })
  it('full flow over HTTP: no leaks in responses or logs, 204 on DELETE, Idempotency-Key required', async () => {
    const { app, store, logs } = build()
    const g = (await request(app).post('/v1/grants').send({
      userId: 'demo-user', walletAddress: MARTA, finishUri: 'http://localhost:5173/grant-callback', limit: { debitAmount: cop(200_00) },
    })).body
    const s = store.getGrant(g.grantId)!
    const hash = interactHash(s.clientNonce, s.interactNonce, 'REF', s.grantEndpointUri)
    const c = await request(app).post(`/v1/grants/${g.grantId}/continue`).send({ interactRef: 'REF', hash })
    expect(c.status).toBe(200)
    const q = (await request(app).post('/v1/quotes').send({ grantId: g.grantId, receiver: LAURA, receiveAmount: cop(20_00) })).body
    expect((await request(app).post('/v1/payments').send({ quoteId: q.quoteId })).body.error.code).toBe('IDEMPOTENCY_KEY_REQUIRED')
    const p = await request(app).post('/v1/payments').set('Idempotency-Key', 'k1').send({ quoteId: q.quoteId })
    expect(p.status).toBe(201)
    const st = await request(app).get(`/v1/payments/${p.body.paymentId}`)
    expect(st.body.status).toBe('PROCESSING')
    expect((await request(app).delete(`/v1/grants/${g.grantId}`)).status).toBe(204)

    const everything = JSON.stringify([c.body, q, p.body, st.body, logs])
    for (const secret of ['ACCESS-TOKEN', 'CONTINUE-TOKEN', 'inonce', hash, s.clientNonce, 'rs.test', 'REF'])
      expect(everything).not.toContain(secret)
    expect(logs.every((l) => 'requestId' in l && 'durationMs' in l)).toBe(true)
    expect(logs.some((l) => l.opCalls > 0)).toBe(true)
  })
})

describe('config', () => {
  const base = { WALLET_ADDRESS: 'https://ilp.test/m', KEY_ID: 'k', PRIVATE_KEY_PATH: '/nonexistent', DB_ENCRYPTION_KEY: Buffer.alloc(32).toString('base64') }
  it('names the missing variable without printing values', () => {
    expect(() => loadConfig({ ...base, PRIVATE_KEY_PATH: __filename, DB_ENCRYPTION_KEY: '' })).toThrow(/DB_ENCRYPTION_KEY/)
    expect(() => loadConfig({ ...base, KEY_ID: undefined })).toThrow(/KEY_ID/)
    expect(() => loadConfig(base)).toThrow(/PRIVATE_KEY_PATH/)
  })
  it('rejects a short encryption key', () => {
    expect(() => loadConfig({ ...base, PRIVATE_KEY_PATH: __filename, DB_ENCRYPTION_KEY: 'c2hvcnQ=' })).toThrow(/DB_ENCRYPTION_KEY/)
  })
})
