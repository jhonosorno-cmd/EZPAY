// Shared helpers for Test Wallet experiments (unit 4).
// Runs with `tsx --env-file=.env experiments/<script>.ts`: the .env is read by
// the PROCESS, never by these helpers. Every console/file output uses a strict
// whitelist: no tokens, nonces, interact_ref, hash, keyId, interactUrl or
// grant/continue/manage URLs. Wallet addresses are masked in all reports.
import { readFile, unlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { createServer, type Server } from 'node:http'
import { randomUUID, type UUID } from 'node:crypto'
import { spawn } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  createAuthenticatedClient,
  isFinalizedGrant,
  isPendingGrant,
  OpenPaymentsClientError,
  type AuthenticatedClient,
  type Grant,
  type PendingGrant,
} from '@interledger/open-payments'
import { loadConfig } from '../src/config.js'

export const RECEIVER = process.env.EXPERIMENT_RECEIVER ?? 'https://ilp.interledger-test.dev/laura'
export const CALLBACK_PORT = Number(process.env.CALLBACK_PORT ?? 5173)
export const CALLBACK_TIMEOUT_MS = 8 * 60_000
export const SDK_VERSION = '7.4.0'

export type WalletInfo = {
  id: string
  authServer: string
  resourceServer: string
  assetCode: string
  assetScale: number
}

export type Wallet = {
  client: AuthenticatedClient
  sender: WalletInfo
  receiver: WalletInfo
}

const infoOf = (w: { id: string; authServer: string; resourceServer: string; assetCode: string; assetScale: number }): WalletInfo => ({
  id: w.id,
  authServer: w.authServer,
  resourceServer: w.resourceServer,
  assetCode: w.assetCode,
  assetScale: w.assetScale,
})

/** Loads the environment the service uses. Throws naming the missing variable, never printing values. */
export function loadEnv(): { walletAddress: string; keyId: string; privateKey: string } {
  const cfg = loadConfig(process.env)
  return { walletAddress: cfg.walletAddress, keyId: cfg.keyId, privateKey: cfg.privateKey }
}

/** `--dry-run` / `--self-test`: validates imports and configuration, exercises the report write
 *  path (sample file in the OS temp dir, read back, deleted) and the callback listener
 *  (open → simulated redirect → param names → close → re-open on the same port → close).
 *  No real network, no browser, no payments. */
export async function dryRunGuard(name: string, extra = ''): Promise<boolean> {
  const argv = process.argv.slice(2)
  if (!argv.includes('--dry-run') && !argv.includes('--self-test')) return false
  const selfTestOnly = argv.includes('--self-test') && !argv.includes('--dry-run')
  const checks: string[] = []
  if (!selfTestOnly) {
    loadEnv()
    checks.push('configuración cargada (variables requeridas presentes)')
  }
  await reportWriteCheck()
  checks.push('escritura de informe en temp, leído de vuelta y borrado OK')
  await listenerSelfTest()
  checks.push('listener: abrir → redirect simulado → nombres de parámetros OK → cerrar → reabrir en el mismo puerto sin EADDRINUSE → cerrar OK')
  console.log(`dry-run ${name}: ${checks.join('; ')}. Sin red real, sin navegador, sin pagos.${extra ? ` ${extra}` : ''}`)
  return true
}

async function reportWriteCheck(): Promise<void> {
  const file = `ezpay-exp-dryrun-${process.pid}.md`
  const sample = '# dry-run\n\n- línea de muestra'
  await writeReport(file, [sample], tmpdir())
  const back = await readFile(join(tmpdir(), file), 'utf8')
  if (!back.includes('línea de muestra')) throw new Fail('el informe de muestra no se leyó de vuelta')
  await unlink(join(tmpdir(), file))
}

/** Loopback-only self test of the callback listener (never touches the wallet). */
export async function listenerSelfTest(): Promise<void> {
  const first = openCallbackListener()
  await first.ready
  await fetch(`http://127.0.0.1:${CALLBACK_PORT}/grant-callback?interact_ref=selftest&hash=selftest`)
  const params = await first.promise
  if (params.get('interact_ref') !== 'selftest' || params.get('hash') !== 'selftest')
    throw new Fail('el listener no devolvió los parámetros simulados')
  await first.close()
  const second = openCallbackListener()
  await second.ready
  await second.close()
}

export async function openWallet(): Promise<Wallet> {
  const cfg = loadEnv()
  const client = await createAuthenticatedClient({
    walletAddressUrl: cfg.walletAddress,
    privateKey: cfg.privateKey,
    keyId: cfg.keyId,
    logLevel: 'silent',
  })
  const sender = await client.walletAddress.get({ url: cfg.walletAddress })
  const receiver = await client.walletAddress.get({ url: RECEIVER })
  return { client, sender: infoOf(sender), receiver: infoOf(receiver) }
}

export class Fail extends Error {}

export type ErrInfo = { status?: number; code?: string; description?: string }

/** Whitelisted error data. Descriptions get sanitized (URLs, uuids, long values removed). */
export function errInfo(e: unknown): ErrInfo {
  if (e instanceof OpenPaymentsClientError)
    return { status: e.status, code: e.code, description: e.description ? sanitize(e.description) : undefined }
  return { code: (e as Error)?.name ?? 'unknown', description: sanitize((e as Error)?.message ?? String(e)) }
}

export function sanitize(text: string): string {
  return text
    .replace(/https?:\/\/[^\s"'<>]+/gi, '<url redactada>')
    .replace(/\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b/g, '<uuid redactado>')
    .replace(/[A-Za-z0-9_-]{24,}/g, '<valor redactado>')
    .slice(0, 140)
}

export const money = (value: string, scale: number) => {
  const base = 10n ** BigInt(scale)
  return `${BigInt(value) / base}.${(BigInt(value) % base).toString().padStart(scale, '0')}`
}

export function maskWallet(w: WalletInfo, role: 'sender' | 'receiver'): string {
  const at = w.id.lastIndexOf('/')
  return at > 0 ? `${w.id.slice(0, at)}/<${role === 'sender' ? 'remitente' : 'receptor'}>` : `<${role === 'sender' ? 'remitente' : 'receptor'}>`
}

/** Opens the default browser with rundll32 (D-11a). Never prints the URL. */
export function openInBrowser(url: string): void {
  const child = spawn('rundll32', ['url.dll,FileProtocolHandler', url], { detached: true, stdio: 'ignore' })
  child.unref()
}

export type Callback = {
  /** Resolves once the port is listening; rejects (e.g. EADDRINUSE) BEFORE any grant exists. */
  ready: Promise<void>
  promise: Promise<URLSearchParams>
  close: () => Promise<void>
}

/** Listens on 127.0.0.1:5173 for the finishUri redirect. Aborts cleanly if the port is busy. */
export function openCallbackListener(log: (line: string) => void = (l) => console.log(l)): Callback {
  let resolve!: (p: URLSearchParams) => void
  let reject!: (e: Error) => void
  const promise = new Promise<URLSearchParams>((res, rej) => {
    resolve = res
    reject = rej
  })
  let server: Server | null = createServer((req, res) => {
    const url = new URL(req.url ?? '/', 'http://localhost')
    if (req.method !== 'GET' || !url.pathname.startsWith('/grant-callback')) {
      res.statusCode = 404
      res.end()
      return
    }
    const names = [...url.searchParams.keys()]
    log(`      redirect recibido con parámetros: ${names.length ? names.join(', ') : '(ninguno)'}`)
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' })
    res.end('<!doctype html><html lang="es"><body><p>Listo, ya podés volver a la terminal.</p></body></html>')
    resolve(url.searchParams)
  })
  let bound!: () => void
  const ready = new Promise<void>((resolve, fail) => {
    bound = resolve as unknown as () => void
    server!.once('error', (e: NodeJS.ErrnoException) => {
      server = null
      fail(new Fail(
        e.code === 'EADDRINUSE'
          ? `el puerto ${CALLBACK_PORT} está ocupado; cerrá el proceso que lo usa y volvé a correr`
          : `no se pudo abrir el listener del callback: ${e.message}`,
      ))
    })
  })
  server.listen(CALLBACK_PORT, '127.0.0.1', () => {
    bound()
    log(`      listener del callback en 127.0.0.1:${CALLBACK_PORT} listo`)
  })
  return {
    ready,
    promise,
    close: () =>
      new Promise<void>((resolve) => {
        if (!server) return resolve()
        server.close(() => {
          server = null
          resolve()
        })
      }),
  }
}

export async function waitCallback(
  listener: Callback,
  what: string,
  timeoutMs = CALLBACK_TIMEOUT_MS,
): Promise<URLSearchParams> {
  return Promise.race([
    listener.promise,
    new Promise<never>((_, rej) =>
      setTimeout(() => rej(new Fail(`timeout de ${Math.round(timeoutMs / 60000)} min esperando la interacción en la wallet (${what})`)), timeoutMs),
    ),
  ])
}

/** Prints one progress line per minute (whitelisted, no secrets). */
export function progressPerMinute(totalMs: number, log: (line: string) => void = (l) => console.log(l)): Promise<void> {
  const totalMin = Math.round(totalMs / 60_000)
  return new Promise((resolve) => {
    let minute = 0
    const timer = setInterval(() => {
      minute += 1
      log(`      espera: ${minute}/${totalMin} min`)
      if (minute >= totalMin) {
        clearInterval(timer)
        resolve()
      }
    }, 60_000)
  })
}

// ------------------------------------------------------------------ payments

export type TokenGrant = { accessToken: string; manageUrl: string; expiresIn: number | null; access?: unknown[] }

/** Non-interactive grant (incoming-payment or quote) for the given auth server. */
export async function nonInteractiveToken(w: Wallet, authServer: string, kind: 'incoming-payment' | 'quote'): Promise<string> {
  const access = kind === 'incoming-payment'
    ? [{ type: 'incoming-payment' as const, actions: ['create', 'read', 'list'] }]
    : [{ type: 'quote' as const, actions: ['create', 'read'] }]
  const g = await w.client.grant.request({ url: authServer }, { access_token: { access } })
  if (!isFinalizedGrant(g) || !g.access_token) throw new Fail('el grant no interactivo no finalizó con access token')
  return g.access_token.value
}

export type PaymentResult = { debitValue: string; receiveValue: string; sentValue: string | null; failed: boolean }

/** quote + outgoing payment of `receiveValue` (500 COP by unit rules). Returns whitelisted fields only. */
export async function payOnce(
  w: Wallet,
  receiveValue: string,
  grantAccessToken: string,
): Promise<PaymentResult> {
  const inToken = await nonInteractiveToken(w, w.receiver.authServer, 'incoming-payment')
  const expiresAt = new Date(Date.now() + 10 * 60_000).toISOString()
  const incoming = await w.client.incomingPayment.create(
    { url: w.receiver.resourceServer, accessToken: inToken },
    { walletAddress: w.receiver.id, incomingAmount: { value: receiveValue, assetCode: w.receiver.assetCode, assetScale: w.receiver.assetScale }, expiresAt },
  )
  const qToken = await nonInteractiveToken(w, w.sender.authServer, 'quote')
  const quote = await w.client.quote.create(
    { url: w.sender.resourceServer, accessToken: qToken },
    { method: 'ilp', walletAddress: w.sender.id, receiver: incoming.id },
  )
  const op = await w.client.outgoingPayment.create(
    { url: w.sender.resourceServer, accessToken: grantAccessToken },
    { walletAddress: w.sender.id, quoteId: quote.id },
  )
  return {
    debitValue: op.debitAmount?.value ?? quote.debitAmount.value,
    receiveValue: op.receiveAmount?.value ?? receiveValue,
    sentValue: op.sentAmount?.value ?? null,
    failed: Boolean(op.failed),
  }
}

export type SpentAmounts = { spentDebit: string | null; spentReceive: string | null }

/** Direct getGrantSpentAmounts against the resource server (no service in between). */
export async function grantSpent(w: Wallet, accessToken: string): Promise<SpentAmounts> {
  const r = await w.client.outgoingPayment.getGrantSpentAmounts({ url: w.sender.resourceServer, accessToken })
  return {
    spentDebit: r.spentDebitAmount?.value ?? null,
    spentReceive: r.spentReceiveAmount?.value ?? null,
  }
}

/** Interactive grant with limits; returns the pending grant and the fresh nonce (never printed). */
export async function requestInteractiveGrant(
  w: Wallet,
  finishUri: string,
  capValue: string,
  interval?: string,
): Promise<PendingGrant> {
  const g = await w.client.grant.request(
    { url: w.sender.authServer },
    {
      access_token: {
        access: [{
          type: 'outgoing-payment',
          actions: ['create', 'read', 'list'],
          identifier: w.sender.id,
          limits: { debitAmount: { value: capValue, assetCode: w.sender.assetCode, assetScale: w.sender.assetScale }, ...(interval ? { interval } : {}) },
        }],
      },
      interact: { start: ['redirect'], finish: { method: 'redirect', uri: finishUri, nonce: randomUUID() as UUID } },
    },
  )
  if (!isPendingGrant(g)) throw new Fail('el grant interactivo no quedó pendiente')
  return g
}

export type FinalizedAccess = { accessToken: string; manageUrl: string | null; expiresIn: number | null; limits: unknown[] }

/** Continues a pending grant with the redirect params. Whitelisted output: amounts, interval, expires_in, presence booleans. */
export async function continueGrant(w: Wallet, pending: PendingGrant, params: URLSearchParams): Promise<FinalizedAccess> {
  const interactRef = params.get('interact_ref')
  if (!interactRef) throw new Fail('el redirect no trajo interact_ref')
  const g = (await w.client.grant.continue(
    { url: pending.continue.uri, accessToken: pending.continue.access_token.value },
    { interact_ref: interactRef },
  )) as Grant
  if (!isFinalizedGrant(g) || !g.access_token) throw new Fail('el continue no devolvió access token (¿rechazo?)')
  return {
    accessToken: g.access_token.value,
    manageUrl: g.access_token.manage ?? null,
    expiresIn: g.access_token.expires_in ?? null,
    limits: (g.access_token.access ?? []).map((a) => ({ type: a.type, actions: a.actions, limits: a.limits })),
  }
}

// ------------------------------------------------------------------ reports

export type ReportSection = string

/** Writes experiments/<fileName> (or <dir>/<fileName>) from whitelisted sections only. */
export async function writeReport(fileName: string, sections: ReportSection[], dir?: string): Promise<void> {
  const path = join(dir ?? dirname(fileURLToPath(import.meta.url)), fileName)
  await writeFile(path, sections.join('\n\n') + '\n', 'utf8')
  console.log(`informe escrito: ${dir ? path : `experiments/${fileName}`}`)
}

export const REPORT_HEADER = (title: string, sdkVersion = SDK_VERSION): string =>
  `# ${title}\n\n- **Fecha:** ${new Date().toISOString()}\n- **SDK:** @interledger/open-payments ${sdkVersion} (Node ${process.version})\n- **Remitente:** \`<remitente>\` · **Receptor:** \`<receptor>\` (mascarados por seguridad)\n- Los valores se reducen a lista blanca: no hay tokens, nonces, interact_ref, hash, keyId, interactUrl ni URLs de grants/manage/continue.`
