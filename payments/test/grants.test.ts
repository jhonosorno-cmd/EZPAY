import { describe, expect, it } from 'vitest'
import { OpError } from '../src/errors.js'
import { interactHash } from '../src/crypto.js'
import { activeGrant, cop, makeEnv, MARTA } from './fakes.js'

const body = (extra = {}) => ({
  userId: 'demo-user', walletAddress: MARTA, finishUri: 'http://localhost:5173/grant-callback',
  limit: { debitAmount: cop(100_00) }, ...extra,
})
const rejects = (p: Promise<unknown>, code: string, status?: number) =>
  expect(p).rejects.toMatchObject({ code, ...(status ? { status } : {}) })

describe('amount validation', () => {
  it.each([['10.5'], ['-5'], [''], ['1,000'], ['0']])('rejects %j', async (v) => {
    const env = makeEnv()
    await rejects(env.svc.createGrant(body({ limit: { debitAmount: { ...cop(1), value: v } } })), 'INVALID_AMOUNT', 400)
  })
  it('rejects a numeric value', async () => {
    const env = makeEnv()
    await rejects(env.svc.createGrant(body({ limit: { debitAmount: { ...cop(1), value: 5 } } })), 'INVALID_AMOUNT')
  })
})

describe('grant creation', () => {
  it('creates a PENDING grant with a total cap', async () => {
    const env = makeEnv()
    const r = await env.svc.createGrant(body())
    expect(r).toMatchObject({ status: 'PENDING', interactUrl: expect.any(String) })
    expect(r.grantId).toMatch(/^g_/)
    expect(JSON.stringify(r)).not.toContain('TOKEN')
  })
  it('INVALID_WALLET when the wallet does not resolve', async () => {
    const env = makeEnv()
    await rejects(env.svc.createGrant(body({ walletAddress: 'https://ilp.test/nobody' })), 'INVALID_WALLET', 400)
  })
  it('UPSTREAM_ERROR when Open Payments times out', async () => {
    const env = makeEnv()
    env.op.failNext.getWallet = new OpError('timeout')
    await rejects(env.svc.createGrant(body()), 'UPSTREAM_ERROR', 502)
  })
})

describe('continue + hash', () => {
  it('activates with a correct hash and returns remaining', async () => {
    const env = makeEnv()
    const id = await activeGrant(env, 100_00)
    const g = await env.svc.getGrant(id)
    expect(g).toMatchObject({ status: 'ACTIVE', remaining: cop(100_00), spent: cop(0) })
  })
  it('INVALID_HASH with a tampered hash and does not continue', async () => {
    const env = makeEnv()
    const { grantId } = await env.svc.createGrant(body())
    await rejects(env.svc.continueGrant(grantId, { interactRef: 'REF', hash: 'AAAA' }), 'INVALID_HASH', 400)
    expect(env.op.calls).not.toContain('continueGrant')
  })
  it('INVALID_HASH when only the trailing slash of the URI differs', async () => {
    const env = makeEnv()
    const { grantId } = await env.svc.createGrant(body())
    const s = env.store.getGrant(grantId)!
    const hash = interactHash(s.clientNonce, s.interactNonce, 'REF', s.grantEndpointUri + '/')
    await rejects(env.svc.continueGrant(grantId, { interactRef: 'REF', hash }), 'INVALID_HASH')
  })
  it('GRANT_NOT_PENDING when continued twice', async () => {
    const env = makeEnv()
    const id = await activeGrant(env)
    await rejects(env.svc.continueGrant(id, { interactRef: 'REF', hash: 'x' }), 'GRANT_NOT_PENDING', 409)
  })
  it('GRANT_NOT_FOUND for unknown grant', async () => {
    await rejects(makeEnv().svc.continueGrant('g_nope', {}), 'GRANT_NOT_FOUND', 404)
  })
  it('GRANT_REJECTED when the user rejects', async () => {
    const env = makeEnv()
    env.op.rejectOnContinue = true
    const { grantId } = await env.svc.createGrant(body())
    const s = env.store.getGrant(grantId)!
    const hash = interactHash(s.clientNonce, s.interactNonce, 'REF', s.grantEndpointUri)
    await rejects(env.svc.continueGrant(grantId, { interactRef: 'REF', hash }), 'GRANT_REJECTED', 403)
    expect(env.store.getGrant(grantId)!.status).toBe('REJECTED')
  })
})

describe('expiry and cancellation', () => {
  it('a PENDING grant older than 10 min is EXPIRED and cannot continue', async () => {
    const t = { v: 1_000_000 }
    const env = makeEnv({ now: () => t.v })
    const { grantId } = await env.svc.createGrant(body())
    t.v += 11 * 60_000
    expect((await env.svc.getGrant(grantId)).status).toBe('EXPIRED')
    await rejects(env.svc.continueGrant(grantId, { interactRef: 'a', hash: 'b' }), 'GRANT_NOT_PENDING')
  })
  it('DELETE cancels, is idempotent and 404s on unknown', async () => {
    const env = makeEnv()
    const id = await activeGrant(env)
    await env.svc.cancelGrant(id)
    expect(env.op.calls.filter((c) => c === 'cancelGrant')).toHaveLength(1)
    expect((await env.svc.getGrant(id)).status).toBe('EXPIRED')
    await env.svc.cancelGrant(id)
    expect(env.op.calls.filter((c) => c === 'cancelGrant')).toHaveLength(1)
    await rejects(env.svc.cancelGrant('g_nope'), 'GRANT_NOT_FOUND', 404)
  })
  it('502 on cancel failure but the grant ends up EXPIRED', async () => {
    const env = makeEnv()
    const id = await activeGrant(env)
    env.op.failNext.cancelGrant = new OpError('timeout')
    await rejects(env.svc.cancelGrant(id), 'UPSTREAM_ERROR', 502)
    expect(env.store.getGrant(id)!.status).toBe('EXPIRED')
  })
  it('an interval with exhausted repeats is EXPIRED; a new period resets spent', async () => {
    const t = { v: Date.parse('2026-10-16T12:00:00Z') }
    const env = makeEnv({ now: () => t.v })
    env.op.now = t.v
    const id = await activeGrant(env, 200_00, 'R1/2026-10-16T00:00:00Z/P1D')
    t.v = Date.parse('2026-10-17T01:00:00Z')
    expect((await env.svc.getGrant(id)).status).toBe('EXPIRED')
  })
  it('weekly period only counts payments from the current week', async () => {
    const t = { v: Date.parse('2026-10-16T12:00:00Z') }
    const env = makeEnv({ now: () => t.v })
    env.op.now = t.v
    const id = await activeGrant(env, 200_00, 'R52/2026-10-12T00:00:00Z/P1W')
    const q = await env.svc.createQuote({ grantId: id, receiver: 'https://ilp.test/laura', receiveAmount: cop(150_00) })
    await env.svc.pay('k1', { quoteId: q.quoteId })
    expect((await env.svc.getGrant(id)).remaining).toEqual(cop(50_00))
    t.v = Date.parse('2026-10-20T12:00:00Z')
    expect(await env.svc.getGrant(id)).toMatchObject({ spent: cop(0), remaining: cop(200_00), status: 'ACTIVE' })
  })
})

describe('several active grants', () => {
  it('a second grant does not affect the first', async () => {
    const env = makeEnv()
    const a = await activeGrant(env, 200_00)
    const b = await activeGrant(env, 300_00)
    const q = await env.svc.createQuote({ grantId: b, receiver: 'https://ilp.test/laura', receiveAmount: cop(300_00) })
    await env.svc.pay('kb', { quoteId: q.quoteId })
    expect(await env.svc.getGrant(a)).toMatchObject({ status: 'ACTIVE', remaining: cop(200_00) })
  })
})
