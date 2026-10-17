# Spec Delta — payments-service

## Purpose

Microservicio interno que concentra toda la interacción con Open Payments: grants interactivos
con presupuesto limitado, quotes y pagos idempotentes. Su único cliente es el backend Python, a
través del Contrato A (`docs/contratos-http-v1.md`).

Convenciones de los escenarios: los montos están en COP con `assetScale: 2` (por ejemplo,
"100.00" es `{ value: "10000" }`). "Open Payments" se refiere a la Test Wallet real o a un doble
de prueba. Los puntos [VERIFICAR] dependen de los experimentos E2–E4.

## ADDED Requirements

### Requirement: Formato uniforme de errores
Toda respuesta de error SHALL tener el cuerpo `{ "error": { "code": string, "message": string } }`, con un `code` del Contrato A. El `message` es para humanos y el cliente nunca decide según su texto.

#### Scenario: Error con formato del contrato
- **WHEN** cualquier endpoint responde con un status 4xx o 5xx
- **THEN** el cuerpo tiene `error.code` y `error.message`
- **AND** `error.code` es uno de los códigos definidos en el Contrato A

### Requirement: Validación de montos
Todo `Amount` recibido SHALL tener `value` como string de solo dígitos (`^\d+$`) y `assetScale` entero no negativo. Si no, el servicio MUST responder `400 INVALID_AMOUNT` sin llamar a Open Payments. Los montos nunca se redondean ni se convierten en silencio.

#### Scenario: Valor con decimales
- **WHEN** llega `POST /v1/quotes` con `receiveAmount.value = "200.50"`
- **THEN** responde `400 INVALID_AMOUNT`
- **AND** no se hace ninguna llamada a Open Payments

#### Scenario: Valor negativo, vacío o con coma
- **WHEN** llega `POST /v1/grants` con `limit.debitAmount.value` igual a `"-3"`, `""` o `"1,5"`
- **THEN** responde `400 INVALID_AMOUNT`

#### Scenario: Valor numérico en lugar de string
- **WHEN** llega un `Amount` con `value: 20000` (número JSON)
- **THEN** responde `400 INVALID_AMOUNT`

### Requirement: Creación de grant interactivo con límite
`POST /v1/grants` SHALL pedir a Open Payments un grant interactivo de `outgoing-payment` con acciones `create`, `read` y `list`, `limits.debitAmount` igual al del request y `limits.interval` solo si viene. Responde `201` con `grantId` propio, `status: "PENDING"` e `interactUrl`.

#### Scenario: Grant con tope total
- **WHEN** llega `POST /v1/grants` con `limit.debitAmount` de 200.00 y sin `interval`
- **THEN** responde `201` con `status: "PENDING"` y una `interactUrl` no vacía
- **AND** el grant pedido a Open Payments no incluye `interval`

#### Scenario: Grant con tope por período
- **WHEN** llega `POST /v1/grants` con `interval: "R52/2026-10-16T00:00:00Z/P1W"`
- **THEN** el grant pedido a Open Payments incluye ese `interval` sin modificarlo

### Requirement: Wallet del usuario válida
Si la `walletAddress` del request no se puede resolver en Open Payments, `POST /v1/grants` MUST responder `400 INVALID_WALLET`.

#### Scenario: Wallet inexistente
- **WHEN** llega `POST /v1/grants` con una `walletAddress` que Open Payments no reconoce
- **THEN** responde `400 INVALID_WALLET`
- **AND** no se crea ningún grant

### Requirement: Verificación del hash de interacción
Antes de continuar un grant, el servicio MUST recalcular el hash como `base64(sha256(clientNonce + "\n" + interactNonce + "\n" + interactRef + "\n" + grantEndpointUri))`, donde `grantEndpointUri` es el `authServer` de la wallet del remitente, tal como se usó en la solicitud inicial. La salida es Base64 estándar con padding `=`. Si no coincide, responde `400 INVALID_HASH` sin llamar a `grant.continue`.

#### Scenario: Hash correcto
- **GIVEN** un grant PENDING
- **WHEN** llega `POST /v1/grants/{grantId}/continue` con el `hash` que devolvió la wallet
- **THEN** el servicio llama a `grant.continue` con el `interactRef`

#### Scenario: Hash alterado
- **GIVEN** un grant PENDING
- **WHEN** llega `/continue` con un `hash` que difiere en un solo carácter
- **THEN** responde `400 INVALID_HASH`
- **AND** no se llama a `grant.continue` y el grant sigue PENDING

#### Scenario: Diferencia solo en la barra final de la URI
- **GIVEN** un grant pedido a `https://auth.example/` (con barra final)
- **WHEN** se calcula el hash esperado usando `https://auth.example` (sin barra)
- **THEN** los hashes no coinciden y la respuesta es `400 INVALID_HASH`

### Requirement: Continuación del grant
Si el hash es válido y `grant.continue` devuelve un access token, el grant SHALL pasar a `ACTIVE` y la respuesta es `200` con `limit` y `remaining`. Continuar un grant que no está `PENDING` MUST responder `409 GRANT_NOT_PENDING`; un `grantId` desconocido, `404 GRANT_NOT_FOUND`.

#### Scenario: Continuación exitosa
- **GIVEN** un grant PENDING con límite de 200.00
- **WHEN** llega `/continue` con `interactRef` y `hash` válidos
- **THEN** responde `200` con `status: "ACTIVE"` y `remaining` de 200.00

#### Scenario: Continuar dos veces
- **GIVEN** un grant que ya está ACTIVE
- **WHEN** llega otro `/continue` para el mismo `grantId`
- **THEN** responde `409 GRANT_NOT_PENDING`

#### Scenario: Grant desconocido
- **WHEN** llega `/continue` con un `grantId` que no existe
- **THEN** responde `404 GRANT_NOT_FOUND`

### Requirement: Rechazo en la wallet
Si el usuario rechaza la autorización, el grant SHALL pasar a `REJECTED` y `/continue` MUST responder `403 GRANT_REJECTED`. [VERIFICAR] en E3 qué parámetros trae el redirect cuando el usuario rechaza; si no trae `interact_ref` y `hash`, el Contrato B necesita un cambio.

#### Scenario: Usuario rechaza
- **GIVEN** un grant PENDING
- **WHEN** Open Payments indica que el usuario rechazó la interacción
- **THEN** responde `403 GRANT_REJECTED` y el grant queda `REJECTED`

### Requirement: Varios grants activos por usuario
Continuar con éxito un grant nuevo MUST NOT vencer a los demás grants `ACTIVE` del mismo usuario: cada grant conserva su propio `spent`/`remaining` y su propio estado. Cotizar o pagar usa únicamente el grant del `grantId` recibido en el request.

#### Scenario: El grant de presupuesto sobrevive al grant puntual
- **GIVEN** el grant A (de presupuesto, con 180.00 restantes) está ACTIVE
- **WHEN** el grant B (puntual, con tope total de 300.00) del mismo usuario se continúa con éxito
- **THEN** `GET /v1/grants/A` sigue devolviendo `status: "ACTIVE"` con 180.00 restantes
- **AND** crear un pago con el grant B no cambia el `spent` del grant A

### Requirement: Cancelación de un grant
`DELETE /v1/grants/{grantId}` SHALL responder `204` y dejar el grant `EXPIRED` localmente.
Cambio A-1, ratificado. Node cancela el grant en Open Payments con `grant.cancel` (no con
`token.revoke`). Un `grantId` desconocido responde `404 GRANT_NOT_FOUND`; si Open Payments falla,
responde `502 UPSTREAM_ERROR` y el grant igual queda `EXPIRED` localmente, sin usarse de nuevo.
Cancelar un grant ya cancelado responde `204`.

#### Scenario: Cancelación exitosa
- **GIVEN** un grant ACTIVE con su continue URI y su continue token guardados
- **WHEN** llega `DELETE /v1/grants/{grantId}`
- **THEN** responde `204`, el grant queda `EXPIRED` y Node llamó a `grant.cancel` (DELETE sobre la
  continue URI con el continue token), que anula el grant entero

#### Scenario: Cancelar dos veces
- **GIVEN** un grant ya `EXPIRED` por cancelación
- **WHEN** llega otro `DELETE` con el mismo `grantId`
- **THEN** responde `204` de nuevo, sin error

#### Scenario: Grant desconocido
- **WHEN** llega `DELETE` con un `grantId` que no existe
- **THEN** responde `404 GRANT_NOT_FOUND`

#### Scenario: Open Payments falla al cancelar
- **GIVEN** un grant ACTIVE
- **WHEN** `grant.cancel` falla con timeout
- **THEN** responde `502 UPSTREAM_ERROR`
- **AND** el grant igual queda `EXPIRED` localmente y ya no se usa para cotizar ni pagar

### Requirement: Vencimiento de grants pendientes
Un grant que siga `PENDING` más de 10 minutos después de creado SHALL considerarse `EXPIRED`.

#### Scenario: Interacción abandonada
- **GIVEN** un grant creado hace 11 minutos que nunca se continuó
- **WHEN** llega `GET /v1/grants/{grantId}`
- **THEN** devuelve `status: "EXPIRED"`
- **AND** un `/continue` posterior responde `409 GRANT_NOT_PENDING`

### Requirement: Consulta del presupuesto
`GET /v1/grants/{grantId}` SHALL devolver `status`, `limit`, `spent` y `remaining`, con `remaining = limit − spent` en el período vigente. Un `grantId` desconocido MUST responder `404 GRANT_NOT_FOUND`.

#### Scenario: Presupuesto después de un pago
- **GIVEN** un grant ACTIVE con límite de 200.00 y un pago COMPLETED de 60.00
- **WHEN** llega `GET /v1/grants/{grantId}`
- **THEN** `spent` es 60.00 y `remaining` es 140.00

### Requirement: Cómputo del gastado
`spent` SHALL ser el mayor entre el gastado que informa el servidor para el período vigente (`spentDebitAmount`) y la suma local de los `debitAmount` de los pagos `PROCESSING` y `COMPLETED` del período, con aritmética entera exacta. Si el servidor no responde, se usa solo la suma local.

#### Scenario: Pago recién creado que el servidor todavía no refleja
- **GIVEN** el servidor informa 30.00 gastados y localmente hay pagos por 50.00 (el último recién creado)
- **WHEN** se consulta el grant
- **THEN** `spent` es 50.00

#### Scenario: Pago fallido no consume presupuesto (servidor sin gastado informado)
- **GIVEN** el servidor no informa el gastado del grant
- **AND** un grant con límite de 100.00, un pago COMPLETED de 30.00 y un pago FAILED de 50.00
- **WHEN** se consulta el grant
- **THEN** `spent` es 30.00

#### Scenario: Sin errores de redondeo
- **GIVEN** tres pagos COMPLETED de 0.10, 0.20 y 19.99
- **WHEN** se consulta el grant
- **THEN** `spent` es exactamente `{ value: "2029" }`

### Requirement: Presupuesto por período
Si el grant tiene `interval` (`R<n>/<inicio>/<período>`), `spent` SHALL contar solo los pagos del período vigente (`inicio + k·período`). Cuando se agotan las `n` repeticiones, el grant pasa a `EXPIRED`. [VERIFICAR] en E3 que el servidor calcula los períodos igual.

#### Scenario: Cambio de período
- **GIVEN** un grant con `interval` semanal, límite de 200.00 y 150.00 gastados la semana anterior
- **WHEN** se consulta el grant en la semana siguiente
- **THEN** `spent` es 0.00 y `remaining` es 200.00

#### Scenario: Repeticiones agotadas
- **GIVEN** un grant con `interval` `R1/<inicio>/P1D`
- **WHEN** se consulta después de terminado ese único día
- **THEN** devuelve `status: "EXPIRED"`

#### Scenario: Grant puntual semanal vencido no se usa para pagar
- **GIVEN** un grant puntual con `interval` `R1/<inicio>/P1W` al que ya pasaron 8 días desde `<inicio>`
- **WHEN** llega `POST /v1/payments` con ese grant
- **THEN** responde `401 GRANT_INVALID`, el grant queda `EXPIRED` y no se llama a Open Payments
- **AND** el final de la semana no se prueba contra la Test Wallet: lo hace cumplir el servicio

### Requirement: Creación de quote
`POST /v1/quotes` SHALL crear el incoming payment en la wallet del receptor y una quote desde la wallet del usuario por el `receiveAmount` pedido. Responde `201` con `quoteId` propio, `debitAmount`, `receiveAmount`, `expiresAt` y `exceedsRemaining`.

#### Scenario: Quote dentro del presupuesto
- **GIVEN** un grant ACTIVE con 200.00 restantes
- **WHEN** se pide una quote con `receiveAmount` de 20.00 y Open Payments cotiza un débito de 20.15
- **THEN** responde `201` con `debitAmount` de 20.15 y `exceedsRemaining: false`

### Requirement: Señal preventiva de exceso
`exceedsRemaining` SHALL ser `true` si y solo si el `debitAmount` de la quote es estrictamente mayor que `remaining`.

#### Scenario: Gasta exactamente lo que queda
- **GIVEN** un grant con 20.15 restantes
- **WHEN** la quote tiene `debitAmount` de 20.15
- **THEN** `exceedsRemaining` es `false`

#### Scenario: Se pasa por un centavo
- **GIVEN** un grant con 20.14 restantes
- **WHEN** la quote tiene `debitAmount` de 20.15
- **THEN** `exceedsRemaining` es `true`

### Requirement: Receptor válido
Si el `receiver` no se resuelve en Open Payments, o el `assetCode` o `assetScale` de `receiveAmount` no coinciden con los de la wallet del receptor, `POST /v1/quotes` MUST responder `400 INVALID_RECEIVER`.

#### Scenario: Moneda distinta a la del receptor
- **GIVEN** la wallet del receptor está en USD
- **WHEN** se pide una quote con `receiveAmount.assetCode = "COP"`
- **THEN** responde `400 INVALID_RECEIVER`

### Requirement: Grant activo obligatorio para cotizar o pagar
Cotizar o pagar con un grant que no está `ACTIVE` MUST responder `401 GRANT_INVALID`. Un `grantId` desconocido responde `404 GRANT_NOT_FOUND`.

#### Scenario: Cotizar con un grant pendiente
- **GIVEN** un grant PENDING
- **WHEN** llega `POST /v1/quotes` con ese `grantId`
- **THEN** responde `401 GRANT_INVALID`

### Requirement: Idempotency-Key obligatorio
`POST /v1/payments` MUST rechazar con `400 IDEMPOTENCY_KEY_REQUIRED` cualquier request sin header `Idempotency-Key` no vacío, sin crear ningún pago.

#### Scenario: Falta el header
- **WHEN** llega `POST /v1/payments` sin `Idempotency-Key`
- **THEN** responde `400 IDEMPOTENCY_KEY_REQUIRED` y no se llama a Open Payments

### Requirement: Reintento con la misma clave
Un `POST /v1/payments` con una `Idempotency-Key` ya completada y el mismo `quoteId` SHALL devolver exactamente la respuesta original (status y cuerpo) sin crear otro pago.

#### Scenario: Reintento después de un timeout
- **GIVEN** un grant con 100.00 restantes y una quote de 60.00
- **WHEN** llegan dos `POST /v1/payments` secuenciales con la misma clave y el mismo `quoteId`
- **THEN** las dos respuestas son idénticas
- **AND** existe un solo outgoing payment y `remaining` es 40.00

#### Scenario: Reintentos concurrentes
- **WHEN** llegan dos `POST /v1/payments` simultáneos con la misma clave y el mismo `quoteId`
- **THEN** se crea un solo outgoing payment en Open Payments

### Requirement: Clave reutilizada para otra quote
Una `Idempotency-Key` ya registrada usada con un `quoteId` distinto MUST responder `422 IDEMPOTENCY_KEY_REUSED` sin crear ningún pago. **Cambio de contrato.**

#### Scenario: Misma clave, otra quote
- **GIVEN** la clave K ya se usó con la quote Q1
- **WHEN** llega `POST /v1/payments` con la clave K y la quote Q2
- **THEN** responde `422 IDEMPOTENCY_KEY_REUSED` y no se paga Q2

### Requirement: Pago todavía en curso
Si llega un request con una clave cuyo primer intento sigue procesándose, el servicio SHALL esperar hasta 2 segundos su resultado; si termina, devuelve esa respuesta; si no, MUST responder `409 PAYMENT_IN_PROGRESS`. **Cambio de contrato.**

#### Scenario: El primer intento tarda
- **GIVEN** un primer `POST /v1/payments` con la clave K que tarda más de 2 s en Open Payments
- **WHEN** llega un segundo request con la clave K y el mismo `quoteId`
- **THEN** el segundo responde `409 PAYMENT_IN_PROGRESS`
- **AND** existe un solo outgoing payment

### Requirement: Resultado incierto del pago
Si la creación del outgoing payment queda sin respuesta (timeout o caída), el servicio MUST responder `502 UPSTREAM_ERROR`, bloquear la quote para cualquier otra clave y, ante un reintento con la misma clave, buscar el pago en Open Payments antes de volver a crearlo. Nunca debe existir más de un outgoing payment por quote.

#### Scenario: Timeout al crear el pago
- **GIVEN** `outgoingPayment.create` de la quote Q con la clave K excede el timeout, pero el pago sí se creó en el servidor
- **WHEN** Python reintenta con la clave K y la quote Q
- **THEN** responde `201` con ese pago
- **AND** existe un solo outgoing payment para Q

#### Scenario: Otra clave sobre una quote con resultado incierto
- **GIVEN** la quote Q quedó con resultado incierto bajo la clave K
- **WHEN** llega `POST /v1/payments` con la quote Q y una clave nueva K2
- **THEN** responde `404 QUOTE_NOT_FOUND` y no se crea otro pago

#### Scenario: Reinicio con una clave reservada que nunca envió el pago
- **GIVEN** el proceso cayó después de reservar la clave K y antes de enviar el pago
- **WHEN** el servicio reinicia y llega un reintento con la clave K
- **THEN** el pago se procesa normalmente y no responde `409 PAYMENT_IN_PROGRESS`

#### Scenario: Reinicio con un pago enviado sin respuesta guardada
- **GIVEN** el proceso cayó después de enviar el pago de la clave K y antes de guardar la respuesta
- **WHEN** el servicio reinicia y llega un reintento con la clave K
- **THEN** el servicio busca el pago en Open Payments antes de crearlo
- **AND** existe un solo outgoing payment para la quote

### Requirement: Quote vencida o ya usada
Si la quote ya pasó su `expiresAt` guardado, `POST /v1/payments` MUST responder `409 QUOTE_EXPIRED` sin llamar a Open Payments; si el servidor rechaza la quote al crear el pago, también. Una quote ya usada por otro pago, o desconocida, MUST responder `404 QUOTE_NOT_FOUND`.

#### Scenario: Quote vencida
- **GIVEN** una quote con `expiresAt` en el pasado
- **WHEN** llega `POST /v1/payments` con ese `quoteId` y una clave nueva
- **THEN** responde `409 QUOTE_EXPIRED` y no se llama a Open Payments

#### Scenario: El servidor rechaza la quote
- **GIVEN** una quote que localmente sigue vigente
- **WHEN** Open Payments rechaza la creación del pago con `400 "invalid quote"`
- **THEN** responde `409 QUOTE_EXPIRED` y no existe ningún outgoing payment para esa quote

#### Scenario: Quote usada con otra clave
- **GIVEN** la quote Q ya se pagó con la clave K1
- **WHEN** llega `POST /v1/payments` con la quote Q y una clave nueva K2
- **THEN** responde `404 QUOTE_NOT_FOUND` y no se crea un segundo pago

### Requirement: Presupuesto insuficiente
Si el `debitAmount` de la quote supera el `remaining` del grant, `POST /v1/payments` MUST responder `403 LIMIT_EXCEEDED` sin crear el pago. Si Open Payments igual rechaza con su `403` genérico, el servicio recalcula el gastado: si el pago no entra → `403 LIMIT_EXCEEDED`; si entra → `401 GRANT_INVALID`.

#### Scenario: Chequeo local
- **GIVEN** un grant con 10.00 restantes y una quote de 15.00
- **WHEN** llega `POST /v1/payments`
- **THEN** responde `403 LIMIT_EXCEEDED` y no se llama a Open Payments

#### Scenario: 403 del servidor con el tope realmente agotado
- **GIVEN** el chequeo previo permitía el pago, pero Open Payments responde `403 "unauthorized"`
- **AND** al recalcular, el gastado del servidor más el `debitAmount` supera el límite
- **WHEN** llega `POST /v1/payments`
- **THEN** responde `403 LIMIT_EXCEEDED`

#### Scenario: 403 del servidor con presupuesto disponible
- **GIVEN** Open Payments responde `403 "unauthorized"` y, al recalcular, el pago entra en el presupuesto
- **WHEN** llega `POST /v1/payments`
- **THEN** responde `401 GRANT_INVALID`

### Requirement: Pago exitoso
Si todas las validaciones pasan, `POST /v1/payments` SHALL crear el outgoing payment con el access token vigente del grant y responder `201` con `paymentId` propio, `status`, `debitAmount` y `sentAmount`. El pago suma inmediatamente al `spent` del grant.

#### Scenario: Pago dentro del presupuesto
- **GIVEN** un grant con 200.00 restantes y una quote vigente de 20.15
- **WHEN** llega `POST /v1/payments` con una clave nueva
- **THEN** responde `201` con un `paymentId`
- **AND** `GET /v1/grants/{grantId}` muestra `remaining` de 179.85

### Requirement: Token del grant inválido
Los access tokens duran 600 s. El servicio SHALL rotarlos cuando están por vencer, ante un `401`,
o ante un `403` del servidor cuyo `debitAmount` entra en lo que queda del grant, reintentando una
vez en cada caso. Si no puede rotarlo, MUST responder `401 GRANT_INVALID` para que el cliente pida
un grant nuevo. Verificado en la Test Wallet (`payments/experiments/weekly-interval-and-token.md`,
sección P4).

#### Scenario: Grant usado después de 10 minutos
- **GIVEN** un grant ACTIVE cuyo access token se emitió hace 11 minutos
- **WHEN** llega `POST /v1/payments` dentro del presupuesto
- **THEN** el servicio rota el token y el pago se crea con éxito

#### Scenario: 403 con token vencido y monto dentro del límite
- **GIVEN** un grant ACTIVE cuyo access token venció en la wallet aunque el servicio lo cree vigente
- **WHEN** llega `POST /v1/payments` dentro del presupuesto y Open Payments rechaza el pago con su `403` genérico
- **THEN** el servicio rota el token una vez y reintenta el pago con la misma `Idempotency-Key`
- **AND** el pago se crea, el token nuevo queda guardado y no se debita dos veces

#### Scenario: Token revocado
- **GIVEN** un grant ACTIVE cuyo token fue revocado en la wallet
- **WHEN** llega `POST /v1/payments`
- **THEN** responde `401 GRANT_INVALID`

### Requirement: Estado del pago
`GET /v1/payments/{paymentId}` SHALL devolver `FAILED` si Open Payments marca el pago como fallido, `COMPLETED` si `sentAmount ≥ debitAmount`, y `PROCESSING` en cualquier otro caso. Un `paymentId` desconocido MUST responder `404 PAYMENT_NOT_FOUND`.

#### Scenario: Pago completado
- **GIVEN** un pago cuyo `sentAmount` en Open Payments ya iguala su `debitAmount`
- **WHEN** llega `GET /v1/payments/{paymentId}`
- **THEN** devuelve `status: "COMPLETED"`

#### Scenario: Pago todavía en tránsito
- **GIVEN** un pago con `sentAmount` menor que `debitAmount` y sin marca de fallo
- **WHEN** llega `GET /v1/payments/{paymentId}`
- **THEN** devuelve `status: "PROCESSING"`

### Requirement: Fallas de Open Payments y errores inesperados
Timeouts, errores de red y respuestas 5xx de Open Payments MUST responder `502 UPSTREAM_ERROR`. Cualquier otro error no previsto MUST responder `500 INTERNAL_ERROR` (**cambio de contrato**) sin exponer detalles internos.

#### Scenario: Open Payments no responde
- **WHEN** Open Payments supera el timeout configurado durante `POST /v1/quotes`
- **THEN** responde `502 UPSTREAM_ERROR`

#### Scenario: Error inesperado
- **WHEN** ocurre una excepción no prevista
- **THEN** responde `500 INTERNAL_ERROR`
- **AND** el `message` no incluye stack traces, URLs de Open Payments ni tokens

### Requirement: Sin reintentos automáticos de escrituras
El servicio MUST NOT reintentar automáticamente ningún POST a Open Payments, con una sola excepción: ante un rechazo por token vencido al pagar, rota el token y reintenta una vez.

#### Scenario: Falla al crear el incoming payment
- **WHEN** la creación del incoming payment falla con un error de red
- **THEN** responde `502 UPSTREAM_ERROR` después de un solo intento

### Requirement: Identificadores propios
Los identificadores que ve el cliente (`grantId`, `quoteId`, `paymentId`) SHALL ser propios del servicio. Ninguna respuesta MUST incluir URLs internas de Open Payments, tokens ni nonces.

#### Scenario: Respuesta sin datos internos
- **WHEN** se inspecciona cualquier respuesta del servicio
- **THEN** no contiene access tokens, continue tokens, nonces ni URLs de recursos de Open Payments

### Requirement: Configuración obligatoria al arrancar
Si falta o es inválida alguna variable requerida (`WALLET_ADDRESS`, `KEY_ID`, `PRIVATE_KEY_PATH`, `DB_ENCRYPTION_KEY`), el servicio MUST NOT arrancar y SHALL indicar qué variable falla, sin imprimir su valor.

#### Scenario: Falta la llave de cifrado
- **WHEN** el servicio arranca sin `DB_ENCRYPTION_KEY`
- **THEN** termina con un error que nombra `DB_ENCRYPTION_KEY`
- **AND** no queda escuchando en ningún puerto

### Requirement: Tokens cifrados en reposo
Access tokens y continue tokens SHALL guardarse cifrados. Sin `DB_ENCRYPTION_KEY`, el archivo de base de datos no revela ningún token.

#### Scenario: Inspección del archivo
- **GIVEN** un grant ACTIVE guardado
- **WHEN** se busca el valor del access token como texto plano en el archivo de base de datos
- **THEN** no aparece

### Requirement: Secretos fuera de los logs
Los logs MUST NOT contener access tokens, continue tokens, `interact_ref`, `hash`, nonces, llaves ni headers `Authorization`.

#### Scenario: Flujo completo sin fugas
- **WHEN** se ejecuta grant, continue, quote y payment con logs habilitados
- **THEN** ninguna línea de log contiene esos valores

### Requirement: Solo acceso local
El servicio SHALL escuchar únicamente en `127.0.0.1` y MUST NOT habilitar CORS.

#### Scenario: Acceso desde otra máquina
- **WHEN** se intenta conectar al puerto del servicio desde otra máquina de la red
- **THEN** la conexión es rechazada

### Requirement: Supervivencia a reinicios
Grants, quotes, pagos y claves de idempotencia SHALL sobrevivir a un reinicio del proceso.

#### Scenario: Reinicio en plena demo
- **GIVEN** un grant ACTIVE con un pago hecho con la clave K
- **WHEN** el servicio se reinicia
- **THEN** el grant sigue ACTIVE con el mismo `remaining`
- **AND** repetir el pago con la clave K devuelve la respuesta original sin pagar de nuevo

### Requirement: Un log estructurado por request
Cada request SHALL producir una línea de log JSON con `requestId`, método, ruta, status, duración total, y cantidad y duración de las llamadas a Open Payments. El `requestId` se toma del header `X-Request-Id` si viene; si no, se genera.

#### Scenario: requestId propagado
- **WHEN** llega un request con `X-Request-Id: abc-123`
- **THEN** su línea de log tiene `requestId: "abc-123"`

### Requirement: Health check
`GET /v1/health` SHALL responder `200 { "ok": true }` si la configuración es válida y la base de datos responde, sin llamar a Open Payments.

#### Scenario: Servicio sano
- **WHEN** llega `GET /v1/health` con el servicio arrancado
- **THEN** responde `200 { "ok": true }` sin llamadas a Open Payments
