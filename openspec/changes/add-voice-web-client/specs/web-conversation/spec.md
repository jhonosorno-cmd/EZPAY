# Spec Delta — web-conversation

## Purpose

Pantalla de conversación de la web app. Habla solo con el backend Python por el Contrato B
(`docs/contratos-http-v1.md`) y decide qué mostrar y qué enviar según
`TurnResponse.state`. No decide nada sobre pagos: eso es del motor (ML 2) y del orquestador (Pagos,
capability `turn-orchestration`). Los requisitos marcados "cambio de contrato propuesto" dependen del
OK de los cuatro.

Resumen de la pantalla por estado (cada fila se detalla en los requisitos de abajo y en
`wallet-handoff`):

| `state` | Qué muestra | Qué entrada habilita |
|---|---|---|
| `AWAITING_COMMAND` | `say` | Grabar o escribir un comando |
| `AWAITING_CONFIRMATION` | `say` y botones Sí / No | Grabar la respuesta o tocar un botón |
| `AWAITING_PIN` | Teclado de PIN | Solo el teclado |
| `AWAITING_RECIPIENT_CHOICE` | `options` como botones | Tocar una opción o grabar |
| `AWAITING_AUTHORIZATION` | Pantalla de ida a la wallet | Botón "Ir a mi billetera" |
| `COMPLETED` | Recibo con `payment` | Volver a empezar |
| `PAYMENT_PENDING` (propuesto) | Envío "en camino" | Grabar un comando |
| `REJECTED` | `say` | Volver a empezar |

## ADDED Requirements

### Requirement: Solo el Contrato B
La web app SHALL llamar únicamente a `http://localhost:8000/api` (Contrato B) y MUST NOT llamar al microservicio Node ni a Open Payments. En desarrollo, el servidor de la web app (puerto 5173, CONV-5) SHALL redirigir `/api` al backend Python, para que el navegador vea un solo origen.

#### Scenario: Ninguna llamada a Node
- **WHEN** se recorre el flujo completo de un pago y se revisan las peticiones del navegador
- **THEN** todas van a `/api` y ninguna al puerto 4000

### Requirement: La pantalla sigue al estado del turno
Por cada `TurnResponse`, la web app SHALL mostrar el `say` como texto grande, mostrar el `transcript` si no es `null`, leer el `say` en voz alta (capability `web-voice-io`) y habilitar solo la entrada que corresponde al `state`, según la tabla del Purpose.

#### Scenario: Esperando un comando
- **WHEN** llega un `TurnResponse` con `state: "AWAITING_COMMAND"`
- **THEN** la pantalla muestra y lee el `say`
- **AND** habilita grabar y escribir un comando

#### Scenario: Comando rechazado
- **WHEN** llega un `TurnResponse` con `state: "REJECTED"`
- **THEN** la pantalla muestra y lee el `say` y ofrece volver a empezar

#### Scenario: Confirmación
- **WHEN** llega un `TurnResponse` con `state: "AWAITING_CONFIRMATION"` y `say: "¿Le envío 20.000 pesos a Laura?"`
- **THEN** la pantalla muestra ese texto, lo lee en voz alta y ofrece grabar o tocar Sí / No

#### Scenario: Estado desconocido
- **WHEN** llega un `state` que la web app no conoce
- **THEN** muestra y lee el `say`, y vuelve a la pantalla de inicio sin enviar nada

### Requirement: Botones Sí y No como texto
En `AWAITING_CONFIRMATION`, tocar "Sí" o "No" SHALL enviar `POST /api/turns` con `text` igual a "sí" o "no". El "sí" escrito pasa por el mismo clasificador que el hablado (ML 1, `reply-classification`); la web app MUST NOT confirmar un pago por su cuenta.

#### Scenario: Botón Sí
- **WHEN** la usuaria toca "Sí" en una confirmación
- **THEN** se envía `POST /api/turns` con el `sessionId` y `text: "sí"`
- **AND** la pantalla espera la respuesta de Python antes de mostrar un recibo

### Requirement: Un turno a la vez
Mientras un `POST /api/turns` está en curso, la web app MUST NOT enviar otro turno: deshabilita la grabación, los botones y el teclado, y muestra un estado "Procesando…". El tiempo de espera de la petición SHALL ser de al menos 30 s, porque un turno puede incluir transcripción, cotización, hasta 15 s de reintentos y ~10 s de consulta del pago (capability `payments-client`).

#### Scenario: Doble toque
- **WHEN** la usuaria toca dos veces seguidas el botón de enviar
- **THEN** sale una sola petición `POST /api/turns`

#### Scenario: Turno lento
- **WHEN** Python tarda 20 s en responder un turno de pago
- **THEN** la web app sigue esperando y muestra "Procesando…"

### Requirement: Sesión de la conversación
La web app SHALL enviar en cada `POST /api/turns` el `sessionId` del último `TurnResponse` y guardarlo en `sessionStorage`, para que sobreviva a la recarga de la vuelta de la wallet. El primer turno va sin `sessionId`.

#### Scenario: Turno siguiente
- **WHEN** un `TurnResponse` trae `sessionId: "s_1"` y la usuaria graba el siguiente comando
- **THEN** el `POST /api/turns` lleva `sessionId: "s_1"`

### Requirement: Identificador por acción (CONV-3)
Cada acción de la usuaria que llama a la API SHALL llevar un header `X-Request-Id` nuevo, generado como UUID. La web app lo escribe en la consola del navegador junto al `state` resultante, sin el cuerpo de la petición.

#### Scenario: Seguir un pago
- **WHEN** la usuaria confirma un pago
- **THEN** la petición lleva un `X-Request-Id` nuevo
- **AND** la consola del navegador muestra ese id y el `state` de la respuesta

### Requirement: Errores por código (CONV-2)
Ante una respuesta de error, la web app SHALL decidir por `error.code`, nunca por `error.message`, y decir en voz alta un mensaje en español de su propio catálogo. Los códigos de `/turns` de los escenarios son un **cambio de contrato propuesto** (ML 1, C-6).

#### Scenario: Código conocido con otro mensaje
- **WHEN** Python responde `400 INVALID_AUDIO` con un `message` distinto del habitual
- **THEN** la web app hace exactamente lo mismo que con el `message` habitual

#### Scenario: Audio inválido
- **WHEN** Python responde `400 INVALID_AUDIO`
- **THEN** la web app dice "No pude escuchar bien. ¿Lo intentas de nuevo?"
- **AND** sigue en el mismo estado

#### Scenario: Audio demasiado largo
- **WHEN** Python responde `400 AUDIO_TOO_LONG`
- **THEN** la web app pide decirlo en una frase corta y sigue en el mismo estado

#### Scenario: Ni audio ni texto
- **WHEN** Python responde `400 AUDIO_OR_TEXT_REQUIRED`
- **THEN** la web app lo registra en la consola como error de programación y vuelve al estado anterior

#### Scenario: Sesión perdida
- **WHEN** Python responde `404 SESSION_NOT_FOUND`
- **THEN** la web app borra el `sessionId` guardado y vuelve a `AWAITING_COMMAND` sin `sessionId`

#### Scenario: Error después de un turno con transcripción
- **WHEN** un turno falla después de otro que trajo `transcript`
- **THEN** la pantalla muestra el mensaje del error sin la transcripción anterior

#### Scenario: Código desconocido
- **WHEN** Python responde un `code` que la web app no conoce
- **THEN** dice "Algo falló. Intenta de nuevo" y muestra el `code` en letra pequeña

### Requirement: Comando por texto como camino alterno
La web app SHALL ofrecer un campo de texto para comandos, como camino de H1 y como respaldo si falla el micrófono. Un comando escrito siempre lleva a `AWAITING_PIN` (ML 2 D3, aceptado por Pagos); la web app no lo trata como un atajo.

#### Scenario: Comando escrito
- **WHEN** la usuaria escribe "envíale 20 mil a Laura"
- **THEN** se envía `POST /api/turns` con `text`
- **AND** si la respuesta es `AWAITING_PIN`, se muestra el teclado

### Requirement: Teclado de PIN
En `AWAITING_PIN`, la web app SHALL mostrar un teclado numérico con botones grandes, que dice "punto" (nunca el dígito) al tocar cada tecla y envía el PIN como `text` en un único `POST /api/turns`. El PIN MUST NOT guardarse en `localStorage`, `sessionStorage` ni en la consola, ni leerse en voz alta. En este estado la web app MUST NOT grabar audio (Pagos descarta el audio en `AWAITING_PIN`).

#### Scenario: Envío del PIN
- **WHEN** la usuaria toca cuatro dígitos y "Enviar"
- **THEN** sale un `POST /api/turns` con `text` igual a esos dígitos
- **AND** el campo del PIN queda vacío después de enviarlo

#### Scenario: PIN incorrecto
- **WHEN** la respuesta sigue en `AWAITING_PIN` con un `say` de intentos restantes
- **THEN** la web app lee el `say` y muestra el teclado vacío

#### Scenario: Sin micrófono en el PIN
- **WHEN** el estado es `AWAITING_PIN`
- **THEN** el botón de grabar no está disponible (no se muestra)

> Esperaba un botón deshabilitado; pasó que el dock del micrófono tapaba la última fila del teclado
> en un teléfono de 390 px; cambio: en `AWAITING_PIN`, `AWAITING_AUTHORIZATION`, `COMPLETED` y
> `REJECTED` el micrófono no se muestra.

### Requirement: Elección de destinatario
En `AWAITING_RECIPIENT_CHOICE`, cada elemento de `options` SHALL mostrarse como un botón grande con su `name`. Tocar un botón envía `POST /api/turns` con `text` igual a su `alias`. La usuaria también puede responder por voz. **Cambio de contrato propuesto** (ML 1 C-6; Pagos `turn-orchestration`).

#### Scenario: Elección por botón
- **WHEN** `options` es `[{alias: "laura-hija", name: "Laura (hija)"}, {alias: "laura-vecina", name: "Laura (vecina)"}]` y la usuaria toca "Laura (hija)"
- **THEN** se envía `POST /api/turns` con `text: "laura-hija"`

### Requirement: Recibo
En `COMPLETED`, la web app SHALL mostrar un recibo con el destinatario y `receiveAmount` de `payment` y, si `debitAmount` difiere de `receiveAmount`, también el costo, calculado con enteros sobre `value` (`BigInt`).

#### Scenario: Recibo con costo
- **WHEN** `payment.receiveAmount.value` es "2000000" y `payment.debitAmount.value` es "2015000", ambos COP con escala 2
- **THEN** el recibo muestra "20.000" enviados y "150" de costo

### Requirement: Pago pendiente
En `PAYMENT_PENDING` (B-2, ratificado), la web app SHALL mostrar el envío como "en camino" (con el monto y el destinatario cuando llega `payment`), leer el `say` y, unos 20 s después, enviar **un único** `POST /api/turns` de verificación con el `sessionId` y `kind=verify_pending`, sin `audio` ni `text` (decisión D-1b, `x-proposed` en `openapi/contract-b.yaml`; resuelve F-1). MUST NOT repetirlo ni hacer polling.

#### Scenario: Una sola verificación
- **WHEN** llega un `TurnResponse` en `PAYMENT_PENDING` y pasan 20 s
- **THEN** sale un único turno de verificación con `kind=verify_pending`
- **AND** no sale ninguno más aunque la respuesta siga en `PAYMENT_PENDING`

#### Scenario: La usuaria habla antes
- **WHEN** llega `PAYMENT_PENDING` y la usuaria graba un comando antes de los 20 s
- **THEN** se envía ese comando y se cancela el turno de verificación automático

### Requirement: Montos sin number (CONV-1)
La web app MUST NOT convertir un `value` a `number` ni usar `parseFloat`. Para mostrar un `Amount` SHALL operar sobre el string: separar los últimos `assetScale` dígitos como decimales, agrupar los miles con punto y usar coma decimal (formato es-CO, igual que `format_amount` de ML 1), omitiendo decimales en cero.

#### Scenario: Monto en pesos
- **WHEN** se muestra `{ value: "2000000", assetCode: "COP", assetScale: 2 }`
- **THEN** el texto es "20.000"

#### Scenario: Monto con centavos
- **WHEN** se muestra `{ value: "1050", assetCode: "COP", assetScale: 2 }`
- **THEN** el texto es "10,50"
