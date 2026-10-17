// PARTE B (NO ejecutar sin GO del supervisor): one-off grant semanal contra la Test Wallet real.
// Grant con interval R1/<ahora>/P1W y tope de 500,00 COP (value "50000"): aprobar en la pantalla,
// un único pago (quote + outgoing payment), verificación del gastado y DELETE con GNAP
// grant.cancel; después, leer con el access token debe responder 403.
// Informe: experiments/one-off-grant-real.md (solo datos de lista blanca, lo escribe el script).
// Run (solo con GO): npm run exp:one-off
import {
  dryRunGuard, errInfo, grantSpent, money, maskWallet, openCallbackListener, openInBrowser,
  openWallet, payOnce, requestInteractiveGrant, continueGrant, REPORT_HEADER, waitCallback, writeReport,
} from './lib.js'
import type { PendingGrant } from '@interledger/open-payments'

if (await dryRunGuard('one-off-grant-real')) process.exit(0)

const CAP = '50000' // 500,00 COP
const PAY = '50000'

const state = {
  acceptedInterval: null as string | null,
  expiresIn: null as number | null,
  quote: null as { debitValue: string; receiveValue: string } | null,
  payment: null as { debitValue: string; sentValue: string | null } | null,
  spentAfterPayment: null as string | null,
  spentVerifiedSeconds: null as number | null,
  cancelResult: null as string | null,
  readAfterCancel: null as string | null,
  readAlive: false,
  error: null as string | null,
}

const log = (line: string) => console.log(line)

async function flow(): Promise<void> {
  const w = await openWallet()
  log(`Experimento D — remitente ${maskWallet(w.sender, 'sender')} receptor ${maskWallet(w.receiver, 'receiver')}`)
  const listener = openCallbackListener(log)
  await listener.ready
  const finishUri = 'http://localhost:5173/grant-callback'
  const s = w.sender.assetScale
  const interval = `R1/${new Date().toISOString()}/P1W`

  log('PASO 1: pidiendo el grant puntual semanal (500,00 COP, intervalo R1/<ahora>/P1W)...')
  let pending: PendingGrant
  try {
    pending = await requestInteractiveGrant(w, finishUri, CAP, interval)
    state.acceptedInterval = interval
    log(`PASO 1: grant puntual pendiente OK (intervalo ${interval})`)
  } catch (e) {
    const info = errInfo(e)
    throw new Error(`el grant puntual no se pudo crear: status ${info.status ?? '?'} código ${info.code ?? '?'}`)
  }
  log('PASO 1: abriendo la wallet en el navegador (500,00 COP = APROBAR)...')
  openInBrowser(pending.interact.redirect!)
  const params = await waitCallback(listener, 'aprobación del grant puntual')
  await listener.close()
  const finalized = await continueGrant(w, pending, params)
  state.expiresIn = finalized.expiresIn
  log(`PASO 2: continue OK; expires_in=${state.expiresIn ?? 'no informado'}`)

  const payment = await payOnce(w, PAY, finalized.accessToken)
  state.quote = { debitValue: payment.debitValue, receiveValue: payment.receiveValue }
  state.payment = { debitValue: payment.debitValue, sentValue: payment.sentValue }
  log(`PASO 2: pago único OK — debit=${money(payment.debitValue, s)} receive=${money(payment.receiveValue, s)}`)

  const t0 = Date.now()
  for (;;) {
    const spent = await grantSpent(w, finalized.accessToken).catch(() => null)
    if (spent?.spentDebit && BigInt(spent.spentDebit) >= BigInt(payment.debitValue)) {
      state.spentAfterPayment = spent.spentDebit
      state.spentVerifiedSeconds = Math.round((Date.now() - t0) / 1000)
      break
    }
    if (Date.now() - t0 > 30_000) break
    await new Promise((r) => setTimeout(r, 1000))
  }
  log(`PASO 2: gastado verificado=${state.spentAfterPayment ? money(state.spentAfterPayment, s) : 'NO en 30 s'} (${state.spentVerifiedSeconds ?? '?'} s)`)

  log('PASO 3: DELETE del grant con GNAP grant.cancel (continue URI + continue token)...')
  try {
    await w.client.grant.cancel({ url: pending.continue.uri, accessToken: pending.continue.access_token.value })
    state.cancelResult = 'grant.cancel OK'
  } catch (e) {
    const info = errInfo(e)
    state.cancelResult = `grant.cancel falló: status ${info.status ?? '?'} código ${info.code ?? '?'}`
  }
  log(`PASO 3: ${state.cancelResult}`)

  const probe = await grantSpent(w, finalized.accessToken)
    .then((x) => ({ ok: true as const, spentDebit: x.spentDebit }))
    .catch((e) => ({ ok: false as const, err: errInfo(e) }))
  state.readAlive = probe.ok
  state.readAfterCancel = probe.ok
    ? `aceptada (spentDebit=${money(String(probe.spentDebit), s)})`
    : `rechazada: status ${probe.err.status ?? '?'} código ${probe.err.code ?? '?'}`
  log(`PASO 3: lectura con el access token después del DELETE: ${state.readAfterCancel}`)
}

async function main(): Promise<void> {
  try {
    await flow()
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    state.error = msg
    console.error(`error: ${msg}`)
  } finally {
    await writeReport('one-off-grant-real.md', buildReport(2))
  }
  process.exit(state.error ? 1 : 0)
}

function buildReport(scale: number): string[] {
  const lines: string[] = [
    REPORT_HEADER('Experimento D — grant puntual semanal: pago único y cancelación con grant.cancel'),
    `## Grant puntual con interval semanal\n\nInterval pedido y aceptado: ${state.acceptedInterval ? `\`${state.acceptedInterval}\`` : 'no se pudo crear'}. expires_in del token: ${state.expiresIn ?? 'no informado'}.`,
    `## Pago único\n\n- Quote: debit=${state.quote ? money(state.quote.debitValue, scale) : '—'} receive=${state.quote ? money(state.quote.receiveValue, scale) : '—'}.\n- Pago: debit=${state.payment ? money(state.payment.debitValue, scale) : '—'} sent=${state.payment?.sentValue ? money(state.payment.sentValue, scale) : '—'}.\n- Gastado verificado: ${state.spentAfterPayment ? money(state.spentAfterPayment, scale) : 'no apareció en 30 s'} en ${state.spentVerifiedSeconds ?? '?'} s.`,
    `## Cancelación y lectura posterior\n\n- ${state.cancelResult ?? 'no se llegó a cancelar'}.\n- Lectura con el access token después del DELETE: ${state.readAfterCancel ?? 'no realizada'}.`,
    `## Pagos reales de esta corrida\n\n- Un único pago de 500,00 COP: ${state.payment ? 'realizado' : 'no realizado'}.`,
  ]
  if (state.error) lines.push(`## Error de la corrida\n\n${state.error}`)
  return lines
}

main()