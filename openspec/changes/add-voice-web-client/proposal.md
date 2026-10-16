# Proposal — Web app de voz (Frontend)

## Why

El frontend es el único rol sin specs. Los otros tres ya tienen los suyos (`add-payments-service`,
`add-payments-client`, `add-voice-understanding` y la revisión de ML 2), y varias de sus decisiones
le piden cosas concretas al navegador: grabar solo cuando termina el TTS, enviar la elección de
destinatario como `text`, mostrar el teclado de PIN desde H1, reenviar el callback completo de la
wallet y mandar un único turno de verificación tras `PAYMENT_PENDING`. Sin un spec del frontend esas
peticiones quedan repartidas en cuatro ramas, y las pruebas de aceptación de ML 2 no tienen contra
qué escribirse del lado del navegador.

## What Changes

- Nueva capability `web-conversation`: la pantalla como máquina de estados guiada por
  `TurnResponse.state` (Contrato B), con `sessionId`, un turno a la vez, `X-Request-Id`, errores por
  `code`, montos sin `number` y el texto como camino alterno (siempre con PIN).
- Nueva capability `web-voice-io`: captura con `MediaRecorder` (push-to-talk, sin persistir el audio,
  tope de duración) y TTS con `speechSynthesis` (voz en español, desbloqueo por gesto, nunca grabar
  mientras habla).
- Nueva capability `wallet-handoff`: explicación por voz antes de ir a la wallet, botón grande,
  `sessionId` que sobrevive a la recarga, y página `/grant-callback` que reenvía **todos** los
  parámetros de `finishUri`.
- Nueva capability `enrollment-ui`: consentimiento explícito (PRIV-2), tres muestras de voz y manejo de
  los errores de `/enrollment`.
- Se adoptan del lado del navegador, **sin aprobarlos** (cada uno requiere el OK de los cuatro), los
  cambios de contrato propuestos por los otros roles:
  - `TurnState` `PAYMENT_PENDING` y el turno único de verificación (Pagos, D-2).
  - `/api/grant-callback` con `{interactRef?, hash?, result?}` (Pagos, D-1).
  - Errores de `/turns`: `AUDIO_OR_TEXT_REQUIRED`, `INVALID_AUDIO`, `AUDIO_TOO_LONG`,
    `SESSION_NOT_FOUND` (ML 1, C-6).
  - Elección de destinatario como `text` = `alias` (ML 1 C-6, Pagos `turn-orchestration`).
  - Errores de `/enrollment` y `GET /enrollment` (ML 2, C-3).
- **Contradicción detectada entre propuestas** (la decide el equipo): el turno de verificación de
  `PAYMENT_PENDING` va "sin `audio` ni `text`" (Pagos), pero ML 1 propone `400
  AUDIO_OR_TEXT_REQUIRED` cuando no llega ninguno de los dos. Este spec propone que esa regla tenga
  una excepción cuando la sesión está en `PAYMENT_PENDING`.

## Capabilities

### New Capabilities

- `web-conversation`: comportamiento observable de la pantalla de conversación frente al Contrato B.
- `web-voice-io`: grabación del comando y lectura en voz alta del `say`.
- `wallet-handoff`: ida a la wallet y vuelta por `/grant-callback`.
- `enrollment-ui`: registro de la voz con consentimiento.

### Modified Capabilities

Ninguna: `openspec/specs/` sigue vacío. Se referencian, sin modificarlas, `payment-safety`,
`voice-privacy` y `service-conventions` (`add-team-baseline`).

## Impact

- **Frontend:** todo el trabajo del rol desde H1. El PIN pasa de H3 a H1, porque un comando por texto
  siempre pide PIN (ML 2 D3, aceptado por Pagos).
- **Pagos:** el mock del Contrato B tiene que incluir los estados y errores propuestos para que el
  frontend los pruebe. Todavía no existe `openapi.yaml` en ninguna rama.
- **ML 1:** recibe del frontend una muestra real de audio del navegador (X-4), fuera del repo.
- **ML 2:** escribe el texto del consentimiento y las frases del enrolamiento; el frontend los muestra.
- **Contratos:** este cambio no modifica los Contratos HTTP v1. Lo marcado "cambio de contrato
  propuesto" depende de la decisión de los cuatro; si se rechaza, se quita el requisito.

## Open Questions

- **F-1 — Turno de verificación de `PAYMENT_PENDING`:** ¿cómo se envía si "ni `audio` ni `text`" es un
  `400`? Propuesta: excepción por estado de la sesión. Deciden Pagos y ML 1.
- **F-2 — Consentimiento para el proveedor externo (Groq):** ML 1 propone sumarlo al texto del
  consentimiento del enrolamiento (C-3), pero su spec contempla "usuario sin consentimiento para el
  proveedor externo" como caso aparte. ¿Es un solo `consent` o dos casillas? Dos casillas serían un
  campo nuevo en `/enrollment` (cambio de contrato).
- **F-3 — Arranque del presupuesto:** ¿la demo autoriza el presupuesto con el botón (`POST /budget`) o
  desde el primer comando de voz sin presupuesto (Pagos, "Sin grant de presupuesto activo")? El
  frontend soporta los dos; el monto depende de D-4.
- **F-4 — Lectura de "20.000" por el TTS:** ML 1 pide verificar que el TTS diga "veinte mil". Se
  verifica en la laptop de la demo.
- **F-5 — Duración máxima de un comando:** ML 2 midió que hace falta un tope (propone 30 s en el
  servidor). El frontend corta antes, en 15 s **[PROPUESTA]**.
