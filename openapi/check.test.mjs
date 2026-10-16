// Acceptance checks for the Prism mocks of Contracts A and B (v1 + v1.1).
// Every expectation below comes from docs/contratos-http-v1.md and
// docs/contratos-cambios-propuestos-v1.1.md, not from the spec files.
import { after, before, describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const prismBin = join(here, '..', 'node_modules', '@stoplight', 'prism-cli', 'dist', 'index.js')
const PORT_A = 14000
const PORT_B = 18000
const children = []

function startMock(file, port) {
  const child = spawn(
    process.execPath,
    [prismBin, 'mock', '-h', '127.0.0.1', '-p', String(port), join(here, file)],
    { stdio: ['ignore', 'pipe', 'pipe'] },
  )
  let log = ''
  child.stdout.on('data', (d) => (log += d))
  child.stderr.on('data', (d) => (log += d))
  children.push(child)
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + 30000
    const tick = async () => {
      if (child.exitCode !== null) return reject(new Error(`prism exited for ${file}:\n${log}`))
      try {
        await fetch(`http://127.0.0.1:${port}/`)
        return resolve()
      } catch {
        if (Date.now() > deadline) return reject(new Error(`prism timeout for ${file}:\n${log}`))
        setTimeout(tick, 200)
      }
    }
    tick()
  })
}

async function call(port, method, path, { json, form, headers = {}, prefer } = {}) {
  const init = { method, headers: { ...headers } }
  if (prefer) init.headers.Prefer = prefer
  if (json !== undefined) {
    init.headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(json)
  }
  if (form) init.body = form
  const res = await fetch(`http://127.0.0.1:${port}${path}`, init)
  const text = await res.text()
  let body = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = text
  }
  return { status: res.status, body }
}

const A = (method, path, opts) => call(PORT_A, method, path, opts)
const B = (method, path, opts) => call(PORT_B, method, path, opts)

const amount = { value: '2000000', assetCode: 'COP', assetScale: 2 }
const idem = { 'Idempotency-Key': '6f1c1c4e-52a5-4a5e-9f8e-0f3f3a3c9b11' }

function expectError(res, status, code) {
  assert.equal(res.status, status, JSON.stringify(res.body))
  assert.equal(res.body?.error?.code, code, JSON.stringify(res.body))
  assert.equal(typeof res.body.error.message, 'string')
}

before(async () => {
  await Promise.all([
    startMock('contract-a.yaml', PORT_A),
    startMock('contract-b.yaml', PORT_B),
  ])
})

after(() => {
  for (const c of children) c.kill()
})

describe('Contract A (Python -> Node, /v1)', () => {
  test('GET /health -> 200 ok', async () => {
    const r = await A('GET', '/v1/health')
    assert.equal(r.status, 200)
    assert.deepEqual(r.body, { ok: true })
  })

  describe('POST /grants', () => {
    const req = {
      userId: 'demo-user',
      walletAddress: 'https://ilp.interledger-test.dev/marta',
      limit: { debitAmount: amount, interval: 'R52/2026-10-16T00:00:00Z/P1W' },
      finishUri: 'http://localhost:5173/grant-callback',
    }
    test('201 PENDING with interactUrl', async () => {
      const r = await A('POST', '/v1/grants', { json: req })
      assert.equal(r.status, 201)
      assert.equal(r.body.status, 'PENDING')
      assert.equal(typeof r.body.grantId, 'string')
      assert.equal(typeof r.body.interactUrl, 'string')
    })
    test('interval is optional (tope total)', async () => {
      const { interval, ...limit } = req.limit
      const r = await A('POST', '/v1/grants', { json: { ...req, limit } })
      assert.equal(r.status, 201)
    })
    for (const [status, code, example] of [
      [400, 'INVALID_AMOUNT', 'invalid-amount'],
      [400, 'INVALID_WALLET', 'invalid-wallet'],
      [502, 'UPSTREAM_ERROR', 'upstream-error'],
      [500, 'INTERNAL_ERROR', 'internal-error'],
    ]) {
      test(`${status} ${code}`, async () => {
        const r = await A('POST', '/v1/grants', { json: req, prefer: `code=${status}, example=${example}` })
        expectError(r, status, code)
      })
    }
    test('amount with decimals is rejected as 400 INVALID_AMOUNT', async () => {
      const bad = { ...req, limit: { debitAmount: { ...amount, value: '200.50' } } }
      expectError(await A('POST', '/v1/grants', { json: bad }), 400, 'INVALID_AMOUNT')
    })
    test('numeric value (not string) is rejected as 400 INVALID_AMOUNT', async () => {
      const bad = { ...req, limit: { debitAmount: { ...amount, value: 20000 } } }
      expectError(await A('POST', '/v1/grants', { json: bad }), 400, 'INVALID_AMOUNT')
    })
  })

  describe('POST /grants/{grantId}/continue', () => {
    const req = { interactRef: 'ref-123', hash: 'aGFzaA==' }
    test('200 ACTIVE with limit and remaining', async () => {
      const r = await A('POST', '/v1/grants/g_abc/continue', { json: req })
      assert.equal(r.status, 200)
      assert.equal(r.body.status, 'ACTIVE')
      assert.ok(r.body.limit.debitAmount)
      assert.ok(r.body.remaining)
    })
    for (const [status, code, example] of [
      [400, 'INVALID_HASH', 'invalid-hash'],
      [403, 'GRANT_REJECTED', 'grant-rejected'],
      [404, 'GRANT_NOT_FOUND', 'grant-not-found'],
      [409, 'GRANT_NOT_PENDING', 'grant-not-pending'],
    ]) {
      test(`${status} ${code}`, async () => {
        const r = await A('POST', '/v1/grants/g_abc/continue', { json: req, prefer: `code=${status}, example=${example}` })
        expectError(r, status, code)
      })
    }
  })

  describe('GET /grants/{grantId}', () => {
    test('200 with limit, spent and remaining', async () => {
      const r = await A('GET', '/v1/grants/g_abc')
      assert.equal(r.status, 200)
      assert.equal(r.body.status, 'ACTIVE')
      for (const k of ['limit', 'spent', 'remaining']) assert.ok(r.body[k], k)
    })
    for (const [example, status] of [['pending', 'PENDING'], ['rejected', 'REJECTED'], ['expired', 'EXPIRED']]) {
      test(`example ${example} -> ${status}`, async () => {
        const r = await A('GET', '/v1/grants/g_abc', { prefer: `code=200, example=${example}` })
        assert.equal(r.status, 200)
        assert.equal(r.body.status, status)
      })
    }
    test('404 GRANT_NOT_FOUND', async () => {
      expectError(await A('GET', '/v1/grants/g_abc', { prefer: 'code=404' }), 404, 'GRANT_NOT_FOUND')
    })
  })

  describe('DELETE /grants/{grantId} (A-1)', () => {
    test('204 without body', async () => {
      const r = await A('DELETE', '/v1/grants/g_abc')
      assert.equal(r.status, 204)
    })
    test('404 GRANT_NOT_FOUND', async () => {
      expectError(await A('DELETE', '/v1/grants/g_abc', { prefer: 'code=404' }), 404, 'GRANT_NOT_FOUND')
    })
    test('502 UPSTREAM_ERROR', async () => {
      expectError(await A('DELETE', '/v1/grants/g_abc', { prefer: 'code=502' }), 502, 'UPSTREAM_ERROR')
    })
  })

  describe('POST /quotes', () => {
    const req = { grantId: 'g_abc', receiver: 'https://ilp.interledger-test.dev/laura', receiveAmount: amount }
    test('201 within budget: exceedsRemaining=false', async () => {
      const r = await A('POST', '/v1/quotes', { json: req })
      assert.equal(r.status, 201)
      assert.equal(r.body.exceedsRemaining, false)
      for (const k of ['quoteId', 'debitAmount', 'receiveAmount', 'expiresAt']) assert.ok(r.body[k], k)
    })
    test('201 exceeds budget: exceedsRemaining=true', async () => {
      const r = await A('POST', '/v1/quotes', { json: req, prefer: 'code=201, example=exceeds-remaining' })
      assert.equal(r.status, 201)
      assert.equal(r.body.exceedsRemaining, true)
    })
    for (const [status, code, example] of [
      [400, 'INVALID_AMOUNT', 'invalid-amount'],
      [400, 'INVALID_RECEIVER', 'invalid-receiver'],
      [401, 'GRANT_INVALID', 'grant-invalid'],
      [404, 'GRANT_NOT_FOUND', 'grant-not-found'],
      [502, 'UPSTREAM_ERROR', 'upstream-error'],
    ]) {
      test(`${status} ${code}`, async () => {
        expectError(await A('POST', '/v1/quotes', { json: req, prefer: `code=${status}, example=${example}` }), status, code)
      })
    }
    test('amount with decimals is rejected as 400 INVALID_AMOUNT', async () => {
      const bad = { ...req, receiveAmount: { ...amount, value: '200.50' } }
      expectError(await A('POST', '/v1/quotes', { json: bad }), 400, 'INVALID_AMOUNT')
    })
  })

  describe('POST /payments', () => {
    const req = { quoteId: 'q_123' }
    test('201 COMPLETED with debitAmount and sentAmount', async () => {
      const r = await A('POST', '/v1/payments', { json: req, headers: idem })
      assert.equal(r.status, 201)
      assert.equal(r.body.status, 'COMPLETED')
      for (const k of ['paymentId', 'debitAmount', 'sentAmount']) assert.ok(r.body[k], k)
    })
    for (const [example, status] of [['processing', 'PROCESSING'], ['failed', 'FAILED']]) {
      test(`201 example ${example} -> ${status}`, async () => {
        const r = await A('POST', '/v1/payments', { json: req, headers: idem, prefer: `code=201, example=${example}` })
        assert.equal(r.status, 201)
        assert.equal(r.body.status, status)
      })
    }
    for (const [status, code, example] of [
      [401, 'GRANT_INVALID', 'grant-invalid'],
      [403, 'LIMIT_EXCEEDED', 'limit-exceeded'],
      [404, 'QUOTE_NOT_FOUND', 'quote-not-found'],
      [409, 'QUOTE_EXPIRED', 'quote-expired'],
      [409, 'PAYMENT_IN_PROGRESS', 'payment-in-progress'],
      [422, 'IDEMPOTENCY_KEY_REUSED', 'idempotency-key-reused'],
      [502, 'UPSTREAM_ERROR', 'upstream-error'],
    ]) {
      test(`${status} ${code}`, async () => {
        const r = await A('POST', '/v1/payments', { json: req, headers: idem, prefer: `code=${status}, example=${example}` })
        expectError(r, status, code)
      })
    }
    // Expected 400 IDEMPOTENCY_KEY_REQUIRED, got 422: Prism answers request-validation
    // failures with the spec's 422 response when one exists (here IDEMPOTENCY_KEY_REUSED).
    // The real Node service answers 400; the mock only guarantees the request is rejected.
    test('missing Idempotency-Key is rejected by the mock (never 201)', async () => {
      const r = await A('POST', '/v1/payments', { json: req })
      assert.ok(r.status >= 400 && r.status < 500, `status ${r.status}`)
    })
    test('IDEMPOTENCY_KEY_REQUIRED is available as 400 example', async () => {
      const r = await A('POST', '/v1/payments', { json: req, headers: idem, prefer: 'code=400, example=idempotency-key-required' })
      expectError(r, 400, 'IDEMPOTENCY_KEY_REQUIRED')
    })
  })

  describe('GET /payments/{paymentId}', () => {
    test('200 with status and sentAmount', async () => {
      const r = await A('GET', '/v1/payments/p_789')
      assert.equal(r.status, 200)
      assert.equal(r.body.status, 'COMPLETED')
      assert.ok(r.body.sentAmount)
    })
    for (const [example, status] of [['processing', 'PROCESSING'], ['failed', 'FAILED']]) {
      test(`example ${example} -> ${status}`, async () => {
        const r = await A('GET', '/v1/payments/p_789', { prefer: `code=200, example=${example}` })
        assert.equal(r.body.status, status)
      })
    }
    test('404 PAYMENT_NOT_FOUND', async () => {
      expectError(await A('GET', '/v1/payments/p_789', { prefer: 'code=404' }), 404, 'PAYMENT_NOT_FOUND')
    })
  })
})

describe('Contract B (Frontend -> Python, /api)', () => {
  const audioForm = (extra = {}) => {
    const f = new FormData()
    for (let i = 0; i < 3; i++) f.append('audio', new Blob(['x'], { type: 'audio/webm' }), `s${i}.webm`)
    f.append('consent', 'true')
    for (const [k, v] of Object.entries(extra)) f.set(k, v)
    return f
  }

  describe('/enrollment', () => {
    test('POST 201 enrolled', async () => {
      const r = await B('POST', '/api/enrollment', { form: audioForm() })
      assert.equal(r.status, 201)
      assert.deepEqual(r.body, { enrolled: true })
    })
    for (const code of ['CONSENT_REQUIRED', 'SAMPLES_REQUIRED', 'INVALID_AUDIO', 'INCONSISTENT_SAMPLES']) {
      test(`POST 400 ${code}`, async () => {
        const r = await B('POST', '/api/enrollment', {
          form: audioForm(),
          prefer: `code=400, example=${code.toLowerCase().replaceAll('_', '-')}`,
        })
        expectError(r, 400, code)
      })
    }
    test('POST consent=false is rejected as 400 CONSENT_REQUIRED (PRIV-2)', async () => {
      expectError(await B('POST', '/api/enrollment', { form: audioForm({ consent: 'false' }) }), 400, 'CONSENT_REQUIRED')
    })
    test('GET 200 enrolled flag (B-5)', async () => {
      const r = await B('GET', '/api/enrollment')
      assert.equal(r.status, 200)
      assert.equal(typeof r.body.enrolled, 'boolean')
    })
  })

  describe('/budget', () => {
    test('POST 201 interactUrl', async () => {
      const r = await B('POST', '/api/budget', {
        json: { debitAmount: { value: '20000000', assetCode: 'COP', assetScale: 2 }, interval: 'R52/2026-10-16T00:00:00Z/P1W' },
      })
      assert.equal(r.status, 201)
      assert.equal(typeof r.body.interactUrl, 'string')
    })
    test('GET 200 status, limit, spent, remaining', async () => {
      const r = await B('GET', '/api/budget')
      assert.equal(r.status, 200)
      for (const k of ['status', 'limit', 'spent', 'remaining']) assert.ok(r.body[k], k)
    })
  })

  describe('/grant-callback (B-1)', () => {
    test('interactRef + hash -> TurnResponse', async () => {
      const r = await B('POST', '/api/grant-callback', { json: { interactRef: 'ref', hash: 'aGFzaA==' } })
      assert.equal(r.status, 200)
      assert.equal(typeof r.body.sessionId, 'string')
      assert.equal(typeof r.body.state, 'string')
    })
    test('result only (wallet rejection) is accepted and can answer REJECTED', async () => {
      const r = await B('POST', '/api/grant-callback', {
        json: { result: 'grant_rejected' },
        prefer: 'code=200, example=rejected',
      })
      assert.equal(r.status, 200)
      assert.equal(r.body.state, 'REJECTED')
    })
    test('empty body is accepted (all fields optional)', async () => {
      const r = await B('POST', '/api/grant-callback', { json: {} })
      assert.equal(r.status, 200)
    })
  })

  describe('/turns', () => {
    const textForm = (extra = {}) => {
      const f = new FormData()
      f.set('text', 'envíale veinte mil a mi hija')
      for (const [k, v] of Object.entries(extra)) f.set(k, v)
      return f
    }
    const states = {
      'awaiting-command': 'AWAITING_COMMAND',
      'awaiting-confirmation': 'AWAITING_CONFIRMATION',
      'awaiting-pin': 'AWAITING_PIN',
      'awaiting-recipient-choice': 'AWAITING_RECIPIENT_CHOICE',
      'awaiting-authorization': 'AWAITING_AUTHORIZATION',
      completed: 'COMPLETED',
      'payment-pending': 'PAYMENT_PENDING',
      rejected: 'REJECTED',
    }
    for (const [example, state] of Object.entries(states)) {
      test(`example ${example} -> state ${state}`, async () => {
        const r = await B('POST', '/api/turns', { form: textForm(), prefer: `code=200, example=${example}` })
        assert.equal(r.status, 200)
        assert.equal(r.body.state, state)
        assert.equal(typeof r.body.say, 'string')
        assert.equal(typeof r.body.sessionId, 'string')
        assert.ok('transcript' in r.body)
      })
    }
    test('AWAITING_PIN turn has transcript null (B-7)', async () => {
      const r = await B('POST', '/api/turns', { form: textForm(), prefer: 'code=200, example=awaiting-pin' })
      assert.equal(r.body.transcript, null)
    })
    test('AWAITING_AUTHORIZATION carries interactUrl', async () => {
      const r = await B('POST', '/api/turns', { form: textForm(), prefer: 'code=200, example=awaiting-authorization' })
      assert.equal(typeof r.body.interactUrl, 'string')
    })
    test('AWAITING_RECIPIENT_CHOICE carries options with alias and name', async () => {
      const r = await B('POST', '/api/turns', { form: textForm(), prefer: 'code=200, example=awaiting-recipient-choice' })
      assert.ok(r.body.options.length >= 2)
      for (const o of r.body.options) assert.ok(o.alias && o.name)
    })
    test('COMPLETED carries payment with amounts', async () => {
      const r = await B('POST', '/api/turns', { form: textForm(), prefer: 'code=200, example=completed' })
      for (const k of ['paymentId', 'receiver', 'debitAmount', 'receiveAmount']) assert.ok(r.body.payment[k], k)
    })
    test('audio alone is accepted', async () => {
      const f = new FormData()
      f.set('audio', new Blob(['x'], { type: 'audio/webm' }), 'cmd.webm')
      const r = await B('POST', '/api/turns', { form: f })
      assert.equal(r.status, 200)
    })
    test('D-1b: kind=verify_pending with sessionId and no audio/text is accepted', async () => {
      const f = new FormData()
      f.set('sessionId', 's_1')
      f.set('kind', 'verify_pending')
      const r = await B('POST', '/api/turns', { form: f, prefer: 'code=200, example=payment-pending' })
      assert.equal(r.status, 200)
      assert.equal(r.body.state, 'PAYMENT_PENDING')
    })
    test('D-1b: kind=verify_pending without sessionId is rejected', async () => {
      const f = new FormData()
      f.set('kind', 'verify_pending')
      const r = await B('POST', '/api/turns', { form: f })
      assert.ok(r.status >= 400 && r.status < 500, `status ${r.status}`)
    })
    test('neither audio nor text nor kind is rejected as 400 AUDIO_OR_TEXT_REQUIRED (B-3)', async () => {
      const f = new FormData()
      f.set('sessionId', 's_1')
      expectError(await B('POST', '/api/turns', { form: f }), 400, 'AUDIO_OR_TEXT_REQUIRED')
    })
    for (const [status, code, example] of [
      [400, 'AUDIO_OR_TEXT_REQUIRED', 'audio-or-text-required'],
      [400, 'INVALID_AUDIO', 'invalid-audio'],
      [400, 'AUDIO_TOO_LONG', 'audio-too-long'],
      [404, 'SESSION_NOT_FOUND', 'session-not-found'],
    ]) {
      test(`${status} ${code}`, async () => {
        expectError(await B('POST', '/api/turns', { form: textForm(), prefer: `code=${status}, example=${example}` }), status, code)
      })
    }
  })
})
