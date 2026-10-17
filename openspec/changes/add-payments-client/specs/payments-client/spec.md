# Spec Delta — payments-client

## Purpose

Cliente de Node que vive dentro del backend Python. Es dueño el rol Pagos según el
Spec general §7: llamadas al Contrato A, reglas de `Idempotency-Key`, reautorización ante
exceso de límite y polling de pagos. Esta capability cubre lo observable de ese cliente frente
a Node (`docs/contratos-http-v1.md`); no cubre el lado servidor
(capability `payments-service`) ni la voz, la intención ni la agenda del backend Python. La
orquestación del turno (flujo, motor y transiciones de `TurnState`) vive en la capability
hermana `turn-orchestration`, también parte de este cambio.

Fuente de verdad: los Contratos HTTP v1, decisión del equipo; ningún requisito de acá los
contradice. Convenciones de los escenarios: los montos están en COP con `assetScale: 2` (por
ejemplo, "20.00" es `{ value: "2000" }`); "Node" es el microservicio de pagos real o su mock del
Contrato A; la "intención pendiente" es el par receptor + `receiveAmount` que el usuario ya
confirmó.

Nota de evidencia (sin inventar números): en la única medición disponible (E2,
`pagos-node/experimentos/capturas/e2-e3-errores.json`) el pago se completó entre la primera y la
segunda consulta, con 1 s de diferencia; el `resource-server.yaml` de Open Payments solo define
`failed` + `sentAmount`, sin tope de tiempo. `PAYMENT_PENDING` debería ser raro, pero queda
cubierto.

Nota: pagar con la quote original tras la reautorización (opción a) queda como mejora futura:
requiere `grantId` en `POST /payments` (el Contrato A no lo acepta hoy) y comportamiento por
[VERIFICAR] en Open Payments.

## ADDED Requirements

### Requirement: Una clave de idempotencia por intención de pago
Cada intención de pago SHALL llevar una `Idempotency-Key` nueva, generada como UUID, en el
header de `POST /v1/payments` (Contratos § Contrato A › `POST /payments`). Nueva intención
significa nueva quote: después de reautorizar y recotizar, el pago de la quote nueva MUST usar
otra clave, nunca la del intento anterior.

#### Scenario: Clave nueva por cada quote
- **GIVEN** dos pagos sucesivos al mismo destinatario, cada uno con su quote
- **WHEN** el cliente envía cada `POST /v1/payments`
- **THEN** cada request usa una `Idempotency-Key` UUID distinta

#### Scenario: Clave nueva tras reautorizar y recotizar
- **GIVEN** un pago interrumpido por un exceso de límite que terminó en reautorización
- **WHEN** el usuario aprueba en la wallet, el flujo recotiza y vuelve a pagar
- **THEN** el `POST /v1/payments` usa una `Idempotency-Key` distinta de la usada antes de
  reautorizar

### Requirement: Reintento con la misma clave ante resultado incierto o pago en curso
Ante `502 UPSTREAM_ERROR` o `409 PAYMENT_IN_PROGRESS` de `POST /v1/payments`, el cliente SHALL
reintentar con la **misma** `Idempotency-Key` y el **mismo** `quoteId`: hasta **3 intentos**,
con espera de 0,5 s antes del segundo y de 1 s antes del tercero, dentro de un máximo total de
**15 s** desde el primer intento. MUST NOT generar una clave nueva para ese `quoteId`. Si se
agota sin `201`, el turno pasa a `PAYMENT_PENDING`, no a `REJECTED`.

#### Scenario: Reintento tras 502
- **GIVEN** un `POST /v1/payments` con la clave K y la quote Q que respondió `502 UPSTREAM_ERROR`
- **WHEN** el cliente reintenta
- **THEN** lo hace con la clave K y la quote Q, sin generar una clave nueva

#### Scenario: Reintento tras pago en curso
- **GIVEN** un primer `POST /v1/payments` con la clave K cuyo intento sigue en proceso y
  respondió `409 PAYMENT_IN_PROGRESS`
- **WHEN** el cliente reintenta
- **THEN** lo hace con la clave K y el mismo `quoteId`

#### Scenario: Tres 502 seguidos
- **GIVEN** tres intentos de `POST /v1/payments` con la misma clave y el mismo `quoteId`, todos
  con `502 UPSTREAM_ERROR`
- **WHEN** se agotan los 3 intentos o los 15 s
- **THEN** el turno queda en `PAYMENT_PENDING`, no en `REJECTED`
- **AND** no se genera una clave nueva

### Requirement: Error interno igual que upstream error
`500 INTERNAL_ERROR` de Node SHALL tratarse igual que `502 UPSTREAM_ERROR` (Contratos § Tipos
compartidos). Si ocurrió durante `POST /v1/payments`, el reintento conserva la misma
`Idempotency-Key` y el mismo `quoteId`.

#### Scenario: 500 al pagar
- **WHEN** `POST /v1/payments` responde `500 INTERNAL_ERROR`
- **THEN** el cliente lo trata igual que `502 UPSTREAM_ERROR`
- **AND** el reintento usa la misma `Idempotency-Key` y el mismo `quoteId`

### Requirement: Quote no encontrada no se recotiza automáticamente
Ante `404 QUOTE_NOT_FOUND` de `POST /v1/payments`, el cliente MUST NOT recotizar
automáticamente (Contratos § Contrato A › `POST /payments`: una quote ya pagada, o con un pago
de resultado incierto, responde así a cualquier clave nueva). Qué se comunica al usuario lo
decide el motor del turno, no este cliente.

#### Scenario: Quote ya usada o con resultado incierto
- **GIVEN** una quote que ya se pagó con otra clave, o que quedó con un pago de resultado
  incierto
- **WHEN** `POST /v1/payments` responde `404 QUOTE_NOT_FOUND`
- **THEN** el cliente no crea una quote nueva automáticamente

### Requirement: Quote vencida admite recotizar
Ante `409 QUOTE_EXPIRED` de `POST /v1/payments`, recotizar es seguro porque el servidor no creó
el pago (Contratos § Contrato A › `POST /payments`). El cliente SHALL pedir una quote nueva
conservando la intención pendiente (receptor y `receiveAmount`), y el pago de esa quote nueva
usa una `Idempotency-Key` nueva. La recotización no repite la confirmación hablada, salvo que
la quote nueva tenga `exceedsRemaining: true`.

#### Scenario: Recotización tras quote vencida
- **WHEN** `POST /v1/payments` responde `409 QUOTE_EXPIRED`
- **THEN** el cliente pide una quote nueva con el mismo receptor y el mismo `receiveAmount`
- **AND** el pago posterior de esa quote usa una `Idempotency-Key` nueva

### Requirement: Reautorización puntual por exceso de límite
Ante `exceedsRemaining: true` en la quote, o `403 LIMIT_EXCEEDED` de `POST /v1/payments`, el
cliente SHALL pedir un **grant puntual**: `POST /v1/grants` con `limit.debitAmount` igual al
`debitAmount` de la quote que excedió y `limit.interval` semanal de una repetición; el turno
pasa a `AWAITING_AUTHORIZATION`. Tras el callback y el `/continue` exitoso, recotiza con el
`grantId` del puntual; si la quote nueva entra, paga con clave nueva. El grant de presupuesto
queda intacto.

#### Scenario: Señal preventiva en la quote
- **GIVEN** una quote con `exceedsRemaining: true` y la confirmación hablada del usuario ("sí")
- **WHEN** se procesa esa confirmación
- **THEN** el cliente pide el grant puntual con `POST /v1/grants` y el turno responde
  `AWAITING_AUTHORIZATION` con `interactUrl`
- **AND** no se llama a `POST /v1/payments` con el grant de presupuesto

#### Scenario: Grant puntual con números
- **GIVEN** un grant de presupuesto con límite de 200.00 y 180.00 restantes
- **WHEN** la quote del pedido de 300.00 tiene `debitAmount` de 300.00 y `exceedsRemaining: true`,
  y el usuario dice "sí"
- **THEN** el grant puntual se pide con `debitAmount` de 300.00 y `limit.interval` `R1/<hoy 00:00:00Z>/P1W`
  (decisión #1 del 16 oct; la Test Wallet lo acepta y lo devuelve, ver
  `payments/experiments/weekly-interval-and-token.md`, sección P1)
- **AND** después del pago con el grant puntual, `GET /v1/grants/{grant de presupuesto}` sigue
  mostrando 180.00 restantes

#### Scenario: Límite excedido al pagar
- **WHEN** `POST /v1/payments` responde `403 LIMIT_EXCEEDED`
- **THEN** el cliente pide el grant puntual (mismo `debitAmount` de la quote, con `limit.interval` `R1/<hoy 00:00:00Z>/P1W`)
- **AND** el turno pasa a `AWAITING_AUTHORIZATION` sin pagar con el grant de presupuesto

#### Scenario: Recotización después del callback
- **GIVEN** un turno `AWAITING_AUTHORIZATION` esperando el grant puntual, con la intención
  pendiente conservada
- **WHEN** llega `POST /grant-callback` y el `POST /v1/grants/{grantId}/continue` termina con el
  grant puntual `ACTIVE`
- **THEN** el cliente pide una quote nueva usando el `grantId` del grant puntual
- **AND** si la quote nueva entra en el puntual, el pago posterior usa una `Idempotency-Key`
  nueva

### Requirement: Recotización con débito cambiado
Tras el callback y el `/continue` exitoso del grant puntual, el cliente recotiza con el
`grantId` del puntual. Si la quote nueva tiene `exceedsRemaining: true` contra el puntual (el
débito subió), el cliente MUST NOT pagar con ese grant: cancela el puntual, pide otro por el
`debitAmount` de la quote nueva y el turno pasa a `AWAITING_AUTHORIZATION`, con un `say` que no
menciona el costo ni el monto debitado.

#### Scenario: La quote nueva ya no entra en el puntual
- **GIVEN** un grant puntual de 301.500 recién activado
- **WHEN** la quote nueva (mismo `receiveAmount`) tiene `debitAmount` de 301.600 y
  `exceedsRemaining: true`
- **THEN** el cliente no paga, cancela el puntual y pide otro con `debitAmount` de 301.600
- **AND** el turno pasa a `AWAITING_AUTHORIZATION`

#### Scenario: El say no menciona el débito
- **WHEN** el turno pide la nueva autorización tras el cambio de débito
- **THEN** el `say` no menciona el costo ni el monto debitado (por ejemplo, "El monto a debitar
  cambió; necesito que lo autorices de nuevo en tu billetera")

#### Scenario: Quote que sí entra
- **GIVEN** una quote nueva con `exceedsRemaining: false` contra el grant puntual
- **THEN** el pago continúa normal con una `Idempotency-Key` nueva

### Requirement: Cancelación del grant puntual
El cliente SHALL cancelar el grant puntual con `DELETE /v1/grants/{grantId}` (cambio de
contrato propuesto) después de un pago `COMPLETED` con ese grant, cuando la intención pendiente
se descarta (rechazo, "no" claro, sesión terminada) y cuando lo reemplaza otro puntual. MUST NOT
cancelar el grant de presupuesto por esta vía. Si el `DELETE` falla, no bloquea el turno: se
registra y sigue. Si el pago quedó `PAYMENT_PENDING`, la cancelación espera a que el pago se
resuelva.

#### Scenario: Cancelación después de un pago completado
- **GIVEN** un pago `COMPLETED` pagado con un grant puntual
- **WHEN** el turno termina
- **THEN** el cliente llama a `DELETE /v1/grants/{grantId}` del grant puntual

#### Scenario: Intención descartada
- **GIVEN** un turno `AWAITING_AUTHORIZATION` esperando el grant puntual
- **WHEN** la intención se descarta (el usuario rechaza o la sesión termina)
- **THEN** el cliente cancela el grant puntual y no lo deja `ACTIVE`

#### Scenario: Fallo de cancelación no bloquea
- **GIVEN** un pago `COMPLETED` con grant puntual
- **WHEN** el `DELETE` responde `502 UPSTREAM_ERROR`
- **THEN** el turno continúa normalmente y el fallo queda registrado

#### Scenario: Pago pendiente difiere la cancelación
- **GIVEN** un pago `PAYMENT_PENDING` pagado con el grant puntual
- **WHEN** el pago todavía no se resuelve
- **THEN** el puntual no se cancela todavía; se cancela cuando el pago se resuelve

### Requirement: Grant de presupuesto inválido
Ante un `401 GRANT_INVALID` con el grant de presupuesto (también desde `POST /v1/quotes`, por
derivación de la regla de los Contratos), el cliente SHALL pedir un **grant de presupuesto
nuevo** con `limit.debitAmount` igual al `remaining` del grant que falló, consultado con
`GET /v1/grants/{grantId}`, para no devolverle a la usuaria lo ya gastado. Si el grant tenía
`interval`, el criterio del período queda en Open Questions. El turno pasa a
`AWAITING_AUTHORIZATION`.

#### Scenario: Vence el grant de presupuesto
- **WHEN** `POST /v1/quotes` o `POST /v1/payments` con el grant de presupuesto responde
  `401 GRANT_INVALID`
- **THEN** el cliente consulta `GET /v1/grants/{grantId}` y pide el grant de presupuesto nuevo
  con `limit.debitAmount` igual al `remaining` del grant que falló
- **AND** el turno pasa a `AWAITING_AUTHORIZATION`

### Requirement: Grant puntual inválido
Ante un `401 GRANT_INVALID` del grant puntual, el cliente SHALL pedir **otro grant puntual
igual**: mismo `debitAmount` de la quote que excedió, con `limit.interval` `R1/<hoy 00:00:00Z>/P1W`. El turno pasa a
`AWAITING_AUTHORIZATION`.

#### Scenario: Vence el grant puntual
- **WHEN** `POST /v1/payments` con el grant puntual responde `401 GRANT_INVALID`
- **THEN** el cliente pide otro grant puntual con el mismo `debitAmount` de la quote y sin
  `interval`, y el turno pasa a `AWAITING_AUTHORIZATION`

### Requirement: Sin grant de presupuesto activo (SEG-1)
Si llega un comando de pago y no hay un grant de presupuesto `ACTIVE`, el cliente MUST NOT
cotizar ni pagar: el turno ofrece autorizar el presupuesto con un `POST /v1/grants` de
presupuesto y pasa a `AWAITING_AUTHORIZATION` (Spec general §4 SEG-1). El grant puntual se usa
solo para el exceso, nunca para este caso: sin presupuesto activo no hay quote posible, porque
`POST /v1/quotes` exige un grant activo.

#### Scenario: Comando sin presupuesto autorizado
- **GIVEN** que no hay un grant de presupuesto `ACTIVE`
- **WHEN** el usuario dice "envíale veinte mil a mi hija"
- **THEN** no se llama a `POST /v1/quotes` y no se ejecuta ningún pago
- **AND** el turno responde `AWAITING_AUTHORIZATION` con la `interactUrl` de un grant de
  presupuesto

#### Scenario: El grant puntual no sustituye al presupuesto
- **GIVEN** un grant puntual `ACTIVE` de un exceso anterior, sin grant de presupuesto activo
- **WHEN** llega un comando de pago nuevo
- **THEN** el turno ofrece autorizar el presupuesto y no usa el grant puntual

### Requirement: Decisión por error.code (CONV-2)
El cliente SHALL decidir siempre por `error.code` y nunca por el texto de `error.message`
(Spec general §6 CONV-2; Contratos § Tipos compartidos).

#### Scenario: Message variable, code estable
- **WHEN** Node responde un error cuyo `message` difiere del habitual pero cuyo `code` es el
  esperado
- **THEN** el cliente toma exactamente la misma decisión que con el `message` habitual

### Requirement: Polling del estado del pago
Después de un `POST /v1/payments` aceptado (201), el cliente SHALL consultar
`GET /v1/payments/{paymentId}` hasta que el status sea `COMPLETED` o `FAILED`, con un tiempo
total de alrededor de 10 segundos (Contratos § Contrato B: Python consulta el estado antes de
responder; el frontend nunca hace polling). Si al vencer el timeout el pago sigue `PROCESSING`,
el turno pasa a `PAYMENT_PENDING`; si el pago termina `FAILED`, el turno pasa a `REJECTED`.

#### Scenario: Consulta hasta el estado final
- **GIVEN** un pago creado con `status: "PROCESSING"`
- **WHEN** el polling observa `COMPLETED`
- **THEN** el cliente deja de consultar y el turno continúa con el resultado del pago

#### Scenario: El navegador no participa en el polling
- **GIVEN** un pago en curso
- **WHEN** el frontend espera la respuesta del turno
- **THEN** toda consulta `GET /v1/payments/{paymentId}` sale del backend Python, nunca del
  navegador

### Requirement: Pago pendiente (`PAYMENT_PENDING`)
Se agrega el `TurnState` `PAYMENT_PENDING` al `TurnResponse`. **Cambio de contrato propuesto
(requiere el OK de los cuatro).** El turno SHALL pasar a `PAYMENT_PENDING` si el polling de
~10 s termina con el pago en `PROCESSING` o si se agotan los reintentos sin `201`; incluye el
`payment` si hay `paymentId` y un `say` que informa que el envío está en camino y que no hace
falta repetirlo. Un pago `FAILED` SHALL llevar el turno a `REJECTED`. Cómo sale: requisitos de
verificación y bloqueo.

#### Scenario: Pago en procesamiento al vencer el polling
- **GIVEN** un pago con `paymentId` cuyo status sigue `PROCESSING` al vencer los ~10 s de
  polling
- **WHEN** el turno responde
- **THEN** el estado es `PAYMENT_PENDING`
- **AND** el `say` informa que el envío está en camino y que no hace falta repetirlo

#### Scenario: Reintentos agotados sin pago creado
- **GIVEN** tres intentos de `POST /v1/payments` con la misma clave que terminaron en `502`
- **WHEN** se agota el tope de 15 s
- **THEN** el turno responde `PAYMENT_PENDING` y no `REJECTED`
- **AND** como no hay `paymentId`, el `payment` del turno es `null`

#### Scenario: Pago fallido
- **GIVEN** un pago cuyo polling observa `FAILED`
- **WHEN** el turno responde
- **THEN** el estado es `REJECTED`
- **AND** el `say` informa que el envío falló

### Requirement: Verificación del pago pendiente en la próxima interacción
Antes de procesar cualquier turno nuevo, si hay un pago pendiente, el cliente SHALL consultar
`GET /v1/payments/{paymentId}`: `COMPLETED` → el turno lo informa y continúa con lo pedido;
`FAILED` → informa que el envío falló; `PROCESSING` → el pago sigue pendiente. Si no hay
`paymentId` (reintentos agotados sin `201`), SHALL reintentar `POST /v1/payments` con la
**misma** `Idempotency-Key` y la misma quote, para que Node resuelva el resultado incierto.

#### Scenario: Pendiente que se completa en la próxima interacción
- **GIVEN** un pago `PAYMENT_PENDING` a Laura con `paymentId`
- **WHEN** llega el próximo turno y la verificación observa `COMPLETED`
- **THEN** el turno informa "Ya le llegaron los 20 mil a Laura"
- **AND** continúa procesando lo que la usuaria pidió

#### Scenario: Pendiente que pasa a FAILED
- **GIVEN** un pago `PAYMENT_PENDING` con `paymentId`
- **WHEN** la verificación observa `FAILED` marcado por la wallet
- **THEN** el turno informa que el envío falló

#### Scenario: Pendiente que sigue en procesamiento
- **GIVEN** un pago `PAYMENT_PENDING` con `paymentId`
- **WHEN** la verificación observa `PROCESSING`
- **THEN** el pago sigue pendiente y no se declara fallido

#### Scenario: Reintentos agotados sin paymentId
- **GIVEN** un `PAYMENT_PENDING` sin `paymentId` (los 3 intentos terminaron en `502`)
- **WHEN** ocurre la verificación (próxima interacción o turno automático)
- **THEN** el cliente reintenta `POST /v1/payments` con la misma `Idempotency-Key` y la misma
  quote
- **AND** no genera una clave nueva

### Requirement: Verificación automática única
Unos **20 segundos** después de recibir `PAYMENT_PENDING`, el frontend SHALL enviar **un único**
turno de verificación, sin comando de voz ni texto. **Cambio de contrato propuesto (requiere el
OK de los cuatro).** No es polling: ocurre una sola vez. Python responde con el resultado de la
verificación (requisito anterior).

#### Scenario: Un solo turno automático
- **GIVEN** un turno en `PAYMENT_PENDING`
- **WHEN** pasan unos 20 s
- **THEN** el frontend envía un único turno de verificación y no repite más

### Requirement: Pago pendiente disponible para el motor
Ante cada comando de pago, el cliente SHALL consultar el pago pendiente (si lo hay) y exponer al
orquestador el dato, por ejemplo `pendingPayment: { recipient, createdAt, status }`, para que el
motor de ML 2 decida vía `context` si bloquea el pago o pide la confirmación reforzada. El
cliente no decide el bloqueo por su cuenta: la regla propuesta por Pagos (tope de 2 minutos) y
su umbral final viven en la capability `turn-orchestration`.

#### Scenario: El cliente expone el pago pendiente
- **GIVEN** un pago pendiente a Laura
- **WHEN** llega un comando de pago
- **THEN** el orquestador recibe `pendingPayment` con el destinatario, la fecha de creación y el
  estado del pago pendiente

#### Scenario: La decisión de bloquear no es del cliente
- **GIVEN** un pago pendiente a Laura
- **WHEN** el motor decide permitir un envío a otro destinatario
- **THEN** el cliente lo ejecuta sin bloqueo propio

### Requirement: Sin fallos declarados por tiempo
El sistema MUST NOT declarar fallido un pago por tiempo: `FAILED` SHALL venir solo de la marca
de Open Payments, que Node traduce. Pasado el tope, el mensaje es "no pude confirmar", no
"falló". Declararlo fallido sin evidencia puede terminar en un doble pago si el pago se completa
después.

#### Scenario: Pago completado después del tope
- **GIVEN** un pago que pasó a `PAYMENT_PENDING` y superó los 2 minutos de tope
- **WHEN** una verificación posterior observa `COMPLETED`
- **THEN** el sistema informa que el envío se completó, nunca que falló

### Requirement: Monto que se dice antes de la confirmación
El `say` del turno antes del "sí" menciona el `receiveAmount` y el destinatario ("¿Le envío 20
mil a Laura?") y MUST NOT mencionar el costo ni el débito de la transacción. **Cambio de
contrato propuesto (requiere el OK de los cuatro):** corrige la fila "Pago" de Contratos §
Decisiones, que decía "el monto real debitado".

#### Scenario: Pregunta de confirmación
- **GIVEN** una quote con `receiveAmount` de 2000000 (20 mil) y `debitAmount` de 2015000, en COP
  con escala 2
- **WHEN** el turno pide la confirmación
- **THEN** el `say` menciona 20 mil y el destinatario
- **AND** el `say` no menciona el costo ni el débito

### Requirement: Monto que se dice en el recibo del pago
Tras un pago `COMPLETED`, el `say` SHALL informar lo enviado y, si `debitAmount` difiere de
`receiveAmount` (mismo `assetCode` y `assetScale`), también el costo, calculado como
`debitAmount − receiveAmount` con aritmética entera; si no difieren, no se menciona costo. Tras
recotizar por `409 QUOTE_EXPIRED` el `receiveAmount` no cambia: no se repite el "sí", salvo que
la quote nueva tenga `exceedsRemaining: true`. **Cambio de contrato propuesto (requiere el OK
de los cuatro).**

#### Scenario: Recibo con costo
- **GIVEN** un pago `COMPLETED` con `debitAmount` de 2015000 y `receiveAmount` de 2000000 (COP,
  escala 2)
- **WHEN** el turno informa el resultado
- **THEN** el `say` menciona el envío de 20 mil y el costo de 150
- **AND** el costo sale de `debitAmount − receiveAmount` sin usar `float`

#### Scenario: Recibo sin costo mencionado
- **GIVEN** un pago `COMPLETED` con `debitAmount` igual a `receiveAmount`
- **WHEN** el turno informa el resultado
- **THEN** el `say` no menciona costo

#### Scenario: Recotización no repite el sí
- **GIVEN** un pago rechazado con `409 QUOTE_EXPIRED`
- **WHEN** la quote nueva se crea con el mismo `receiveAmount` y sin exceso
- **THEN** el flujo continúa al pago sin pedir de nuevo el "sí" hablado

### Requirement: Montos sin floats (CONV-1)
El cliente MUST NOT convertir ningún monto a `number`/`float`: usa los `Amount` de Node tal
como llegan y envía los suyos con la forma `{ value, assetCode, assetScale }`, con `value` de
solo dígitos (Spec general §6 CONV-1; Contratos § Tipos compartidos). **Aclaración:** comparar
dos `value` como enteros de Python es aceptable y no constituye una conversión a float; esta
aclaración no modifica CONV-1.

#### Scenario: Comparación entera
- **GIVEN** una comparación de dos montos dentro de Python (por ejemplo, un umbral del motor de
  decisión)
- **WHEN** el cliente compara sus `value`
- **THEN** la comparación se hace como enteros, sin pasar por `float`
- **AND** los dos montos comparten `assetCode` y `assetScale`

#### Scenario: El cliente no recalcula el presupuesto
- **WHEN** el cliente necesita saber si un pago excede el presupuesto restante
- **THEN** usa el `exceedsRemaining` que devuelve la quote
- **AND** no calcula `spent` ni `remaining` por su cuenta (la contabilidad es de Node, Contratos
  § Decisiones)

#### Scenario: Montos sin transformación
- **WHEN** el cliente envía o recibe cualquier `Amount` del Contrato A
- **THEN** conserva `value` como string de solo dígitos, junto a `assetCode` y `assetScale`

### Requirement: Moneda y escala de la demo en configuración
Python SHALL tomar `assetCode` y `assetScale` de la configuración (`ASSET_CODE`, `ASSET_SCALE`;
demo: `COP` y `2`) para construir los montos, porque el Contrato A no los expone (V-17 de la
revisión de ML 1). Si no coinciden con la wallet del receptor, Node responde `400
INVALID_RECEIVER` y el turno lo informa sin pagar. Si falta la configuración, el servicio no
arranca.

#### Scenario: Montos construidos con la configuración
- **GIVEN** `ASSET_CODE: COP` y `ASSET_SCALE: 2`
- **WHEN** Python construye un monto de 20 mil
- **THEN** produce `{ value: "2000000", assetCode: "COP", assetScale: 2 }`

#### Scenario: Moneda que no coincide
- **GIVEN** la wallet del receptor no opera en la moneda configurada
- **WHEN** se pide una quote
- **THEN** Node responde `400 INVALID_RECEIVER`
- **AND** el turno lo informa y no paga

#### Scenario: Falta la configuración
- **WHEN** el servicio arranca sin `ASSET_CODE` o sin `ASSET_SCALE`
- **THEN** no arranca

### Requirement: Propagación de X-Request-Id (CONV-3)
Cada llamada al Contrato A SHALL propagar el header `X-Request-Id` del turno, para que Node lo
escriba en cada línea de su log (Spec general §6 CONV-3).

#### Scenario: Identificador propagado a Node
- **GIVEN** un turno con `X-Request-Id: abc-123`
- **WHEN** el cliente llama a cualquier endpoint del Contrato A
- **THEN** el request lleva el header `X-Request-Id: abc-123`

### Requirement: Secretos fuera del cliente y de sus logs (PRIV-4)
El cliente solo conoce el `grantId` de cada grant: los access tokens, continue tokens y nonces
los guarda Node (Contratos § Decisiones › Estado del grant). Los logs del cliente MUST NOT
contener `interact_ref`, `hash` ni ids internos sensibles (Spec general §5 PRIV-4).

#### Scenario: Logs limpios en el flujo completo
- **WHEN** se ejecuta un pago completo (grant, callback, quote, payment y polling) con los logs
  del cliente habilitados
- **THEN** ninguna línea de log contiene `interact_ref`, `hash` ni valores de tokens

#### Scenario: El cliente no maneja secretos
- **WHEN** el cliente se refiere a un grant en un request o en un log
- **THEN** lo hace solo por su `grantId`

### Requirement: Callback robusto ante rechazo
`POST /api/grant-callback` acepta `{ interactRef?, hash?, result? }` y el frontend reenvía todo
lo que recibió en la URL de `finishUri`. **Cambio de contrato propuesto (requiere el OK de los
cuatro).** Si faltan `interactRef` o `hash`, el cliente MUST NOT llamar a
`POST /v1/grants/{grantId}/continue`: el turno pasa a `REJECTED` con un `say` del estilo "No
autorizaste el envío; no se hizo ningún pago", y la intención pendiente se descarta.

#### Scenario: La wallet informa el rechazo
- **WHEN** llega `/grant-callback` con `result: "grant_rejected"` y sin `interactRef`
- **THEN** el cliente no llama a `/continue`
- **AND** el turno pasa a `REJECTED` y la intención pendiente se descarta

#### Scenario: Callback vacío
- **WHEN** llega `/grant-callback` sin `interactRef`, sin `hash` y sin `result`
- **THEN** el turno pasa a `REJECTED` con el mismo mensaje y no se llama a `/continue`

### Requirement: Reenvío del callback sin validación
`POST /grant-callback` (Contrato B) SHALL reenviar el `interactRef` y el `hash` recibidos del
frontend a `POST /v1/grants/{grantId}/continue` tal como llegan, sin validarlos ni modificarlos:
la verificación del hash es responsabilidad de Node (Contratos § Contrato A ›
`POST /grants/{grantId}/continue`).

#### Scenario: Reenvío sin alteraciones
- **GIVEN** un frontend que llama a `/grant-callback` con `interactRef` y `hash`
- **WHEN** el cliente continúa el grant
- **THEN** `POST /v1/grants/{grantId}/continue` recibe exactamente los valores que envió el
  frontend, sin agregar, quitar ni validar nada

#### Scenario: La validación no es del cliente
- **WHEN** llega `/grant-callback` con un `hash` que no va a pasar la verificación de Node
- **THEN** el cliente igualmente lo reenvía a `POST /v1/grants/{grantId}/continue`
- **AND** quien responde el error (`400 INVALID_HASH`) es Node