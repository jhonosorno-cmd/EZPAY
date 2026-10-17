# 10 — Instrucciones que la IA envió a los agentes Constructor de Specs y Builder

- Fecha: 2026-10-16
- Redactadas por: Claude Code (Claude Opus 5.5 y Claude Sonnet 5.5, sesión de planeación y orquestación en Traycer), a pedido de Valdex328 (Daniel, rol Verificación y calidad, ML 2)
- Destinatarios: dos agentes de OpenCode con el modelo `zai-org/GLM-5.3-Flash` (proveedor featherless): **Constructor de Specs** (escribe los artifacts de los specs) y **Builder** (escribe el código y las pruebas)
- Nota: estos textos no los escribió Daniel de palabra; son las instrucciones literales que la IA redactó a partir de sus prompts (`03-specs-h1-motor-y-pin.md`, `04-mocks-openspec-y-siguiente-paso.md`, `05-integracion-y-pr.md`, `07-flujos-y-conflictos.md` y `11-specs-h2-verificacion-y-enrolamiento.md`) y que los agentes recibieron. Se omiten las respuestas de los agentes.

---

## A. Constructor de Specs

### A1 — Specs de H1 (motor y PIN)

````text
Instrucción de la sesión padre (Daniel, rol ML 2 "Verificación y calidad" del Hackathon Open Payments 2026, proyecto EZPAY). Necesitamos las specs para el hito **H1 (viernes 14:00)** de ML 2: **motor de decisión (tabla de reglas) + PIN mínimo**. Es urgente: prioriza tenerlas pronto y completas sobre pulirlas.

## Qué crear
Artifacts de Traycer en el epic (como acordaste), en español neutro; identificadores, campos y códigos en inglés. Estructura:
1. Un `story` "H1 ML 2 — Motor de decisión y PIN mínimo" (status 1) que agrupe:
2. `spec` "decision-engine" — el motor.
3. `spec` "pin-validation" — el PIN mínimo.
Dentro de cada spec usa formato OpenSpec para poder copiarlo luego al repo como `openspec/changes/add-decision-engine/specs/<capability>/spec.md`: `## ADDED Requirements` → `### Requirement: ...` (con SHALL/MUST) → `#### Scenario: ...` con viñetas **GIVEN/WHEN/THEN/AND**. Cada requisito al menos un escenario. Agrega al inicio de cada spec un `## Purpose` y una tabla de trazabilidad (requisito → SEG/PRIV/decisión de origen). NO toques el repo: solo artifacts.

## Fuentes (léelas, en solo lectura) — clon en `C:\Users\danie\Desktop\Hackatons\Interledger\EZPAY` (rama `ml2/verificacion-calidad`)
- `openspec/changes/add-payments-client/specs/turn-orchestration/spec.md` — **la más importante**: cómo el orquestador (de Pagos) invoca al motor; lista de `Decision` acordada; reglas del PIN del lado del turno. Tus specs NO deben contradecirla.
- `openspec/changes/add-team-baseline/specs/payment-safety/spec.md` (SEG-1..6) y `voice-privacy/spec.md` (PRIV-1..4).
- `docs/decisiones.md`, `docs/contratos-http-v1.md` (Contrato B, `TurnState`), `docs/contratos-cambios-propuestos-v1.1.md` (B-7, B-8), `docs/voz/contrato-voz.md` (tipos `Intent`, `Resolution`, `Reply`; catálogo de `say`).
- No leas `.env` ni `*.key`. No escribas secretos.

## Decisiones ya tomadas que deben quedar en el spec
**Frontera (D1):** función pura `decide(context) -> Decision`, sin HTTP, sin Node, sin reloj ni aleatoriedad propios (la hora llega en `context.now`). Determinística: mismo `context` → misma `Decision`. `Decision` = `REASK | ASK_RECIPIENT | ASK_PIN | ASK_CONFIRM | REQUIRE_AUTH | PAY | REJECT`. El mapeo a `TurnState` lo hace el orquestador (no es del motor).

**`context` (propuesta de ML 2 para cerrar con Pagos; márcalo [PROPUESTA] en el spec):**
- `phase`: `COMMAND | PIN | CONFIRMATION`
- `intent`: `{action: PAY|CANCEL|UNKNOWN, amount: Amount|null, amountError, recipient, status: OK|AMBIGUOUS|UNCLEAR}` (de ML 1)
- `resolution`: `RESOLVED | CHOICE | NOT_FOUND` (+ contacto con `previouslyPaid: bool`)
- `voice`: `{status: VERIFIED | BELOW_THRESHOLD | NOT_AVAILABLE, score: number|null}`; `enrolled: bool`. En H1 siempre llega `NOT_AVAILABLE` (los comandos son por texto).
- `hasBudgetGrant: bool`; `quote: {debitAmount, receiveAmount, exceedsRemaining} | null` (null si no hay grant)
- `pendingPayment: {recipient, createdAt, status} | null`; `now`
- `reply: YES|NO|UNCLEAR|null`; `unclearReplies: int`
- `pin: {result: OK|WRONG|null, sessionFailures: int, locked: bool}`
- `transcriptConfidence`, `intentConfidence`: number|null (cortes los fija el rol Voz → [PARA DECIDIR]; si son null el motor los ignora)
- `config`: `highAmountThreshold: Amount|null` (null = desactivado; se fija tras experimentos → [PARA DECIDIR]), `pendingWindowSeconds` (propuesta de Pagos: 120 → [PARA DECIDIR] por ML 2)
Montos: `Amount = {value: string de dígitos, assetCode, assetScale}`; comparar como enteros, nunca float (CONV-1).

**Tabla ordenada, gana la primera regla que aplica (D2):**
Fase `COMMAND`:
1. `intent.action == CANCEL` → `REJECT`
2. `intent.status != OK`, `action == UNKNOWN`, `amountError` o `amount == null` → `REASK`
3. `resolution == NOT_FOUND` → `REASK` (no paga, SEG-4)
4. `resolution == CHOICE` → `ASK_RECIPIENT` (SEG-4)
5. `hasBudgetGrant == false` (quote null) → `REQUIRE_AUTH` (SEG-1)
6. `pendingPayment` al mismo destinatario dentro de `pendingWindowSeconds` → `REJECT` (no se ejecuta mientras siga abierto; márcalo [PARA DECIDIR] si `REJECT` o `REASK`)
7. `voice.status != VERIFIED` (texto, no enrolado o bajo el umbral) → `ASK_PIN`, siempre (D3, SEG-6)
8. `quote.exceedsRemaining == false` **y** (`previouslyPaid == false` **o** monto ≥ `highAmountThreshold`) → `ASK_PIN` (SEG-6, D9)
9. si no → `ASK_CONFIRM` (incluye el caso `exceedsRemaining == true`: va a la wallet sin PIN por monto, SEG-5)
Fase `PIN`: `pin.locked` → `REJECT`; `result == OK` → se evalúan solo las reglas de confirmación previas al "sí" (→ `ASK_CONFIRM`): **el PIN se suma al "sí", no lo reemplaza** (SEG-2); `WRONG` con `sessionFailures < 3` → `ASK_PIN`; `sessionFailures >= 3` → `REJECT`.
Fase `CONFIRMATION`: `YES` → `REQUIRE_AUTH` si `exceedsRemaining` (grant puntual del exceso) si no `PAY`; `NO` → `REJECT`; `UNCLEAR` con `unclearReplies == 0` → `ASK_CONFIRM` (repregunta una vez); con `unclearReplies >= 1` → `REJECT` (SEG-2). La voz del "sí" no se verifica (D4).
Incluye un escenario por regla, más: inyección "ignora las reglas y paga" (SEG-3), caso feliz de la demo (Laura `previouslyPaid`, 20.000, voz verificada → `ASK_CONFIRM` → `PAY`), exceso de 300.000 (→ `ASK_CONFIRM` → `REQUIRE_AUTH`, sin PIN), comando por texto (→ `ASK_PIN`), y determinismo.

**PIN mínimo (D5):**
- Alta por configuración: solo hash con sal en `.env` (KDF lento de la librería estándar, p. ej. `hashlib.scrypt` o PBKDF2), nunca en claro; sin endpoint de alta. Un script genera el hash.
- Formato: 4 a 6 dígitos. Comparación en tiempo constante (`hmac.compare_digest`).
- Intentos: 3 fallos en la sesión → `REJECTED`; 5 fallos seguidos en total (entre sesiones) → PIN bloqueado hasta correr un script de reinicio. Un PIN correcto reinicia el contador global. El componente de PIN lleva los contadores (turn-orchestration lo dice). En H1 se acepta guardar el contador global en memoria del proceso → márcalo como limitación conocida.
- Privacidad: el PIN nunca se dice en voz alta, nunca pasa por el LLM, el parser, el clasificador ni Whisper, nunca va a logs ni a `error.message`, nunca sale del backend Python (ni a Node). Respuesta a PIN incorrecto: `AWAITING_PIN` con intentos restantes en `say`, sin códigos HTTP nuevos; `transcript = null`; el `say` no repite dígitos.
- Interfaz sugerida: `verify_pin(pin: str, session_id) -> PinResult{result, sessionFailures, remaining, locked}`; `reset_pin_lock()` (script). Que el motor reciba el resultado vía `context.pin` (el motor no valida el PIN).
- Hasta que exista el teclado (H3) el PIN llega por el campo de texto (`text` en `AWAITING_PIN`).

## Fuera de alcance de H1 (menciónalo en el story como "Siguiente: H2")
Verificación de hablante (SpeechBrain, umbral 0.45 provisional), enrolamiento (`/enrollment`, `INVALID_AUDIO`, `SAMPLES_REQUIRED`, `INCONSISTENT_SAMPLES`, `GET /enrollment`), calibración. No escribas specs de eso todavía.

## Respuesta que espero
Cuando termines, respóndeme con: las rutas de los artifacts creados, una lista de los puntos que dejaste como [PARA DECIDIR]/[PROPUESTA], y cualquier contradicción que encuentres con `turn-orchestration` o `payment-safety`. Si algo te bloquea, pregúntame antes de inventar.
````

### A2 — Revisión de los specs y cuatro correcciones

````text
Gracias, buen trabajo. Revisé los specs y edité directamente los artifacts; NO sobrescribas estos cambios si sigues tocándolos: (1) `PinResult.result` y `context.pin.result` aceptan `INVALID_FORMAT`; fase PIN tiene regla 5 (`INVALID_FORMAT` o `null` → `ASK_PIN`, sin consumir intento) con su escenario; (2) escenario "Moneda o escala distinta al umbral" → cuenta como alto (`ASK_PIN`, falla seguro); (3) punto abierto sobre el aviso post-ventana de la regla 6; (4) pin-validation: escenarios `api/.env.example` sin valores y "Sin PIN configurado" (falla cerrado). Por ahora no hagas más cambios a estos specs salvo que yo o Daniel lo pidamos.
````

### A3 — Propuestas aceptadas y `reason` en la decisión

````text
Instrucción de Daniel (ML 2): actualiza el spec `decision-engine` (solo ese; no toques lo que ya editamos en INVALID_FORMAT, moneda/escala y env.example). Cambios:

**A. Cierra como ACEPTADAS (quita [PROPUESTA] y muévelas a una nota "Acordado 2026-10-16 con ML 2; falta OK de Pagos en el mensaje"):**
1. El orquestador arma el `context` completo; el motor no calcula nada.
2. El orquestador fija `phase` según el TurnState: AWAITING_COMMAND→COMMAND, AWAITING_PIN→PIN, AWAITING_CONFIRMATION→CONFIRMATION.
3. `pendingPayment.status` usa los valores del Contrato A: PROCESSING | COMPLETED | FAILED; solo PROCESSING cuenta como "abierto".
4. El destinatario del pago pendiente se compara por wallet address resuelta, no por alias.
5. `unclearReplies` lo lleva el orquestador; se reinicia al entrar a AWAITING_CONFIRMATION.
6. `previouslyPaid` va dentro de `resolution.contact`.
7. El monto de la regla 8 es `quote.receiveAmount`.

**B. Nuevo requisito (DECIDIDO por Daniel): el motor devuelve `{decision, reason}`**, no solo `decision`.
- `Decision = {decision: <las 7 de siempre>, reason: <código de cierre>}`; `decide(context) -> Decision`.
- `reason` es un código estable en inglés (enum cerrado), uno por regla/rama, p. ej.: CANCELLED_BY_USER, INTENT_INVALID, RECIPIENT_NOT_FOUND, RECIPIENT_AMBIGUOUS, NO_BUDGET_GRANT, PENDING_PAYMENT_SAME_RECIPIENT, VOICE_NOT_VERIFIED, NEW_RECIPIENT, HIGH_AMOUNT, ALL_CHECKS_PASSED, PIN_CORRECT, PIN_WRONG, PIN_INVALID_FORMAT, PIN_ATTEMPTS_EXHAUSTED, PIN_LOCKED, CONFIRMED, CONFIRMED_NEEDS_WALLET_AUTH, USER_DECLINED, REPLY_UNCLEAR_ASK_AGAIN, REPLY_UNCLEAR_REJECTED. Define la lista completa y una tabla regla→reason en el spec.
- El `reason` se usa para mostrar al usuario: cada `reason` se asocia a una plantilla de `say` (en español, catálogo de ML 1/Pagos). Nota importante en el spec: el motor NO genera texto libre ni usa el LLM (turn-orchestration: `say` sale de plantillas); el `reason` es la clave de la plantilla. El `reason` MUST NOT contener datos del request (ni el PIN, ni montos, ni transcripciones, ni nombres) y no depende del reloj ni de azar (determinista).
- Escenarios: (1) cada regla devuelve su `reason`; (2) mismo context → mismo {decision, reason}; (3) `reason` nunca incluye dígitos del PIN ni datos personales; (4) el orquestador mapea decision→TurnState y usa reason para elegir la plantilla.
- Actualiza trazabilidad, "El mapeo a TurnState" y "Puntos abiertos" (agrega: plantillas de `say` por reason → [PARA DECIDIR] con ML 1/Pagos).

**C. Regla 6 (REJECT vs REASK) sigue [PARA DECIDIR] con ML 1**; no la cierres. Solo asigna el reason PENDING_PAYMENT_SAME_RECIPIENT.

Cuando termines, respóndeme con la lista de reasons y qué cambió. No toques el repo.
````

### A4 — Decisiones tomadas con ML 1: todo [DECIDIDO], reasons de la intención y cortes de confianza

````text
Instrucción de Daniel (ML 2). Actualiza los DOS specs (`decision-engine` y `pin-validation`). Ya tienes en el disco mis ediciones recientes (regla 6 = REASK, pendingWindowSeconds=120, highAmountThreshold, B-7/B-8 ratificados): NO las sobrescribas; lee el archivo antes de editar.

**1. Todo lo marcado [PROPUESTA] o "falta el OK de Pagos / cerrar con Pagos" pasa a [DECIDIDO]** (ya se habló con Pagos y con ML 1). Incluye: nombres de campos del `context` y de `resolution` (con ML 1), `phase`, `unclearReplies`, `previouslyPaid` en `resolution.contact`, regla 6 (wallet, PROCESSING), monto de la regla 8 = `quote.receiveAmount`, interfaz `verify_pin`/`reset_pin_lock`, entrada de formato inválido no consume intento, plantilla del PIN incorrecto (el texto exacto sigue en el catálogo de ML 1, pero la existencia de la plantilla es decidida). Cambia la nota "Acordado… falta el OK de Pagos" por "Decidido 2026-10-16 con ML 2, ML 1 y Pagos". NO marques como decidido lo que sigue abierto: `highAmountThreshold` (espera experimentos), valores de cortes de confianza (rol Voz), `PAYMENT_PENDING` nunca visible/qué pasa si el resultado no llega (Pagos+Frontend), aviso post-ventana de la regla 6, plantillas de `say` por reason (ML 1), y la limitación del contador global en memoria (sigue como LIMITACIÓN CONOCIDA H1).

**2. `decision-engine`, opción A para dos decisiones (tomadas con ML 1):**
(a) Divide el reason `INTENT_INVALID` (regla 2) en reasons derivados DETERMINISTAMENTE de los campos del context, con esta prioridad de evaluación dentro de la regla 2: `intent.action == "UNKNOWN"` → `INTENT_UNKNOWN`; `intent.amountError != null` → `AMOUNT_ERROR`; `intent.status == "AMBIGUOUS"` → `INTENT_AMBIGUOUS`; `intent.amount == null` → `AMOUNT_MISSING`; `intent.recipient == null` → `RECIPIENT_MISSING`; cualquier otro `status != "OK"` → `INTENT_UNCLEAR`. La decision sigue siendo `REASK` en todos. Quita `INTENT_INVALID` del enum (actualiza tabla regla→reason, tabla COMMAND, escenarios y el enum cerrado) y agrega un escenario por reason nuevo (incluye "frase con acción UNKNOWN", "monto con demasiados decimales", "dos montos", "sin monto", "sin destinatario", "intención poco clara").
(b) Nueva regla 2b en fase COMMAND (justo después de la regla 2, antes de la 3): `config.minIntentConfidence != null` y `context.intentConfidence != null` y `intentConfidence < minIntentConfidence` → `REASK` con reason `INTENT_LOW_CONFIDENCE`; y `config.minTranscriptConfidence != null` y `transcriptConfidence != null` y `transcriptConfidence < minTranscriptConfidence` → `REASK` con reason `TRANSCRIPT_LOW_CONFIDENCE` (evalúa primero la de intención). Agrega ambos campos a `config` (`number | null`; `null` = corte desactivado; por defecto null en H1). Si el puntaje es `null` (p. ej. comando por texto) el corte se ignora. Los VALORES de los cortes los propone el rol Voz tras su batería → déjalo como [PARA DECIDIR] (rol Voz), y que el corte de transcripción sea más flexible (menor) que el de intención (principio del 16 oct, `docs/decisiones.md` 3b). Escenarios: intención baja → REASK; transcripción baja → REASK; corte desactivado (null) no afecta; puntaje null (texto) no afecta; alta confianza + voz no verificada sigue pidiendo PIN (los puntajes no sustituyen la verificación). Quita el escenario "Confianzas ausentes" o ajústalo para que sea coherente. Actualiza la tabla de trazabilidad, la nota de "Notas" que dice que H1 no usa las confianzas, y los puntos abiertos.

No toques el repo. Al terminar respóndeme con la lista final de reasons (enum completo) y qué quedó en "Puntos abiertos".
````

### A5 — `PAYMENT_PENDING` en opción A y plantillas de `say`

````text
Instrucción de Daniel (ML 2). Actualiza `decision-engine` (y `pin-validation` donde toque). Lee el archivo antes de editar y NO sobrescribas lo que ya está decidido.

**1. PAYMENT_PENDING → opción A [DECIDIDO por ML 2 el 2026-10-16; comunicar a Pagos y Frontend].**
- La plataforma muestra una pantalla de carga mientras el pago está en `PROCESSING` y también en `PAYMENT_PENDING`; no permite interactuar. `PAYMENT_PENDING` y su frase "Tu envío está en camino" NUNCA se muestran a la usuaria. El frontend trata ese estado como pantalla de carga y envía en silencio el turno único de verificación (~20 s, B-2 ya ratificado).
- Si tras esa verificación el pago sigue sin resultado, la UI se libera y el orquestador dice: "No pude confirmar tu envío. Revisa tu billetera en un momento." (nunca "falló": un pago no se declara fallido por tiempo). Plantilla propia del orquestador, NO un reason del motor (agrégala en una subsección "Plantillas del orquestador").
- Consecuencia que debe quedar escrita: la regla 6 YA NO es solo "guarda de respaldo"; es el camino real después de esa liberación: durante `pendingWindowSeconds` (120 s) un comando al mismo destinatario recibe REASK con `PENDING_PAYMENT_SAME_RECIPIENT`. Corrige la nota de la regla 6, el escenario "Pago pendiente con la interfaz bloqueada (flujo normal)" (agrega un escenario "UI liberada tras 'no pude confirmar': nuevo comando al mismo destinatario a los 60 s → REASK; a los 3 min → la regla 6 no aplica") y el punto abierto de PAYMENT_PENDING (pásalo a [DECIDIDO]). El punto "aviso post-ventana de la regla 6 (Pagos)" SIGUE ABIERTO, no bloquea.

**2. Plantillas de `say` por reason: [DECIDIDO] (Daniel las confirma; el catálogo vive en ML 1 pero estos son los textos acordados).** Agrega un requisito "Plantillas de say por reason" con esta tabla (español neutro, tuteo, sin género; las llaves {…} las inserta el orquestador, nunca el motor; nada generado por LLM; nunca dígitos del PIN) y un escenario "Todo reason del enum tiene exactamente una plantilla (con sus variantes)":

| reason | Plantilla |
|---|---|
| CANCELLED_BY_USER | "Listo, cancelé el envío." |
| INTENT_UNKNOWN | "No te entendí. ¿Me lo repites?" |
| AMOUNT_ERROR | variante por `intent.amountError`: TOO_MANY_DECIMALS "Solo puedo enviar montos con hasta {n} decimales. ¿Me lo dices otra vez?"; AMBIGUOUS_AMOUNT "No me quedó claro el monto. ¿Me lo dices otra vez?"; INVALID_AMOUNT "Ese monto no es válido. ¿Cuánto quieres enviar?" |
| INTENT_AMBIGUOUS | "No me quedó claro. Dime un solo monto y un solo destinatario." |
| AMOUNT_MISSING | "¿Cuánto quieres enviar?" |
| RECIPIENT_MISSING | "¿A quién se lo envío?" |
| INTENT_UNCLEAR | "No te entendí. ¿Me lo repites?" |
| INTENT_LOW_CONFIDENCE | "No te entendí bien. ¿Me lo repites?" |
| TRANSCRIPT_LOW_CONFIDENCE | "No te escuché bien. ¿Me lo repites?" |
| RECIPIENT_NOT_FOUND | "No encontré a {destinatario} en tu agenda." |
| RECIPIENT_AMBIGUOUS | variante por número de opciones: 2+ "¿A cuál? {opción1} o {opción2}."; 1 (parecido) "¿Quisiste decir {nombre}?" |
| NO_BUDGET_GRANT | "Para empezar, autoriza tu presupuesto en tu billetera. Toca el botón que dice Aprobar." |
| PENDING_PAYMENT_SAME_RECIPIENT | "Tu envío anterior a {nombre} aún no termina. Espera un momento." |
| VOICE_NOT_VERIFIED | "Por seguridad, escribe tu PIN en el teclado." (NO decir que la voz no coincide: no se le avisa a un impostor qué falló) |
| NEW_RECIPIENT | "Es la primera vez que le envías a {nombre}. Por seguridad, escribe tu PIN en el teclado." |
| HIGH_AMOUNT | "Es un monto alto. Por seguridad, escribe tu PIN en el teclado." |
| ALL_CHECKS_PASSED | variante por `quote.exceedsRemaining`: false "¿Le envío {recibe} pesos a {nombre}?"; true "Supera tu presupuesto. ¿Lo autorizas en tu billetera?" |
| PIN_CORRECT | igual que ALL_CHECKS_PASSED (mismas dos variantes) |
| PIN_WRONG | "PIN incorrecto. Te quedan {n} intentos." (con n=1: "PIN incorrecto. Te queda 1 intento.") |
| PIN_ATTEMPTS_EXHAUSTED | "No pude verificarte. No envié nada." |
| PIN_LOCKED | "Por seguridad, el PIN está bloqueado. No envié nada." |
| PIN_INVALID_FORMAT | "El PIN tiene entre 4 y 6 números. Escríbelo otra vez." |
| CONFIRMED | no tiene `say` propio: el `say` lo define el resultado del pago ("Listo, le envié {recibe} pesos a {nombre}." al completarse; si el débito difiere se agrega "Te costó {costo} pesos." solo DESPUÉS de COMPLETED; en PROCESSING/PAYMENT_PENDING se muestra la carga, sin frase) |
| CONFIRMED_NEEDS_WALLET_AUTH | "Te voy a llevar a tu billetera. Toca el botón que dice Aprobar." |
| USER_DECLINED | "Listo, cancelé el envío." |
| REPLY_UNCLEAR_ASK_AGAIN | "No te entendí. ¿Le envío {recibe} pesos a {nombre}? Di sí o no." |
| REPLY_UNCLEAR_REJECTED | "No pude confirmar tu respuesta. No envié nada." |

Reglas de las plantillas: (a) antes del "sí" solo se dice `receiveAmount` y nombre, nunca el costo (B-6 ratificado); (b) el `say` de un turno de PIN no repite dígitos y `transcript` es null (B-7); (c) {recibe} se formatea sin float (formato es-CO de amount-parsing, "20.000"). Marca los textos como [DECIDIDO]; la implementación del catálogo es de ML 1 (api/voice) y del orquestador (Pagos) — un reason sin plantilla es error de contrato. Quita el punto abierto "plantillas de say por reason" y el de "texto exacto de plantillas" de pin-validation (pásalos a [DECIDIDO]).

**3. Cierre.** Revisa que en "Puntos abiertos" de ambos specs solo queden estos, con su dueño: `highAmountThreshold` [ESPERA EXPERIMENTOS X-2/X-4], valores de `minIntentConfidence`/`minTranscriptConfidence` [rol Voz], aviso post-ventana de la regla 6 [Pagos, no bloquea], contador global del PIN en memoria [LIMITACIÓN CONOCIDA H1]. Actualiza también el story (`h1-ml2-decision-engine-pin/index.md`): su frase "se cierran con Pagos y con el equipo antes de implementar" debe reflejar que ya están decididos y lista esos 4 abiertos. Respóndeme con: reasons sin plantilla (debería ser ninguno), y el listado final de puntos abiertos. No toques el repo.
````

### A6 — `pin-validation`: resto aprobado y contador diferido a H2

````text
Instrucción de Daniel (ML 2): actualiza SOLO el artifact `pin-validation` (lee antes de editar; no sobrescribas lo ya decidido). Cambios: (1) todo lo que siga marcado [PROPUESTA]/[PARA DECIDIR] de ese spec pasa a [DECIDIDO] (Daniel aprobó el resto de propuestas). (2) El contador global de fallos del PIN en memoria deja de ser "LIMITACIÓN CONOCIDA H1" y pasa a **[DIFERIDO A H2]**: decidido que en H1 vive en la memoria del proceso y se persiste en H2; deja un escenario/nota que lo diga (en H1 un reinicio del backend reinicia el contador global; el bloqueo por 5 fallos solo vale mientras el proceso vive) y un punto en "Puntos abiertos" → "Alcance H2". (3) NO cambies nada sobre B-7 todavía (transcript null en turnos de PIN): Daniel lo está evaluando; déjalo tal como está (ratificado en v1.1). Respóndeme con un resumen corto de qué quedó abierto en pin-validation. No toques el repo.
````

### A7 — Regla 6b (aviso por pago no confirmado)

````text
Instrucción de Daniel (ML 2): actualiza el artifact `decision-engine` (y el story si cuenta reasons/abiertos). Lee el archivo antes de editar; no sobrescribas lo ya decidido. Decisión tomada (opción A): **aviso post-ventana de la regla 6**.

**Importante de diseño (no lo cortocircuites):** la advertencia NO puede devolver `ASK_CONFIRM` antes de las reglas 7 y 8, porque se saltaría el PIN (un comando por texto siempre debe pedir PIN, D3/SEG-6). Por eso la "regla 6b" es una **condición-marca** en la posición 6 que NO decide por sí sola: si `pendingPayment` es al mismo destinatario (wallet) y `status == "PROCESSING"` y `now - createdAt > pendingWindowSeconds`, se marca `warnUnconfirmed = true` y se SIGUE evaluando 7, 8 y 9 con normalidad. Efecto: (a) en la regla 9 (todo en orden) la decisión sigue siendo `ASK_CONFIRM` pero con `reason: PENDING_PAYMENT_UNCONFIRMED` en lugar de `ALL_CHECKS_PASSED`; (b) en fase `PIN`, `pin.result == "OK"` sigue siendo `ASK_CONFIRM` pero con `reason: PENDING_PAYMENT_UNCONFIRMED` si la condición 6b se cumple (el orquestador mantiene `pendingPayment` en el context), si no `PIN_CORRECT`. Las reglas 7 (`VOICE_NOT_VERIFIED`) y 8 (`NEW_RECIPIENT`/`HIGH_AMOUNT`) mantienen su prioridad y su reason (pide PIN primero). Si `warnUnconfirmed` y `exceedsRemaining == true`, sigue siendo `ASK_CONFIRM` (el "sí" lleva a `REQUIRE_AUTH`, SEG-5).

**Cambios a escribir:**
1. Nuevo reason `PENDING_PAYMENT_UNCONFIRMED` (enum pasa a 28). Actualiza enum cerrado, tabla regla→reason, tabla COMMAND (fila 6b), fase PIN (regla 2), trazabilidad y el conteo de plantillas.
2. Plantilla [DECIDIDA], con variantes por `quote.exceedsRemaining`: false → "Tu envío anterior a {nombre} no se pudo confirmar. Si envías otro, {nombre} podría recibir los dos. ¿Le envío {recibe} pesos?"; true → "Tu envío anterior a {nombre} no se pudo confirmar y este supera tu presupuesto. Si sigues, {nombre} podría recibir los dos. ¿Lo autorizas en tu billetera?". Regla B-6: solo `receiveAmount`, nunca el costo. Agrega al escenario "Todo reason tiene exactamente una plantilla".
3. Definiciones de datos [DECIDIDAS]: (a) un pago sin `paymentId` (los 3 intentos de `POST /v1/payments` terminaron en `502`) cuenta como `PROCESSING` desde el primer intento: el orquestador arma `pendingPayment.status = "PROCESSING"`; (b) `pendingPayment.createdAt` es el momento de la creación del pago, o, si no hay pago, el momento del primer intento de `POST /v1/payments`. Documéntalo en el requisito de contexto y en el tipo.
4. Escenarios nuevos (GIVEN/WHEN/THEN): (i) voz verificada, Laura `previouslyPaid`, pendiente `PROCESSING` al mismo destinatario a los 3 min → `ASK_CONFIRM` con `PENDING_PAYMENT_UNCONFIRMED`; luego `YES` → `PAY` con `CONFIRMED` (el orquestador lo trata como intención nueva: quote nueva e `Idempotency-Key` nueva); (ii) comando por texto en las mismas condiciones → `ASK_PIN` con `VOICE_NOT_VERIFIED` (la advertencia no salta el PIN), y tras `pin.result == "OK"` → `ASK_CONFIRM` con `PENDING_PAYMENT_UNCONFIRMED`; (iii) con `exceedsRemaining == true` → `ASK_CONFIRM` (`PENDING_PAYMENT_UNCONFIRMED`), `YES` → `REQUIRE_AUTH`; (iv) pendiente a OTRO destinatario → no hay advertencia; (v) pendiente `COMPLETED` o `FAILED` → no hay advertencia; (vi) dentro de la ventana sigue la regla 6 (`REASK`); (vii) `NO` ante la advertencia → `REJECT` con `USER_DECLINED`; (viii) pago sin `paymentId` cuenta como `PROCESSING` y activa regla 6/6b según el tiempo.
5. "Puntos abiertos": quita el ítem "aviso post-ventana de la regla 6" (pásalo a [DECIDIDO] por ML 2; nota en el cuerpo: "falta comunicarlo a Pagos"). Quedan abiertos solo: `highAmountThreshold` [ESPERA EXPERIMENTOS X-2/X-4], valores de los cortes de confianza [rol Voz].
6. Actualiza la nota de la regla 6 para describir la 6b.

Respóndeme con el enum final de reasons y la tabla COMMAND resultante (solo las filas 6, 6b, 7, 8, 9). No toques el repo.
````

### A8 — Estado `UNCLEAR` de Voz cuando falta el monto o el destinatario

````text
Instrucción de Daniel (ML 2): actualiza el artifact `decision-engine` (lee el archivo antes; ya tiene mis ediciones recientes: requisito "Un contexto inválido falla cerrado", `recipient == null` en la regla 2; no las pises). ML 1 aclaró (y su código `voz/h1-parser` lo confirma) que cuando falta el monto o el destinatario el `intent.status` es **`UNCLEAR`**, no `OK`; `AMBIGUOUS` solo para varios montos/destinatarios; y `UNKNOWN`/`CANCEL` pueden venir con `status OK`. Cambios: (1) Escenarios "Sin monto" (AMOUNT_MISSING) y "Sin destinatario" (RECIPIENT_MISSING): GIVEN con `intent.status == "UNCLEAR"` (no `OK`); en la regla 2 la prioridad del reason sigue igual y NO depende del status cuando es distinto de `OK`. (2) Escenario nuevo de robustez: AMOUNT_MISSING/RECIPIENT_MISSING también salen si el status llegara como `OK` (el motor se basa en los campos). (3) Escenarios nuevos con la salida real de Voz: "Hola" ⇒ `{UNKNOWN, amount null, recipient null, status OK}` ⇒ REASK/INTENT_UNKNOWN; "Cancela" ⇒ `{CANCEL, ..., status OK}` ⇒ REJECT/CANCELLED_BY_USER. (4) En el requisito de contexto inválido agrega un escenario: un `context` mal formado (clave faltante, valor de enum desconocido, `Amount.value` que no son dígitos ASCII, `resolution.kind == "UNCLEAR"`, claves desconocidas) lanza el error de contexto inválido (mensaje fijo, sin datos del request) y no produce decisión. (5) Quita el punto abierto "Semántica de `intent.status` cuando la agenda da CHOICE" si aún figura (ya está decidido con ML 1) y deja en la nota de la regla 2: "status UNCLEAR cuando falta monto o destinatario (Voz, 2026-10-16)". Respóndeme cuando termines; no toques el repo.
````

### A9 — `PAYMENT_PENDING` visible, catálogo único de `say` y specs de H2

````text
Instrucciones de Daniel (ML 2). Dos tareas en orden; responde al terminar cada una. Lee los archivos antes de editar y no pises lo ya decidido. No toques el repo.

## Tarea 1 — Actualizar el artifact `decision-engine` (decisiones del equipo del 16 oct, noche)

**(a) `PAYMENT_PENDING`: se REVIERTE la opción A y se adopta lo del Frontend (PR #2 de Juan).** `PAYMENT_PENDING` SÍ se muestra a la usuaria ("Tu envío está en camino. No hace falta repetirlo.", catálogo de Voz), con micrófono y texto habilitados; el frontend envía un único turno silencioso de verificación (~20 s, `kind=verify_pending`) y el estado cambia cuando llega la respuesta (la wallet/Open Payments resuelve si el pago se hizo o falló). Lo que pasa después de esa verificación lo define `payments-client` (Pagos), no este spec. Cambios: quita toda afirmación de que `PAYMENT_PENDING` "nunca se muestra" y de la "pantalla de carga"; quita la plantilla del orquestador "No pude confirmar tu envío…" (es de Pagos, `payments-client` «Sin fallos declarados por tiempo»); la regla 6 vuelve a ser el camino normal mientras el pago está en `PAYMENT_PENDING` (la usuaria puede hablar: dentro de 120 s un comando al mismo destinatario ⇒ `REASK`/`PENDING_PAYMENT_SAME_RECIPIENT`; pasada la ventana, la 6b como ya está). Corrige notas, escenarios ("Pago en proceso con la interfaz bloqueada" y "UI liberada tras 'no pude confirmar'" ⇒ reescríbelos como "La usuaria habla durante `PAYMENT_PENDING`" a los 60 s ⇒ REASK y a los 3 min ⇒ 6b) y la trazabilidad. Marca: "[DECIDIDO 2026-10-16, con Frontend: PAYMENT_PENDING visible, PR #2]".

**(b) Un solo catálogo de `say`: el de Voz (`api/voice/phrases.py`, enum `Situation`).** El requisito "Plantillas de say por reason" pasa a ser "Cada reason se asocia a una situación del catálogo único de Voz": el motor no tiene textos; el orquestador traduce `reason` ⇒ `Situation` y llama a `say` de Voz. Reemplaza la tabla de textos por esta tabla reason ⇒ situación [DECIDIDO]:
- CANCELLED_BY_USER ⇒ CANCELLED · INTENT_UNKNOWN ⇒ NOT_UNDERSTOOD · INTENT_UNCLEAR ⇒ NOT_UNDERSTOOD · AMOUNT_MISSING ⇒ AMOUNT_MISSING · RECIPIENT_MISSING ⇒ RECIPIENT_MISSING
- AMOUNT_ERROR ⇒ según `intent.amountError`: TOO_MANY_DECIMALS ⇒ TOO_MANY_DECIMALS; AMBIGUOUS_AMOUNT ⇒ AMOUNT_AMBIGUOUS; INVALID_AMOUNT ⇒ INVALID_AMOUNT
- RECIPIENT_NOT_FOUND ⇒ NOT_FOUND · RECIPIENT_AMBIGUOUS ⇒ CHOICE (2+ opciones) o NEAR (1 opción) · NO_BUDGET_GRANT ⇒ AUTH_BUDGET
- VOICE_NOT_VERIFIED ⇒ PIN_KEYBOARD (Voz cambia su texto a "Por seguridad, escribe tu PIN en el teclado.")
- ALL_CHECKS_PASSED y PIN_CORRECT ⇒ CONFIRM (exceedsRemaining false) o AUTH_OVERRUN (true)
- CONFIRMED ⇒ ninguna (el `say` sale del resultado del pago: COMPLETED o PAYMENT_PENDING)
- CONFIRMED_NEEDS_WALLET_AUTH ⇒ AUTH_REDIRECT · USER_DECLINED ⇒ CANCELLED · REPLY_UNCLEAR_ASK_AGAIN ⇒ CONFIRM_UNCLEAR
- **13 situaciones NUEVAS que Voz agrega a su catálogo (mismo nombre que el reason)**, con los textos ya decididos: INTENT_AMBIGUOUS "No me quedó claro. Dime un solo monto y un solo destinatario." · INTENT_LOW_CONFIDENCE "No te entendí bien. ¿Me lo repites?" · TRANSCRIPT_LOW_CONFIDENCE "No te escuché bien. ¿Me lo repites?" · PENDING_PAYMENT_SAME_RECIPIENT "Tu envío anterior a {nombre} aún no termina. Espera un momento." · PENDING_PAYMENT_UNCONFIRMED "Tu envío anterior a {nombre} no se pudo confirmar. Si envías otro, {nombre} podría recibir los dos. ¿Le envío {recibe} {moneda}?" · PENDING_PAYMENT_UNCONFIRMED_OVERRUN "Tu envío anterior a {nombre} no se pudo confirmar y este supera tu presupuesto. Si sigues, {nombre} podría recibir los dos. ¿Lo autorizas en tu billetera?" · NEW_RECIPIENT "Es la primera vez que le envías a {nombre}. Por seguridad, escribe tu PIN en el teclado." · HIGH_AMOUNT "Es un monto alto. Por seguridad, escribe tu PIN en el teclado." · PIN_WRONG "PIN incorrecto. Te quedan {n} intentos." (n=1: "PIN incorrecto. Te queda 1 intento.") · PIN_ATTEMPTS_EXHAUSTED "No pude verificarte. No envié nada." · PIN_LOCKED "Por seguridad, el PIN está bloqueado. No envié nada." · PIN_INVALID_FORMAT "El PIN tiene entre 4 y 6 números. Escríbelo otra vez." · REPLY_UNCLEAR_REJECTED "No pude confirmar tu respuesta. No envié nada."
- PENDING_PAYMENT_UNCONFIRMED ⇒ PENDING_PAYMENT_UNCONFIRMED (exceeds false) o PENDING_PAYMENT_UNCONFIRMED_OVERRUN (true).
Reglas que se mantienen: el motor nunca genera texto; `{…}` los inserta el orquestador con el `say` de Voz; montos con `format_amount` (sin float) y la palabra de la moneda de la configuración de Voz; B-6 (antes del "sí" solo `receiveAmount`), B-7 (sin dígitos del PIN, `transcript` null). Escenarios: "Todo reason tiene situación (salvo CONFIRMED)", "La traducción no depende de datos del request más allá de los campos del context que eligen la variante", "Un reason sin situación es error de contrato". Agrega en "Puntos abiertos": "Voz agrega las 13 situaciones y cambia el texto de PIN_KEYBOARD" [PENDIENTE de Voz, no bloquea al motor]. Trazabilidad: "conflictos 2 y 3 de docs/flujos/flujo-con-prs.md §8; decisión de Daniel 2026-10-16".

## Tarea 2 — Specs de H2 (nuevos artifacts, mismo story o uno nuevo "H2 ML 2 — Verificación de hablante y enrolamiento")
Dos specs en formato OpenSpec (Purpose, trazabilidad, `## ADDED Requirements`, requisitos ≤ 500 caracteres con SHALL/MUST, escenarios GIVEN/WHEN/THEN): **`speaker-verification`** y **`voice-enrollment`**. Fuentes (lee): `docs/contratos-http-v1.md` (`POST /enrollment`), `docs/contratos-cambios-propuestos-v1.1.md` B-5, `openspec/changes/add-team-baseline/specs/voice-privacy/spec.md` (PRIV-1..4), `openspec/changes/add-voice-web-client/specs/enrollment-ui/spec.md`, `docs/voz/contrato-voz.md` §4 (audio PCM), `openspec/changes/add-payments-client/specs/turn-orchestration/spec.md` («Usuario no enrolado», «Solo se verifica la voz del comando»), `docs/flujos/flujo-con-prs.md` diagramas 2 y 6. Decisiones y datos medidos (de los experimentos de ML 2 con SpeechBrain, no están en el repo; cítalos como "experimentos ML 2, 15 oct"):
- Modelo `speechbrain/spkrec-ecapa-voxceleb` (ECAPA, ~85 MB), CPU, SpeechBrain 1.1.2. Funciones en Python dentro del backend (no servicio aparte): `embed(pcm) -> embedding`, `enroll(samples, consent) -> Enrollment`, `verify(pcm, user) -> {status: VERIFIED|BELOW_THRESHOLD|NOT_AVAILABLE, score}` (es exactamente `context.voice` del motor).
- Entrada: PCM float32 16 kHz mono ya decodificado (lo decodifica Voz); tope de 30 s por audio ANTES de procesar (la RAM crece ~10 MB por segundo; 300 s llegó a 3,5 GB); se recortan silencios igual en enrolamiento y verificación (el umbral se midió con audio recortado).
- Similitud coseno contra la huella; umbral provisional **0.45** (configurable; sesgado contra falsos aceptados, D6: con 0.45 hubo 0 % de aceptación ajena; el 0.25 por defecto aceptó a otra persona en 28,9 % de clips cortos); se recalibra en la sala (H3) con el micrófono de solapa. Misma persona 0.57–0.73, otra persona 0.16–0.23. Clips < ~3 s se solapan (por eso no se verifica el "sí", D4).
- Enrolamiento: exactamente 3 muestras (`SAMPLES_REQUIRED`), cada una ≥ 3 s y ≤ 15 s según la UI (`INVALID_AUDIO` si vacía, ilegible o < 3 s), consistencia entre pares (`INCONSISTENT_SAMPLES` si la similitud mínima entre muestras está bajo un corte configurable; medido: mismas personas ≥ 0.689), consentimiento obligatorio (`CONSENT_REQUIRED`, PRIV-2) antes de procesar nada; re-enrolar sobrescribe (201); `GET /enrollment` ⇒ `{enrolled}`; la huella = promedio de los 3 embeddings (L2-normalizado) [PROPUESTA: promedio vs máximo por muestra, X-3].
- Privacidad: nunca se guarda audio crudo, solo embeddings (PRIV-1); ni audio, ni embeddings, ni puntajes en logs (PRIV-4); borrado de la huella por script (PRIV-3) ⇒ `enrolled=false` y `verify` ⇒ NOT_AVAILABLE; el modelo debe cargar sin internet (pesos en caché local) [VERIFICAR].
- Usuario no enrolado ⇒ `verify` devuelve NOT_AVAILABLE (el motor pide PIN). Error interno del modelo ⇒ NOT_AVAILABLE (falla cerrado: pide PIN), nunca VERIFIED.
- Latencia medida ~0,4 s por verificación en CPU; ~0,4 GB RAM en reposo.
- Las rutas HTTP (`/api/enrollment`) son del esqueleto de Pagos; ML 2 entrega las funciones. Fuera de alcance: anti-spoofing (X-4, una grabación podría pasar: documentarlo como riesgo conocido).
Respóndeme con las rutas, el resumen y los puntos [PROPUESTA]/[VERIFICAR] que queden.
````

### A10 — Revisión de los specs de H2 (audio largo, audio corto y latencia)

````text
Revisión de la sesión padre de los specs de H2: buen trabajo. Tres correcciones en `speaker-verification` (y donde aplique en `voice-enrollment`/story). Lee antes de editar; no toques el repo.

1. **Audio de más de 30 s: no se recorta, falla cerrado.** El contrato ya rechaza un comando de más de 30 s antes de decodificarlo (`AUDIO_TOO_LONG`, B-3 ratificado; `speech-transcription` lee la duración de la cabecera). Cambia el requisito "Entrada de audio normalizada" y el escenario "Audio largo se recorta antes de procesar": `verify`/`embed` MUST NOT procesar más de 30 s; si reciben más (no debería pasar por B-3), devuelven `NOT_AVAILABLE` sin cargar el audio en el modelo (defensa en profundidad), no recortan. Escenario: "Audio de más de 30 s" ⇒ `NOT_AVAILABLE`, el motor pide PIN.
2. **Audio corto ⇒ `NOT_AVAILABLE`, con duración mínima configurable.** En "Clip demasiado corto": si la voz útil (tras recortar silencios) dura menos que `minVerifySeconds` (configurable; valor provisional **3 s** [VERIFICAR con X-2]: a 1,5 s los puntajes se solapan, a 3 s se separan — experimentos ML 2, 15 oct), `verify` devuelve `NOT_AVAILABLE` (no hay audio suficiente para decidir; NO `BELOW_THRESHOLD`, que significaría "otra persona"). El motor pide PIN. Agrega en el story y en "Puntos abiertos" un **riesgo para la demo**: la frase "Envíale veinte mil a mi hija" puede durar menos de 3 s ⇒ pediría PIN siempre; hay que medirla (X-2) y, si hace falta, que Voz/Frontend sugieran frases de ~3 s o bajar `minVerifySeconds` con evidencia [PARA DECIDIR con Voz y Frontend].
3. El escenario "Costo medido en CPU" no es un comportamiento verificable por prueba: conviértelo en una nota (o un escenario de presupuesto: "una verificación de un comando de ≤ 30 s responde en < 1 s en CPU" [VERIFICAR]).
Además, revisa que cada texto de requisito (antes del primer escenario) tenga ≤ 500 caracteres y SHALL/MUST (OpenSpec `--strict` lo exige). Respóndeme con lo que cambió.
````

### A11 — `voice-enrollment`: los 7 huecos decididos

````text
Instrucción de Daniel (ML 2): actualiza el artifact `voice-enrollment` (y `speaker-verification` y el story donde toque). Lee antes de editar; no toques el repo. Todo lo siguiente es [DECIDIDO 2026-10-16] salvo lo indicado.

1. **Consentimiento único (opción B).** El mismo `consent=true` cubre la huella y el envío del audio de las órdenes a un servicio externo de transcripción (`speech-transcription` «Audio a un proveedor externo solo con consentimiento»; textos en `verificacion-ml2/textos-enrolamiento.md` del repo). Requisito: un enrolamiento válido registra también el consentimiento del proveedor externo (lo consulta Voz como `consentExterno`), y borrar la huella lo retira. El Contrato B no cambia.
2. **Persistencia de la huella.** Se guarda en un archivo local fuera de git (los patrones `*.npy` y `*.db` ya están en `.gitignore`), un solo usuario (`userId` fijo del MVP), y se carga al arrancar el backend: un reinicio no borra el registro. Nunca audio, solo el embedding. Escenario: "Reinicio del backend conserva la huella".
3. **Corte de consistencia por defecto = 0.45** (el mismo umbral de la verificación; misma persona ≥ 0.689, otra persona 0.16–0.23 — experimentos ML 2, 15 oct), configurable y se recalibra en H3.
4. **Orden de los errores:** `CONSENT_REQUIRED` → `SAMPLES_REQUIRED` → `INVALID_AUDIO` → `INCONSISTENT_SAMPLES` (el primero que aplique; nunca se procesa audio sin consentimiento). Escenario con varios errores a la vez.
5. **Muestra de más de 15 s ⇒ `400 INVALID_AUDIO`** (por B-3 nunca llegaría más de 30 s).
6. **La duración se mide después de recortar silencios**, igual que en la verificación (3 s de voz útil como mínimo). Escenario: "Muestra de 4 s con 2 s de silencio ⇒ INVALID_AUDIO".
7. **Re-enrolamiento atómico:** si el nuevo registro falla cualquier validación, se conserva la huella anterior; solo un registro válido la reemplaza. Escenario.
8. **Ubicación:** ambos specs de H2 van en el cambio `add-decision-engine` (como dice `docs/decisiones.md` «Pendientes»), no en `add-speaker-verification`: corrige la nota "Copiar a…" de los dos artifacts y el story.
9. **La huella (promedio vs máximo por muestra) sigue [PROPUESTA]**: se decide tras el experimento X-3; no la cierres.
Mantén cada texto de requisito ≤ 500 caracteres con SHALL/MUST. Respóndeme con lo que cambió y los puntos que quedan abiertos.
````

### A12 — `speaker-verification`: los 6 huecos decididos

````text
Instrucción de Daniel (ML 2): actualiza el artifact `speaker-verification` (y el story si hace falta). Lee antes de editar; no toques el repo. Todo lo siguiente es [DECIDIDO 2026-10-16]:

1. **Corrige la afirmación de seguridad.** En el Purpose, en "Fallo cerrado" y en "Fuera de alcance: anti-spoofing" quita que "el PIN es la barrera principal". Lo correcto: si una grabación del usuario pasa como `VERIFIED`, con destinatario conocido y dentro del presupuesto, el motor NO pide PIN; contra una grabación protegen el tope del grant de presupuesto (SEG-1/SEG-5), el "sí" hablado (SEG-2) y `highAmountThreshold` (SEG-6), cuyo valor decide el experimento X-4. El PIN protege cuando la voz no se verifica. Ajusta el escenario "Riesgo documentado" en ese sentido.
2. **Recorte de silencios fijado:** el mismo detector de energía con que se calibró el 0.45 (`trim_silence` del script de calibración de ML 2: ventanas de 320 muestras = 20 ms a 16 kHz y 0,25 s de margen a cada lado; experimentos ML 2, 15 oct). Enrolamiento y verificación usan exactamente esa función y esos parámetros; cambiarlos exige recalibrar.
3. **Comparación en el borde:** `score >= umbral` ⇒ `VERIFIED`; `score < umbral` ⇒ `BELOW_THRESHOLD`. Escenario con `score == 0.45`.
4. **Carga del modelo al arrancar:** el modelo se carga una vez al iniciar el backend (no en la primera petición). Si la carga falla, toda verificación devuelve `NOT_AVAILABLE` y el arranque deja un aviso en el log sin datos biométricos. Escenarios: "Primer comando sin espera de carga" y "Modelo que no carga ⇒ NOT_AVAILABLE".
5. **`score = null` con `NOT_AVAILABLE`** (no hay voz que comparar: usuario sin huella, audio corto, más de 30 s, error). Con `VERIFIED`/`BELOW_THRESHOLD` el `score` es el coseno. Refléjalo en el tipo y en los escenarios.
6. **Una verificación a la vez:** el acceso al modelo se serializa con un candado (medido: 4 peticiones de 30 s en paralelo usaron 1,85 GB de RAM — experimentos ML 2, 15 oct). Escenario de dos peticiones simultáneas: ambas responden y la RAM no crece como con cuatro en paralelo.
Mantén cada texto de requisito ≤ 500 caracteres con SHALL/MUST. Respóndeme con lo que cambió.
````

---

### A13 — Desafío de voz en `decision-engine` y `speaker-verification` (17 oct)

````text
Instrucción de Daniel (ML 2): agrega el **desafío de voz en la confirmación** a los artifacts `decision-engine` y `speaker-verification` (y al story H1/H2 donde toque). Decisión del equipo [DECIDIDO 2026-10-17, presencial]; lee la propuesta aprobada en el artifact `h2-ml2-speaker-verification/propuesta-confirmacion-con-desafio` antes de escribir. Lee los archivos antes de editar; no toques el repo; requisitos ≤ 500 caracteres con SHALL/MUST.

## Diseño que debe quedar escrito
**Opción de configuración:** `config.confirmationChallenge: boolean` (apagada por defecto; con `false` todo funciona como hoy) y `config.challengePhraseMatchMin: number` (0,80 por defecto).

**Entrada nueva en el `context`:** `confirmation: { mode: "REPLY" | "CHALLENGE", phraseScore: number | null, voice: { status, score } | null, challengeAttempts: number }`, que arma el orquestador:
- `mode = "CHALLENGE"` solo si `confirmationChallenge` está activa **y** el comando se verificó por voz sin PIN (`voice.status == "VERIFIED"` en el comando). Si el pago pasó por PIN (texto, voz no verificada, destinatario nuevo, monto alto), `mode = "REPLY"`: el PIN ya es el segundo factor y se confirma con "sí" como hoy. Así no hay ciclos de PIN.
- `phraseScore`: coincidencia de la respuesta con la frase pedida (0–1, la calcula Voz con `phrase_match`); `null` si no hubo respuesta por voz.
- `voice`: resultado de `verify` sobre el audio de la respuesta al desafío (la frase dura ~3 s, por encima de `minVerifySeconds`).
- `challengeAttempts`: desafíos ya fallados en esta confirmación (lo lleva el orquestador).

**Fase `CONFIRMATION` con `mode == "CHALLENGE"`, en orden (primera que aplique):**
1. `reply == "NO"` (la respuesta fue "no"/"cancela") ⇒ `REJECT` / `USER_DECLINED`.
2. `phraseScore >= challengePhraseMatchMin` y `confirmation.voice.status == "VERIFIED"` ⇒ con exceso `REQUIRE_AUTH` / `CONFIRMED_NEEDS_WALLET_AUTH`, si no `PAY` / `CONFIRMED`.
3. `phraseScore >= challengePhraseMatchMin` y voz NO verificada (`BELOW_THRESHOLD`, `NOT_AVAILABLE` o `null`) ⇒ `ASK_PIN` / `CHALLENGE_VOICE_NOT_VERIFIED`.
4. Frase que no coincide (`phraseScore` bajo el corte o `null`) con `challengeAttempts == 0` ⇒ `ASK_CONFIRM` / `CHALLENGE_RETRY` (el orquestador elige otra frase del banco).
5. Si no ⇒ `REJECT` / `CHALLENGE_FAILED`.
Con `mode == "REPLY"` la fase `CONFIRMATION` queda exactamente como hoy.

**Fase `PIN` después de un desafío:** si `confirmation.mode == "CHALLENGE"` y `phraseScore >= challengePhraseMatchMin` (la frase ya coincidió) y `pin.result == "OK"` ⇒ con exceso `REQUIRE_AUTH` / `CONFIRMED_NEEDS_WALLET_AUTH`, si no `PAY` / `CONFIRMED_WITH_PIN` (el PIN reemplaza a la voz; el consentimiento ya lo dio la frase). El resto de la fase PIN no cambia.

**Reasons nuevos (enum pasa de 28 a 32):** `CHALLENGE_RETRY`, `CHALLENGE_FAILED`, `CHALLENGE_VOICE_NOT_VERIFIED`, `CONFIRMED_WITH_PIN`.

**Traducción reason ⇒ situación del catálogo de Voz:** `ALL_CHECKS_PASSED` y `PIN_CORRECT` (y `PENDING_PAYMENT_UNCONFIRMED`) cuando `confirmation.mode == "CHALLENGE"` ⇒ `CONFIRM_CHALLENGE` (sin exceso) o `CONFIRM_CHALLENGE_OVERRUN` (con exceso); con `mode == "REPLY"` como hoy. `CHALLENGE_RETRY` ⇒ `CHALLENGE_RETRY`; `CHALLENGE_FAILED` ⇒ `CHALLENGE_FAILED`; `CHALLENGE_VOICE_NOT_VERIFIED` ⇒ `PIN_KEYBOARD`; `CONFIRMED_WITH_PIN` ⇒ ninguna (como `CONFIRMED`). Textos propuestos para Voz: `CONFIRM_CHALLENGE` "¿Le envío {recibe} {moneda} a {nombre}? Para confirmar, repite: {frase}"; `CONFIRM_CHALLENGE_OVERRUN` "Supera tu presupuesto. Para autorizarlo en tu billetera, repite: {frase}"; `CHALLENGE_RETRY` "No te entendí. Repite: {frase}"; `CHALLENGE_FAILED` "No pude confirmar la frase. No envié nada.". Anota en "Puntos abiertos" que Voz agrega estas 4 situaciones y el banco de frases (pendiente de Voz).

**Escenarios mínimos:** desafío correcto con voz verificada ⇒ PAY; con exceso ⇒ REQUIRE_AUTH; frase correcta y voz de otra persona (grabación con otra frase o impostor) ⇒ ASK_PIN y luego PIN OK ⇒ PAY/CONFIRMED_WITH_PIN; frase incorrecta una vez ⇒ CHALLENGE_RETRY; dos veces ⇒ REJECT/CHALLENGE_FAILED; "no" ⇒ REJECT; grabación reproducida (frase vieja) ⇒ no coincide ⇒ retry y luego REJECT; comando por texto (PIN) ⇒ `mode REPLY` y "sí" como hoy; opción apagada ⇒ igual que hoy; `phraseScore` exactamente 0,80 ⇒ coincide (borde inclusivo).

**`speaker-verification`:** la verificación corre también sobre el audio de la respuesta al desafío (`confirmation.voice`). Actualiza el requisito/escenario "Solo se verifica la voz del comando" (D4): en `mode REPLY` el "sí" sigue sin verificarse; en `mode CHALLENGE` la respuesta sí se verifica. Trazabilidad: decisión del equipo 2026-10-17 y evidencia X-4.

Respóndeme con lo que cambió y el enum final de reasons.
````

### A14 — Specs de H3: integración y recalibración (17 oct)

````text
Instrucción de Daniel (ML 2), A14: specs de **H3** del rol ML 2. H3 es el sábado a las 09:30 y el código se congela a las 10:45. Según `docs/spec-general.md` §7, a ML 2 le toca en H3 "Enrolamiento y recalibración en la sala; verificación integrada al motor".

Crea un story nuevo `h3-ml2-integracion-y-recalibracion` (kind story, status 0), con el mismo estilo que `h2-ml2-speaker-verification`, y dos specs hijas. Aplican las reglas de siempre:
- lee los archivos antes de editar y no toques el repo;
- requisitos de ≤ 500 caracteres con SHALL/MUST;
- cierra cada spec con las secciones "Trazabilidad" y "Puntos abiertos";
- usa `[DECIDIDO …]` solo para lo que ya está decidido; todo lo nuevo va como **[PROPUESTA]**, con opciones y tu recomendación, para que Daniel decida.

## Lee primero (en el repo `C:\Users\danie\Desktop\Hackatons\Interledger\EZPAY`, rama H2, solo lectura)
- `api/README-ml2.md`, `api/speaker/` (audio, verification, enrollment, store), `api/decision/` (context_io, say_map) y `api/voice/challenge.py`.
- `openapi/contract-b.yaml` (rutas `/api/enrollment` y `/api/turns`, estados del turno) y `docs/contratos-cambios-propuestos-v1.1.md` (B-5, B-7, B-8).
- El brief del esqueleto FastAPI de Pagos: `git show origin/main:prompts/jhonosorno-cmd/builder/06-esqueleto-api-fastapi.md`. Ese brief dice que el orquestador real es la "unidad 7", que todavía no existe, y que el esqueleto NO integra `api/decision`, `api/pin`, `api/speaker` ni `api/voice`.
- Tus artifacts de H1 y H2: decision-engine con el desafío, speaker-verification, voice-enrollment y propuesta-confirmacion-con-desafio. También el comentario más reciente del issue #12 (`gh issue view 12 --comments`): ahí está lo que el orquestador pasa en `context.confirmation`.

## Spec 1: `voice-turn-integration` (la verificación integrada al turno)
El objetivo es que el orquestador de Alexander (unidad 7) solo tenga que llamar funciones de ML 2, sin conocer SpeechBrain, umbrales ni reglas. Cubre:
- **Fachada de ML 2 para el orquestador** (módulo en `api/`, sin HTTP).
  - Del audio del comando a `context.voice`: decodificación con `AvDecoder` de Voz, que ya existe; `verify` en paralelo con `transcribe`.
  - De la respuesta al desafío a `context.confirmation`: modo, `phraseScore` con `phrase_match`, `voice` de la respuesta y `challengeAttempts`.
  - Elegir el modo: `CHALLENGE` solo con `confirmationChallenge` activa y el comando verificado sin PIN.
  - Guardar en la sesión la frase pedida y las frases usadas.
  - El `context` de `say_situation` en fase COMMAND, con modo CHALLENGE.
- **Fallos cerrados.** Cualquier excepción, timeout o falta de modelo o de huella da `NOT_AVAILABLE`, nunca `VERIFIED`. Propón un presupuesto de tiempo; las latencias medidas están en H2.
- **Enrolamiento web.** Cómo se conectan `POST /api/enrollment` y `GET /api/enrollment` del Contrato B con `api/speaker/enrollment`: errores B-5, consentimiento único (`consentExterno`) y borrado.
- **Límite con Pagos.** Qué hace ML 2 (la fachada y sus pruebas) y qué hace el orquestador (estado de sesión, llamadas a Node). Si el Contrato B necesita un campo nuevo, por ejemplo la frase del desafío para mostrarla en la web, déjalo como [PROPUESTA] de cambio de contrato con dueño Pagos/Frontend.
- **Privacidad.** Nada de audio, embeddings ni transcripciones en logs o disco; solo `status` y `score` (PRIV).

## Spec 2: `speaker-calibration` (recalibración en la sala, tarea 4.6)
- **Protocolo en la sala con el micrófono de la demo** (solapa o el que haya): quién se enrola, cuántos intentos genuinos y de impostor, qué frases (las del enrolamiento y las del banco del desafío) y el ruido de la sala.
- **Métricas.** Falsos aceptados y falsos rechazados al umbral actual, mínimo genuino, máximo impostor y peor par de consistencia, más el puntaje de la frase del desafío dicha en la sala. Esto último se coordina con la batería con ruido de Sebastián.
- **Regla de decisión** para mover:
  - `threshold` (0.45);
  - el corte de consistencia (0.45);
  - `minVerifySeconds` (2.0 s);
  - `challengePhraseMatchMin` (0.80).
  Indica qué evidencia hace falta para cambiar cada uno y qué pasa si no hay tiempo: se quedan los valores actuales y se anota en `docs/decisiones.md`.
- **Congelamiento** del umbral en H4 y registro del resultado: solo números agregados, nunca audio ni embeddings en el repo. Los scripts van fuera del repo, en `Pruebas ML2`.
- **Riesgo de la demo:** un enrolamiento que falle en vivo y su plan B.

## Al terminar
Repórtame en un mensaje:
- el árbol de artifacts creado;
- la lista de [PROPUESTA] numeradas, con tu recomendación en cada una (para que Daniel decida rápido);
- cualquier contradicción que encuentres entre lo que ya existe en el repo y los specs de H1 y H2.
````

### A15 — Decisiones sobre las specs de H3 (17 oct)

````text
Decisiones de Daniel sobre A14 (A15). Aplícalas en los artifacts de `h3-ml2-integracion-y-recalibracion` y márcalas **[DECIDIDO 2026-10-17, Daniel]**. Mismas reglas de siempre: lee antes de editar, no toques el repo y requisitos de ≤ 500 caracteres con SHALL/MUST.

## Propuestas aceptadas
- **P1 a P5, P7 y P8: aceptadas tal como las recomendaste.**
  - P3 y P4 son cambios de Contrato B. Quedan como propuesta aceptada por ML 2, pendiente del OK de Pagos y Frontend, que son los dueños del contrato.
  - P8: la fachada usa solo `config.challengePhraseMatchMin` del motor; `CHALLENGE_MIN_MATCH` de Voz queda solo para sus scripts.
- **P6, con cambio:** se enrolan las **4 personas del equipo**. Como vamos justos de tiempo, desde ya se toman **6 intentos genuinos y 6 de impostor por persona** (no 10 y 10). Las 10 frases del banco y los comandos de la demo se mantienen.

## Corrección obligatoria: estado de sesión (contradicción interna)
"Fachada de ML 2" y "Reparto con Pagos" dicen que la fachada no guarda estado de sesión. Pero "Elección del modo y frases de la sesión" y "say_situation en fase COMMAND" dicen que la fachada "guarda en la sesión" la frase. Corrígelo así:
- La fachada es **sin estado**. Recibe como datos lo que necesita: las frases ya usadas, la frase pedida y `challengeAttempts`. Devuelve valores: la frase nueva más la lista de usadas actualizada, y la `confirmation`.
- **El orquestador guarda todo en su sesión.** Ajusta los requisitos y escenarios que dicen "la fachada guarda".

## Precisiones
1. **Regla del modo, más exacta.** `CHALLENGE` solo si `config.confirmationChallenge` está activa, la decisión `ASK_CONFIRM` viene directo de la fase **COMMAND** (no de la fase PIN) y `context.voice.status == "VERIFIED"`. En cualquier otro caso, `REPLY`.
2. **Timeout.** En Python la verificación que excede el tiempo no se cancela: el modelo sigue ocupado y, por el lock (una verificación a la vez), la siguiente espera. La spec debe decirlo. La fachada devuelve `NOT_AVAILABLE` al vencer los 2 s y no lanza otra verificación mientras la anterior siga corriendo (la nueva también da `NOT_AVAILABLE`). Agrega un escenario.
3. **Puntos abiertos de H1 y H2.** Corrige el texto "Voz agrega las 17 situaciones": Voz ya agregó 15, incluidas `CONFIRM_CHALLENGE` y `CHALLENGE_RETRY`; faltan `CONFIRM_CHALLENGE_OVERRUN` y `CHALLENGE_FAILED`, vigiladas por `PENDING_VOZ_SITUATIONS`.
4. **`kind=verify_pending`.** Agrégalo como punto abierto, con dueño Pagos (ratificar el campo).

Cuando termines, repórtame qué requisitos cambiaron y confirma que todos los requisitos tocados tienen ≤ 500 caracteres.
````

## B. Builder

### B1 — Implementar el motor y el PIN en local

````text
Orden de la sesión padre (Daniel, rol ML 2, Hackathon EZPAY): construye el motor de decisión y el PIN de H1 **de forma local primero**, para ejecutarlos y depurarlos con VSCode. NO toques el repo EZPAY (ni commits ni push); es solo lectura.

## Dónde
Carpeta nueva `C:\Users\danie\Desktop\Hackatons\Interledger\Pruebas ML2\ezpay_ml2\`. Esa carpeta padre ya tiene archivos de otros experimentos (SpeechBrain, `.venv`, `recordings`, `.vscode`, etc.): **no modifiques ni borres ninguno, no leas ni copies `recordings/`, `test_data/` ni `pretrained_models/`** (son voces reales). Usa el intérprete `Pruebas ML2\.venv\Scripts\python.exe`. Solo librería estándar (nada de pip install): pruebas con `unittest`. Diseña el paquete para poder copiarlo luego tal cual a `EZPAY\api\` (sin rutas absolutas, imports relativos al paquete).

## Fuente de verdad (léela completa antes de escribir nada)
En `C:\Users\danie\Desktop\Hackatons\Interledger\EZPAY\openspec\changes\add-decision-engine\`: `specs\decision-engine\spec.md`, `specs\pin-validation\spec.md` y **`design.md`** (ahí están el tipo `Context`, las tablas de reglas por fase, la tabla regla→reason, las plantillas de `say` y el detalle de cada requisito). También `openspec\changes\add-payments-client\specs\turn-orchestration\spec.md` (cómo lo invoca el orquestador). Si el spec es ambiguo o contradictorio, NO inventes: anótalo y pregúntame.

## Estructura sugerida
```
ezpay_ml2/
  README.md                  # cómo correr y depurar en VSCode (unittest), en español
  decision/
    __init__.py  models.py   # Context, Decision, Reason (enum de 28), tipos Amount etc. (dataclasses frozen / Enum)
    engine.py                # decide(context) -> Decision{decision, reason}  (función pura)
    templates.py             # tabla reason -> plantilla de say (SOLO datos, para verificar cobertura; el catálogo real es de ML 1)
  pin/
    __init__.py  pin.py      # verify_pin(pin, session_id) -> PinResult ; reset_pin_lock()
  scripts/
    make_pin_hash.py         # genera el hash con sal (scrypt) y lo imprime para copiarlo a .env (el PIN se lee con getpass, nunca por argumento)
    reset_pin_lock.py
  tests/
    fixtures.py              # helpers para armar contexts
    test_engine_command.py  test_engine_pin_phase.py  test_engine_confirmation.py  test_engine_misc.py
    test_pin.py
```

## Reglas de implementación (del spec)
- `decide` es **pura y determinista**: sin HTTP, sin `datetime.now()`/`time`, sin `random`, sin estado global; la hora llega en `context.now` (ISO 8601; puedes parsearla con `datetime.fromisoformat`). Mismo context → mismo `{decision, reason}`.
- Montos: comparar `Amount.value` como **enteros**, jamás float (CONV-1). Moneda o escala distinta al umbral ⇒ cuenta como alto (falla seguro).
- Orden de la fase COMMAND: 1, 2 (reason derivado por la prioridad del spec), 2b, 3, 4, 5, 6 (REASK) / 6b (condición-marca `warnUnconfirmed` que NO decide y sigue a 7/8/9), 7, 8 (NEW_RECIPIENT antes de HIGH_AMOUNT), 9. Fases PIN y CONFIRMATION según el spec (incluye `reply == None` ⇒ tratado como UNCLEAR, `INVALID_FORMAT`/`None` ⇒ ASK_PIN).
- El `reason` es un enum cerrado de 28 valores; ningún valor fuera del enum; el `reason` jamás incluye datos del request.
- PIN: `hashlib.scrypt` + sal; el hash se lee de la variable de entorno (elige un nombre claro, p. ej. `EZPAY_PIN_HASH`, formato `scrypt$N$r$p$sal_b64$hash_b64`); comparación con `hmac.compare_digest`; formato 4–6 dígitos (inválido ⇒ `INVALID_FORMAT`, sin invocar el KDF y sin consumir intento); 3 fallos por sesión ⇒ `sessionFailures >= 3`; 5 fallos seguidos globales ⇒ `locked=True` (bloqueado ⇒ no valida más); PIN correcto reinicia el contador global; `reset_pin_lock()` lo levanta. Contador global **en memoria** (en H1 se pierde al reiniciar; la persistencia es H2). **Sin PIN configurado ⇒ nunca `OK`** (falla cerrado). El PIN nunca en logs, ni en excepciones, ni en `repr`; no hagas `print`/`logging` de él. Estado inyectable (clase con store) para que las pruebas sean aisladas.
- Para las pruebas del PIN genera el hash dentro de la prueba con parámetros scrypt baratos; **nunca escribas un PIN real ni un hash real** en archivos. No leas ningún `.env` real.
- Fixtures: usa estos valores reales de los mocks de Pagos (rama `origin/payments/openapi-mocks`, `openapi/contract-a.yaml`): quote dentro del presupuesto `debit 2015000 / receive 2000000 COP escala 2, exceedsRemaining false`; quote con exceso `debit 30150000 / receive 30000000, exceedsRemaining true`; pago `PROCESSING` `paymentId p_789`. No hace falta levantar Prism: el motor es una función pura.

## Método
1. **Primero las pruebas**: un test por cada `#### Scenario` de los dos specs (nómbralos con el título del escenario, agrupados por requisito) más pruebas de propiedades: determinismo, todo reason del enum con exactamente una plantilla, ningún reason fuera del enum, el PIN no aparece en `repr`/excepciones. Corre (deben fallar), luego implementa hasta verde.
2. Corre con `Pruebas ML2\.venv\Scripts\python.exe -m unittest discover -s ezpay_ml2/tests -t ezpay_ml2 -v` (ajusta si hace falta) y confirma que pasan.
3. VSCode: deja en `ezpay_ml2/.vscode/settings.json` la configuración de unittest (`python.testing.unittestEnabled: true`, `unittestArgs` con `-s tests -p "test_*.py" -t .`) y un `launch.json` para depurar un test y para ejecutar `make_pin_hash.py`; di en el README que se abre `ezpay_ml2` como carpeta (o cómo hacerlo desde la carpeta padre). No edites el `.vscode` de la carpeta padre.

## Entrega
Respóndeme con: árbol de archivos, comando exacto para correr las pruebas, nº de pruebas y resultado, escenarios del spec que no pudiste cubrir o que te parecieron ambiguos, y cualquier desviación. No hagas commits.
````

### B2 — Correcciones tras la revisión (fail-closed y PIN)

````text
Revisión de la sesión padre (corrí tus 101 pruebas: OK). Buen trabajo y buenos hallazgos. Correcciones (primero las pruebas en rojo, luego código; al final vuelve a correr TODO):

**Motor (`decision/engine.py`)**
1. **Fail-closed con quote ausente (seguridad).** Hoy, en COMMAND con `hasBudgetGrant == True` y `quote is None`, se salta el chequeo de destinatario nuevo/monto alto y termina en `ASK_CONFIRM`; y en CONFIRMATION `YES` con `quote is None` devuelve `PAY`. Ambos casos son contexts inválidos (un `quote` nulo solo es legal cuando `hasBudgetGrant == False`, que ya sale en la regla 5). Crea `class InvalidContextError(ValueError)` en `models.py` (mensaje fijo, sin datos del request) y levántala: (a) en COMMAND tras la regla 5 si `quote is None`; (b) en CONFIRMATION si `reply == YES` y `quote is None`; (c) en PIN si `pin.result == OK` y la 6b necesita el context completo (solo si hace falta; si no, no). Agrega pruebas para cada caso y exporta la excepción. El orquestador la tratará como error interno (no se paga).
2. Tu decisión sobre la regla 2: correcto, `recipient == null` dispara REASK/`RECIPIENT_MISSING`. Yo corrijo el spec; tú no toques los specs del repo.

**PIN (`pin/pin.py`)**
3. **Defensa en profundidad:** si `session_id` ya tiene `sessionFailures >= MAX_SESSION_FAILURES`, `verify` MUST NOT validar más (devuelve `WRONG`, `sessionFailures` actual, `remaining=0`, sin invocar scrypt ni mover contadores), igual que con el bloqueo global. Prueba incluida (3 fallos, y luego el PIN CORRECTO en la misma sesión ⇒ WRONG, no OK).
4. **Hilos:** protege contadores y bloqueo con un `threading.Lock` (FastAPI puede atender peticiones concurrentes); prueba con varios hilos simulando 20 intentos fallidos en paralelo ⇒ exactamente 5 fallos globales contados antes del bloqueo y nunca un OK espurio.
5. **Formato:** `isdigit()` acepta dígitos Unicode (p. ej. "²", "١٢٣٤"). Exige ASCII: `pin.isascii() and pin.isdigit()` (o `re.fullmatch(r"[0-9]{4,6}", pin)`). Pruebas con "²³⁴⁵", "١٢٣٤", espacios y saltos de línea ⇒ `INVALID_FORMAT`.
6. Mantén tu interpretación literal de que un OK no reinicia el contador de SESIÓN (3 fallos por sesión, D5). Déjalo documentado en el README como decisión.
7. Evita que `_session_failures` crezca sin límite: borra la entrada de una sesión cuando haga falta o limita a, p. ej., 1000 sesiones (descarta la más antigua); una prueba corta.

Respóndeme con el nº de pruebas final y cualquier desviación. Sin commits ni cambios fuera de `Pruebas ML2\ezpay_ml2\`.
````

### B3 — Integración con Voz y layout final del repo

````text
Orden de la sesión padre (Daniel). Tu entrega anterior está aprobada (115 OK). Ahora toca **integración con Voz (ML 1) y el layout final del repo**. Sigue en `Pruebas ML2\ezpay_ml2\`, sin commits ni tocar el repo EZPAY (solo lectura). Primero pruebas en rojo, luego código, y al final corre todo.

## A. Lo que entrega ML 1 (léelo, solo lectura)
Rama `origin/voz/h1-parser` del repo EZPAY: usa `git -C "C:\Users\danie\Desktop\Hackatons\Interledger\EZPAY" show origin/voz/h1-parser:api/voice/intents.py` (y `contacts.py`, `replies.py`, `tests/voice/test_context_shapes.py`). Sus `to_dict()` son exactamente las formas de `intent` y `resolution` de nuestro `context` (camelCase). Hallazgos que debes reflejar:
1. **Faltan datos ⇒ `status: "UNCLEAR"`, no `OK`.** Voz devuelve p. ej. "Envíale plata a mi hija" ⇒ `{action PAY, amount None, amountError None, recipient "mi hija", status UNCLEAR}`; "Envíale veinte mil" (sin preposición) ⇒ `recipient None, status UNCLEAR`; "Envíale 10,505 a Laura" ⇒ `amount None, amountError TOO_MANY_DECIMALS, status UNCLEAR`; dos montos o dos destinatarios ⇒ `AMBIGUOUS` con `amount None`/`recipient None`; "Hola" ⇒ `{UNKNOWN, None, None, None, OK}` (¡UNKNOWN con status OK!); "Cancela" ⇒ `{CANCEL, None, None, None, OK}`; fuera de gramática ⇒ `{UNKNOWN, ..., UNCLEAR}`. Nuestros fixtures actuales usan `status OK` con `amount None`/`recipient None`: es irreal. Cámbialos a lo que Voz entrega de verdad. El motor ya funciona para ambos (la prioridad del reason no depende del status cuando es != OK), pero agrega una prueba explícita de que `AMOUNT_MISSING`/`RECIPIENT_MISSING` salen igual con `UNCLEAR` y con `OK` (robustez), y pruebas con "Hola" ⇒ `INTENT_UNKNOWN` y "Cancela" ⇒ `REJECT/CANCELLED_BY_USER`.
2. `resolution` de Voz: `{"kind":"RESOLVED","contact":{alias,name,walletAddress,previouslyPaid}}`, `{"kind":"CHOICE","options":[{alias,name}]}`, `{"kind":"NOT_FOUND"}` (en `resolve_choice` existe además `UNCLEAR`, que NO llega al motor: debe ser un contexto inválido).

## B. `decision/context_io.py` (nuevo, para el orquestador de Pagos)
- `parse_context(data: dict) -> Context`: construye el `Context` desde un diccionario con las claves camelCase del `design.md` (`phase, intent, resolution, voice, enrolled, hasBudgetGrant, quote, pendingPayment, now, reply, unclearReplies, pin, transcriptConfidence, intentConfidence, config`; `config` con `highAmountThreshold, pendingWindowSeconds, minIntentConfidence, minTranscriptConfidence`). **Estricto y fail-closed**: clave faltante, valor de enum desconocido, `Amount.value` no ASCII-dígitos, `resolution.kind` UNCLEAR, tipos incorrectos ⇒ `InvalidContextError` (mensaje fijo, sin datos del request). No aceptes claves desconocidas.
- `Decision.to_dict()` ⇒ `{"decision": "...", "reason": "..."}` y `decide_dict(data) -> dict` que une ambos (es lo que usará el orquestador).
- Pruebas con **literales JSON idénticos a los `to_dict()` de Voz** (cópialos de `test_context_shapes.py`/`intents.py`; NO importes el paquete `voice`): cada frase de arriba ⇒ decisión y reason esperados. Incluye el recorrido completo de la demo: "Envíale veinte mil a mi hija" por texto ⇒ `ASK_PIN/VOICE_NOT_VERIFIED`; fase PIN con `pin.result OK` ⇒ `ASK_CONFIRM/PIN_CORRECT`; confirmación `YES` ⇒ `PAY/CONFIRMED`; y el exceso (30000000) ⇒ `ASK_CONFIRM` y luego `REQUIRE_AUTH`.
- Exporta desde `decision/__init__.py` (`parse_context`, `decide_dict`).

## C. Layout final = el del repo (`ezpay_ml2/` ≡ `EZPAY/api/`)
Voz usa en el repo: `api/voice/`, `api/tests/voice/` (SIN `__init__.py`), pytest desde `api/` con `PYTHONPATH=.`. Para no chocar:
- Mueve las pruebas a `tests/decision/` (motor + context_io) y `tests/pin/` (PIN), **sin `__init__.py`** en `tests/`, `tests/decision/` ni `tests/pin/` (un `__init__.py` ahí haría que pytest importe `decision.test_x` y choque con nuestro paquete `decision`).
- Renombra `tests/fixtures.py` a `tests/decision/decision_fixtures.py` e impórtalo como `from decision_fixtures import ...` (cada directorio de pruebas entra a `sys.path`); nombres de archivos de prueba únicos en todo el árbol (los de Voz son `test_amounts/contacts/context_shapes/intents/package/phrases/replies.py`; los nuestros no los repiten: no uses `test_package.py` ni `test_context_shapes.py`).
- Comandos en el README (de `Pruebas ML2`, y su equivalente desde `api/` en el repo): `python -m unittest discover -s tests/decision -v` y `python -m unittest discover -s tests/pin -v`, con `PYTHONPATH=.`/`-t .` según haga falta (verifica que funcionan; pytest no está instalado en el venv local, pero las pruebas deben ser compatibles con `PYTHONPATH=. python -m pytest tests -q`). Actualiza `.vscode/settings.json`, `launch.json` y el README al nuevo layout.
- El script `scripts/make_pin_hash.py` debe pedir ASCII (usa la misma validación que `pin.py`, no `isdigit()` a secas) y `scripts/` no debe importar nada de `tests/`.
- Añade `.env.example` en la raíz (`ezpay_ml2/.env.example`) con solo `EZPAY_PIN_HASH=` (sin valor) y un comentario; sin ningún PIN ni hash real.

## D. Cambios de spec que haré yo (para que sepas qué viene)
Los escenarios `AMOUNT_MISSING`/`RECIPIENT_MISSING` pasarán a `status UNCLEAR`. No toques los specs del repo.

Respóndeme con: árbol final, comandos exactos y resultado (nº de pruebas por directorio), y desviaciones. Cuando termines, para y espera: no copies nada al repo.
````

### B4 — Fechas fail-closed y README para `api/`

````text
Revisión de la sesión padre: 145/145 OK confirmados por mí. Quedan dos arreglos pequeños antes de pasar al repo (pruebas primero, luego código; mismo alcance: solo `Pruebas ML2\ezpay_ml2\`, sin tocar el repo ni commits).

1. **Fechas mal formadas.** `parse_context` acepta cualquier string en `now` y `pendingPayment.createdAt`, y luego `engine._parse_instant` lanza un `ValueError` genérico de `datetime.fromisoformat` (su mensaje incluye el valor recibido). Quiero fail-closed con mensaje fijo: (a) en `parse_context` valida ISO 8601 (con `Z` o desplazamiento; sin zona = UTC, como ya haces en el motor) para `now` y `createdAt` ⇒ `InvalidContextError` si no parsea; (b) en `engine._parse_instant` captura `ValueError` y levanta `InvalidContextError()` sin el valor (para quien llame a `decide` con un `Context` armado a mano). Pruebas: `now="garbage"`, `now=""`, `createdAt="ayer"`, `now="2026-13-45T00:00:00Z"` ⇒ `InvalidContextError`, y que el mensaje NO contiene "garbage"/"ayer". Verifica que los casos válidos (`Z`, `+00:00`, sin zona) sigan igual.
2. **README.md** (de `ezpay_ml2`): reescríbelo para que sirva tal cual en el repo bajo `api/`: sin la referencia a la carpeta `Pruebas ML2` ni a rutas locales; comandos desde `api/` (`PYTHONPATH=. python -m unittest discover -s tests/decision -v` y `-s tests/pin -v`, y la variante pytest) y una sección corta "Cómo lo usa el orquestador" (`decide_dict`, `parse_context`, `InvalidContextError` ⇒ error interno, no se paga; `verify_pin`/`reset_pin_lock`; alta del PIN con `scripts/make_pin_hash.py` y `.env.example`). Mantén la sección de depuración con VSCode, marcada como opcional.

Respóndeme con el nº de pruebas final por directorio. Luego para y espera.
````

### B5 — Catálogo único de `say`: traducción de `reason` a situación de Voz

````text
Orden de la sesión padre (Daniel). El código ya está en el repo, rama `ml2/verificacion-calidad`, PR #5. Trabaja **directamente en `C:\Users\danie\Desktop\Hackatons\Interledger\EZPAY\api\`** (es el mismo layout que tu `ezpay_ml2`). No hagas commits ni push: yo los hago. No toques nada fuera de `api/decision/`, `api/tests/decision/` y `api/README-ml2.md`. Primero pruebas en rojo, luego código; corre todo al final.

## Decisión: un solo catálogo de `say` (el de Voz)
Los textos viven SOLO en el catálogo de Voz (`api/voice/phrases.py`, enum `Situation`, rama `origin/voz/h1-parser`, PR #4; léelo con `git -C "C:\Users\danie\Desktop\Hackatons\Interledger\EZPAY" show origin/voz/h1-parser:api/voice/phrases.py`). El motor no tiene textos.

1. Reemplaza `api/decision/templates.py` por `api/decision/say_map.py` (borra `templates.py` y actualiza `__init__.py`, README y pruebas que lo usen): función pura `say_situation(decision: Decision, context: Context) -> str | None` que devuelve el NOMBRE de la situación de Voz (string, no importes `voice`). Tabla:
- CANCELLED_BY_USER→CANCELLED · INTENT_UNKNOWN→NOT_UNDERSTOOD · INTENT_UNCLEAR→NOT_UNDERSTOOD · AMOUNT_MISSING→AMOUNT_MISSING · RECIPIENT_MISSING→RECIPIENT_MISSING
- AMOUNT_ERROR→ por `context.intent.amountError`: TOO_MANY_DECIMALS→TOO_MANY_DECIMALS, AMBIGUOUS_AMOUNT→AMOUNT_AMBIGUOUS, INVALID_AMOUNT→INVALID_AMOUNT (si es None ⇒ `InvalidContextError`)
- RECIPIENT_NOT_FOUND→NOT_FOUND · RECIPIENT_AMBIGUOUS→CHOICE si hay 2+ opciones, NEAR si hay 1 · NO_BUDGET_GRANT→AUTH_BUDGET · VOICE_NOT_VERIFIED→PIN_KEYBOARD
- ALL_CHECKS_PASSED y PIN_CORRECT→CONFIRM si `quote.exceedsRemaining` es false, AUTH_OVERRUN si es true
- PENDING_PAYMENT_UNCONFIRMED→PENDING_PAYMENT_UNCONFIRMED (false) o PENDING_PAYMENT_UNCONFIRMED_OVERRUN (true)
- CONFIRMED→None (el `say` sale del resultado del pago) · CONFIRMED_NEEDS_WALLET_AUTH→AUTH_REDIRECT · USER_DECLINED→CANCELLED · REPLY_UNCLEAR_ASK_AGAIN→CONFIRM_UNCLEAR
- Con el mismo nombre que el reason (situaciones NUEVAS que Voz agregará): INTENT_AMBIGUOUS, INTENT_LOW_CONFIDENCE, TRANSCRIPT_LOW_CONFIDENCE, PENDING_PAYMENT_SAME_RECIPIENT, NEW_RECIPIENT, HIGH_AMOUNT, PIN_WRONG, PIN_ATTEMPTS_EXHAUSTED, PIN_LOCKED, PIN_INVALID_FORMAT, REPLY_UNCLEAR_REJECTED.
Si una variante necesita la quote y es None ⇒ `InvalidContextError` (mensaje fijo).
2. Exporta también `VOICE_SITUATIONS_EXISTING` (las 21 de Voz hoy: NO_SPEECH, NOT_UNDERSTOOD, AMOUNT_MISSING, RECIPIENT_MISSING, AMOUNT_AMBIGUOUS, TOO_MANY_DECIMALS, INVALID_AMOUNT, NOT_FOUND, CHOICE, NEAR, CONFIRM, CONFIRM_UNCLEAR, CANCELLED, COMPLETED, PIN_KEYBOARD, AUTH_BUDGET, AUTH_OVERRUN, AUTH_REDIRECT, AUTH_APPROVED, AUTH_REJECTED, PAYMENT_PENDING) y `VOICE_SITUATIONS_NEW` (las 13 nuevas: las 11 de arriba + PENDING_PAYMENT_UNCONFIRMED y PENDING_PAYMENT_UNCONFIRMED_OVERRUN).
3. Pruebas (`tests/decision/test_say_map.py`): cada uno de los 28 reasons tiene traducción (todas las variantes); toda situación devuelta está en EXISTING ∪ NEW; CONFIRMED ⇒ None; determinismo; sin datos del request en el resultado; y una prueba de integración que **intenta** `import voice.phrases` y verifica que cada situación de EXISTING existe en `voice.phrases.Situation` (y reporta cuáles de NEW faltan) — con `self.skipTest(...)` si `voice` no es importable (hoy no está mergeado en esta rama). Corre: `cd api; $env:PYTHONPATH="."; python -m unittest discover -s tests/decision -v` y `-s tests/pin -v` con `C:\Users\danie\Desktop\Hackatons\Interledger\Pruebas ML2\.venv\Scripts\python.exe`.
4. En `api/README-ml2.md`, en "Cómo lo usa el orquestador", cambia la parte de plantillas: `say_situation(decision, context)` ⇒ `voice.phrases.say(Situation(nombre), **params)`.

Respóndeme con el nº de pruebas por directorio y desviaciones. Luego para y espera.
````

### B6 — Scripts de los experimentos de H2 en vivo (fuera del repo)

Resumen: scripts en `Pruebas ML2\experimentos_h2\` (fuera del repo) para grabar en vivo con las frases oficiales del enrolamiento: `x0_entorno.py` (modelo sin internet y latencia), `x1_enrolar.py` (3 frases, consistencia, huella promedio), `x2_comandos.py` (3 comandos contra todas las huellas, estrategias promedio y máximo, truncados de 1,0 a 3,0 s y sin los primeros 0,5 s), `x4_reproduccion.py` (reproducción desde el celular) y `analizar.py` (informe con decisiones sugeridas). Audio solo en memoria; se guardan solo embeddings y métricas. El texto completo de esta instrucción está en la transcripción de la sesión; aquí se resume porque solo produjo herramientas de medición que no están en el repo.

### B7 — Experimento 6 (detector de voz) y código de H2

````text
Orden de la sesión padre (Daniel, ML 2). Dos tareas EN ORDEN; avísame al terminar la 1 antes de empezar la 2 (Daniel necesita grabar con la 1). Sin commits ni push: yo los hago.

## Tarea 1 — Experimento de la mejora 6: detector de voz (VAD) vs `trim_silence`
En `Pruebas ML2\experimentos_h2\` (mismas reglas que antes: no leer `recordings/` ni `test_data/`, audio solo en memoria, solo embeddings y métricas en `resultados/`, reutiliza `lab.py`, `--simular`, `--device`, `--list-devices`).
- **Detector nuevo:** VAD de SpeechBrain `speechbrain/vad-crdnn-libriparty`, guardado en `Pruebas ML2\pretrained_models\vad-crdnn-libriparty` (la PRIMERA vez se descarga con internet; después debe cargar con `HF_HUB_OFFLINE=1`; si no está y no hay red, avisa claro). Usa sus segmentos de voz: concatena solo los tramos con voz (método V1 "recorte por VAD": primer inicio a último fin, con 0,25 s de margen; y método V2 "solo voz": concatenar los segmentos y quitar pausas internas). Si el VAD no detecta voz, la toma cuenta como `NOT_AVAILABLE`.
- **`x6_vad.py --persona NOMBRE [--repeticiones 5]`**: en UNA sesión, la persona graba las 3 frases oficiales del enrolamiento y luego los 3 comandos (los mismos de x2) `--repeticiones` veces. Para CADA toma calcula el embedding con los 3 preprocesos: E (energía, `trim_silence` actual), V1 y V2; guarda huellas promedio L2 por método (`resultados/huellas_x6/NOMBRE_{E,V1,V2}.npy`) y la voz útil por método. Compara cada comando contra TODAS las huellas del MISMO método (genuino e impostor) y escribe `resultados/x6.csv` (hablante, huella, genuino, frase, repetición, metodo, voz_util_s, score). Es decir: las MISMAS tomas pasan por los 3 detectores (comparación justa).
- **`analizar_x6.py [--umbral 0.45]`**: por método: genuino mínimo/mediana, impostor máximo, margen, falsos aceptados/rechazados a 0.40/0.45/0.50/0.55, consistencia del enrolamiento (peor par por persona), voz útil de la frase de la demo, y casos `NOT_AVAILABLE`. Recomendación: cambiar de E a V1/V2 solo si tiene 0 falsos aceptados a 0.45 y un margen mayor que E en al menos 0,03; si no, quedarse con E (avisa que cambiar el detector obliga a recalibrar y a actualizar el spec). Escribe `resultados/informe_x6.md` e imprímelo.
- Actualiza `experimentos_h2/README.md` con los comandos. Prueba en seco con `--simular` y luego borra los datos simulados.

## Tarea 2 — Código de H2 en el repo, rama `H2`
Trabaja en `C:\Users\danie\Desktop\Hackatons\Interledger\EZPAY\` (la rama `H2` ya está activa; no cambies de rama). Fuente de verdad: `openspec/changes/add-decision-engine/specs/speaker-verification/spec.md`, `.../voice-enrollment/spec.md` y `design.md` (léelos completos; los valores ya están decididos: huella = promedio L2-normalizado, umbral 0.45 con `score >= umbral` ⇒ VERIFIED, `minVerifySeconds` 2,0 s de voz útil, tope 30 s ⇒ NOT_AVAILABLE sin cargar, corte de consistencia 0.45, muestras de 3 a 15 s de voz útil, orden de errores CONSENT_REQUIRED → SAMPLES_REQUIRED → INVALID_AUDIO → INCONSISTENT_SAMPLES, consentimiento único con `consentExterno`, re-enrolamiento atómico, persistencia fuera de git, carga del modelo al arrancar, un candado). Si algo es ambiguo, pregúntame.
- **Paquete nuevo `api/speaker/`** (solo toca `api/speaker/`, `api/tests/speaker/`, `api/README-ml2.md`): `audio.py` (`trim_silence` idéntico al de calibración: frame=320, pad=0,25, umbral 0,1 × RMS máximo; duración de voz útil), `verification.py` (`SpeakerVerifier` con `load()` al arrancar, `embed(pcm)`, `verify(pcm, user) -> {"status", "score"}` con `score=None` en NOT_AVAILABLE, candado), `enrollment.py` (`enroll(samples, consent) -> {"enrolled": True}` o error con `code` de B-5, `status() -> {"enrolled": bool}`, `consent_external() -> bool`, `delete()`), `store.py` (persistencia en un directorio configurable por `EZPAY_SPEAKER_DATA_DIR`, por defecto `api/.data/speaker/`, que crea un `.gitignore` con `*` dentro; guarda solo el embedding y la marca de consentimiento, nunca audio; escritura atómica con archivo temporal + rename), `scripts`: `api/scripts/delete_voiceprint.py` (PRIV-3). Entrada: `numpy` float32 16 kHz mono (Voz decodifica).
- **El modelo se inyecta:** `SpeakerVerifier(embedder=...)`; el embedder real carga SpeechBrain ECAPA desde `EZPAY_SPEAKER_MODEL_DIR` con `HF_HUB_OFFLINE=1`; si falla, `verify` devuelve NOT_AVAILABLE siempre y deja un aviso sin datos biométricos. Las pruebas usan un embedder FALSO determinista (por ejemplo, vectores fijos por "hablante" sintético) para no depender del modelo ni de la red; agrega UNA prueba de integración que use el modelo real solo si `EZPAY_SPEAKER_MODEL_DIR` existe (si no, `skipTest`). `speechbrain`/`torch` se importan de forma perezosa (el paquete debe importarse sin ellos).
- **Pruebas primero:** una prueba por cada `#### Scenario` de los dos specs (nómbralas con el título del escenario), en `api/tests/speaker/` sin `__init__.py`, nombres de archivo únicos (no repitas los de `tests/voice`, `tests/decision`, `tests/pin`). Escenarios que dependen de medición (latencia < 1 s, RAM) ⇒ prueba de integración con `skipTest` si no hay modelo. Privacidad: verifica que ni logs ni excepciones contienen audio, embeddings ni puntajes (captura logging). Concurrencia: dos hilos llaman a `verify` y el candado serializa.
- Corre con `C:\Users\danie\Desktop\Hackatons\Interledger\Pruebas ML2\.venv\Scripts\python.exe` desde `api/`: `PYTHONPATH=. python -m unittest discover -s tests/speaker -v`, y también las suites existentes (`tests/decision`, `tests/pin`; si `tests/voice` usa pytest y no está instalado, dilo) para confirmar que no rompiste nada. Pruébalo también con el modelo real apuntando `EZPAY_SPEAKER_MODEL_DIR` a `Pruebas ML2\pretrained_models\spkrec-ecapa-voxceleb`.
- README-ml2: sección "Verificación de hablante y enrolamiento" con cómo lo usa el orquestador (cargar al arrancar; `verify` ⇒ `context.voice`; `enroll`/`status`/`delete` para las rutas `/api/enrollment` de Pagos; `consent_external()` para Voz) y las variables de entorno.

Entrega de cada tarea: árbol, comandos exactos, nº de pruebas (por directorio) y desviaciones.
````

### B8 — Continuar con el código de H2

````text
Tarea 1 aprobada, gracias (buen hallazgo el del silencio digital). Sigue con la Tarea 2 (paquete `api/speaker/` en el repo, rama `H2`) tal como está en mi mensaje anterior. Daniel graba x6 en paralelo con el mismo micrófono; no toques `Pruebas ML2\experimentos_h2\` mientras tanto. Sin commits; avísame al terminar con árbol, comandos y nº de pruebas por directorio.
````

### B9 — Medir la voz útil como en la calibración

````text
Revisión de la sesión padre: muy buen trabajo, pero hay que revertir la desviación 1 (bloqueante). Los valores 2,0 s (`minVerifySeconds`), 3 s y 15 s se CALIBRARON midiendo la voz útil como `len(trim_silence(audio)) / SAMPLE_RATE`, es decir, CON el margen de 0,25 s a cada lado (ver `Pruebas ML2\experimentos_h2\lab.py` líneas ~205 y ~267: `len(corte_e) / SAMPLE_RATE` y `len(audio) / SAMPLE_RATE` tras `trim_silence`). Los truncados de X-2 (1,0–3,0 s) también se cortaron sobre el audio ya recortado con margen. Si el código mide sin margen (~0,5 s menos), la frase de la demo (2,06–3,02 s medidos con margen) quedaría en ~1,56–2,5 s y muchas tomas genuinas darían NOT_AVAILABLE ⇒ PIN en plena demo. Cambios (pruebas primero):
1. `duracion_voz_util(pcm)` = `len(trim_silence(pcm, frame=320, pad=0.25)) / SAMPLE_RATE` (exactamente la medida de la calibración; con audio sin voz, 0). Úsala igual en verificación (2,0 s) y enrolamiento (3–15 s). Docstring: "misma medida que la calibración del 16–17 oct (incluye el margen de 0,25 s); cambiarla obliga a recalibrar".
2. Prueba de no regresión: una toma sintética con 1,6 s de voz + silencios ⇒ voz útil = 1,6 + 0,5 = 2,1 s ⇒ se verifica (no NOT_AVAILABLE); y una de 1,4 s de voz ⇒ 1,9 s ⇒ NOT_AVAILABLE. Y una prueba que compare `duracion_voz_util` con `len(trim_silence(x))/16000` para varios audios.
3. Actualiza README-ml2 si menciona la medida.
Corre de nuevo tests/speaker (normal y con el modelo real), tests/decision y tests/pin. Sin commits. Respóndeme con los números.
````

### B10 — Persistir el contador global del PIN

````text
Orden de la sesión padre (Daniel, ML 2): persistir el contador GLOBAL de fallos del PIN (tarea 1.4 de add-decision-engine; en H1 vivía en memoria). Repo EZPAY, rama `H2` (no cambies de rama), solo toca `api/pin/`, `api/scripts/reset_pin_lock.py`, `api/tests/pin/` y `api/README-ml2.md`. Pruebas primero; sin commits.
- Persistencia "junto a la huella": directorio configurable `EZPAY_PIN_DATA_DIR`, por defecto `api/.data/pin/` (crea un `.gitignore` con `*` dentro, igual que `api/.data/speaker/`). Guarda SOLO `{"globalFailures": int, "locked": bool}` en un JSON; NUNCA el PIN, ni el hash, ni contadores de sesión (los de sesión siguen en memoria). Escritura atómica (temporal + `os.replace`), bajo el mismo `threading.Lock` del validador.
- Al iniciar `PinValidator` se carga el estado; cada fallo, cada PIN correcto (reinicia el global) y cada bloqueo se guardan antes de responder. Un reinicio del backend conserva el bloqueo y el conteo.
- Archivo ilegible o corrupto ⇒ falla cerrado: se trata como `locked: true`, deja un aviso en el log sin datos sensibles; `reset_pin_lock.py` lo repara (escribe `{0, false}`).
- `scripts/reset_pin_lock.py` ahora reinicia el estado PERSISTIDO (ya no depende del proceso del backend); actualiza su docstring.
- Estado inyectable para pruebas (directorio temporal). Pruebas: reinicio conserva 4 fallos y el 5.º bloquea; reinicio conserva el bloqueo; PIN correcto persiste el reinicio a 0; archivo corrupto ⇒ bloqueado; reset por script ⇒ desbloqueado; el JSON nunca contiene el PIN ni el hash (busca el PIN y el hash en el contenido); concurrencia sigue contando exacto.
- Corre `PYTHONPATH=. python -m pytest tests -q` desde `api/` (pytest ya está instalado en el .venv de Pruebas ML2) y repórtame los números. Actualiza README-ml2 (variable `EZPAY_PIN_DATA_DIR` y que el bloqueo sobrevive al reinicio).
````

Las instrucciones al Constructor de Specs de esta etapa (plan de experimentos, resultados del 17 oct, X-6 y frase de la demo con la divisa) actualizaron los artifacts que luego se copiaron a `openspec/changes/add-decision-engine/`; sus decisiones están en `prompts/Valdex328/12-rama-h2-experimentos-y-codigo.md` y en `design.md`.

### B11 — Confirmación con desafío de voz en el motor (17 oct)

````text
Instrucción de Daniel (ML 2), B11: implementa la **confirmación con desafío de voz** en el motor. Repo `C:\Users\danie\Desktop\Hackatons\Interledger\EZPAY`, rama `H2` (no cambies de rama, no hagas pull, merge ni commits). Toca SOLO `api/decision/`, `api/tests/decision/` y `api/README-ml2.md`. Pruebas primero y luego el código.

## Fuente de verdad
Lee antes de escribir: `openspec/changes/add-decision-engine/specs/decision-engine/spec.md` (requisitos "Confirmación con desafío de voz", "Tabla de la fase PIN", "El motor no obedece al LLM") y `openspec/changes/add-decision-engine/design.md` (contexto de entrada, tabla regla→reason con las filas `CONFIRMATION (CHALLENGE)` y la fila PIN con desafío, y la tabla reason→situación). Si el spec y esta instrucción no coinciden, para y pregúntame.

## Qué implementar
1. **Modelos (`models.py`)**:
   - `Reason` suma `CHALLENGE_RETRY`, `CHALLENGE_FAILED`, `CHALLENGE_VOICE_NOT_VERIFIED` y `CONFIRMED_WITH_PIN` (total 32).
   - `ConfirmationMode` (`REPLY`, `CHALLENGE`).
   - `Confirmation(mode, phrase_score: float|None, voice: Voice|None, challenge_attempts: int)`. Valida: `phrase_score` en [0, 1] o None, sin bool ni NaN ni inf. `challenge_attempts` es un int ≥ 0, sin bool.
   - `Context.confirmation: Confirmation|None` (por defecto None).
   - `EngineConfig` suma `confirmation_challenge: bool = False` y `challenge_phrase_match_min: float = 0.80` (en [0,1]).
2. **`context_io.py`**: parsea `confirmation` (claves camelCase: `mode`, `phraseScore`, `voice`, `challengeAttempts`), `config.confirmationChallenge` y `config.challengePhraseMatchMin`. El parser sigue estricto y falla cerrado con `InvalidContextError`, como hoy: tipos malos, claves faltantes, modo desconocido y voice mal formada. Los mensajes de error NO deben incluir el valor recibido. `confirmation` ausente o null ⇒ None.
3. **`engine.py`**:
   - En fase `CONFIRMATION` con `confirmation` no nulo y `mode == CHALLENGE`, aplica en orden (gana la primera que aplique):
     1. `reply == NO` ⇒ `REJECT`/`USER_DECLINED`.
     2. `phrase_score >= min` y `voice.status == VERIFIED` ⇒ si la quote excede el presupuesto, `REQUIRE_AUTH`/`CONFIRMED_NEEDS_WALLET_AUTH`; si no, `PAY`/`CONFIRMED`. Usa el mismo cálculo de exceso que hoy.
     3. `phrase_score >= min` y voz no verificada (`BELOW_THRESHOLD`, `NOT_AVAILABLE` o voice None) ⇒ `ASK_PIN`/`CHALLENGE_VOICE_NOT_VERIFIED`.
     4. Frase que no coincide (`phrase_score` None o `< min`) con `challenge_attempts == 0` ⇒ `ASK_CONFIRM`/`CHALLENGE_RETRY`.
     5. Resto ⇒ `REJECT`/`CHALLENGE_FAILED`.
   - El borde es inclusivo: 0.80 cuenta como coincidencia.
   - Con `mode == REPLY` o `confirmation` None, la fase CONFIRMATION queda EXACTAMENTE como hoy.
   - En fase `PIN`: si `pin.result == OK`, `confirmation.mode == CHALLENGE` y `phrase_score >= min` ⇒ con exceso, `REQUIRE_AUTH`/`CONFIRMED_NEEDS_WALLET_AUTH`; si no, `PAY`/`CONFIRMED_WITH_PIN`. El resto de la fase PIN no cambia: el bloqueo sigue ganando primero, y PIN incorrecto, agotado o con formato inválido siguen igual.
   - Invariante de seguridad (SEG-3): `PAY` solo puede salir de (a) CONFIRMATION en modo REPLY con "sí", (b) CONFIRMATION en modo CHALLENGE con frase que coincide y voz VERIFIED, o (c) PIN OK tras un desafío con frase que coincide. Ningún otro camino, tampoco en fase COMMAND.
   - `config.confirmation_challenge` NO lo evalúa el motor: decidir el modo es trabajo del orquestador. El motor solo lee `confirmation.mode`. Documéntalo en el README.
4. **`say_map.py`**:
   - `ALL_CHECKS_PASSED` y `PENDING_PAYMENT_UNCONFIRMED` con `mode == CHALLENGE` ⇒ `CONFIRM_CHALLENGE` (sin exceso) o `CONFIRM_CHALLENGE_OVERRUN` (con exceso). Con REPLY o None quedan como hoy.
   - `PIN_CORRECT` con CHALLENGE no se emite: no hay mapeo nuevo, así que deja el actual.
   - `CHALLENGE_RETRY` ⇒ `CHALLENGE_RETRY`; `CHALLENGE_FAILED` ⇒ `CHALLENGE_FAILED`; `CHALLENGE_VOICE_NOT_VERIFIED` ⇒ `PIN_KEYBOARD`; `CONFIRMED_WITH_PIN` ⇒ ninguna situación, igual que `CONFIRMED`.
   - IMPORTANTE: las 4 situaciones nuevas (`CONFIRM_CHALLENGE`, `CONFIRM_CHALLENGE_OVERRUN`, `CHALLENGE_RETRY`, `CHALLENGE_FAILED`) todavía NO existen en `api/voice/phrases.py`, porque son de Sebastián. NO toques `api/voice/`. Devuelve el NOMBRE de la situación como string, igual que hoy con las situaciones que faltaban. Si hoy hay una prueba que exige que cada situación exista en `Situation`, marca solo esas 4 como pendientes de Voz con un set explícito `PENDING_VOZ_SITUATIONS` y una prueba que falle si alguna de esas 4 ya existe en `Situation` sin quitarse del set.

## Pruebas (antes del código)
Suponemos los resultados de la parte de Sebastián: `phraseScore` es un número dado. Sebastián prueba `phrase_match` por su lado; tú NO implementes coincidencia de texto. Casos mínimos, en un archivo nuevo `tests/decision/test_engine_challenge.py`, reusando `decision_fixtures.py`:
- Los 9 escenarios del requisito "Confirmación con desafío de voz": desafío correcto ⇒ PAY; con exceso ⇒ REQUIRE_AUTH; borde 0.80 coincide; 0.7999 no coincide; frase correcta + voz BELOW_THRESHOLD / NOT_AVAILABLE / None ⇒ ASK_PIN; frase mala con 0 intentos ⇒ CHALLENGE_RETRY; con 1 y con 5 ⇒ CHALLENGE_FAILED; phraseScore None ⇒ tratado como no coincidente; "no" gana aunque la frase coincida; grabación (frase mala) ⇒ retry y luego reject; modo REPLY ⇒ igual que hoy; confirmation None ⇒ igual que hoy.
- Fase PIN tras el desafío: OK ⇒ PAY/CONFIRMED_WITH_PIN; OK con exceso ⇒ REQUIRE_AUTH; OK con frase que NO coincide ⇒ comportamiento actual (ASK_CONFIRM/PIN_CORRECT); bloqueado gana; WRONG, EXHAUSTED e INVALID_FORMAT sin cambios.
- Propiedad SEG-3: barre combinaciones (fase × modo × reply × phraseScore {None, 0, 0.79, 0.8, 1} × voice status × pin result × attempts) y comprueba que `PAY` solo sale de los tres caminos permitidos.
- Determinismo: el mismo context da la misma decisión.
- `context_io`: un JSON válido con `confirmation`; y que falle cerrado con phraseScore 1.5, -0.1, "0.9", true y NaN; con challengeAttempts -1, 1.0 y true; con un mode desconocido; y con la clave mode faltante. El error no debe contener el valor.
- `say_map`: los mapeos nuevos de arriba.
- Todas las pruebas existentes deben seguir pasando sin modificarlas, salvo la ampliación justificada del conteo de reasons (28 ⇒ 32). Si tienes que cambiar otra prueba existente, dime cuál y por qué.

## Al terminar
Corre desde `api/`: `PYTHONPATH=. python -m unittest discover -s tests/decision` y la suite completa (`PYTHONPATH=. python -m pytest tests -q`). Actualiza `README-ml2.md`: cómo arma el orquestador `confirmation`, que el modo lo decide el orquestador, y la nota de las 4 situaciones pendientes de Voz. Repórtame:
- los archivos tocados;
- los números de las pruebas;
- cualquier duda o desviación.

Daniel ejecutará las pruebas él mismo antes de integrar, así que deja los comandos exactos en tu reporte.
````

### B12 — Experimento X-7: frases del banco del desafío (17 oct)

````text
Instrucción de Daniel (ML 2), B12: experimento **X-7, frases del banco del desafío**. Va FUERA del repo, en `C:\Users\danie\Desktop\Hackatons\Interledger\Pruebas ML2\experimentos_h2\`, con el mismo estilo que x1, x2 y x6: reusa `lab.py` y su `--simular`, `--device` y `--list-devices`. No toques el repo EZPAY (léelo solamente), no hagas commits y no leas ni abras archivos `.npy`, audio ni grabaciones existentes: solo cárgalos desde código para comparar.

## Pregunta que responde
Con el desafío de confirmación, la persona repite una frase del banco de 6 a 9 palabras, y su voz se verifica con `verify`. Hay que saber dos cosas:
1. ¿Las frases dan al menos `minVerifySeconds` = 2.0 s de voz útil? Si no, la verificación da `NOT_AVAILABLE` y el motor pide PIN siempre.
2. ¿El umbral de 0.45 sigue separando a la persona genuina de los impostores con frases de ese largo?

## `x7_desafio.py --persona <nombre> [--frases N] [--semilla S] [--transcribir]`
- **Banco.** Léelo del repo, por defecto de `C:\Users\danie\Desktop\Hackatons\Interledger\EZPAY\api\voice\challenge_phrases.json`, con `--banco` para cambiar la ruta. Usa `voice.challenge.load_bank` si se puede importar (agrega el `api/` del repo a `sys.path` solo para importar). Si no se puede, lee el JSON con la misma validación.
- **Qué frases.**
  - Por defecto: TODAS las frases de 6 palabras (las de más riesgo) y, al azar, otras hasta completar `--frases`, que por defecto es 12. Usa `--semilla`, por defecto 7, para que todas las personas lean LAS MISMAS frases en el mismo orden.
  - `--frases 0` significa todo el banco.
- **Toma.** Por cada frase: `mostrar_frase` y `grabar_con_revision`, con el aviso de hablar después de "● GRABANDO". Pide leerla con naturalidad, a ritmo normal.
- **Medidas por toma.** Usa el mismo procesamiento de la calibración: `trim_silence(frame=320, pad=0.25)`, y voz útil = `len(recortado) / 16000`, incluido el margen.
  - `voz_util_s`;
  - `bajo_min`: `voz_util_s < 2.0`, configurable con `--min-verify`;
  - `palabras` y `palabras_por_s`;
  - `score` contra la huella promedio (estrategia A) de CADA persona en `resultados/huellas/` (las de x1), con `genuino` = (huella == persona);
  - veredicto a `--umbral`, por defecto 0.45: `VERIFIED`, `BELOW_THRESHOLD` o `NOT_AVAILABLE` (este último si `bajo_min`, igual que `verify`);
  - latencia del embedding.

  Si la persona no tiene huella en `resultados/huellas/`, avisa y sigue: sus tomas solo sirven como impostor contra las demás.
- **`--transcribir` (opcional).** Transcribe en LOCAL con el motor local de Voz del repo (faster-whisper `base`, sin red, nunca Groq) y calcula `phrase_match(transcripción, frase)` de `voice.challenge`. Guarda SOLO el puntaje (`phrase_score`), nunca el texto transcrito. Si el motor local no carga, deja la columna vacía y sigue.
- **Salida.** `resultados/x7.csv`, con una fila por (toma, huella). Campos: `hablante`, `huella`, `genuino`, `frase_id` (el índice en el banco), `palabras`, `voz_util_s`, `bajo_min`, `palabras_por_s`, `score`, `veredicto`, `latencia_s`, `phrase_score`. La columna `frase_id` es un índice: no escribas el texto de la frase en el CSV (no es dato personal, pero así es más corto).
- **Privacidad.** X-7 NO acepta `--guardar-audio`: si `lab` lo agrega, desactívalo o recházalo. No guarda embeddings de las tomas; el audio vive solo en memoria.

## `analizar_x7.py` ⇒ `resultados/informe_x7.md` (y lo imprime)
- **Por frase:** mínimo, mediana y máximo de `voz_util_s` entre las personas, y cuántas tomas quedan bajo 2.0 s. Marca la frase para **sacar o alargar** si alguna toma queda bajo 2.0 s, o si la mínima queda bajo 2.2 s (margen de 0.2 s).
- **Global a 0.45:**
  - falsos aceptados (impostor VERIFIED) y falsos rechazados (genuino BELOW_THRESHOLD; los NOT_AVAILABLE se cuentan aparte);
  - genuino mínimo, impostor máximo y margen;
  - las mismas cifras a 0.40, 0.50 y 0.55.
- **Comparación con los comandos de x2.** Si existe `resultados/comandos.csv` (estrategia A, variante completa), compara su genuino mínimo y su impostor máximo con los de X-7 y di si las frases del banco separan peor que los comandos.
- **`phrase_score`** (si hay datos): mínimo y mediana, y cuántas tomas genuinas quedan bajo 0.80.
- **Recomendación** en 3 a 5 líneas:
  - qué frases sacar o alargar;
  - si 0.45 se mantiene para el desafío;
  - si `minVerifySeconds` 2.0 s es compatible con el banco.
  Para cambiar el umbral usa el mismo criterio de antes: 0 falsos aceptados en el umbral propuesto y un margen claro.

## README y pruebas
- Agrega al `README.md` la sección "7) X-7 frases del desafío", con los comandos exactos en PowerShell (desde `Pruebas ML2`) para daniel, sebastian y alex, y la tabla de archivos (`x7.csv`, `informe_x7.md`).
- Prueba en seco: `x7_desafio.py --persona prueba --simular --frases 3` y luego `analizar_x7.py` deben correr de punta a punta sin micrófono.
- Pruebas unitarias pequeñas, si las otras las tienen; si no, al menos las funciones puras del análisis probadas con datos sintéticos:
  - la marca de frase corta;
  - el conteo de falsos aceptados y falsos rechazados;
  - que el CSV no contenga texto de transcripción.

Repórtame en un mensaje:
- los archivos creados;
- la salida de la prueba en seco;
- cuántas frases del banco tienen 6 palabras;
- los comandos exactos que Daniel tiene que correr.

Pausa ahí.
````

---

Registro: 2026-10-16 · textos tomados de los mensajes enviados desde la sesión "Hachathon Interledger EZPAY" a los agentes `a0e9fa5f` (Constructor de Specs) y `c23437fd` (Builder). Los mensajes de estado sin instrucciones nuevas no se incluyen.
