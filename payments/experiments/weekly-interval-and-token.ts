// Experiment A: weekly interval (P1), spent delay (P5), expired-token rotation (P4), revoke (P3 part 1).
// Grant cap: 5.000,00 COP (value "500000"). Payments: 500,00 COP each; up to 3 in this script,
// 5 across the whole unit (authorized by the supervisor).
// Run: npm run exp:weekly   (owner approves in the browser; 5.000 COP = APROBAR)
import {
  dryRunGuard, errInfo, grantSpent, money, maskWallet, openCallbackListener, openInBrowser,
  openWallet, payOnce, progressPerMinute, requestInteractiveGrant, continueGrant,
  REPORT_HEADER, waitCallback, writeReport,
} from './lib.js'
import type { PendingGrant } from '@interledger/open-payments'

if (await dryRunGuard('weekly-interval-and-token')) process.exit(0)

const CAP = '500000'
const PAY = '50000'

type Variant = { interval: string; accepted: boolean; err?: { status?: number; code?: string; description?: string } }
type Echo = { interval?: string; debitValue?: string }
type SeriesEntry = { second: number; value: string | null }
type PaymentRecord = { label: string; made: boolean; detail: string }

const state = {
  variants: [] as Variant[],
  acceptedInterval: null as string | null,
  expires_in: null as number | null,
  manageExists: null as boolean | null,
  manageChangedOnRotate: null as boolean | null,
  echo: null as Echo | null,
  spentBefore: null as string | null,
  series: [] as SeriesEntry[],
  reflectedSeconds: null as number | null,
  expiredAttempt: null as string | null,
  rotateResult: null as string | null,
  oldTokenAfterRotate: null as string | null,
  revokeResult: null as string | null,
  revokeBlocks: 'unknown' as 'yes' | 'no' | 'unknown',
  payment3: null as string | null,
  payments: [] as PaymentRecord[],
  error: null as string | null,
}

const log = (line: string) => {
  console.log(line)
}

const todayMidnightUtc = () => `${new Date().toISOString().slice(0, 10)}T00:00:00Z`

async function flow(): Promise<void> {
  const w = await openWallet()
  log(`Experimento A — remitente ${maskWallet(w.sender, 'sender')} receptor ${maskWallet(w.receiver, 'receiver')}`)
  const listener = openCallbackListener(log)
  await listener.ready
  const finishUri = 'http://localhost:5173/grant-callback'
  const s = w.sender.assetScale

  // --- step a: interval variants (P1)
  let pending: PendingGrant | null = null
  for (const interval of [`R1/${todayMidnightUtc()}/P1W`, `R1/${todayMidnightUtc()}/P7D`, `R/${todayMidnightUtc()}/P1W`]) {
    try {
      pending = await requestInteractiveGrant(w, finishUri, CAP, interval)
      state.acceptedInterval = interval
      state.variants.push({ interval, accepted: true })
      log(`PASO a: intervalo ${interval} ACEPTADO (grant pendiente creado)`)
      break
    } catch (e) {
      const info = errInfo(e)
      state.variants.push({ interval, accepted: false, err: info })
      log(`PASO a: intervalo ${interval} rechazado (status ${info.status ?? '?'} código ${info.code ?? '?'})`)
    }
  }
  if (!pending || !state.acceptedInterval) throw new Error('ninguna variante de intervalo fue aceptada')

  // --- step b: owner approval + continue (P1 echo)
  log('PASO b: abriendo la wallet en el navegador (5.000,00 COP = APROBAR)...')
  openInBrowser(pending.interact.redirect!)
  const params = await waitCallback(listener, 'aprobación del grant A')
  await listener.close() // frees 5173 for the other experiments during the 11-minute wait
  const finalized = await continueGrant(w, pending, params)
  state.expires_in = finalized.expiresIn
  state.manageExists = finalized.manageUrl !== null
  const raw = finalized.limits[0] as { limits?: { interval?: string; debitAmount?: { value: string } } } | undefined
  state.echo = { interval: raw?.limits?.interval, debitValue: raw?.limits?.debitAmount?.value }
  log(`PASO b: continue OK; expires_in=${state.expires_in ?? 'no informado'}; manage URL existe: ${state.manageExists}`)
  log(`PASO b: eco de limits: interval=${state.echo.interval ?? 'ausente'}; debitAmount=${state.echo.debitValue ? money(state.echo.debitValue, s) : 'ausente'}`)

  // --- step c: payment 1 + spent delay series (P5)
  const before = await grantSpent(w, finalized.accessToken)
  state.spentBefore = before.spentDebit
  log(`PASO c: gastado antes del pago (consulta directa): ${state.spentBefore ?? 'no informado'}`)
  const pay1 = await payOnce(w, PAY, finalized.accessToken)
  state.payments.push({ label: 'Pago 1 (grant A, token original)', made: true, detail: `debit=${money(pay1.debitValue, s)}` })
  log(`PASO c: pago 1 OK — debit=${money(pay1.debitValue, s)} receive=${money(pay1.receiveValue, s)}`)
  const t0 = Date.now()
  for (;;) {
    const x = await grantSpent(w, finalized.accessToken).catch(() => null)
    state.series.push({ second: Math.round((Date.now() - t0) / 1000), value: x?.spentDebit ?? null })
    if (x?.spentDebit && BigInt(x.spentDebit) >= BigInt(pay1.debitValue)) {
      state.reflectedSeconds = Math.round((Date.now() - t0) / 1000)
      break
    }
    if (Date.now() - t0 > 30_000) break
    await new Promise((r) => setTimeout(r, 1000))
  }
  log(`PASO c (P5): el gastado reflejó el pago en ${state.reflectedSeconds !== null ? `${state.reflectedSeconds} s` : 'NO en 30 s'}`)

  // --- step d: expired token (P4)
  log('PASO d: esperando 11 minutos para que venza el token...')
  await progressPerMinute(11 * 60_000, log)
  const oldToken = finalized.accessToken
  try {
    const p2 = await payOnce(w, PAY, oldToken)
    state.expiredAttempt = `el pago con el token VENCIDO SUCEDIÓ (debit=${money(p2.debitValue, s)})`
    state.payments.push({ label: 'Intento de pago con el token VENCIDO', made: true, detail: `debit=${money(p2.debitValue, s)} (hallazgo: el token vencido todavía pagó)` })
  } catch (e) {
    const info = errInfo(e)
    state.expiredAttempt = `pago con token vencido rechazado: status ${info.status ?? '?'} código ${info.code ?? '?'}`
    state.payments.push({ label: 'Intento de pago con el token VENCIDO', made: false, detail: `status ${info.status ?? '?'} código ${info.code ?? '?'}` })
  }
  log(`PASO d: ${state.expiredAttempt}`)
  try {
    const r = await w.client.token.rotate({ url: finalized.manageUrl!, accessToken: oldToken })
    const newToken = r.access_token.value
    const newManage = r.access_token.manage ?? null
    state.manageChangedOnRotate = newManage !== finalized.manageUrl
    state.rotateResult = `token.rotate sobre token VENCIDO aceptado; expires_in nuevo=${r.access_token.expires_in ?? 'no informado'}; manage URL cambió: ${state.manageChangedOnRotate}`
    log(`PASO d: ${state.rotateResult}`)
    const pay2 = await payOnce(w, PAY, newToken)
    state.payments.push({ label: 'Pago 2 con token rotado', made: true, detail: `debit=${money(pay2.debitValue, s)}` })
    log(`PASO d: pago 2 con token rotado OK — debit=${money(pay2.debitValue, s)}`)
    const probe = await grantSpent(w, oldToken).then((x) => ({ ok: true as const, spentDebit: x.spentDebit })).catch((e) => ({ ok: false as const, err: errInfo(e) }))
    state.oldTokenAfterRotate = probe.ok
      ? `consulta con el token VIEJO tras rotar: ACEPTADA (spentDebit=${money(String(probe.spentDebit), s)})`
      : `consulta con el token VIEJO tras rotar: RECHAZADA (status ${probe.err.status ?? '?'} código ${probe.err.code ?? '?'})`
    log(`PASO d: ${state.oldTokenAfterRotate}`)

    // --- step e: revoke (P3 part 1)
    try {
      await w.client.token.revoke({ url: newManage ?? finalized.manageUrl!, accessToken: newToken })
      const probe2 = await grantSpent(w, newToken).then((x) => ({ ok: true as const, spentDebit: x.spentDebit })).catch((e) => ({ ok: false as const, err: errInfo(e) }))
      if (probe2.ok) {
        state.revokeResult = `token.revoke OK; consulta de lectura con el token revocado ACEPTADA (spentDebit=${money(String(probe2.spentDebit), s)})`
        state.revokeBlocks = 'no'
      } else {
        state.revokeResult = `token.revoke OK; consulta de lectura con el token revocado RECHAZADA (status ${probe2.err.status ?? '?'} código ${probe2.err.code ?? '?'})`
        state.revokeBlocks = 'yes'
      }
    } catch (e) {
      const info = errInfo(e)
      state.revokeResult = `token.revoke falló: status ${info.status ?? '?'} código ${info.code ?? '?'}`
    }
    log(`PASO e: ${state.revokeResult}`)
    if (state.revokeBlocks === 'no') {
      try {
        const p3 = await payOnce(w, PAY, newToken)
        state.payment3 = `el pago con el token revocado SUCEDIÓ (debit=${money(p3.debitValue, s)}) — hallazgo importante`
        state.payments.push({ label: 'Pago 3 con el token revocado', made: true, detail: `debit=${money(p3.debitValue, s)}` })
      } catch (e) {
        const info = errInfo(e)
        state.payment3 = `el pago con el token revocado fue rechazado: status ${info.status ?? '?'} código ${info.code ?? '?'}`
        state.payments.push({ label: 'Pago 3 con el token revocado', made: false, detail: `status ${info.status ?? '?'} código ${info.code ?? '?'}` })
      }
      log(`PASO e: ${state.payment3}`)
    } else {
      state.payment3 = 'no se hizo: la lectura ya demostró que el token revocado queda inusable'
      log(`PASO e: ${state.payment3}`)
    }
  } catch (e) {
    const info = errInfo(e)
    state.rotateResult = `token.rotate falló: status ${info.status ?? '?'} código ${info.code ?? '?'}`
    log(`PASO d: ${state.rotateResult}`)
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
    await writeReport('weekly-interval-and-token.md', buildReport())
  }
  process.exit(state.error ? 1 : 0)
}

function buildReport(): string[] {
  const lines: string[] = [
    REPORT_HEADER('Experimento A — intervalo semanal, retraso del gastado, rotación y revocación'),
    `## P1 — ¿la wallet acepta un interval semanal con una repetición junto a debitAmount?\n\nIntentos (en orden); la cadena de intervalo es pública:\n\n| interval | aceptado | status / código |\n|---|---|---|\n${state.variants.map((v) => `| \`${v.interval}\` | ${v.accepted ? 'sí' : 'no'} | ${v.accepted ? '—' : `${v.err?.status ?? '?'} ${v.err?.code ?? ''}`.trim()} |`).join('\n')}`,
  ]
  if (state.acceptedInterval) {
    lines.push(`Intervalo aceptado: \`${state.acceptedInterval}\`.\n\nRespuesta del continue: eco de limits.interval: ${state.echo?.interval ? `\`${state.echo.interval}\`` : 'ausente'}; eco de limits.debitAmount: ${state.echo?.debitValue ? 'presente' : 'ausente'}; expires_in del token: ${state.expires_in ?? 'no informado'}; manage URL existe: ${state.manageExists}.`)
  }
  if (state.series.length) {
    lines.push(`## P5 — retraso del gastado tras un pago (consulta directa, sin servicio)\n\nGastado antes del pago: ${state.spentBefore ?? 'no informado'}. Serie tras crear el pago (segundo, spentDebitAmount):\n\n| segundo | spentDebitAmount |\n|---|---|\n${state.series.map((x) => `| ${x.second} | ${x.value ?? 'error de consulta'} |`).join('\n')}\n\nEl pago se reflejó en ${state.reflectedSeconds !== null ? `${state.reflectedSeconds} s` : 'más de 30 s (no apareció)'}.`)
  }
  if (state.expiredAttempt) {
    lines.push(`## P4 — rotación de un token vencido (>10 min)\n\n- Intento de pago con el token vencido: ${state.expiredAttempt}\n- ${state.rotateResult ?? 'no se llegó a rotar'}\n- ${state.oldTokenAfterRotate ?? 'no se probó el token viejo tras rotar (rotación no exitosa)'}`)
  }
  if (state.revokeResult) {
    lines.push(`## P3 (parte 1) — ¿token.revoke invalida de verdad el acceso?\n\n- ${state.revokeResult}\n- ${state.payment3 ?? ''}\n\n¿Bloquea el acceso?: ${state.revokeBlocks === 'yes' ? 'sí (la lectura quedó inusable)' : state.revokeBlocks === 'no' ? 'no (la lectura siguió funcionando)' : 'desconocido (el revoke mismo falló)'}.`)
  }
  const made = state.payments.filter((p) => p.made)
  lines.push(`## Pagos reales de esta corrida (tope de la unidad: 5 pagos de 500,00 COP)\n\n| pago | realizado | detalle |\n|---|---|---|\n${state.payments.map((p) => `| ${p.label} | ${p.made ? 'sí' : 'no'} | ${p.detail} |`).join('\n')}\n\nPagos reales hechos aquí: ${made.length}${made.length ? ` (${made.map((p) => p.label).join('; ')})` : ''}.`)
  if (state.error) lines.push(`## Error de la corrida\n\n${state.error}`)
  return lines
}

main()