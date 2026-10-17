/* Cancelación con GNAP grant.cancel (unidad 8): el doble registra continueUri/continueToken,
   idempotencia, cancelación de grants sin continuar y el grant muerto tras DELETE. */
import { describe, expect, it } from 'vitest'
import { Cipher } from '../src/crypto.js'
import { OpError } from '../src/errors.js'
import { activeGrant, cop, KEY, LAURA, makeEnv, MARTA } from './fakes.js'

const rejects = (p: Promise<unknown>, code: string, status?: number) =>
  expect(p).rejects.toMatchObject({ code, ...(status ? { status } : {}) })
const grantBody = (cap = 100_00) => ({
  userId: 'demo-user', walletAddress: MARTA, finishUri: 'http://localhost:5173/grant-callback',
  limit: { debitAmount: cop(cap) },
})

describe('cancellation with grant.cancel (unit 8)', () => {
  it('DELETE calls grant.cancel with the stored continueUri/continueToken (5a)', async () => {
    const env = makeEnv()
    const id = await activeGrant(env, 100_00)
    await env.svc.cancelGrant(id)
    const stored = env.store.getGrant(id)!
    expect(env.op.cancelArgs).toEqual({ continueUri: stored.continueUri, continueToken: stored.continueToken })
    expect(env.op.calls).not.toContain('revokeToken')
  })

  it('second DELETE is idempotent, unknown id is 404 and a wallet failure leaves EXPIRED (5b)', async () => {
    const env = makeEnv()
    const id = await activeGrant(env, 100_00)
    await env.svc.cancelGrant(id)
    await env.svc.cancelGrant(id)
    expect(env.op.calls.filter((c) => c === 'cancelGrant')).toHaveLength(1)
    await rejects(env.svc.cancelGrant('g_nope'), 'GRANT_NOT_FOUND', 404)

    const env2 = makeEnv()
    const id2 = await activeGrant(env2, 100_00)
    env2.op.failNext.cancelGrant = new OpError('timeout')
    await rejects(env2.svc.cancelGrant(id2), 'UPSTREAM_ERROR', 502)
    expect(env2.store.getGrant(id2)!.status).toBe('EXPIRED')
  })

  it('a PENDING grant is cancelled via grant.cancel; without continue data it only expires locally (req 3)', async () => {
    const env = makeEnv()
    const pending = await env.svc.createGrant(grantBody())
    await env.svc.cancelGrant(pending.grantId)
    expect(env.op.cancelArgs).toEqual({ continueUri: 'https://auth.test/continue/1', continueToken: 'CONTINUE-TOKEN-SECRET' })

    const blank = await env.svc.createGrant(grantBody())
    const emptyBlob = new Cipher(KEY).encrypt('')
    env.store.db.prepare("UPDATE grants SET continue_uri='', continue_token=? WHERE id=?").run(emptyBlob, blank.grantId)
    await env.svc.cancelGrant(blank.grantId)
    expect(env.op.calls.filter((c) => c === 'cancelGrant')).toHaveLength(1)
    expect(env.store.getGrant(blank.grantId)!.status).toBe('EXPIRED')
  })

  it('after DELETE, a quote and a payment with that grant answer GRANT_INVALID without touching Open Payments (5d)', async () => {
    const env = makeEnv()
    const id = await activeGrant(env, 100_00)
    const q = await env.svc.createQuote({ grantId: id, receiver: LAURA, receiveAmount: cop(10_00) })
    await env.svc.cancelGrant(id)
    const callsBefore = env.op.calls.length
    await rejects(env.svc.createQuote({ grantId: id, receiver: LAURA, receiveAmount: cop(10_00) }), 'GRANT_INVALID', 401)
    await rejects(env.svc.pay('k1', { quoteId: q.quoteId }), 'GRANT_INVALID', 401)
    expect(env.op.calls.slice(callsBefore)).toHaveLength(0)
  })
})
