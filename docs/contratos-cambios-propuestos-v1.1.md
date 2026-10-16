# Contratos — cambios propuestos para v1.1

**Estado: [PARA DECIDIR].** Ninguno está ratificado. Salen de las revisiones por rol hechas antes
del evento (13 al 15 de octubre). La versión vigente sigue siendo [`contratos-http-v1.md`](./contratos-http-v1.md):
hasta que los cuatro aprueben un cambio, se implementa v1.

Algunos specs de `openspec/changes/` ya asumen estos cambios (se indica en la última columna). Si
un cambio se rechaza, hay que ajustar ese spec antes de implementarlo.

## Contrato A — Python → Node

| # | Cambio | Motivo | Specs que lo asumen |
|---|---|---|---|
| A-1 | Nuevo `DELETE /v1/grants/{id}` → `204`, idempotente; `404 GRANT_NOT_FOUND`; ante `502 UPSTREAM_ERROR` el grant igual queda `EXPIRED` | Cancelar el grant puntual del exceso de límite al usarlo, descartarlo o reemplazarlo | `add-payments-service`, `add-payments-client` |
| A-2 | Se permiten varios grants `ACTIVE` por usuario (antes, uno solo) | El grant puntual convive con el del presupuesto | `add-payments-service` |
| A-3 | El grant pide las acciones `["create","read","list"]` | Poder buscar un pago de resultado incierto | `add-payments-service` |

No se propone: pagar con la quote original pasando `grantId` a `/payments`. Queda como mejora futura.

## Contrato B — Frontend → Python

| # | Cambio | Motivo | Specs que lo asumen |
|---|---|---|---|
| B-1 | `POST /grant-callback` acepta `{interactRef?, hash?, result?}` | La wallet puede volver sin `interact_ref` cuando el usuario rechaza (E3 sin correr) | `add-payments-client`, `add-voice-web-client` |
| B-2 | Nuevo `TurnState` `PAYMENT_PENDING`, con un turno automático de verificación unos 20 s después, sin `audio` ni `text` | El pago puede tardar más que el polling de Python | `add-payments-client`, `add-voice-web-client`, `add-voice-understanding` |
| B-3 | Errores de `/turns`: `AUDIO_OR_TEXT_REQUIRED`, `INVALID_AUDIO`, `AUDIO_TOO_LONG`, `SESSION_NOT_FOUND` | No había códigos para entradas inválidas | `add-voice-understanding`, `add-voice-web-client` |
| B-4 | La elección de destinatario vuelve como `text` = `alias` | Evitar una segunda transcripción ambigua | `add-voice-understanding`, `add-voice-web-client` |
| B-5 | `/enrollment`: errores `SAMPLES_REQUIRED`, `INVALID_AUDIO`, `INCONSISTENT_SAMPLES`, y nuevo `GET /enrollment` | Informar por qué falló el registro y si ya existe. **Revisado por el equipo el 16 oct** | `add-voice-web-client` |
| B-6 | Antes del "sí" se dice el `receiveAmount`; el costo se dice después de `COMPLETED` | Confirmación corta y clara para la usuaria | `add-voice-understanding`, `add-payments-client` |
| B-7 | `transcript` es `null` en los turnos de PIN | El PIN nunca se muestra ni se registra | `add-payments-client`, `add-voice-web-client` |

## Inconsistencias que resolver junto con estos cambios

- **Nombres de la intención:** el Spec general (SEG-3) y `add-payments-client` usan
  `{accion, monto, moneda, destino}`; `add-voice-understanding` usa `{action, amount, recipient, status}`.
- **B-2 y B-3:** el turno automático de `PAYMENT_PENDING` no trae `audio` ni `text`, y B-3 lo
  rechazaría con `AUDIO_OR_TEXT_REQUIRED`. `speech-transcription` agrega una excepción que Pagos no
  aprobó todavía.
- **Grant puntual:** el equipo decidió el 16 oct que **vence por semana** (`docs/decisiones.md`).
  `add-payments-service` (D13) y `add-payments-client` todavía lo cancelan con `DELETE` y lo piden
  sin `interval`. Falta decidir cómo se implementa y si A-1 (`DELETE`) sigue haciendo falta.
- **Reglas del PIN** en `turn-orchestration` (proteger el PIN): escritas, pero sin aprobación
  explícita del equipo.
- **SEG-1:** hay una propuesta de modificarlo por inclusión, y un análisis de Pagos que concluye
  que Open Payments no lo permite (la autorización la da el proveedor de identidad de la wallet).
  Mientras no se decida, rige SEG-1 tal como está.
- **Reglas duplicadas** entre capabilities, para limpiar antes de archivar: reglas de `/turns`
  (`speech-transcription` y `turn-orchestration`), "el PIN nunca llega al LLM"
  (`reply-classification` y `turn-orchestration`), moneda y escala desde la configuración
  (`amount-parsing`, `payments-client` y `wallet-handoff`).
- **Decisiones del 16 oct que todavía no están en ningún spec:** el texto siempre pide PIN y el
  usuario no enrolado también (falta en `turn-orchestration`); `previouslyPaid` exige que el
  esqueleto guarde los destinatarios con pagos completados (falta en `payments-client`); el puntaje
  de confianza por pipeline (falta en `intent-extraction`, `speech-transcription` y en el contexto
  del motor).
- **Cambio de ML 2 sin crear:** el motor, la verificación, el enrolamiento y el PIN no tienen spec
  (`add-decision-engine`).
