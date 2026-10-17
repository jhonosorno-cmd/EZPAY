import { describe, expect, it, vi } from 'vitest'
import type { WalletInfo } from '../src/ports.js'
import { cop } from './fakes.js'

const state = vi.hoisted(() => ({ grantRequest: undefined as unknown, spentArgs: undefined as unknown }))

vi.mock('@interledger/open-payments', () => ({
  createAuthenticatedClient: async () => ({
    grant: {
      request: async (_opts: unknown, body: unknown) => {
        state.grantRequest = body
        return {
          interact: { redirect: 'https://auth.test/interact/1', finish: 'inonce' },
          continue: { uri: 'https://auth.test/continue/1', access_token: { value: 'ct' } },
        }
      },
    },
    outgoingPayment: {
      getGrantSpentAmounts: async (args: unknown) => {
        state.spentArgs = args
        return { spentDebitAmount: { value: '1', assetCode: 'COP', assetScale: 2 } }
      },
    },
  }),
  isPendingGrant: (g: { access_token?: unknown }) => !g.access_token,
  isFinalizedGrant: (g: { access_token?: unknown }) => Boolean(g.access_token),
  OpenPaymentsClientError: class OpenPaymentsClientError extends Error {},
}))

import { SdkOpenPayments } from '../src/op/adapter.js'

const wallet: WalletInfo = {
  id: 'https://rs.example/marta',
  authServer: 'https://auth.example',
  resourceServer: 'https://rs.example/',
  assetCode: 'COP',
  assetScale: 2,
}
const client = () => SdkOpenPayments.create({ walletAddress: 'https://rs.example/marta', keyId: 'k', privateKey: 'k.pem', timeoutMs: 1000 })

describe('op adapter', () => {
  it('getGrantSpent passes the resource server root, so the SDK builds <root>/outgoing-payment-grant', async () => {
    const op = await client()
    const spent = await op.getGrantSpent({ sender: wallet, accessToken: 'TOKEN' })
    expect(spent).toEqual({ value: '1', assetCode: 'COP', assetScale: 2 })
    expect(state.spentArgs).toHaveProperty('accessToken', 'TOKEN')
    expect(state.spentArgs).toHaveProperty('url', 'https://rs.example')
    expect(String((state.spentArgs as { url: string }).url)).not.toContain('outgoing-payments')
  })
  it('requestGrant asks outgoing-payment for exactly the actions create, read, list (A-3)', async () => {
    const op = await client()
    await op.requestGrant({ wallet, limit: { debitAmount: cop(1) }, finishUri: 'http://localhost:5173/grant-callback', clientNonce: 'n' })
    const body = state.grantRequest as { access_token: { access: { type: string; actions: string[]; identifier: string }[] } }
    expect(body.access_token.access).toHaveLength(1)
    expect(body.access_token.access[0]!.type).toBe('outgoing-payment')
    expect(body.access_token.access[0]!.actions).toEqual(['create', 'read', 'list'])
    expect(body.access_token.access[0]!.identifier).toBe(wallet.id)
  })
})