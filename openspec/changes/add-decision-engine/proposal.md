## Why

El Spec general (SEG-1 a SEG-6) dice qué debe cumplir el sistema antes de mover dinero, y
`turn-orchestration` dice cómo el orquestador de Pagos invoca al motor, pero ningún spec define el
motor mismo: qué recibe, en qué orden aplica las reglas, qué devuelve ni cómo se valida el PIN. Sin
eso, el motor de H1 (viernes 14:00) se escribe contra la implementación y las pruebas de aceptación
no tienen contra qué verificarse.

## What Changes

- Dos capabilities nuevas para H1:
  - `decision-engine`: función pura `decide(context) -> {decision, reason}` con tabla de reglas
    ordenada por fase (`COMMAND`, `PIN`, `CONFIRMATION`), enum cerrado de `reason` y plantillas de `say`
    por `reason`.
  - `pin-validation`: PIN mínimo con hash con sal en configuración, comparación en tiempo constante,
    contadores de intentos (3 por sesión, 5 en total) y privacidad del PIN.
- Ningún requisito común cambia ni se contradicen los Contratos v1 más v1.1 (ratificados el 16 oct).
- Decisiones de ML 2 que materializa (`docs/decisiones.md`, 16 oct): D1 (función pura), D2 (tabla
  ordenada; el PIN se suma al "sí"), D3 (el texto y el usuario no enrolado piden PIN), D4 (solo se
  verifica la voz del comando), D5 (diseño del PIN) y D9 (`previouslyPaid`).
- Quedan fuera de H1 (cambio posterior de ML 2): `speaker-verification` (SpeechBrain, umbral 0.45
  provisional) y `voice-enrollment` (`/enrollment`, `GET /enrollment`, errores de B-5).
- Código en `api/`: el motor (`api/decision/`), el PIN (`api/pin/`), sus scripts (`api/scripts/`), `api/.env.example` y las pruebas de los escenarios (`api/tests/decision/`, `api/tests/pin/`), escritas antes del código.

## Capabilities

### New Capabilities

- `decision-engine`: decisión determinística de cada turno de un pago, con `reason` para elegir la
  plantilla de `say`.
- `pin-validation`: validación del PIN dentro del backend Python, con contadores y bloqueo.

### Modified Capabilities

Ninguna: `openspec/specs/` está vacío. Los requisitos comunes (`payment-safety`, `voice-privacy`,
`service-conventions`) viven en `add-team-baseline`.

## Impact

- Pagos: el orquestador arma el `context` completo, fija `phase`, lleva `unclearReplies`, mapea la
  `Decision` a `TurnState` y elige la plantilla de `say` por `reason`.
- Voz (ML 1): entrega `Intent`, `Resolution`, `Reply` y los puntajes de confianza; escribe el
  catálogo de `say` con las plantillas por `reason`; propone los valores de los cortes de confianza.
- Frontend: trata `PAYMENT_PENDING` como pantalla de carga y envía en silencio el turno único de
  verificación; el PIN llega por el campo `text` hasta que exista el teclado.
- Contratos: sin cambios nuevos; B-7 y B-8 (ya ratificados) rigen el turno de PIN.
