// Experiment B: what the wallet sends to finishUri when the user REJECTS (P2), and what grant.continue answers without interact_ref.
// Grant cap: 3.000,00 COP (value "300000"), no interval. No payments.
// Run: npm run exp:reject   (owner must REJECT in the browser; 3.000 COP = RECHAZAR)
import {
  dryRunGuard, errInfo, maskWallet, openCallbackListener, openInBrowser,
  openWallet, requestInteractiveGrant, REPORT_HEADER, waitCallback, writeReport,
} from './lib.js'
import type { PendingGrant } from '@interledger/open-payments'

if (await dryRunGuard('reject-redirect')) process.exit(0)

const CAP = '300000'

const state = {
  names: [] as string[],
  hasInteractRef: null as boolean | null,
  hasHash: null as boolean | null,
  result: 'ausente' as string,
  outcome: null as string | null,
  approvedByMistake: false,
  error: null as string | null,
}

const log = (line: string) => console.log(line)

async function flow(): Promise<void> {
  const w = await openWallet()
  log(`Experimento B — remitente ${maskWallet(w.sender, 'sender')}`)
  const listener = openCallbackListener(log)
  await listener.ready
  const finishUri = 'http://localhost:5173/grant-callback'

  log('PASO a: pidiendo el grant B (3.000,00 COP, sin interval)...')
  let pending: PendingGrant
  try {
    pending = await requestInteractiveGrant(w, finishUri, CAP)
    log('PASO a: grant B pendiente OK')
  } catch (e) {
    const info = errInfo(e)
    throw new Error(`el grant B no se pudo crear: status ${info.status ?? '?'} código ${info.code ?? '?'}`)
  }

  log('PASO b: abriendo la wallet en el navegador (3.000,00 COP = RECHAZAR)...')
  openInBrowser(pending.interact.redirect!)
  const params = await waitCallback(listener, 'rechazo del grant B')
  await listener.close() // frees 5173 for the next experiment

  state.names = [...params.keys()]
  const resultValue = params.get('result')
  state.hasInteractRef = params.has('interact_ref')
  state.hasHash = params.has('hash')
  const resultSafe = resultValue !== null && resultValue.length <= 64 && !/token|nonce|ref|hash/i.test(resultValue)
  state.result = resultValue === null ? 'ausente' : resultSafe ? resultValue : 'presente (valor no mostrado)'
  log(`PASO b: parámetros del redirect: ${state.names.length ? state.names.join(', ') : '(ninguno)'}`)
  log(`PASO b: interact_ref presente: ${state.hasInteractRef}; hash presente: ${state.hasHash}; result: ${state.result}`)

  if (state.hasInteractRef && state.hasHash) {
    log('PASO c: el redirect trajo interact_ref y hash; llamando a grant.continue CON ellos...')
    try {
      const g = await w.client.grant.continue(
        { url: pending.continue.uri, accessToken: pending.continue.access_token.value },
        { interact_ref: params.get('interact_ref')! },
      )
      if ('access_token' in g && g.access_token) {
        state.outcome = 'el continue DEVOLVIÓ access token'
        state.approvedByMistake = true
        log('PASO c: el dueño aprobó por error.')
      } else {
        state.outcome = 'el continue finalizó SIN access token (rechazo registrado del lado del servidor)'
        log(`PASO c: ${state.outcome}`)
      }
    } catch (e) {
      const info = errInfo(e)
      state.outcome = `continue con interact_ref rechazado: status ${info.status ?? '?'} código ${info.code ?? '?'}`
      log(`PASO c: ${state.outcome}`)
    }
  } else {
    log('PASO c: llamando a grant.continue SIN interact_ref...')
    try {
      const g = await w.client.grant.continue({ url: pending.continue.uri, accessToken: pending.continue.access_token.value })
      if ('access_token' in g && g.access_token) {
        state.outcome = 'inesperado: el continue SIN interact_ref devolvió access token (hallazgo importante)'
      } else {
        state.outcome = 'el continue SIN interact_ref finalizó sin access token (sin error HTTP)'
      }
      log(`PASO c: ${state.outcome}`)
    } catch (e) {
      const info = errInfo(e)
      state.outcome = `continue sin interact_ref respondió: status ${info.status ?? '?'} código ${info.code ?? '?'}`
      log(`PASO c: ${state.outcome}`)
    }
  }

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
    await writeReport('reject-redirect.md', buildReport())
  }
  process.exit(state.error ? 1 : 0)
}

function buildReport(): string[] {
  const lines: string[] = [
    REPORT_HEADER('Experimento B — rechazo en la wallet y continue sin interact_ref'),
    `## P2 — ¿qué nombres de parámetros trae el redirect a finishUri cuando el usuario rechaza?\n\nParámetros recibidos: ${state.names.length ? state.names.map((n) => `\`${n}\``).join(', ') : '(ninguno)'}.\n\n- interact_ref: ${state.hasInteractRef === null ? 'no llegó redirect' : state.hasInteractRef ? 'presente' : 'ausente'}\n- hash: ${state.hasHash === null ? 'no llegó redirect' : state.hasHash ? 'presente' : 'ausente'}\n- result: ${state.result}`,
    `## P2 — ¿qué responde grant.continue después del rechazo?\n\n${state.outcome ?? 'no se llegó a llamar al continue'}.`,
  ]
  if (state.approvedByMistake) lines.push('## Estado del experimento\n\nAprobado por error: no concluyente. NO se repite sin OK del supervisor.')
  if (state.error) lines.push(`## Error de la corrida\n\n${state.error}`)
  return lines
}

main()