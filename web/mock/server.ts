// Mock del Contrato B (docs/contratos-http-v1.md) para desarrollar el frontend sin Python.
// No es el backend real: responde con reglas fijas para recorrer cada TurnState.
// Correr: npm run mock  (puerto 8000, el mismo del backend Python, CONV-5)
//
// Guion de prueba:
//   - Comando por texto ("envíale 20 mil a laura hija") → siempre pide PIN (1234). Por voz salta el PIN.
//   - "laura" sin "hija"/"vecina" → elección de destinatario.
//   - Monto mayor a lo que queda del presupuesto → confirmación de exceso → wallet.
//   - "lento" en el comando → PAYMENT_PENDING; el turno de verificación lo completa.
//   - "error audio" → 400 INVALID_AUDIO · "error raro" → 400 código desconocido.
//   - Registro de voz: GET/POST /api/enrollment (consent=true y tres audios).
// Para recorrer los ejemplos oficiales del contrato, usar el mock de Prism: `npm run mock:prism`.
import { createServer, type IncomingMessage, type ServerResponse } from "node:http"
import { randomUUID } from "node:crypto"
import { PIN_ATTEMPTS_EXHAUSTED, PIN_PROMPT, pinRetrySay } from "./phrases"

const PORT = 8000
const WEB = "http://localhost:5173"
const ASSET = { assetCode: "COP", assetScale: 2 }
const PIN = "1234"

type Amount = { value: string; assetCode: string; assetScale: number }
type Pending = { alias: string; name: string; receive: Amount; slow: boolean }
type Session = {
  id: string
  state: string
  pending: Pending | null
  pinTries: number
  viaText: boolean
  awaitingGrant: "budget" | "excess" | null
}

const CONTACTS = [
  { alias: "laura-hija", name: "Laura (hija)", wallet: "https://ilp.interledger-test.dev/laura" },
  { alias: "laura-vecina", name: "Laura (vecina)", wallet: "https://ilp.interledger-test.dev/laura-vecina" },
]
const sessions = new Map<string, Session>()
let budget: { limit: bigint; spent: bigint } | null = null
let enrolled = false
let lastSession: Session | null = null // el callback de la wallet no trae sessionId
const extraContacts: { alias: string; name: string; walletAddress: string }[] = []

const amt = (v: bigint): Amount => ({ value: v.toString(), ...ASSET })
const pesos = (v: bigint) => (v / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".")
const fee = (v: bigint) => (v * 75n) / 10_000n // 0,75 % de costo simulado

function turn(s: Session, state: string, say: string, extra: Record<string, unknown> = {}) {
  s.state = state
  return { sessionId: s.id, state, say, transcript: null, interactUrl: null, options: null, payment: null, ...extra }
}

// "20 mil", "veinte mil", "300000" → unidades menores. Suficiente para el mock, no es amount-parsing.
function parseAmount(text: string): bigint | null {
  const words: Record<string, number> = { diez: 10, veinte: 20, cincuenta: 50, cien: 100, trescientos: 300 }
  const m = text.match(/(\d+)\s*mil|(\d{4,})|(diez|veinte|cincuenta|cien|trescientos)\s*mil/)
  if (!m) return null
  const pesosValue = m[1] ? Number(m[1]) * 1000 : m[2] ? Number(m[2]) : words[m[3]!]! * 1000
  return BigInt(pesosValue) * 100n
}

function startCommand(s: Session, text: string, viaText: boolean) {
  if (text.includes("error audio")) throw { status: 400, code: "INVALID_AUDIO" }
  if (text.includes("error raro")) throw { status: 400, code: "SOMETHING_NEW" }
  const receive = parseAmount(text)
  if (!receive) return turn(s, "AWAITING_COMMAND", "No entendí el monto. Di, por ejemplo: envíale veinte mil a Laura.", { transcript: text })
  s.viaText = viaText
  s.pinTries = 0
  const slow = text.includes("lento")
  if (!text.includes("laura")) return turn(s, "REJECTED", "No encuentro a esa persona en tu agenda.", { transcript: text })
  const exact = CONTACTS.find((c) => text.includes(c.alias.split("-")[1]!))
  s.pending = { alias: exact?.alias ?? "", name: exact?.name ?? "", receive: amt(receive), slow }
  if (!budget) {
    s.awaitingGrant = "budget"
    return turn(s, "AWAITING_AUTHORIZATION", "Primero autoriza un presupuesto en tu billetera.", { transcript: text, interactUrl: walletUrl() })
  }
  if (!exact) return turn(s, "AWAITING_RECIPIENT_CHOICE", "¿A cuál Laura?", { transcript: text, options: CONTACTS.map(({ alias, name }) => ({ alias, name })) })
  return afterRecipient(s, text)
}

function afterRecipient(s: Session, transcript: string | null) {
  if (s.viaText) return turn(s, "AWAITING_PIN", PIN_PROMPT, { transcript })
  return confirm(s, transcript)
}

function confirm(s: Session, transcript: string | null) {
  const p = s.pending!
  const debit = BigInt(p.receive.value) + fee(BigInt(p.receive.value))
  const remaining = budget!.limit - budget!.spent
  const say = debit > remaining
    ? `Supera tu presupuesto. Te quedan ${pesos(remaining)} pesos. ¿Lo autorizas en tu billetera?`
    : `¿Le envío ${pesos(BigInt(p.receive.value))} pesos a ${p.name}?`
  return turn(s, "AWAITING_CONFIRMATION", say, { transcript })
}

function pay(s: Session) {
  const p = s.pending!
  const receive = BigInt(p.receive.value)
  const debit = receive + fee(receive)
  if (debit > budget!.limit - budget!.spent) {
    s.awaitingGrant = "excess"
    return turn(s, "AWAITING_AUTHORIZATION", "Te llevo a tu billetera para que lo autorices.", { interactUrl: walletUrl() })
  }
  budget!.spent += debit
  if (p.slow) return turn(s, "PAYMENT_PENDING", "Tu envío va en camino. Te aviso cuando llegue.")
  return completed(s, debit)
}

function completed(s: Session, debit: bigint) {
  const p = s.pending!
  s.pending = null
  const contact = CONTACTS.find((c) => c.alias === p.alias)!
  return turn(s, "COMPLETED", `Listo. Laura recibió ${pesos(BigInt(p.receive.value))} pesos.`, {
    payment: { paymentId: `p_${randomUUID().slice(0, 8)}`, receiver: contact.wallet, debitAmount: amt(debit), receiveAmount: p.receive },
  })
}

function handleTurn(s: Session, text: string | null, hasAudio: boolean, kind: string | null) {
  // Por voz, el mock simula lo que diría Whisper según el estado.
  const said = text ?? (hasAudio ? (s.state === "AWAITING_CONFIRMATION" ? "sí" : "envíale veinte mil a laura hija") : null)
  const viaText = text !== null
  if (said === null) {
    // Turno automático de PAYMENT_PENDING: kind=verify_pending (B-2, D-1b). Cualquier otro vacío es un 400.
    if (kind === "verify_pending" && s.state === "PAYMENT_PENDING" && s.pending) {
      const r = BigInt(s.pending.receive.value)
      return completed(s, r + fee(r))
    }
    throw { status: 400, code: "AUDIO_OR_TEXT_REQUIRED" }
  }
  const t = said.toLowerCase().trim()
  switch (s.state) {
    case "AWAITING_PIN": {
      if (hasAudio) throw { status: 400, code: "AUDIO_OR_TEXT_REQUIRED" } // el audio se descarta en el PIN
      if (t === PIN) return confirm(s, null)
      s.pinTries++
      if (s.pinTries >= 3) { s.pending = null; return turn(s, "REJECTED", PIN_ATTEMPTS_EXHAUSTED) }
      return turn(s, "AWAITING_PIN", pinRetrySay(3 - s.pinTries))
    }
    case "AWAITING_RECIPIENT_CHOICE": {
      const c = CONTACTS.find((x) => x.alias === t || t.includes(x.alias.split("-")[1]!))
      if (!c) return turn(s, "AWAITING_RECIPIENT_CHOICE", "No te entendí. ¿Laura tu hija o Laura tu vecina?", { options: CONTACTS.map(({ alias, name }) => ({ alias, name })) })
      Object.assign(s.pending!, { alias: c.alias, name: c.name })
      return afterRecipient(s, viaText ? null : said)
    }
    case "AWAITING_CONFIRMATION":
      if (/^s[ií](?![a-zñ])/.test(t)) return pay(s) // \b no sirve tras "í" en regex de JS
      s.pending = null
      return turn(s, "REJECTED", "Listo, no envío nada.", { transcript: said })
    default:
      return startCommand(s, t, viaText)
  }
}

function walletUrl() {
  return `http://localhost:${PORT}/mock-wallet`
}

const walletPage = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Billetera de prueba (mock)</title>
<body style="font:20px system-ui;max-width:28rem;margin:3rem auto;padding:0 1rem">
<p><b>Billetera de prueba (mock)</b></p><p>EZPAY pide permiso para enviar pagos con un tope.</p>
<p><a href="${WEB}/grant-callback?interact_ref=mock-ref&hash=mock-hash">Aprobar</a></p>
<p><a href="${WEB}/grant-callback?result=grant_rejected">Rechazar</a></p>`

async function readBody(req: IncomingMessage) {
  const chunks: Buffer[] = []
  for await (const c of req) chunks.push(c as Buffer)
  return Buffer.concat(chunks)
}

function send(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { "Content-Type": "application/json" })
  res.end(JSON.stringify(body))
}

createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://localhost:${PORT}`)
  const rid = req.headers["x-request-id"] ?? "-"
  try {
    if (req.method === "GET" && url.pathname === "/mock-wallet") {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" })
      return res.end(walletPage)
    }
    if (req.method === "POST" && url.pathname === "/api/budget") {
      const { debitAmount } = JSON.parse((await readBody(req)).toString())
      if (!/^\d+$/.test(debitAmount?.value ?? "")) throw { status: 400, code: "INVALID_AMOUNT" }
      const s = lastSession ?? newSession()
      s.awaitingGrant = "budget"
      ;(globalThis as any).__requestedLimit = BigInt(debitAmount.value)
      return send(res, 201, { interactUrl: walletUrl() })
    }
    if (req.method === "GET" && url.pathname === "/api/budget") {
      // [PREGUNTA ABIERTA a Pagos] El contrato no define la respuesta sin presupuesto. El mock responde 404;
      // el frontend trata cualquier error o estado distinto de ACTIVE como "sin presupuesto".
      if (!budget) throw { status: 404, code: "BUDGET_NOT_FOUND" }
      return send(res, 200, { status: "ACTIVE", limit: { debitAmount: amt(budget.limit) }, spent: amt(budget.spent), remaining: amt(budget.limit - budget.spent) })
    }
    if (req.method === "POST" && url.pathname === "/api/grant-callback") {
      const cb = JSON.parse((await readBody(req)).toString())
      const s = lastSession ?? newSession()
      if (!cb.interactRef || !cb.hash) {
        s.pending = null
        s.awaitingGrant = null
        return send(res, 200, turn(s, "REJECTED", "No se autorizó en la billetera. No envié nada."))
      }
      const reason = s.awaitingGrant
      s.awaitingGrant = null
      if (reason === "excess" && s.pending) {
        // El exceso se paga con un grant puntual (add-payments-service D13): el presupuesto no se toca.
        const r = BigInt(s.pending.receive.value)
        return send(res, 200, completed(s, r + fee(r)))
      }
      budget = { limit: (globalThis as any).__requestedLimit ?? 20_000_000n, spent: 0n }
      if (s.pending) return send(res, 200, s.pending.alias ? afterRecipient(s, null) : turn(s, "AWAITING_RECIPIENT_CHOICE", "Presupuesto listo. ¿A cuál Laura?", { options: CONTACTS.map(({ alias, name }) => ({ alias, name })) }))
      return send(res, 200, turn(s, "AWAITING_COMMAND", `Presupuesto autorizado: ${pesos(budget.limit)} pesos. ¿A quién le envío?`))
    }
    if (req.method === "POST" && url.pathname === "/api/turns") {
      const raw = await readBody(req)
      const form = await new Response(raw, { headers: { "content-type": req.headers["content-type"] ?? "" } }).formData()
      const sid = form.get("sessionId") as string | null
      if (sid && !sessions.has(sid)) throw { status: 404, code: "SESSION_NOT_FOUND" }
      const s = sid ? sessions.get(sid)! : newSession()
      lastSession = s
      const text = form.get("text") as string | null
      const out = handleTurn(s, text, form.has("audio"), form.get("kind") as string | null)
      console.log(`[mock] ${rid} /turns -> ${out.state}`)
      return send(res, 200, out)
    }
    // Agenda (x-proposed): el mock no consulta Open Payments; solo exige https y un nombre.
    if (req.method === "GET" && url.pathname === "/api/contacts") {
      const base = CONTACTS.map(({ alias, name, wallet }) => ({ alias, name, walletAddress: wallet }))
      return send(res, 200, { contacts: [...base, ...extraContacts] })
    }
    if (req.method === "POST" && url.pathname === "/api/contacts") {
      const { name, walletAddress } = JSON.parse((await readBody(req)).toString())
      if (!/^[\p{L} ]{1,40}$/u.test(name ?? "")) throw { status: 400, code: "INVALID_CONTACT" }
      if (!/^(https:\/\/|\$)[\w.-]+\/[\w./-]+$/.test(walletAddress ?? "")) throw { status: 400, code: "INVALID_WALLET" }
      const alias = name.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-")
      if (extraContacts.some((c) => c.alias === alias)) throw { status: 409, code: "CONTACT_EXISTS" }
      const c = { alias, name, walletAddress: walletAddress.replace(/^\$/, "https://") }
      extraContacts.push(c)
      return send(res, 201, c)
    }
    if (req.method === "DELETE" && url.pathname.startsWith("/api/contacts/")) {
      const alias = decodeURIComponent(url.pathname.split("/").pop()!)
      const i = extraContacts.findIndex((c) => c.alias === alias)
      if (i < 0) throw { status: 404, code: "CONTACT_NOT_FOUND" }
      extraContacts.splice(i, 1)
      res.writeHead(204)
      return res.end()
    }
    if (req.method === "GET" && url.pathname === "/api/enrollment") return send(res, 200, { enrolled })
    if (req.method === "POST" && url.pathname === "/api/enrollment") {
      const form = await new Response(await readBody(req), { headers: { "content-type": req.headers["content-type"] ?? "" } }).formData()
      if (form.get("consent") !== "true") throw { status: 400, code: "CONSENT_REQUIRED" }
      if (form.getAll("audio").length !== 3) throw { status: 400, code: "SAMPLES_REQUIRED" }
      enrolled = true // el mock no guarda las muestras: solo recuerda que hubo registro
      return send(res, 201, { enrolled: true })
    }
    if (url.pathname === "/mock/reset") {
      sessions.clear(); budget = null; lastSession = null; enrolled = false
      return send(res, 200, { ok: true })
    }
    send(res, 404, { error: { code: "NOT_FOUND", message: url.pathname } })
  } catch (e: any) {
    if (e?.code && e?.status) {
      console.log(`[mock] ${rid} ${url.pathname} -> ${e.status} ${e.code}`)
      return send(res, e.status, { error: { code: e.code, message: "mock" } })
    }
    console.error(e)
    send(res, 500, { error: { code: "INTERNAL_ERROR", message: "mock" } })
  }
}).listen(PORT, () => console.log(`Mock del Contrato B en http://localhost:${PORT}/api  (reset: /mock/reset)`))

function newSession(): Session {
  const s: Session = { id: `s_${randomUUID().slice(0, 8)}`, state: "AWAITING_COMMAND", pending: null, pinTries: 0, viaText: false, awaitingGrant: null }
  sessions.set(s.id, s)
  return s
}
