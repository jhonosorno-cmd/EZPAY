// Experiment C: does GNAP grant.cancel (DELETE on the continue URI with the continue token) kill the access token? (P3 part 2)
// Grant cap: 4.000,00 COP (value "400000"), no interval. Payment (500,00 COP) only if the read probe cannot distinguish.
// Run: npm run exp:cancel   (owner approves in the browser; 4.000 COP = APROBAR)
import {
  dryRunGuard, errInfo, grantSpent, money, maskWallet, openCallbackListener, openInBrowser,
  openWallet, payOnce, requestInteractiveGrant, continueGrant, REPORT_HEADER, waitCallback, writeReport,
} from './lib.js'
import type { PendingGrant } from '@interledger/open-payments'

if (await dryRunGuard('cancel-grant')) process.exit(0)

const CAP = '400000'
const PAY = '50000'

const state = {
  expiresIn: null as number | null,
  readBefore: null as string | null,
  cancelResult: null as string | null,
  readAfter: null as string | null,
  readAlive: null as boolean | null,
  paymentResult: null as string | null,
  paymentMade: false,
  error: null as string | null,
}

const log = (line: string) => console.log(line)

async function flow(): Promise<void> {
  const w = await openWallet()
  log(`Experimento C — remitente ${maskWallet(w.sender, 'sender')}`)
  const listener = openCallbackListener(log)
  await listener.ready
  const finishUri = 'http://localhost:5173/grant-callback'
  const s = w.sender.assetScale

  log('PASO a: pidiendo el grant C (4.000,00 COP, sin interval)...')
  let pending: PendingGrant
  try {
    pending = await requestInteractiveGrant(w, finishUri, CAP)
    log('PASO a: grant C pendiente OK')
  } catch (e) {
    const info = errInfo(e)
    throw new Error(`el grant C no se pudo crear: status ${info.status ?? '?'} código ${info.code ?? '?'}`)
  }

  log('PASO b: abriendo la wallet en el navegador (4.000,00 COP = APROBAR)...')
  openInBrowser(pending.interact.redirect!)
  const params = await waitCallback(listener, 'aprobación del grant C')
  await listener.close() // frees 5173
  const finalized = await continueGrant(w, pending, params)
  state.expiresIn = finalized.expiresIn
  log(`PASO c: continue OK; expires_in=${state.expiresIn ?? 'no informado'}`)

  const before = await grantSpent(w, finalized.accessToken)
  state.readBefore = before.spentDebit
  log(`PASO d: lectura con el access token ANTES de cancelar: aceptada (spentDebit=${state.readBefore ?? 'no informado'})`)

  try {
    await w.client.grant.cancel({ url: pending.continue.uri, accessToken: pending.continue.access_token.value })
    state.cancelResult = 'grant.cancel (DELETE sobre la continue URI con el continue token) OK'
  } catch (e) {
    const info = errInfo(e)
    state.cancelResult = `grant.cancel falló: status ${info.status ?? '?'} código ${info.code ?? '?'}`
  }
  log(`PASO e: ${state.cancelResult}`)

  const after = await grantSpent(w, finalized.accessToken).then((x) => ({ ok: true as const, spentDebit: x.spentDebit })).catch((e) => ({ ok: false as const, err: errInfo(e) }))
  state.readAlive = after.ok
  state.readAfter = after.ok
    ? `aceptada (spentDebit=${money(String(after.spentDebit), s)})`
    : `rechazada: status ${after.err.status ?? '?'} código ${after.err.code ?? '?'}`
  log(`PASO f: lectura con el access token DESPUÉS de cancelar: ${state.readAfter}`)

  if (state.readAlive) {
    try {
      const p = await payOnce(w, PAY, finalized.accessToken)
      state.paymentResult = `el pago con el access token tras cancelar SUCEDIÓ (debit=${money(p.debitValue, s)}) — hallazgo importante: cancel no revocó el acceso`
      state.paymentMade = true
    } catch (e) {
      const info = errInfo(e)
      state.paymentResult = `el pago con el access token tras cancelar fue rechazado: status ${info.status ?? '?'} código ${info.code ?? '?'}`
    }
  } else {
    state.paymentResult = 'no se hizo: la lectura ya distinguió que el token quedó inusable'
  }
  log(`PASO g: ${state.paymentResult}`)

  await listener.close()
}

async function main(): Promise<void> {
  try {
    await flow()
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    state.error = msg
    console.error(`error: ${msg}`)
  } finally {
    await writeReport('cancel-grant.md', buildReport())
  }
  process.exit(state.error ? 1 : 0)
}

function buildReport(): string[] {
  const lines: string[] = [
    REPORT_HEADER('Experimento C — ¿grant.cancel invalida de verdad el acceso? (P3 parte 2)'),
    `## Procedimiento\n\n1. Grant interactivo de 4.000,00 COP sin interval, aprobado por el dueño.\n2. continue OK (expires_in: ${state.expiresIn ?? 'no informado'}).\n3. Lectura de referencia con el access token antes de cancelar: ${state.readBefore !== null ? `aceptada (spentDebit=${state.readBefore})` : 'no realizada'}.`,
    `## P3 (parte 2) — resultado\n\n- ${state.cancelResult ?? 'no se llegó a cancelar'}.\n- Lectura con el access token después de cancelar: ${state.readAfter ?? 'no realizada'}.\n- Pago con el access token después de cancelar: ${state.paymentResult ?? 'no realizado'}.\n\nPagos reales en esta corrida: ${state.paymentMade ? 1 : 0} de 500,00 COP (tope de la unidad: 5 pagos).`,
    `## Conclusión\n\n${state.readAlive === null ? 'Sin datos suficientes.' : state.readAlive ? 'grant.cancel NO revocó el access token: la lectura siguió funcionando; el grant queda cancelado en GNAP pero el token sigue operativo. Comparar con token.revoke en weekly-interval-and-token.md (sección P3 parte 1).' : 'grant.cancel revocó el acceso: la lectura con el access token quedó rechazada, igual que el efecto de token.revoke en el experimento A.'}`,
  ]
  if (state.error) lines.push(`## Error de la corrida\n\n${state.error}`)
  return lines
}

main()