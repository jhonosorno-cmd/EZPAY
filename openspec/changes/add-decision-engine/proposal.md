## Why

El Spec general (SEG-1 a SEG-6) dice qué debe cumplir el sistema antes de mover dinero, y
`turn-orchestration` dice cómo el orquestador de Pagos invoca al motor, pero ningún spec define el
motor mismo: qué recibe, en qué orden aplica las reglas, qué devuelve ni cómo se valida el PIN. Sin
eso, el motor de H1 (viernes 14:00) se escribe contra la implementación y las pruebas de aceptación
no tienen contra qué verificarse.

## What Changes

- Dos capabilities nuevas para H1:
  - `decision-engine`: función pura `decide(context) -> {decision, reason}` con tabla de reglas
    ordenada por fase (`COMMAND`, `PIN`, `CONFIRMATION`), enum cerrado de `reason` y traducción de cada
    `reason` a una situación del catálogo único de `say` de Voz.
  - `pin-validation`: PIN mínimo con hash con sal en configuración, comparación en tiempo constante,
    contadores de intentos (3 por sesión, 5 en total) y privacidad del PIN.
- Ningún requisito común cambia ni se contradicen los Contratos v1 más v1.1 (ratificados el 16 oct).
- Decisiones de ML 2 que materializa (`docs/decisiones.md`, 16 oct): D1 (función pura), D2 (tabla
  ordenada; el PIN se suma al "sí"), D3 (el texto y el usuario no enrolado piden PIN), D4 (solo se
  verifica la voz del comando), D5 (diseño del PIN) y D9 (`previouslyPaid`).
- Dos capabilities nuevas para H2:
  - `speaker-verification`: `embed` y `verify` con SpeechBrain (ECAPA) en CPU dentro del backend;
    `verify` produce el `context.voice` del motor, con umbral configurable (0.45 provisional), falla
    cerrada (`NOT_AVAILABLE`) y sin audio ni puntajes en logs.
  - `voice-enrollment`: huella a partir de 3 muestras con un solo consentimiento (huella y
    transcripción externa), errores de B-5 en orden fijo, huella persistida fuera de git,
    re-enrolamiento atómico y `GET /enrollment`.
- Código en `api/`: el motor (`api/decision/`), el PIN (`api/pin/`), sus scripts (`api/scripts/`), `api/.env.example` y las pruebas de los escenarios (`api/tests/decision/`, `api/tests/pin/`), escritas antes del código.

## Capabilities

### New Capabilities

- `decision-engine`: decisión determinística de cada turno de un pago, con `reason` para elegir la
  situación de `say` del catálogo de Voz.
- `pin-validation`: validación del PIN dentro del backend Python, con contadores y bloqueo.
- `speaker-verification`: verificación de hablante del comando de voz contra la huella (H2).
- `voice-enrollment`: registro, consulta y borrado de la huella de voz con consentimiento (H2).

### Modified Capabilities

Ninguna: `openspec/specs/` está vacío. Los requisitos comunes (`payment-safety`, `voice-privacy`,
`service-conventions`) viven en `add-team-baseline`.

## Impact

- Pagos: el orquestador arma el `context` completo, fija `phase`, lleva `unclearReplies`, mapea la
  `Decision` a `TurnState` y traduce el `reason` a una situación de `say` con `say_situation`.
- Voz (ML 1): entrega `Intent`, `Resolution`, `Reply` y los puntajes de confianza; su catálogo de
  `say` (`api/voice/phrases.py`) es el único y agrega las 13 situaciones nuevas; propone los valores de los cortes de confianza.
- Frontend: muestra `PAYMENT_PENDING` ("en camino") y envía en silencio el turno único de
  verificación (PR #2); el PIN llega por el campo `text` hasta que exista el teclado.
- Contratos: sin cambios nuevos; B-7 y B-8 (ya ratificados) rigen el turno de PIN.
