import { describe, expect, it } from 'vitest'
import { OpError } from '../src/errors.js'
import { activeGrant, cop, makeEnv } from './fakes.js'

describe('spent fallback observability', () => {
  it('emits exactly one spent_fallback warning when the server spent call fails and keeps the local sum', async () => {
    const logs: Record<string, unknown>[] = []
    const env = makeEnv({ log: (l) => logs.push(l) })
    const g = await activeGrant(env, 100_00)
    const q = await env.svc.createQuote({ grantId: g, receiver: 'https://ilp.test/laura', receiveAmount: cop(10_00) })
    await env.svc.pay('k', { quoteId: q.quoteId })

    env.op.failNext.getGrantSpent = new OpError('timeout')
    const view = await env.svc.getGrant(g)

    expect(view.spent).toEqual(cop(10_00))
    const warns = logs.filter((l) => l.event === 'spent_fallback')
    expect(warns).toHaveLength(1)
    expect(warns[0]).toEqual({ level: 'warn', event: 'spent_fallback' })
  })
  it('does not log spent_fallback when the server answers', async () => {
    const logs: Record<string, unknown>[] = []
    const env = makeEnv({ log: (l) => logs.push(l) })
    const g = await activeGrant(env, 100_00)
    await env.svc.getGrant(g)
    expect(logs.filter((l) => l.event === 'spent_fallback')).toHaveLength(0)
  })
  it('does not log spent_fallback when there is no token to query with', async () => {
    const logs: Record<string, unknown>[] = []
    const env = makeEnv({ log: (l) => logs.push(l) })
    const g = await activeGrant(env, 100_00)
    env.store.updateGrant(g, { accessToken: null, accessTokenExpiresAt: null, manageUrl: null })
    const view = await env.svc.getGrant(g)
    expect(view.spent).toEqual(cop(0))
    expect(logs.filter((l) => l.event === 'spent_fallback')).toHaveLength(0)
  })
})