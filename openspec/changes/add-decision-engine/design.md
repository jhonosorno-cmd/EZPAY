# Diseño — add-decision-engine

Material de referencia de las capabilities `decision-engine` y `pin-validation`: trazabilidad, tablas y tipos que los requisitos citan, y puntos abiertos. Los requisitos y escenarios normativos están en `specs/`.

## Trazabilidad

### decision-engine
| Requisito | Origen |
| --- | --- |
| Función pura y determinística | D1; `turn-orchestration` "Motor como función pura"; SEG-3 |
| La Decision incluye un `reason` | Decisión de Daniel (ML 2, 2026-10-16); `turn-orchestration` "Frases de `say` de plantillas, nunca del LLM"; SEG-3 (el motor no genera texto) |
| Contexto de entrada (`context`) | `turn-orchestration` (quote, `pendingPayment`, `previouslyPaid`, puntajes de confianza, voz); contrato-voz (`Intent`, `Resolution`, `Reply`); Contratos v1 (`Amount`, CONV-1) — decidido 2026-10-16 con ML 2, ML 1 y Pagos |
| Decisión por tabla ordenada | D2; SEG-3 |
| Regla 1 `CANCEL → REJECT` | catálogo de `say` (`CANCELLED` → `REJECTED`) |
| Regla 2 intención inválida → `REASK` (reason derivado por prioridad) | SEG-3; SEG-4; `intent-extraction`; decisión con ML 1 (2026-10-16) |
| Regla 2b cortes de confianza → `REASK` | `docs/decisiones.md` 3b (puntaje por pipeline, 16 oct); `turn-orchestration` "Puntajes de confianza en el contexto"; decisión con ML 1 (2026-10-16) |
| Reglas 3–4 agenda (`NOT_FOUND`, `CHOICE`) | SEG-4 |
| Regla 5 sin grant → `REQUIRE_AUTH` | SEG-1; `turn-orchestration` "Sin grant de presupuesto" (allí llamada "regla 4 de la tabla de ML 2"; en esta tabla es la 5) |
| Regla 6 pago pendiente | `turn-orchestration` "Decisión sobre el pago pendiente" (ventana decidida: 120 s, 2026-10-16) |
| Regla 6b aviso post-ventana → `PENDING_PAYMENT_UNCONFIRMED` | Decisión de ML 2 (2026-10-16, opción A); `turn-orchestration` "Pasado el tope con un sí claro"; falta comunicarlo a Pagos |
| `PAYMENT_PENDING` visible con frase "Tu envío está en camino…" y verificación silenciosa (~20 s) | **[DECIDIDO 2026-10-16, con Frontend: PAYMENT_PENDING visible, PR #2]**; B-2 ratificado; revierte la opción A |
| Cada `reason` se asocia a una situación del catálogo único de Voz (`api/voice/phrases.py`) | Decisión de Daniel (2026-10-16): conflictos 2 y 3 de `docs/flujos/flujo-con-prs.md` §8; B-6 ratificado; `turn-orchestration` "Frases de `say` de plantillas, nunca del LLM" |
| Regla 7 voz no verificada → `ASK_PIN` | SEG-6; D3; `turn-orchestration` "Comando por texto…" y "Usuario no enrolado" |
| Regla 8 monto alto o destinatario nuevo → `ASK_PIN` | SEG-6; D9; `turn-orchestration` "Historial de pagos por destinatario" |
| Regla 9 resto → `ASK_CONFIRM` | SEG-2; SEG-5 y SEG-6 (el exceso no pide PIN por monto) |
| Fase PIN | SEG-6 (tres fallos → `REJECTED`); SEG-2 (el PIN se suma al "sí"); D5; capability `pin-validation` |
| Fase CONFIRMATION | SEG-2; SEG-5; D4 |
| El motor no obedece al LLM | SEG-3 |
| Montos comparados como enteros | CONV-1; Contratos v1 "Montos" |

### pin-validation
| Requisito | Origen |
| --- | --- |
| Alta por configuración, hash con sal, sin endpoint | D5 |
| Formato 4–6 dígitos, comparación en tiempo constante | D5 |
| Contadores de intentos (los lleva el componente de PIN) | SEG-6 ("PIN incorrecto tres veces" → `REJECTED`); D5; `turn-orchestration` "PIN incorrecto" |
| Privacidad del PIN | PRIV-4; `turn-orchestration` ("Audio en `AWAITING_PIN`", "Logs del turno…", "Respuesta de un turno de PIN", "Errores sin datos…", "El PIN nunca sale de Python") |
| `transcript: null` y `say` sin dígitos; `AWAITING_PIN` con intentos restantes | B-7, B-8 **[RATIFICADOS 2026-10-16]** (`docs/decisiones.md`, contratos v1.1); `turn-orchestration` |
| Entrada por campo `text` hasta H3 | Decisión #2 del 16 oct (`docs/decisiones.md`); B-8 |
| Interfaz `verify_pin` / `reset_pin_lock` | D5; decidida 2026-10-16 con ML 2, ML 1 y Pagos **[DECIDIDO]** |
| El motor recibe el resultado y no valida el PIN | D1, D5; `turn-orchestration` "Motor como función pura" |

## Detalle de `decision-engine`

#### El motor es una función pura y determinística

El motor SHALL exponerse como función pura `decide(context) -> Decision`, sin HTTP, sin acceso a
Node, sin reloj ni aleatoriedad propios: la hora llega en `context.now`. La función MUST ser
determinística: el mismo `context` produce siempre el mismo `{decision, reason}`. `Decision` SHALL
ser un objeto `{decision, reason}`: `decision` es una de `REASK`, `ASK_RECIPIENT`, `ASK_PIN`,
`ASK_CONFIRM`, `REQUIRE_AUTH`, `PAY`, `REJECT`, y `reason` un código de cierre de la lista cerrada
del requisito "La Decision incluye un reason". El mapeo de cada `Decision` a `TurnState` lo hace el
orquestador, no el motor.

#### El contexto de entrada

El motor SHALL recibir todo lo que necesita en un único objeto `context`. El orquestador SHALL armar
el `context` completo; el motor no calcula nada del contexto. La forma y los nombres de los campos
están decididos (2026-10-16 con ML 2, ML 1 y Pagos; ver la nota de abajo):

```ts
type Decision = { decision: "REASK" | "ASK_RECIPIENT" | "ASK_PIN" | "ASK_CONFIRM" | "REQUIRE_AUTH" | "PAY" | "REJECT"; reason: Reason }

type Reason =
  | "CANCELLED_BY_USER" | "INTENT_UNKNOWN" | "AMOUNT_ERROR" | "INTENT_AMBIGUOUS" | "AMOUNT_MISSING"
  | "RECIPIENT_MISSING" | "INTENT_UNCLEAR" | "INTENT_LOW_CONFIDENCE" | "TRANSCRIPT_LOW_CONFIDENCE"
  | "RECIPIENT_NOT_FOUND" | "RECIPIENT_AMBIGUOUS" | "NO_BUDGET_GRANT" | "PENDING_PAYMENT_SAME_RECIPIENT"
  | "PENDING_PAYMENT_UNCONFIRMED"
  | "VOICE_NOT_VERIFIED" | "NEW_RECIPIENT" | "HIGH_AMOUNT" | "ALL_CHECKS_PASSED"
  | "PIN_LOCKED" | "PIN_CORRECT" | "PIN_WRONG" | "PIN_ATTEMPTS_EXHAUSTED" | "PIN_INVALID_FORMAT"
  | "CONFIRMED" | "CONFIRMED_NEEDS_WALLET_AUTH" | "USER_DECLINED" | "REPLY_UNCLEAR_ASK_AGAIN" | "REPLY_UNCLEAR_REJECTED"

type Context = {
  phase: "COMMAND" | "PIN" | "CONFIRMATION"      // decidido 2026-10-16: la fija el orquestador según el TurnState
                                                 // (AWAITING_COMMAND→COMMAND, AWAITING_PIN→PIN, AWAITING_CONFIRMATION→CONFIRMATION)
  intent: {                                      // Intent de ML 1 (contrato-voz)
    action: "PAY" | "CANCEL" | "UNKNOWN"
    amount: Amount | null                        // Amount = { value: string de dígitos, assetCode, assetScale }
    amountError: "TOO_MANY_DECIMALS" | "AMBIGUOUS_AMOUNT" | "INVALID_AMOUNT" | null
    recipient: string | null
    status: "OK" | "AMBIGUOUS" | "UNCLEAR"
  }
  resolution:
    | { kind: "RESOLVED"; contact: { alias: string; name: string; walletAddress: string; previouslyPaid: boolean } }
    | { kind: "CHOICE"; options: { alias: string; name: string }[] }
    | { kind: "NOT_FOUND" }
  voice: { status: "VERIFIED" | "BELOW_THRESHOLD" | "NOT_AVAILABLE"; score: number | null }
  enrolled: boolean                              // en H1, voice.status llega siempre NOT_AVAILABLE (comandos por texto)
  hasBudgetGrant: boolean
  quote: { debitAmount: Amount; receiveAmount: Amount; exceedsRemaining: boolean } | null  // null si no hay grant
  pendingPayment: { recipient: string; createdAt: string; status: "PROCESSING" | "COMPLETED" | "FAILED" } | null
    // valores del Contrato A; decidido: un pago sin paymentId (los 3 intentos de POST /v1/payments
    // terminaron en 502) cuenta como PROCESSING desde el primer intento; createdAt es el momento
    // de creación del pago o, si no hay pago, del primer intento de POST /v1/payments
  now: string                                    // la hora la trae el contexto; el motor no consulta el reloj
  reply: "YES" | "NO" | "UNCLEAR" | null
  unclearReplies: number                         // decidido 2026-10-16: lo lleva el orquestador; se reinicia al entrar a AWAITING_CONFIRMATION
  pin: { result: "OK" | "WRONG" | "INVALID_FORMAT" | null; sessionFailures: number; locked: boolean }  // lo produce pin-validation
  transcriptConfidence: number | null            // regla 2b: con corte activo, un puntaje bajo → REASK; null → el corte se ignora
  intentConfidence: number | null                // regla 2b: se evalúa antes que el de transcripción
  config: {
    highAmountThreshold: Amount | null           // null = desactivado; valor espera experimentos X-2/X-4 [ESPERA EXPERIMENTOS]
    pendingWindowSeconds: number                 // 120 (decidido 2026-10-16)
    minIntentConfidence: number | null           // null = corte desactivado (por defecto en H1); valor [PARA DECIDIR] (rol Voz)
    minTranscriptConfidence: number | null       // null = desactivado (por defecto en H1); valor [PARA DECIDIR] (rol Voz); más flexible que el de intención
  }
}
```

**Decidido 2026-10-16 con ML 2, ML 1 y Pagos:**

1. El orquestador arma el `context` completo; el motor no calcula nada.
2. El orquestador fija `phase` según el `TurnState`: `AWAITING_COMMAND` → `COMMAND`, `AWAITING_PIN` → `PIN`, `AWAITING_CONFIRMATION` → `CONFIRMATION`.
3. `pendingPayment.status` usa los valores del Contrato A (`PROCESSING | COMPLETED | FAILED`); solo `PROCESSING` cuenta como "abierto".
4. El destinatario del pago pendiente se compara por wallet address resuelta, no por alias.
5. `unclearReplies` lo lleva el orquestador; se reinicia al entrar a `AWAITING_CONFIRMATION`.
6. `previouslyPaid` va dentro de `resolution.contact`.
7. El monto de la regla 8 es `quote.receiveAmount`.
8. Un pago sin `paymentId` (los 3 intentos de `POST /v1/payments` terminaron en `502`) cuenta como
`PROCESSING` desde el primer intento: el orquestador arma `pendingPayment.status = "PROCESSING"`.
9. `pendingPayment.createdAt` es el momento de la creación del pago o, si no hay pago, el momento
del primer intento de `POST /v1/payments`.

Notas:

- `resolution` replica el tipo `Resolution` del contrato-voz menos el caso `UNCLEAR` (solo existe
en `resolve_choice`, que no pasa por el motor); nombres alineados con ML 1 (decidido 2026-10-16
con ML 2, ML 1 y Pagos).
- Los puntajes de confianza alimentan la regla 2b cuando su corte está configurado; con corte
`null` (por defecto en H1) o puntaje `null` (p. ej. comando por texto) la regla no aplica. Los
VALORES de los cortes los propone el rol Voz tras su batería **[PARA DECIDIR]** (rol Voz); el corte
de transcripción MUST ser más flexible (menor) que el de intención (principio del 16 oct,
`docs/decisiones.md` 3b).

#### La Decision incluye un reason

Además del `decision`, el motor SHALL devolver un `reason`: un código estable en inglés, de un
**enum cerrado** (uno por regla o rama). El `reason` SHALL servir de clave para la plantilla de
`say` que muestra al usuario: cada `reason` se asocia a una plantilla del catálogo de ML 1/Pagos
(en español). El motor MUST NOT generar texto libre ni usar el LLM (`turn-orchestration`: el `say`
sale de plantillas); solo emite el código. El `reason` MUST NOT contener datos del request (ni el
PIN, ni montos, ni transcripciones, ni nombres), y MUST NOT depender del reloj ni del azar: es tan
determinista como la decisión.

Tabla regla → reason:

| Fase | Regla / rama | Decision | Reason |
| --- | --- | --- | --- |
| COMMAND | 1 `CANCEL` | `REJECT` | `CANCELLED_BY_USER` |
| COMMAND | 2 intención inválida (reason derivado por prioridad) | `REASK` | `INTENT_UNKNOWN`, `AMOUNT_ERROR`, `INTENT_AMBIGUOUS`, `AMOUNT_MISSING`, `RECIPIENT_MISSING` o `INTENT_UNCLEAR` |
| COMMAND | 2b confianza bajo el corte activo (primero intención, luego transcripción) | `REASK` | `INTENT_LOW_CONFIDENCE` o `TRANSCRIPT_LOW_CONFIDENCE` |
| COMMAND | 3 `NOT_FOUND` | `REASK` | `RECIPIENT_NOT_FOUND` |
| COMMAND | 4 `CHOICE` | `ASK_RECIPIENT` | `RECIPIENT_AMBIGUOUS` |
| COMMAND | 5 sin grant | `REQUIRE_AUTH` | `NO_BUDGET_GRANT` |
| COMMAND | 6 pago pendiente mismo destinatario, abierto y dentro de la ventana (camino normal durante `PAYMENT_PENDING`; también defensa en profundidad) | `REASK` | `PENDING_PAYMENT_SAME_RECIPIENT` |
| COMMAND | 6b aviso post-ventana (condición-marca: no decide por sí sola; marca `warnUnconfirmed` y sigue a 7/8/9) | `ASK_CONFIRM` vía regla 9, o vía fase PIN | `PENDING_PAYMENT_UNCONFIRMED` |
| COMMAND | 7 voz no verificada | `ASK_PIN` | `VOICE_NOT_VERIFIED` |
| COMMAND | 8a destinatario nuevo | `ASK_PIN` | `NEW_RECIPIENT` |
| COMMAND | 8b monto ≥ umbral (o moneda/escala distinta) | `ASK_PIN` | `HIGH_AMOUNT` |
| COMMAND | 9 resto | `ASK_CONFIRM` | `PENDING_PAYMENT_UNCONFIRMED` si `warnUnconfirmed`; si no `ALL_CHECKS_PASSED` |
| PIN | `pin.locked` | `REJECT` | `PIN_LOCKED` |
| PIN | `pin.result == "OK"` | `ASK_CONFIRM` | `PENDING_PAYMENT_UNCONFIRMED` si aplica la 6b; si no `PIN_CORRECT` |
| PIN | `pin.result == "WRONG"`, `sessionFailures < 3` | `ASK_PIN` | `PIN_WRONG` |
| PIN | `pin.result == "WRONG"`, `sessionFailures >= 3` | `REJECT` | `PIN_ATTEMPTS_EXHAUSTED` |
| PIN | `pin.result == "INVALID_FORMAT"` o `null` | `ASK_PIN` | `PIN_INVALID_FORMAT` |
| CONFIRMATION | `YES` con `exceedsRemaining` | `REQUIRE_AUTH` | `CONFIRMED_NEEDS_WALLET_AUTH` |
| CONFIRMATION | `YES` sin exceso | `PAY` | `CONFIRMED` |
| CONFIRMATION | `NO` | `REJECT` | `USER_DECLINED` |
| CONFIRMATION | `UNCLEAR` con `unclearReplies == 0` | `ASK_CONFIRM` | `REPLY_UNCLEAR_ASK_AGAIN` |
| CONFIRMATION | `UNCLEAR` con `unclearReplies >= 1` | `REJECT` | `REPLY_UNCLEAR_REJECTED` |

#### Cada reason se asocia a una situación del catálogo único de Voz

Cada `reason` del enum SHALL asociarse a una situación del catálogo único de `say` de Voz
(`api/voice/phrases.py`, enum `Situation`) **[DECIDIDO]**: el motor no tiene textos; el orquestador
traduce `reason` ⇒ `Situation` (con las variantes que eligen los campos del `context`) y llama al
`say` de Voz. Voz agrega 13 situaciones nuevas a su catálogo con el mismo nombre del `reason` y los
textos ya decididos. Un `reason` sin situación (salvo `CONFIRMED`) es un error de contrato. El
motor nunca genera texto ni usa el LLM (`turn-orchestration`); nada contiene dígitos del PIN.

| reason | Situación del catálogo de Voz |
| --- | --- |
| `CANCELLED_BY_USER` | `CANCELLED` |
| `INTENT_UNKNOWN` | `NOT_UNDERSTOOD` |
| `INTENT_UNCLEAR` | `NOT_UNDERSTOOD` |
| `AMOUNT_ERROR` | según `intent.amountError`: `TOO_MANY_DECIMALS` ⇒ `TOO_MANY_DECIMALS`; `AMBIGUOUS_AMOUNT` ⇒ `AMOUNT_AMBIGUOUS`; `INVALID_AMOUNT` ⇒ `INVALID_AMOUNT` |
| `INTENT_AMBIGUOUS` | `INTENT_AMBIGUOUS` (nueva) |
| `AMOUNT_MISSING` | `AMOUNT_MISSING` |
| `RECIPIENT_MISSING` | `RECIPIENT_MISSING` |
| `INTENT_LOW_CONFIDENCE` | `INTENT_LOW_CONFIDENCE` (nueva) |
| `TRANSCRIPT_LOW_CONFIDENCE` | `TRANSCRIPT_LOW_CONFIDENCE` (nueva) |
| `RECIPIENT_NOT_FOUND` | `NOT_FOUND` |
| `RECIPIENT_AMBIGUOUS` | `CHOICE` (2+ opciones) o `NEAR` (1 opción) |
| `NO_BUDGET_GRANT` | `AUTH_BUDGET` |
| `PENDING_PAYMENT_SAME_RECIPIENT` | `PENDING_PAYMENT_SAME_RECIPIENT` (nueva) |
| `PENDING_PAYMENT_UNCONFIRMED` | `PENDING_PAYMENT_UNCONFIRMED` (nueva; `exceedsRemaining == false`) o `PENDING_PAYMENT_UNCONFIRMED_OVERRUN` (nueva; `true`) |
| `VOICE_NOT_VERIFIED` | `PIN_KEYBOARD` (Voz cambia su texto a "Por seguridad, escribe tu PIN en el teclado.") |
| `NEW_RECIPIENT` | `NEW_RECIPIENT` (nueva) |
| `HIGH_AMOUNT` | `HIGH_AMOUNT` (nueva) |
| `ALL_CHECKS_PASSED` | `CONFIRM` (`exceedsRemaining == false`) o `AUTH_OVERRUN` (`true`) |
| `PIN_CORRECT` | `CONFIRM` (`exceedsRemaining == false`) o `AUTH_OVERRUN` (`true`) |
| `PIN_WRONG` | `PIN_WRONG` (nueva) |
| `PIN_ATTEMPTS_EXHAUSTED` | `PIN_ATTEMPTS_EXHAUSTED` (nueva) |
| `PIN_LOCKED` | `PIN_LOCKED` (nueva) |
| `PIN_INVALID_FORMAT` | `PIN_INVALID_FORMAT` (nueva) |
| `CONFIRMED` | ninguna: el `say` sale del resultado del pago (`COMPLETED` o `PAYMENT_PENDING`) |
| `CONFIRMED_NEEDS_WALLET_AUTH` | `AUTH_REDIRECT` |
| `USER_DECLINED` | `CANCELLED` |
| `REPLY_UNCLEAR_ASK_AGAIN` | `CONFIRM_UNCLEAR` |
| `REPLY_UNCLEAR_REJECTED` | `REPLY_UNCLEAR_REJECTED` (nueva) |

Las 13 situaciones nuevas que Voz agrega (mismo nombre que el `reason`), con los textos decididos
**[DECIDIDO]**:

| Situación | Texto |
| --- | --- |
| `INTENT_AMBIGUOUS` | "No me quedó claro. Dime un solo monto y un solo destinatario." |
| `INTENT_LOW_CONFIDENCE` | "No te entendí bien. ¿Me lo repites?" |
| `TRANSCRIPT_LOW_CONFIDENCE` | "No te escuché bien. ¿Me lo repites?" |
| `PENDING_PAYMENT_SAME_RECIPIENT` | "Tu envío anterior a {nombre} aún no termina. Espera un momento." |
| `PENDING_PAYMENT_UNCONFIRMED` | "Tu envío anterior a {nombre} no se pudo confirmar. Si envías otro, {nombre} podría recibir los dos. ¿Le envío {recibe} {moneda}?" |
| `PENDING_PAYMENT_UNCONFIRMED_OVERRUN` | "Tu envío anterior a {nombre} no se pudo confirmar y este supera tu presupuesto. Si sigues, {nombre} podría recibir los dos. ¿Lo autorizas en tu billetera?" |
| `NEW_RECIPIENT` | "Es la primera vez que le envías a {nombre}. Por seguridad, escribe tu PIN en el teclado." |
| `HIGH_AMOUNT` | "Es un monto alto. Por seguridad, escribe tu PIN en el teclado." |
| `PIN_WRONG` | "PIN incorrecto. Te quedan {n} intentos." (con n=1: "PIN incorrecto. Te queda 1 intento.") |
| `PIN_ATTEMPTS_EXHAUSTED` | "No pude verificarte. No envié nada." |
| `PIN_LOCKED` | "Por seguridad, el PIN está bloqueado. No envié nada." |
| `PIN_INVALID_FORMAT` | "El PIN tiene entre 4 y 6 números. Escríbelo otra vez." |
| `REPLY_UNCLEAR_REJECTED` | "No pude confirmar tu respuesta. No envié nada." |

Reglas que se mantienen **[DECIDIDO]**:

(a) El motor nunca genera texto; las llaves `{…}` las inserta el orquestador con el `say` de Voz.
(b) Antes del "sí" solo se dice `receiveAmount` y nombre, nunca el costo (B-6 ratificado).
(c) El `say` de un turno de PIN no repite dígitos y `transcript` es `null` (B-7).
(d) Los montos se formatean con `format_amount` de `amount-parsing` (sin float) y la palabra de la
moneda sale de la configuración de Voz.

#### Tabla de la fase COMMAND

En fase `COMMAND` el motor SHALL decidir con esta tabla ordenada:

| # | Condición | Decision | Reason | Origen |
| --- | --- | --- | --- | --- |
| 1 | `intent.action == "CANCEL"` | `REJECT` | `CANCELLED_BY_USER` | catálogo `say` (`CANCELLED`) |
| 2 | `intent.status != "OK"`, o `intent.action == "UNKNOWN"`, o `intent.amountError != null`, o `intent.amount == null`, o `intent.recipient == null` | `REASK` | derivado por prioridad (ver notas) | SEG-3, SEG-4 |
| 2b | cortes de confianza activos y puntaje por debajo: primero `minIntentConfidence` vs `intentConfidence`, luego `minTranscriptConfidence` vs `transcriptConfidence` | `REASK` | `INTENT_LOW_CONFIDENCE` o `TRANSCRIPT_LOW_CONFIDENCE` | decisiones.md 3b; decisión con ML 1 (2026-10-16) |
| 3 | `resolution.kind == "NOT_FOUND"` | `REASK` | `RECIPIENT_NOT_FOUND` | SEG-4 |
| 4 | `resolution.kind == "CHOICE"` | `ASK_RECIPIENT` | `RECIPIENT_AMBIGUOUS` | SEG-4 |
| 5 | `hasBudgetGrant == false` (llega con `quote == null`) | `REQUIRE_AUTH` | `NO_BUDGET_GRANT` | SEG-1 |
| 6 | `pendingPayment` al mismo destinatario, `status: "PROCESSING"` y `now - pendingPayment.createdAt <= pendingWindowSeconds` | `REASK` (decidido con ML 1, 2026-10-16) | `PENDING_PAYMENT_SAME_RECIPIENT` | `turn-orchestration`; **[DECIDIDO 2026-10-16, con Frontend: PAYMENT_PENDING visible, PR #2]** — camino normal mientras el pago está en `PAYMENT_PENDING` |
| 6b | condición-marca: `pendingPayment` al mismo destinatario, `status: "PROCESSING"` y `now - pendingPayment.createdAt > pendingWindowSeconds` → marca `warnUnconfirmed = true` y SIGUE a 7/8/9 (no decide por sí sola; ver notas) | vía regla 9 o fase PIN | `PENDING_PAYMENT_UNCONFIRMED` | decisión de ML 2 (2026-10-16); falta comunicarlo a Pagos |
| 7 | `voice.status != "VERIFIED"` (texto, no enrolado o bajo el umbral) | `ASK_PIN` | `VOICE_NOT_VERIFIED` | SEG-6, D3 |
| 8 | `quote.exceedsRemaining == false` **y** (`contact.previouslyPaid == false` **o** monto ≥ `highAmountThreshold`) | `ASK_PIN` | `NEW_RECIPIENT` o `HIGH_AMOUNT` | SEG-6, D9 |
| 9 | resto | `ASK_CONFIRM` | `PENDING_PAYMENT_UNCONFIRMED` si `warnUnconfirmed`; si no `ALL_CHECKS_PASSED` | SEG-2, SEG-5 |

Notas:

- Regla 6: "mismo destinatario" se compara por wallet address resuelta, no por alias, y "siga
abierto" corresponde a `pendingPayment.status == "PROCESSING"` (decidido 2026-10-16 con ML 2, ML 1
y Pagos). **Decidido con ML 1 (2026-10-16): `REASK`**, con
`reason: PENDING_PAYMENT_SAME_RECIPIENT`. **[DECIDIDO 2026-10-16, con Frontend: PAYMENT_PENDING**
**visible, PR #2]** (revierte la opción A): el estado `PAYMENT_PENDING` SÍ se muestra a la usuaria,
con la frase "Tu envío está en camino. No hace falta repetirlo." (catálogo de Voz), con micrófono y
texto habilitados; el frontend envía en silencio un único turno de verificación (~20 s,
`kind=verify_pending`, B-2 ratificado) y el estado cambia cuando llega la respuesta (la wallet/Open
Payments resuelve si el pago se hizo o falló; lo que pasa después de esa verificación lo define
`payments-client` (Pagos), no este spec). La regla 6 vuelve a ser el **camino normal** mientras el
pago está en `PAYMENT_PENDING`: la usuaria puede hablar — dentro de `pendingWindowSeconds` (120 s)
un comando al mismo destinatario recibe `REASK`; pasada la ventana aplica la 6b. Sigue también como
defensa en profundidad (segunda pestaña, cliente que no bloquea, reintento de red).
- Regla 6b (aviso post-ventana) **[DECIDIDO por ML 2, 2026-10-16; falta comunicarlo a Pagos]**:
pasada la ventana, la regla 6b NO decide por sí sola — devolver `ASK_CONFIRM` aquí se saltaría el
PIN de las reglas 7 y 8, contra D3/SEG-6 (un comando por texto siempre pide PIN). Es una
**condición-marca**: si `pendingPayment` es al mismo destinatario (wallet), `status: "PROCESSING"`
y `now - createdAt > pendingWindowSeconds`, el motor marca `warnUnconfirmed = true` y SIGUE
evaluando 7, 8 y 9 con normalidad. Efecto: (a) en la regla 9 la decisión sigue siendo
`ASK_CONFIRM` pero con `reason: PENDING_PAYMENT_UNCONFIRMED` en lugar de `ALL_CHECKS_PASSED`;
(b) en fase `PIN`, `pin.result == "OK"` sigue siendo `ASK_CONFIRM` pero con
`reason: PENDING_PAYMENT_UNCONFIRMED` si la 6b se cumple (el orquestador mantiene
`pendingPayment` en el `context`) o `PIN_CORRECT` si no. Las reglas 7 (`VOICE_NOT_VERIFIED`) y 8
(`NEW_RECIPIENT`/`HIGH_AMOUNT`) mantienen su prioridad y su reason: piden PIN primero. Con
`warnUnconfirmed` y `exceedsRemaining == true` sigue siendo `ASK_CONFIRM` y el "sí" lleva a
`REQUIRE_AUTH` (SEG-5). Ante la advertencia, `NO` → `REJECT` con `USER_DECLINED`.
- Regla 8: si disparan a la vez destinatario nuevo y monto alto, el `reason` es `NEW_RECIPIENT`
(destinatario nuevo se evalúa primero dentro de la regla).
- Regla 2: el `reason` se deriva determinísticamente de los campos del `context`, con esta
prioridad de evaluación dentro de la regla: `intent.action == "UNKNOWN"` → `INTENT_UNKNOWN`;
`intent.amountError != null` → `AMOUNT_ERROR`; `intent.status == "AMBIGUOUS"` → `INTENT_AMBIGUOUS`;
`intent.amount == null` → `AMOUNT_MISSING`; `intent.recipient == null` → `RECIPIENT_MISSING`;
cualquier otro `intent.status != "OK"` → `INTENT_UNCLEAR`. La decisión es `REASK` en todos los
casos, y la prioridad NO depende del `status` cuando este es distinto de `OK`. Aclarado con ML 1
(2026-10-16; lo confirma su código `voz/h1-parser`): falta de monto o de destinatario llega con
`status: "UNCLEAR"`, `AMBIGUOUS` queda solo para varios montos o varios destinatarios, y
`UNKNOWN`/`CANCEL` pueden llegar con `status: "OK"`; el motor se guía por los campos del `context`.
- Regla 2b: los cortes viven en `config` (`minIntentConfidence`, `minTranscriptConfidence`,
`number | null`; `null` = desactivado, por defecto en H1). La regla evalúa primero la confianza de
la intención y luego la de la transcripción; con ambos cortes activos, un solo puntaje bajo basta
para `REASK`. Puntajes altos NO sustituyen la verificación de voz ni ningún otro chequeo.
- Regla 7 va antes que la 8 y la 9: con la voz no verificada se pide PIN **por identidad** (SEG-6),
incluso si `exceedsRemaining == true`; ese PIN no reemplaza la aprobación de la wallet de SEG-5.
- Regla 9 incluye el exceso de presupuesto: va a la wallet **sin PIN por monto** (SEG-5).
- `intent.status == "AMBIGUOUS"` significa varios montos o varios destinatarios dichos (ML 1 no
elige) y cae en la regla 2 con `reason: INTENT_AMBIGUOUS`; la ambigüedad de la **agenda** llega con
`status: "OK"` y `resolution.kind == "CHOICE"` y la resuelve la regla 4. Semántica decidida con
ML 1 (2026-10-16) **[DECIDIDO]**.
- `highAmountThreshold == null` desactiva el corte por monto: entonces solo dispara `ASK_PIN` la
regla 8 por `previouslyPaid == false` **[ESPERA EXPERIMENTOS]**: valor por defecto `null` hasta
X-2/X-4.

#### Tabla de la fase PIN

En fase `PIN` el motor SHALL decidir, en orden:

1. `pin.locked == true` → `REJECT` con `reason: PIN_LOCKED`.
2. `pin.result == "OK"` → `ASK_CONFIRM` con `reason: PENDING_PAYMENT_UNCONFIRMED` si la condición
6b se cumple (el orquestador mantiene el `pendingPayment` abierto y pasado el tope en el
`context`), o `PIN_CORRECT` si no: se evalúan solo las reglas de confirmación previas al "sí"; el
PIN se **suma** a la confirmación hablada, no la reemplaza (SEG-2). El PIN correcto no produce
`PAY` por sí solo.
3. `pin.result == "WRONG"` con `pin.sessionFailures < 3` → `ASK_PIN` con `reason: PIN_WRONG` (el
orquestador responde `AWAITING_PIN` con los intentos restantes en `say`).
4. `pin.result == "WRONG"` con `pin.sessionFailures >= 3` → `REJECT` con
`reason: PIN_ATTEMPTS_EXHAUSTED`.
5. `pin.result == "INVALID_FORMAT"` o `null` → `ASK_PIN` con `reason: PIN_INVALID_FORMAT` (no
consume intento; regla de cierre para que la fase nunca quede sin decisión).

En fase `PIN` el motor MUST NOT volver a evaluar la tabla de `COMMAND`: las reglas 1 a 6 ya pasaron
para llegar a `AWAITING_PIN` y el contexto del comando no cambia.

#### Tabla de la fase CONFIRMATION

En fase `CONFIRMATION` el motor SHALL decidir, en orden:

1. `reply == "YES"`: con `quote.exceedsRemaining == true` → `REQUIRE_AUTH` con
`reason: CONFIRMED_NEEDS_WALLET_AUTH` (grant puntual del exceso, SEG-5); si no → `PAY` con
`reason: CONFIRMED`.
2. `reply == "NO"` → `REJECT` con `reason: USER_DECLINED`.
3. `reply == "UNCLEAR"` con `unclearReplies == 0` → `ASK_CONFIRM` con
`reason: REPLY_UNCLEAR_ASK_AGAIN` (repregunta una vez).
4. `reply == "UNCLEAR"` con `unclearReplies >= 1` → `REJECT` con
`reason: REPLY_UNCLEAR_REJECTED` (SEG-2: lo que no es un "sí" claro es un "no").
5. `reply == null` se trata como `UNCLEAR` (reglas 3 y 4): la fase nunca queda sin decisión y nada
se paga sin un "sí" claro.

El motor MUST NOT verificar la voz del "sí": el `context` conserva la verificación del comando
(D4). El contador `unclearReplies` lo lleva el orquestador y se reinicia al entrar a
`AWAITING_CONFIRMATION` (decidido 2026-10-16 con ML 2, ML 1 y Pagos).

#### El motor no obedece al LLM

Ningún contenido del comando o de la respuesta produce por sí mismo un `PAY`: la única regla que
emite `PAY` exige fase `CONFIRMATION` y `reply == "YES"` (SEG-3).

#### El mapeo a TurnState no es del motor

El motor SHALL devolver solo el `{decision, reason}`. El orquestador mapea `decision` a `TurnState`
y ejecuta las llamadas a Node que correspondan (`turn-orchestration`): `REASK` →
`AWAITING_COMMAND`, `ASK_RECIPIENT` → `AWAITING_RECIPIENT_CHOICE`, `ASK_PIN` → `AWAITING_PIN`,
`ASK_CONFIRM` → `AWAITING_CONFIRMATION`, `REQUIRE_AUTH` → `AWAITING_AUTHORIZATION`, `PAY` → pago
con el cliente de Node (resultando en `COMPLETED`, `PAYMENT_PENDING` o `REJECTED`) y `REJECT` →
`REJECTED`. El orquestador SHALL usar `reason` como clave para elegir la plantilla de `say` del
catálogo (en español); el texto nunca lo genera el motor ni el LLM.

## Detalle de `pin-validation`

#### Contadores de intentos

El componente de PIN SHALL llevar los contadores (así lo exige `turn-orchestration`):

1. **Por sesión:** al tercer fallo en la misma sesión, el componente reporta
`sessionFailures >= 3`; el orquestador responde `REJECTED` y no paga (la decisión la emite el
motor en fase `PIN`).
2. **Global:** con 5 fallos seguidos en total (acumulados entre sesiones), el componente marca el
PIN bloqueado (`locked: true`) hasta que se corra el script de reinicio. Con el PIN bloqueado,
el componente MUST NOT validar más intentos.
3. Un PIN correcto reinicia el contador global de fallos.

**[DIFERIDO A H2]** decidido: en H1 el contador global vive en la memoria del proceso; en H1 un
reinicio del backend reinicia el contador global y el bloqueo por 5 fallos solo vale mientras el
proceso vive. Se persiste en H2.

#### Privacidad del PIN

El PIN MUST NOT decirse en voz alta, ni pasar por el LLM, el parser de montos, la extracción de
intención, el clasificador de respuestas ni Whisper. MUST NOT ir a logs ni a `error.message`, ni a
ninguna respuesta de error. MUST NOT salir del backend Python (ni a Node ni a servicios externos):
la validación ocurre dentro del componente de ML 2 en Python. En un turno de PIN, `transcript`
SHALL ser `null` y el `say` nunca contiene ni repite dígitos del PIN. Ante un PIN incorrecto, el
turno sigue en `AWAITING_PIN` con los intentos restantes en el `say`, sin códigos HTTP nuevos
(B-8). Los textos de las plantillas del PIN están **[DECIDIDOS]** (2026-10-16) en el requisito
"Plantillas de `say` por reason" del spec `decision-engine`: `PIN_WRONG` "PIN incorrecto. Te quedan
{n} intentos." (con n=1: "PIN incorrecto. Te queda 1 intento."), `PIN_ATTEMPTS_EXHAUSTED`
"No pude verificarte. No envié nada.", `PIN_LOCKED` "Por seguridad, el PIN está bloqueado. No envié
nada." y `PIN_INVALID_FORMAT` "El PIN tiene entre 4 y 6 números. Escríbelo otra vez."; su
implementación en el catálogo es de ML 1 (`api/voice`).

#### Interfaz del componente

El componente SHALL exponer `verify_pin(pin: str, session_id: str) -> PinResult` con
`PinResult = {result: "OK" | "WRONG" | "INVALID_FORMAT", sessionFailures: int, remaining: int, locked: bool}`
(interfaz decidida 2026-10-16 con ML 2, ML 1 y Pagos; sugerida en D5 **[DECIDIDO]**) y
`reset_pin_lock()` para el script de reinicio. El
resultado llega al motor vía `context.pin` (`result`, `sessionFailures`, `locked`); `remaining`
alimenta el `say` del orquestador. El motor MUST NOT validar el PIN ni acceder al hash.

## Puntos abiertos

### decision-engine
| Punto | Dueño / estado |
| --- | --- |
| `highAmountThreshold`: valor por defecto `null` (desactivado); se fija con la evidencia de los experimentos | **[ESPERA EXPERIMENTOS]** X-2/X-4 |
| Valores de `minIntentConfidence` y `minTranscriptConfidence` (la regla 2b está decidida; por defecto `null` = desactivado en H1; el corte de transcripción MUST ser más flexible que el de intención) | **[PARA DECIDIR]** — rol Voz, tras su batería |
| Voz agrega las 13 situaciones de `say` y cambia el texto de `PIN_KEYBOARD` | **[PENDIENTE de Voz]** — no bloquea al motor |

### pin-validation
| Punto | Dueño / estado |
| --- | --- |
| Alcance H2: persistir el contador global de fallos del PIN (en H1 vive en la memoria del proceso; un reinicio del backend lo reinicia y el bloqueo por 5 fallos solo vale mientras el proceso vive) | **[DIFERIDO A H2]** |
