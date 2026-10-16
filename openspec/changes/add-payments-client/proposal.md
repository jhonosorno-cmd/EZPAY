# Proposal — Cliente de Node en Python (Contrato A)

## Why

El rol Pagos es dueño, además del microservicio Node, del **cliente de Node en Python**
(Spec general §7): las llamadas al Contrato A, la regla de `Idempotency-Key`, la reautorización
ante `exceedsRemaining`/`401`/`403` y el polling de pagos. Ese comportamiento hoy está repartido
en decisiones dispersas de los Contratos HTTP v1; sin una capability propia, el esqueleto
FastAPI no tiene una fuente única de qué hacer ante cada `error.code`, y las pruebas de ML 2 no
tienen contra qué escribirse del lado cliente. `payments-service` especifica el lado servidor
del Contrato A; esta capability especifica el lado cliente.

## What Changes

- Nueva capability `payments-client`: comportamiento observable del cliente Python frente a Node
  (Contrato A), solo como spec, sin código.
- Reglas de la `Idempotency-Key` del lado cliente: una clave UUID nueva por cada quote; reintento
  con la **misma** clave ante `502 UPSTREAM_ERROR`, `500 INTERNAL_ERROR` o
  `409 PAYMENT_IN_PROGRESS` (tope de 15 s y 3 intentos, decisión del rol); clave nueva después
  de reautorizar y recotizar.
- Reacción a los códigos de error: `404 QUOTE_NOT_FOUND` no dispara recotización automática;
  `409 QUOTE_EXPIRED` permite recotizar con clave nueva y sin repetir el "sí"; `500
  INTERNAL_ERROR` se trata igual que `502 UPSTREAM_ERROR`.
- Dos tipos de grant que el cliente maneja: el grant de presupuesto y el **grant puntual** para
  el exceso de límite (`exceedsRemaining: true` o `403 LIMIT_EXCEEDED`), que no toca el
  presupuesto; ante `401 GRANT_INVALID` se pide un grant nuevo del mismo tipo (el presupuesto
  nuevo usa el `remaining` del grant que falló). El puntual se **cancela** cuando se usó en un
  pago completado, cuando la intención se descarta o cuando lo reemplaza otro puntual.
- **Cambio de contrato propuesto** (requiere el OK de los cuatro): `DELETE /v1/grants/{grantId}`
  para cancelar el grant puntual; Node lo cancela en Open Payments y lo marca `EXPIRED`
  localmente, idempotente.
- Recotización tras el callback: si la quote nueva no entra en el grant puntual, se cancela ese
  puntual y se pide otro por el nuevo `debitAmount`, con un `say` que no menciona el costo ni el
  débito.
- Protección del PIN (A7 cerrada): audio en `AWAITING_PIN` descartado sin transcribir; los logs
  de `POST /api/turns` nunca incluyen el cuerpo del request; dígitos fuera de `AWAITING_PIN` no
  llegan al LLM; `transcript` es `null` en un turno de PIN; los errores no exponen datos del
  request; el PIN nunca sale de Python.
- Sin grant de presupuesto activo: el turno ofrece autorizar el presupuesto y no cotiza ni paga
  (SEG-1, mecanismo cerrado; el monto de la demo queda abierto).
- **Cambios de contrato propuestos** (requieren el OK de los cuatro): `POST /api/grant-callback`
  acepta `interactRef`, `hash` y `result` opcionales; nuevo `TurnState` `PAYMENT_PENDING` con su
  resolución (verificación en la próxima interacción, un único turno de verificación automático
  ~20 s después y bloqueo de 2 minutos solo al mismo destinatario); qué se dice antes del "sí"
  (`receiveAmount`) y después de `COMPLETED` (envío y costo, si lo hay).
- Polling de `GET /v1/payments/{paymentId}` desde Python con ~10 s (el frontend nunca hace
  polling); `FAILED` lleva el turno a `REJECTED`.
- Nueva capability `turn-orchestration` (alineada con ML 2): orquestador del turno con el motor
  como función pura `decide(context) -> Decision`, la quote pedida antes del motor (con la
  excepción `quote = null` sin grant de presupuesto) y `REASK` entre las decisiones.
- Alineación con las revisiones de ML 1 y ML 2 (2026-10-15): el bloqueo por pago pendiente lo
  decide el motor vía `pendingPayment`; repregunta una vez ante respuesta dudosa; moneda y
  escala por configuración (`ASSET_CODE`, `ASSET_SCALE`); el grant de presupuesto nuevo tras
  `401` usa el `remaining` del grant que falló; frases de `say` de plantillas, nunca del LLM;
  comando por texto → verificación `NOT_AVAILABLE` y `ASK_PIN`; historial `previouslyPaid`;
  elección de destinatario por `text` o por voz contra las `options`.
- Convenciones aplicadas al cliente: decisión por `error.code` (CONV-2), montos sin floats
  (CONV-1), propagación de `X-Request-Id` (CONV-3), logs sin `interact_ref`, `hash` ni ids
  sensibles (PRIV-4), y reenvío verbatim de `interactRef` y `hash` cuando vienen.
- Solo requisitos `ADDED`: no usa `MODIFIED` sobre `payment-safety`, `voice-privacy` ni
  `service-conventions`, porque `openspec/specs/` está vacío y la validación fallaría.

## Capabilities

### New Capabilities

- `payments-client`: comportamiento observable del cliente de Node que vive en el backend Python
  frente al Contrato A (grants de presupuesto y puntual, callback, quotes, payments, reintentos
  y polling), con sus reglas de idempotencia, reautorización y secretos.
- `turn-orchestration`: orquestador del turno del esqueleto FastAPI (flujo, motor como función
  pura y tabla de transiciones de `TurnState`). Lista de `Decision` acordada con ML 2
  (2026-10-15); los campos de `context` siguen siendo borrador y los umbrales son de ML 2.

### Modified Capabilities

Ninguna: `openspec/specs/` todavía no tiene capabilities archivadas, así que este cambio solo
agrega. Las convenciones comunes (CONV-1 a CONV-6) se referencian, no se copian ni se modifican.

## Impact

- **Backend Python:** el esqueleto FastAPI (rol Pagos) implementa este cliente; la voz, la
  intención y la agenda (ML 1) y el motor (ML 2) consumen sus resultados sin conocer Node.
- **Contratos:** no cambia ni contradice el Contrato A ni el Contrato B; replica del lado cliente
  decisiones ya marcadas **[DECIDIDO]** en los Contratos HTTP v1.
- **Servidor:** consume `payments-service` (cambio `add-payments-service`) y sus códigos de error
  tipados; las reglas de reintento del cliente complementan la idempotencia del servidor.
- **Pruebas:** base para las pruebas de aceptación de ML 2 sobre exceso de límite, reintento y
  polling.
- Sin código: specs y diseño previos al evento.

## Open Questions

Preguntas abiertas que este cambio no resuelve; ninguna bloquea la escritura del spec, y las
respuestas no contradicen los Contratos (cambiarlos requeriría el OK de los cuatro).

- **P1c — Grant de presupuesto nuevo con `interval`:** si el grant que falló tenía `interval`,
  qué `remaining` usar como límite (el del período vigente o el del tope total) depende de la
  decisión sobre el presupuesto de la demo (Spec general §1 #4). Decide el equipo.
- **P3 — Rechazo en la wallet:** falta confirmar con el experimento E3-rechazo qué parámetros
  trae el redirect a `finishUri` (el Contrato B ya está propuesto con `interactRef`, `hash` y
  `result` opcionales para cubrir cualquier forma). Falta también definir qué informa el turno
  ante `INVALID_HASH` o `GRANT_NOT_PENDING` del `POST /v1/grants/{grantId}/continue`. Decide el
  equipo: tocan el Contrato B.
- **SEG-1 — Monto por defecto de la demo:** el mecanismo quedó resuelto (requisito "Sin grant de
  presupuesto activo"); falta el monto de la demo, que depende de la decisión del equipo sobre
  tope total o semanal (Spec general §1 #4).
- **Fuera de alcance — recordatorio de vencimiento del presupuesto:** cuándo avisar que el
  presupuesto se está por vencer se discute aparte; no es de esta spec.