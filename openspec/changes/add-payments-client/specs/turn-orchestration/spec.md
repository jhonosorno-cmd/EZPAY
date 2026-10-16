# Spec Delta — turn-orchestration

## Purpose

Orquestador del turno, parte del esqueleto FastAPI (dueño: rol Pagos; Spec general
§7). Ejecuta el flujo del turno: intención (ML 1) → agenda de contactos → verificación de voz
(ML 2) → quote con el cliente de Node (capability `payments-client`) → motor de decisión
(ML 2) → transición de `TurnState` y llamadas a Node.

**Estado del acuerdo con ML 2:** la lista de `Decision` quedó acordada con ML 2 el 2026-10-15
(incluye `REASK`). El 2026-10-16 el equipo aceptó D3 (texto y usuario no enrolado piden PIN), D4
(solo se verifica el comando), D9 (`previouslyPaid`) y el puntaje de confianza por pipeline
(`docs/decisiones.md`). Los nombres exactos de los campos de `context` se cierran con ML 2 en
`add-decision-engine`. Los
umbrales del motor (similitud de voz, "monto bajo") siguen siendo decisión de ML 2 (Spec general
§7). Este spec fija la forma de la colaboración, no los umbrales ni el contenido exacto del
contexto.

Fuente de verdad: los Contratos HTTP v1 y los principios del Spec general (§4, SEG-1 a SEG-6).

## ADDED Requirements

### Requirement: Flujo del turno
El orquestador SHALL ejecutar el turno en orden: intención (ML 1) → agenda de contactos →
verificación de voz (ML 2) → quote con el cliente de Node → motor de decisión (ML 2) →
transición de `TurnState` y llamadas a Node. La respuesta final respeta el `TurnResponse` del
Contrato B.

#### Scenario: Turno de pago completo
- **GIVEN** un comando de pago por voz
- **WHEN** se procesa el turno
- **THEN** el orquestador pasa por intención, agenda, verificación de voz, quote, motor y
  transición, en ese orden

### Requirement: La quote se pide antes del motor
El orquestador SHALL pedir la quote al cliente de Node antes de invocar al motor, porque la
decisión necesita el `exceedsRemaining` y el monto de la quote. Excepción (regla 4 de la tabla
de ML 2): si no hay grant de presupuesto activo, el orquestador no cotiza y pasa `quote = null`,
y el motor decide `REQUIRE_AUTH` (SEG-1).

#### Scenario: El contexto incluye la quote
- **GIVEN** un comando de pago con intención completa y verificación de voz superada
- **WHEN** el orquestador invoca al motor
- **THEN** el `context` incluye la quote ya creada, con su `exceedsRemaining`

#### Scenario: Sin grant de presupuesto
- **GIVEN** un comando de pago sin grant de presupuesto activo
- **WHEN** el orquestador invoca al motor
- **THEN** el `context` trae `quote = null` y `hasBudgetGrant: false`
- **AND** el motor decide `REQUIRE_AUTH`, sin llamada de quote

### Requirement: Motor como función pura
El motor SHALL invocarse como función pura `decide(context) -> Decision`, sin HTTP ni acceso a
Node. La lista de `Decision`, acordada con ML 2 (2026-10-15): `REASK`, `ASK_RECIPIENT`,
`ASK_PIN`, `ASK_CONFIRM`, `REQUIRE_AUTH`, `PAY`, `REJECT`. El orquestador mapea cada `Decision`
a un `TurnState` y ejecuta las llamadas a Node que correspondan; `REASK` se mapea a
`AWAITING_COMMAND` (intención confusa o destinatario fuera de la agenda).

#### Scenario: El motor no tiene efectos secundarios
- **WHEN** el orquestador invoca `decide` con un `context`
- **THEN** la función devuelve una `Decision` sin hacer llamadas HTTP ni llamadas a Node

#### Scenario: Mapeo determinístico
- **WHEN** el motor devuelve la misma `Decision` para el mismo `context`
- **THEN** el orquestador produce siempre el mismo `TurnState`

### Requirement: Tabla de transiciones del turno
El orquestador SHALL mapear cada `Decision` del motor al `TurnState` correspondiente y ejecutar
las llamadas a Node que esa decisión implique. Las transiciones quedan especificadas como
escenarios.

#### Scenario: Destinatario ambiguo
- **GIVEN** una intención con un destinatario que coincide con dos contactos de la agenda
- **WHEN** el motor decide `ASK_RECIPIENT`
- **THEN** el turno pasa a `AWAITING_RECIPIENT_CHOICE` con las `options` (Spec general §4 SEG-4)

#### Scenario: Intención confusa o destinatario fuera de la agenda
- **GIVEN** una intención `UNCLEAR` o un destinatario que no está en la agenda
- **WHEN** el motor decide `REASK`
- **THEN** el turno pasa a `AWAITING_COMMAND` y no paga (Spec general §4 SEG-4)

#### Scenario: Voz dudosa o riesgo
- **GIVEN** una verificación de voz por debajo del umbral (o un monto alto o un destinatario
  nuevo)
- **WHEN** el motor decide `ASK_PIN`
- **THEN** el turno pasa a `AWAITING_PIN` (Spec general §4 SEG-6; los umbrales son de ML 2)

#### Scenario: Todo en orden
- **GIVEN** una intención completa, un destinatario único y la voz verificada
- **WHEN** el motor decide `ASK_CONFIRM`
- **THEN** el turno pasa a `AWAITING_CONFIRMATION` con el `say` del `receiveAmount` y el
  destinatario

#### Scenario: Sí dentro del presupuesto
- **GIVEN** una quote con `exceedsRemaining: false` y la confirmación "sí"
- **WHEN** el motor decide `PAY`
- **THEN** el orquestador paga con el cliente de Node y el turno termina en `COMPLETED`, en
  `PAYMENT_PENDING` o en `REJECTED`, según el resultado del pago

#### Scenario: Sí con exceso de límite
- **GIVEN** una quote con `exceedsRemaining: true` y la confirmación "sí"
- **WHEN** el motor decide `REQUIRE_AUTH`
- **THEN** el turno pasa a `AWAITING_AUTHORIZATION` con el grant puntual del exceso (capability
  `payments-client`)

#### Scenario: Respuesta que no es un sí claro
- **GIVEN** el turno esperando la confirmación hablada
- **WHEN** la respuesta es silencio, duda o ruido
- **THEN** el orquestador repregunta una vez y el turno sigue en `AWAITING_CONFIRMATION`
- **AND** si la segunda respuesta tampoco es un "sí" claro, el motor decide `REJECT` y el turno
  pasa a `REJECTED` (Spec general §4 SEG-2)

### Requirement: Decisión sobre el pago pendiente
El `context` del motor SHALL incluir el pago pendiente (`pendingPayment`: destinatario, creación
y estado) cuando el cliente lo expone. La decisión de bloquear o pedir la confirmación
reforzada la toma el motor. **Propuesta de Pagos: tope de 2 minutos** desde que se creó el pago;
el umbral final lo confirma ML 2.

#### Scenario: Dentro del tope al mismo destinatario
- **GIVEN** un `context` con `pendingPayment` al mismo destinatario del comando, dentro del tope
  propuesto
- **WHEN** el motor decide
- **THEN** el pago nuevo no se ejecuta mientras el pendiente siga abierto

#### Scenario: Otro destinatario dentro del tope
- **GIVEN** un `context` con `pendingPayment` a un destinatario distinto del comando
- **WHEN** el motor decide
- **THEN** el pago nuevo sigue su curso normal

#### Scenario: Pasado el tope con un sí claro
- **GIVEN** un `context` con `pendingPayment` al mismo destinatario, pasado el tope propuesto
- **WHEN** la usuaria pide otro envío y responde un "sí" claro al aviso de envío sin confirmar
- **THEN** se ejecuta como intención nueva: quote nueva y `Idempotency-Key` nueva

### Requirement: Comando por texto sin verificación de voz
Un comando que llega como `text` SHALL pasarse al motor con la verificación de voz
`NOT_AVAILABLE`, y el motor SHALL decidir `ASK_PIN` (regla de ML 2). Solo esto: el ruteo y la
protección del PIN se especifican después (Open Questions A7).

#### Scenario: Texto pide PIN
- **GIVEN** un comando que llega como `text`
- **WHEN** el orquestador invoca al motor
- **THEN** la verificación de voz del `context` es `NOT_AVAILABLE`
- **AND** el motor decide `ASK_PIN`

### Requirement: Usuario no enrolado
El orquestador SHALL indicar en `context` si el usuario tiene huella de voz enrolada. Si no la
tiene, la verificación de voz es `NOT_AVAILABLE` y el motor decide `ASK_PIN` (D3).

#### Scenario: Comando por voz sin enrolamiento
- **GIVEN** un usuario sin huella de voz enrolada
- **WHEN** llega un comando de pago por voz
- **THEN** el `context` indica que el usuario no está enrolado
- **AND** el motor decide `ASK_PIN`

### Requirement: Solo se verifica la voz del comando
La verificación de voz SHALL correr solo sobre el comando. En `AWAITING_CONFIRMATION` el
orquestador MUST NOT verificar la voz del "sí": usa el resultado de la verificación del comando
(D4).

#### Scenario: Confirmación sin verificación
- **GIVEN** un comando cuya voz ya se verificó
- **WHEN** llega el "sí" en `AWAITING_CONFIRMATION`
- **THEN** no se llama a la verificación de voz
- **AND** el `context` conserva el resultado de la verificación del comando

### Requirement: Puntajes de confianza en el contexto
El orquestador SHALL pasar al motor el puntaje de confianza de la transcripción y el de la
extracción de intención que entregan los pipelines de ML 1. Los cortes los fija el rol Voz; el
orquestador no los interpreta.

#### Scenario: Puntajes disponibles para el motor
- **GIVEN** un comando por voz transcrito y con intención extraída
- **WHEN** el orquestador invoca al motor
- **THEN** el `context` incluye el puntaje de confianza de la transcripción y el de la intención

### Requirement: PIN incorrecto
Ante un PIN incorrecto, el orquestador SHALL responder `AWAITING_PIN` con un `say` que indica los
intentos restantes, sin códigos HTTP nuevos. Al agotar los intentos de la sesión, responde
`REJECTED` y no paga. El conteo de intentos lo lleva el componente de PIN de ML 2.

#### Scenario: Primer intento fallido
- **GIVEN** el turno en `AWAITING_PIN`
- **WHEN** la usuaria envía un PIN incorrecto por primera vez en la sesión
- **THEN** el turno responde `AWAITING_PIN`
- **AND** el `say` indica que quedan 2 intentos

#### Scenario: Intentos agotados
- **GIVEN** dos intentos fallidos en la sesión
- **WHEN** la usuaria envía otro PIN incorrecto
- **THEN** el turno responde `REJECTED`
- **AND** no se paga

### Requirement: Audio en `AWAITING_PIN`
Si llega `audio` en `AWAITING_PIN`, el orquestador MUST NOT transcribirlo ni enviarlo a ningún
servicio (tampoco a Whisper ni a un proveedor externo): lo descarta, responde `AWAITING_PIN` con
un `say` que pide escribir el PIN en el teclado y `transcript` es `null`.

#### Scenario: Audio descartado
- **GIVEN** el turno en `AWAITING_PIN`
- **WHEN** llega `POST /turns` con `audio`
- **THEN** no se llama a la transcripción (ni local ni a un proveedor externo)
- **AND** el turno responde `AWAITING_PIN` con el `say` del teclado

#### Scenario: Sin transcripción
- **GIVEN** la respuesta del turno con el audio descartado
- **WHEN** se inspecciona el `TurnResponse`
- **THEN** `transcript` es `null`

### Requirement: Logs del turno sin el cuerpo del request
Los logs de `POST /api/turns` MUST NOT incluir el cuerpo del request (ni `text` ni `audio`):
solo `requestId`, ruta, estado HTTP, `state` del turno y duración.

#### Scenario: Turno de PIN sin el PIN en los logs
- **GIVEN** un turno en `AWAITING_PIN` con logs habilitados
- **WHEN** la usuaria envía el PIN como `text`
- **THEN** ninguna línea de log contiene el PIN

### Requirement: Dígitos fuera de `AWAITING_PIN`
Un `text` de solo dígitos (4 a 6) que llega cuando el estado del turno NO es `AWAITING_PIN` —
incluida una sesión desconocida o perdida— MUST NOT enviarse a la extracción de intención ni a
ningún LLM o proveedor externo: el turno responde con el estado `AWAITING_COMMAND` (decisión
`REASK`).

#### Scenario: Sesión perdida con dígitos
- **GIVEN** una sesión desconocida o perdida
- **WHEN** llega `POST /turns` con `text: "1234"`
- **THEN** no se llama al LLM ni a la extracción de intención
- **AND** el turno responde con el estado `AWAITING_COMMAND`

### Requirement: Respuesta de un turno de PIN
En un turno de PIN, `transcript` SHALL ser `null` y el `say` nunca contiene dígitos del PIN ni
lo repite.

#### Scenario: Respuesta sin ecos del PIN
- **GIVEN** la respuesta a un turno en `AWAITING_PIN`
- **WHEN** se inspecciona el `TurnResponse`
- **THEN** `transcript` es `null`
- **AND** el `say` no contiene ningún dígito del PIN ni lo repite

### Requirement: Errores sin datos del request
Ningún `error.message` ni log de error incluye datos del request. Ante una excepción en un
turno de PIN, el PIN MUST NOT aparecer en la respuesta ni en los logs.

#### Scenario: Excepción en un turno de PIN
- **GIVEN** un turno en `AWAITING_PIN` cuando ocurre una excepción
- **WHEN** se generan la respuesta de error y sus logs
- **THEN** el PIN no aparece ni en el `error.message` ni en los logs

### Requirement: El PIN nunca sale de Python
El PIN MUST NOT enviarse a Node ni a ningún servicio externo: la validación la hace el
componente de ML 2 dentro del backend Python.

#### Scenario: Validación local del PIN
- **WHEN** la usuaria envía el PIN
- **THEN** no sale ninguna llamada con el PIN fuera del backend Python (ni a Node ni a
  servicios externos)
- **AND** la validación la hace el componente de ML 2 dentro del backend

### Requirement: Historial de pagos por destinatario
El orquestador SHALL llevar el historial de pagos `COMPLETED` por destinatario, alimentado por
`GET /v1/payments/{paymentId}`, y pasarlo en `context` como `previouslyPaid` (decisión D9 de
ML 2). La siembra de Laura como conocida es preparación de la demo, no un pago.

#### Scenario: Destinatario con pago previo
- **GIVEN** un pago `COMPLETED` previo a Laura registrado en el historial
- **WHEN** el orquestador invoca al motor
- **THEN** el `context` marca a Laura en `previouslyPaid`

### Requirement: Elección de destinatario
En `AWAITING_RECIPIENT_CHOICE`, la elección SHALL volver en el siguiente turno como `text` con
el `alias`, o por voz resuelta **solo** contra las `options` de la sesión. **Cambio de contrato
propuesto (requiere el OK de los cuatro):** el Contrato B solo dice que el estado muestra
`options`; la forma de devolver la elección coincide con lo propuesto en C-6 de ML 1. Cualquier
otra respuesta se repregunta.

#### Scenario: Elección por voz fuera de las opciones
- **GIVEN** un turno en `AWAITING_RECIPIENT_CHOICE` con `options` de dos Lauras
- **WHEN** la respuesta por voz menciona un contacto que no está entre las opciones
- **THEN** el orquestador repregunta

### Requirement: Frases de `say` de plantillas, nunca del LLM
Los textos de `say` SHALL salir de plantillas predeterminadas, nunca de un LLM. Pagos define qué
información lleva cada estado (en `payments-client`: antes del "sí", el `receiveAmount` y el
destinatario; después de `COMPLETED`, lo enviado y el costo si existe) y ML 1 escribe las
frases.

#### Scenario: Sin respuestas generadas por LLM
- **WHEN** se inspecciona la construcción de cualquier `say` del turno
- **THEN** el texto sale de una plantilla con valores insertados, nunca lo genera el LLM