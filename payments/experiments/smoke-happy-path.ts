// Smoke test for the happy path against the real Test Wallet.
// Reads NO secrets: the payments service loads payments/.env itself; this script
// only takes non-secret parameters via flags or environment variables.
//   npm run smoke -- --wallet <sender wallet address> [--print-url]
//   SERVICE_URL (default http://127.0.0.1:4000), RECEIVER, ASSET_CODE, ASSET_SCALE,
//   GRANT_CAP, PAY_AMOUNT, EXCESS_AMOUNT (all optional).
// Never prints access tokens, continue tokens, nonces, interact_ref, hash, keyId
// or the approval URL (that URL opens the default browser directly).
import { createServer, type Server } from 'node:http'
import { randomUUID } from 'node:crypto'
import { spawn } from 'node:child_process'

const args = process.argv.slice(2)
const flag = (name: string) => {
  const i = args.indexOf(`--${name}`)
  return i >= 0 && i + 1 < args.length ? args[i + 1]! : undefined
}
const SERVICE_URL = (process.env.SERVICE_URL ?? 'http://127.0.0.1:4000').replace(/\/$/, '')
const RECEIVER = process.env.RECEIVER ?? 'https://ilp.interledger-test.dev/laura'
const ASSET_CODE = process.env.ASSET_CODE ?? 'COP'
const ASSET_SCALE = Number(process.env.ASSET_SCALE ?? 2)
const GRANT_CAP = flag('grant-cap') ?? process.env.GRANT_CAP ?? '500000'
const PAY_AMOUNT = flag('pay-amount') ?? process.env.PAY_AMOUNT ?? '100000'
const EXCESS_AMOUNT = flag('excess-amount') ?? process.env.EXCESS_AMOUNT ?? '500000'
const CALLBACK_PORT = Number(process.env.CALLBACK_PORT ?? 5173)
const CALLBACK_WAIT_MS = 8 * 60_000
const PAYMENT_POLL_TIMEOUT_MS = 30_000

const SENDER = flag('wallet') ?? process.env.SMOKE_WALLET
const PRINT_URL = args.includes('--print-url')

type Step = { name: string; ok: boolean; detail: string; ms: number }
const steps: Step[] = []

class StopError extends Error {}
class Fail extends Error {}

const money = (value: string, scale = ASSET_SCALE) => {
  const base = 10n ** BigInt(scale)
  const whole = BigInt(value) / base
  const cents = BigInt(value) % base
  return `${whole}.${cents.toString().padStart(scale, '0')} ${ASSET_CODE}`
}

const redact = (text: string) =>
  text
    .replace(/https?:\/\/[^\s"'<>]*interact[^\s"'<>]*/gi, '<interact-url redactado>')
    .replace(/[A-Za-z0-9_-]{24,}/g, (m) => (m.includes('.') ? m : '<valor redactado>'))

const log = (line: string) => console.log(line)

const maskSender = (w: string) => {
  if (!w) return w
  const at = w.lastIndexOf('/')
  return at > 0 ? `${w.slice(0, at)}/<remitente>` : '<remitente>'
}

async function step(name: string, fn: () => Promise<string>) {
  const t0 = Date.now()
  try {
    const detail = await fn()
    steps.push({ name, ok: true, detail, ms: Date.now() - t0 })
    log(`OK    ${name} (${Date.now() - t0} ms)${detail ? ` — ${detail}` : ''}`)
  } catch (e) {
    const detail = redact(e instanceof Error ? e.message : String(e))
    steps.push({ name, ok: false, detail, ms: Date.now() - t0 })
    log(`FALLÓ ${name} (${Date.now() - t0} ms) — ${detail}`)
    throw new StopError()
  }
}

const expect = (cond: unknown, msg: string) => {
  if (!cond) throw new Fail(msg)
}

async function call<T>(method: string, path: string, init?: RequestInit): Promise<{ status: number; body: T }> {
  const res = await fetch(`${SERVICE_URL}${path}`, {
    method,
    ...init,
    headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
  })
  const text = await res.text()
  const body = (text ? JSON.parse(text) : {}) as T
  return { status: res.status, body }
}

const amount = (value: string) => ({ value, assetCode: ASSET_CODE, assetScale: ASSET_SCALE })

type GrantResponse = { grantId: string; status: string; interactUrl: string }
type ContinueResponse = { grantId: string; status: string; limit: { debitAmount: { value: string }; interval?: string }; remaining: { value: string } }
type GrantView = { grantId: string; status: string; spent: { value: string }; remaining: { value: string } }
type QuoteResponse = { quoteId: string; debitAmount: { value: string }; receiveAmount: { value: string }; expiresAt: string; exceedsRemaining: boolean }
type PaymentResponse = { paymentId: string; status: string; debitAmount: { value: string }; sentAmount: { value: string } }

let listener: Server | null = null
let resolveCallback!: (p: URLSearchParams) => void
let rejectCallback!: (e: Error) => void
const callbackParams = new Promise<URLSearchParams>((res, rej) => {
  resolveCallback = res
  rejectCallback = rej
})

async function openListener(): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    listener = createServer((req, res) => {
      const url = new URL(req.url ?? '/', 'http://localhost')
      if (req.method !== 'GET' || !url.pathname.startsWith('/grant-callback')) {
        res.statusCode = 404
        res.end()
        return
      }
      const names = [...url.searchParams.keys()]
      log(`      callback recibido con parámetros: ${names.length ? names.join(', ') : '(ninguno)'}`)
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' })
      res.end('<!doctype html><html lang="es"><body><p>Listo, ya podés volver a la terminal.</p></body></html>')
      resolveCallback(url.searchParams)
    })
    listener.once('error', (e: NodeJS.ErrnoException) => reject(new Fail(e.code === 'EADDRINUSE'
      ? `el puerto ${CALLBACK_PORT} está ocupado; cerrá el proceso que lo usa y volvé a correr`
      : `no se pudo abrir el listener del callback: ${e.message}`)))
    listener.listen(CALLBACK_PORT, '127.0.0.1', () => resolve())
  })
}

function openInBrowser(url: string): void {
  if (PRINT_URL) log(`      interactUrl (por --print-url): ${url}`)
  const child = spawn('rundll32', ['url.dll,FileProtocolHandler', url], { detached: true, stdio: 'ignore' })
  child.unref()
}

const sub = (a: string, b: string) => (BigInt(a) - BigInt(b)).toString()

async function main(): Promise<void> {
  log(`smoke happy path — SERVICE_URL=${SERVICE_URL} receiver=${RECEIVER} sender=${maskSender(SENDER ?? '')} asset=${ASSET_CODE}/${ASSET_SCALE}`)
  if (!SENDER) throw new Fail('falta la wallet de la usuaria: pasá --wallet o la variable SMOKE_WALLET')

  let grantId = ''
  let quoteId = ''
  let paymentId = ''
  let firstPaymentResponse: { status: number; body: PaymentResponse } | null = null
  let paymentKey = ''

  await step('a. health', async () => {
    const r = await call<{ ok: boolean }>('GET', '/v1/health')
    expect(r.status === 200 && r.body.ok === true, `esperaba 200 {ok:true}, recibí ${r.status}`)
    return '200 ok'
  })

  await step('b. listener del callback en 127.0.0.1:5173', async () => {
    await openListener()
    return 'escuchando'
  })

  await step('c. POST /v1/grants (tope total 5.000)', async () => {
    const t0 = Date.now()
    const r = await call<GrantResponse>('POST', '/v1/grants', {
      body: JSON.stringify({ userId: 'demo-user', walletAddress: SENDER, limit: { debitAmount: amount(GRANT_CAP) }, finishUri: `http://localhost:${CALLBACK_PORT}/grant-callback` }),
    })
    expect(r.status === 201, `esperaba 201, recibí ${r.status}: ${'error' in (r.body as object) ? JSON.stringify(r.body) : ''}`)
    expect(typeof r.body.grantId === 'string' && r.body.status === 'PENDING' && typeof r.body.interactUrl === 'string', 'respuesta incompleta del grant')
    grantId = r.body.grantId
    openInBrowser(r.body.interactUrl)
    return `201 (${Date.now() - t0} ms llamada)`
  })

  await step('d. aprobación en la wallet (esperando callback, hasta 8 min)', async () => {
    const params = await Promise.race([
      callbackParams,
      new Promise<never>((_, rej) => setTimeout(() => rej(new Fail('timeout esperando la aprobación en la wallet (8 min)')), CALLBACK_WAIT_MS)),
    ])
    expect(params.has('interact_ref') && params.has('hash'), `la wallet volvió sin interact_ref/hash: parámetros ${[...params.keys()].join(', ') || '(ninguno)'} (¿rechazo?)`)
    return 'redirect recibido'
  })

  await step('e. POST /v1/grants/{id}/continue', async () => {
    const params = await callbackParams
    const t0 = Date.now()
    const r = await call<ContinueResponse | { error: { code: string; message: string } }>('POST', `/v1/grants/${grantId}/continue`, {
      body: JSON.stringify({ interactRef: params.get('interact_ref'), hash: params.get('hash') }),
    })
    expect(r.status === 200, `esperaba 200, recibí ${r.status} ${JSON.stringify(r.body).slice(0, 120)}`)
    const active = r.body as ContinueResponse
    expect(active.status === 'ACTIVE', `esperaba ACTIVE, recibí ${active.status}`)
    expect(active.remaining?.value === GRANT_CAP, `esperaba remaining ${GRANT_CAP}, recibí ${active.remaining?.value}`)
    return `200 ACTIVE remaining=${money(GRANT_CAP)} (${Date.now() - t0} ms llamada)`
  })

  await step('f. GET /v1/grants (presupuesto intacto)', async () => {
    const r = await call<GrantView>('GET', `/v1/grants/${grantId}`)
    expect(r.status === 200, `esperaba 200, recibí ${r.status}`)
    expect(r.body.spent.value === '0', `esperaba spent 0, recibí ${r.body.spent.value}`)
    expect(r.body.remaining.value === GRANT_CAP, `esperaba remaining ${GRANT_CAP}, recibí ${r.body.remaining.value}`)
    return 'spent 0'
  })

  let quoteDebit = ''
  await step('g. POST /v1/quotes (1.000 al receptor)', async () => {
    const t0 = Date.now()
    const r = await call<QuoteResponse>('POST', '/v1/quotes', {
      body: JSON.stringify({ grantId, receiver: RECEIVER, receiveAmount: amount(PAY_AMOUNT) }),
    })
    expect(r.status === 201, `esperaba 201, recibí ${r.status}: ${'error' in (r.body as object) ? JSON.stringify(r.body) : ''}`)
    expect(r.body.receiveAmount.value === PAY_AMOUNT, `esperaba receiveAmount ${PAY_AMOUNT}, recibí ${r.body.receiveAmount?.value}`)
    expect(BigInt(r.body.debitAmount.value) >= BigInt(r.body.receiveAmount.value), `debitAmount ${r.body.debitAmount?.value} < receiveAmount ${r.body.receiveAmount?.value}`)
    expect(r.body.exceedsRemaining === false, `esperaba exceedsRemaining false, recibí ${r.body.exceedsRemaining}`)
    quoteId = r.body.quoteId
    quoteDebit = r.body.debitAmount.value
    return `201 debit=${money(quoteDebit)} costo=${money(sub(quoteDebit, PAY_AMOUNT))} (${Date.now() - t0} ms llamada)`
  })

  await step('h. POST /v1/payments + polling hasta COMPLETED', async () => {
    paymentKey = randomUUID()
    const t0 = Date.now()
    const r = await call<PaymentResponse>('POST', '/v1/payments', {
      headers: { 'idempotency-key': paymentKey },
      body: JSON.stringify({ quoteId }),
    })
    expect(r.status === 201, `esperaba 201, recibí ${r.status}: ${JSON.stringify(r.body).slice(0, 120)}`)
    paymentId = r.body.paymentId
    const created = Date.now() - t0
    firstPaymentResponse = { status: r.status, body: r.body }
    const pollStart = Date.now()
    for (;;) {
      const s = await call<PaymentResponse>('GET', `/v1/payments/${paymentId}`)
      if (s.body.status === 'COMPLETED') return `201 (${created} ms llamada) + COMPLETED tras ${((Date.now() - pollStart) / 1000).toFixed(1)} s de polling`
      if (s.body.status === 'FAILED') throw new Fail('el pago terminó FAILED según Open Payments')
      if (Date.now() - pollStart > PAYMENT_POLL_TIMEOUT_MS) throw new Fail('el pago no llegó a COMPLETED en 30 s de polling')
      await new Promise((r) => setTimeout(r, 1000))
    }
  })

  await step('i. GET /v1/grants (gastado actualizado)', async () => {
    const r = await call<GrantView>('GET', `/v1/grants/${grantId}`)
    expect(r.status === 200, `esperaba 200, recibí ${r.status}`)
    expect(r.body.spent.value === quoteDebit, `esperaba spent ${quoteDebit}, recibí ${r.body.spent.value}`)
    const expectedRemaining = sub(GRANT_CAP, quoteDebit)
    expect(r.body.remaining.value === expectedRemaining, `esperaba remaining ${expectedRemaining}, recibí ${r.body.remaining.value}`)
    return `spent=${money(quoteDebit)} remaining=${money(expectedRemaining)} (fuente servidor vs respaldo: mirar el log del servicio)`
  })

  await step('j. reintento idempotente: misma clave → misma respuesta; clave nueva → 404', async () => {
    const same = await call<PaymentResponse>('POST', '/v1/payments', {
      headers: { 'idempotency-key': paymentKey },
      body: JSON.stringify({ quoteId }),
    })
    expect(same.status === firstPaymentResponse!.status, `esperaba el mismo status ${firstPaymentResponse!.status}, recibí ${same.status}`)
    expect(JSON.stringify(same.body) === JSON.stringify(firstPaymentResponse!.body), 'la respuesta del reintento difiere de la original')
    const other = await call<{ error: { code: string } }>('POST', '/v1/payments', {
      headers: { 'idempotency-key': randomUUID() },
      body: JSON.stringify({ quoteId }),
    })
    expect(other.status === 404, `esperaba 404 QUOTE_NOT_FOUND, recibí ${other.status} ${JSON.stringify(other.body).slice(0, 120)}`)
    expect(other.body.error?.code === 'QUOTE_NOT_FOUND', `esperaba QUOTE_NOT_FOUND, recibí ${other.body.error?.code}`)
    const v = await call<GrantView>('GET', `/v1/grants/${grantId}`)
    expect(v.body.spent.value === quoteDebit, `el gastado cambió tras los reintentos: ${v.body.spent.value}`)
    return `respuesta idéntica + 404 para clave nueva + spent sin cambios (${money(quoteDebit)})`
  })

  await step('k. exceso: quote 5.000 → exceedsRemaining true → pago rechazado 403', async () => {
    const t0 = Date.now()
    const q = await call<QuoteResponse>('POST', '/v1/quotes', {
      body: JSON.stringify({ grantId, receiver: RECEIVER, receiveAmount: amount(EXCESS_AMOUNT) }),
    })
    expect(q.status === 201, `esperaba 201, recibí ${q.status}`)
    expect(q.body.exceedsRemaining === true, `esperaba exceedsRemaining true, recibí ${q.body.exceedsRemaining}`)
    const p = await call<{ error: { code: string } }>('POST', '/v1/payments', {
      headers: { 'idempotency-key': randomUUID() },
      body: JSON.stringify({ quoteId: q.body.quoteId }),
    })
    expect(p.status === 403, `esperaba 403 LIMIT_EXCEEDED, recibí ${p.status} ${JSON.stringify(p.body).slice(0, 120)}`)
    expect(p.body.error?.code === 'LIMIT_EXCEEDED', `esperaba LIMIT_EXCEEDED, recibí ${p.body.error?.code}`)
    return `201 quote (${Date.now() - t0} ms) + 403 LIMIT_EXCEEDED; verificar opCalls=0 en el log del servicio`
  })

  await step('l. cierre del listener y resumen', async () => {
    await new Promise<void>((resolve) => listener!.close(() => resolve()))
    listener = null
    return 'cerrado'
  })
}

main()
  .then(() => {
    log('')
    log('RESUMEN (sin secretos)')
    for (const s of steps) log(`${s.ok ? 'OK   ' : 'FALLÓ'} | ${s.name} | ${s.ms} ms${s.detail ? ` | ${s.detail}` : ''}`)
    process.exit(0)
  })
  .catch((e) => {
    if (e instanceof StopError) {
      log('')
      log('DETENIDO: un paso falló; no se siguieron pagando.')
      for (const s of steps) log(`${s.ok ? 'OK   ' : 'FALLÓ'} | ${s.name} | ${s.ms} ms${s.detail ? ` | ${s.detail}` : ''}`)
    } else {
      log(`error inesperado: ${redact(e instanceof Error ? e.message : String(e))}`)
    }
    listener?.close()
    process.exit(1)
  })