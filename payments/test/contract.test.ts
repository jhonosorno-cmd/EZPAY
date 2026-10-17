import { describe, expect, it } from 'vitest'
import request from 'supertest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { randomUUID } from 'node:crypto'
import * as AjvModule from 'ajv'
import * as addFormatsModule from 'ajv-formats'
import { parse } from 'yaml'
import { OpError } from '../src/errors.js'
import { interactHash } from '../src/crypto.js'
import { createApp } from '../src/http/app.js'
import { LAURA, MARTA, cop, makeEnv } from './fakes.js'

const rootDir = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
const doc: any = parse(readFileSync(join(rootDir, 'openapi', 'contract-a.yaml'), 'utf8'))
const shared: any = parse(readFileSync(join(rootDir, 'openapi', 'components.yaml'), 'utf8'))

const NS = 'https://contract.ezpay.dev/'
function rewriteRefs(node: unknown): unknown {
  if (typeof node === 'string')
    return node.startsWith('components.yaml#/components/schemas/')
      ? NS + 'schemas/' + node.slice('components.yaml#/components/schemas/'.length)
      : node.startsWith('#/components/schemas/')
        ? NS + 'schemas/' + node.slice('#/components/schemas/'.length)
        : node
  if (Array.isArray(node)) return node.map(rewriteRefs)
  if (node && typeof node === 'object') return Object.fromEntries(Object.entries(node).map(([k, v]) => [k, rewriteRefs(v)]))
  return node
}

type AjvInstance = {
  compile: (schema: unknown) => ((data: unknown) => boolean) & { errors?: unknown[] }
  addSchema: (schema: unknown) => AjvInstance
}
const Ajv = (AjvModule as unknown as { default: new (opts?: Record<string, unknown>) => AjvInstance }).default
const addFormats = (addFormatsModule as unknown as { default: (ajv: AjvInstance) => AjvInstance }).default
const ajv = new Ajv({ allErrors: true, strict: false })
addFormats(ajv)
const mergedSchemas: Record<string, unknown> = { ...doc.components.schemas, ...shared.components.schemas }
for (const [name, schema] of Object.entries(mergedSchemas))
  ajv.addSchema(rewriteRefs({ $id: NS + 'schemas/' + name, ...(schema as object) }))

/** undefined: el contrato no define la respuesta; null: la define sin cuerpo (204). */
function responseSchema(method: string, path: string, status: string): unknown {
  const op = doc.paths?.[path]?.[method.toLowerCase()]
  let r = op?.responses?.[status]
  if (r?.$ref) r = doc.components.responses[r.$ref.slice('#/components/responses/'.length)]
  if (!r) return undefined
  const schema = r?.content?.['application/json']?.schema
  return schema ? rewriteRefs(schema) : null
}

function expectValid(method: string, path: string, status: number, body: unknown) {
  const schema = responseSchema(method, path, String(status))
  expect(schema, `${method} ${path} -> ${status} is not defined in contract-a.yaml`).not.toBeUndefined()
  if (schema === null) return
  const validate = ajv.compile(schema as object)
  expect(
    validate(body),
    `${method} ${path} -> ${status}: ${JSON.stringify(validate.errors)} got ${JSON.stringify(body)}`,
  ).toBe(true)
}

function build() {
  const env = makeEnv()
  const app = createApp({ svc: env.svc, ping: () => env.store.ping(), log: () => {} })
  return { ...env, app }
}

const grantBody = {
  userId: 'demo-user',
  walletAddress: MARTA,
  finishUri: 'http://localhost:5173/grant-callback',
  limit: { debitAmount: cop(200_00) },
}

describe('service responses validate against openapi/contract-a.yaml (FakeOp, no network)', () => {
  it('happy path: every 2xx body matches the contract schema', async () => {
    const { app, store } = build()

    const grant = await request(app).post('/v1/grants').send(grantBody).expect(201)
    expectValid('POST', '/v1/grants', 201, grant.body)
    const grantId: string = grant.body.grantId

    const stored = store.getGrant(grantId)!
    const hash = interactHash(stored.clientNonce, stored.interactNonce, 'REF', stored.grantEndpointUri)
    const cont = await request(app).post(`/v1/grants/${grantId}/continue`).send({ interactRef: 'REF', hash }).expect(200)
    expectValid('POST', '/v1/grants/{grantId}/continue', 200, cont.body)

    const g = await request(app).get(`/v1/grants/${grantId}`).expect(200)
    expectValid('GET', '/v1/grants/{grantId}', 200, g.body)

    const quote = await request(app).post('/v1/quotes').send({ grantId, receiver: LAURA, receiveAmount: cop(20_00) }).expect(201)
    expectValid('POST', '/v1/quotes', 201, quote.body)

    const pay = await request(app).post('/v1/payments').set('Idempotency-Key', randomUUID()).send({ quoteId: quote.body.quoteId }).expect(201)
    expectValid('POST', '/v1/payments', 201, pay.body)

    const st = await request(app).get(`/v1/payments/${pay.body.paymentId}`).expect(200)
    expectValid('GET', '/v1/payments/{paymentId}', 200, st.body)

    await request(app).delete(`/v1/grants/${grantId}`).expect(204)

    const h = await request(app).get('/v1/health').expect(200)
    expectValid('GET', '/v1/health', 200, h.body)
  })

  it('every emitted error code has a body matching the contract ErrorBody', async () => {
    const env = build()
    const { app, op } = env

    const malformed = await request(app).post('/v1/grants').set('content-type', 'application/json').send('{bad').expect(500)
    expect(malformed.body.error.code).toBe('INTERNAL_ERROR')
    expectValid('POST', '/v1/grants', 500, malformed.body)

    const amount = await request(app).post('/v1/grants').send({ ...grantBody, limit: { debitAmount: { ...cop(1), value: '1.5' } } }).expect(400)
    expect(amount.body.error.code).toBe('INVALID_AMOUNT')
    expectValid('POST', '/v1/grants', 400, amount.body)

    const wallet = await request(app).post('/v1/grants').send({ ...grantBody, walletAddress: 'https://ilp.test/nobody' }).expect(400)
    expect(wallet.body.error.code).toBe('INVALID_WALLET')
    expectValid('POST', '/v1/grants', 400, wallet.body)

    const unknownGrant = await request(app).get('/v1/grants/g_nope').expect(404)
    expect(unknownGrant.body.error.code).toBe('GRANT_NOT_FOUND')
    expectValid('GET', '/v1/grants/{grantId}', 404, unknownGrant.body)

    const g = await env.svc.createGrant(grantBody)
    const stored = env.store.getGrant(g.grantId)!
    const hash = interactHash(stored.clientNonce, stored.interactNonce, 'REF', stored.grantEndpointUri)

    const tampered = await request(app).post(`/v1/grants/${g.grantId}/continue`).send({ interactRef: 'REF', hash: hash.slice(0, -1) + 'A' }).expect(400)
    expect(tampered.body.error.code).toBe('INVALID_HASH')
    expectValid('POST', '/v1/grants/{grantId}/continue', 400, tampered.body)

    op.rejectOnContinue = true
    const rej = await env.svc.createGrant(grantBody)
    const rejStored = env.store.getGrant(rej.grantId)!
    const rejHash = interactHash(rejStored.clientNonce, rejStored.interactNonce, 'REF', rejStored.grantEndpointUri)
    const rejected = await request(app).post(`/v1/grants/${rej.grantId}/continue`).send({ interactRef: 'REF', hash: rejHash }).expect(403)
    expect(rejected.body.error.code).toBe('GRANT_REJECTED')
    expectValid('POST', '/v1/grants/{grantId}/continue', 403, rejected.body)

    op.rejectOnContinue = false
    await env.svc.continueGrant(g.grantId, { interactRef: 'REF', hash })
    const again = await request(app).post(`/v1/grants/${g.grantId}/continue`).send({ interactRef: 'REF', hash }).expect(409)
    expect(again.body.error.code).toBe('GRANT_NOT_PENDING')
    expectValid('POST', '/v1/grants/{grantId}/continue', 409, again.body)

    const pending = await env.svc.createGrant(grantBody)
    const pendingQuote = await request(app).post('/v1/quotes').send({ grantId: pending.grantId, receiver: LAURA, receiveAmount: cop(1) }).expect(401)
    expect(pendingQuote.body.error.code).toBe('GRANT_INVALID')
    expectValid('POST', '/v1/quotes', 401, pendingQuote.body)

    const badReceiver = await request(app).post('/v1/quotes').send({ grantId: g.grantId, receiver: 'https://ilp.test/none', receiveAmount: cop(1) }).expect(400)
    expect(badReceiver.body.error.code).toBe('INVALID_RECEIVER')
    expectValid('POST', '/v1/quotes', 400, badReceiver.body)

    const noKey = await request(app).post('/v1/payments').send({ quoteId: 'q_nope' }).expect(400)
    expect(noKey.body.error.code).toBe('IDEMPOTENCY_KEY_REQUIRED')
    expectValid('POST', '/v1/payments', 400, noKey.body)

    const unknownQuote = await request(app).post('/v1/payments').set('Idempotency-Key', randomUUID()).send({ quoteId: 'q_nope' }).expect(404)
    expect(unknownQuote.body.error.code).toBe('QUOTE_NOT_FOUND')
    expectValid('POST', '/v1/payments', 404, unknownQuote.body)

    const overLimit = await env.svc.createQuote({ grantId: g.grantId, receiver: LAURA, receiveAmount: cop(210_00) })
    const limited = await request(app).post('/v1/payments').set('Idempotency-Key', randomUUID()).send({ quoteId: overLimit.quoteId }).expect(403)
    expect(limited.body.error.code).toBe('LIMIT_EXCEEDED')
    expectValid('POST', '/v1/payments', 403, limited.body)

    const expiring = await env.svc.createQuote({ grantId: g.grantId, receiver: LAURA, receiveAmount: cop(1) })
    op.now += 6 * 60_000
    const expired = await request(app).post('/v1/payments').set('Idempotency-Key', randomUUID()).send({ quoteId: expiring.quoteId }).expect(409)
    expect(expired.body.error.code).toBe('QUOTE_EXPIRED')
    expectValid('POST', '/v1/payments', 409, expired.body)

    op.now -= 6 * 60_000
    const q1 = await env.svc.createQuote({ grantId: g.grantId, receiver: LAURA, receiveAmount: cop(1) })
    await env.svc.pay('reused-key', { quoteId: q1.quoteId })
    const nextQuote = await env.svc.createQuote({ grantId: g.grantId, receiver: LAURA, receiveAmount: cop(1) })
    const reused = await request(app).post('/v1/payments').set('Idempotency-Key', 'reused-key').send({ quoteId: nextQuote.quoteId }).expect(422)
    expect(reused.body.error.code).toBe('IDEMPOTENCY_KEY_REUSED')
    expectValid('POST', '/v1/payments', 422, reused.body)

    op.failNext.createOutgoingPayment = new OpError('timeout')
    const q2 = await env.svc.createQuote({ grantId: g.grantId, receiver: LAURA, receiveAmount: cop(1) })
    const upstream = await request(app).post('/v1/payments').set('Idempotency-Key', randomUUID()).send({ quoteId: q2.quoteId }).expect(502)
    expect(upstream.body.error.code).toBe('UPSTREAM_ERROR')
    expectValid('POST', '/v1/payments', 502, upstream.body)

    const unknownPayment = await request(app).get('/v1/payments/p_nope').expect(404)
    expect(unknownPayment.body.error.code).toBe('PAYMENT_NOT_FOUND')
    expectValid('GET', '/v1/payments/{paymentId}', 404, unknownPayment.body)
  })

  it('the exercised error codes cover the contract enum', async () => {
    const enumCodes: string[] = doc.components.schemas.ErrorCode.enum
    const exercised = [
      'INTERNAL_ERROR', 'INVALID_AMOUNT', 'INVALID_WALLET', 'INVALID_RECEIVER', 'INVALID_HASH', 'GRANT_REJECTED',
      'GRANT_NOT_FOUND', 'GRANT_NOT_PENDING', 'GRANT_INVALID', 'IDEMPOTENCY_KEY_REQUIRED', 'QUOTE_NOT_FOUND',
      'LIMIT_EXCEEDED', 'QUOTE_EXPIRED', 'IDEMPOTENCY_KEY_REUSED', 'UPSTREAM_ERROR', 'PAYMENT_NOT_FOUND',
    ]
    expect(exercised).toHaveLength(16)
    for (const code of exercised) expect(enumCodes, `${code} is no longer in the contract enum`).toContain(code)
  })
})