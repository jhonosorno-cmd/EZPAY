## Why

Para H3 (sábado 09:30), `docs/spec-general.md` §7 pide a ML 2 "enrolamiento y recalibración en la
sala; verificación integrada al motor". El motor, el PIN, la verificación de hablante, el
enrolamiento y el desafío de confirmación ya existen en `api/` (`add-decision-engine`), pero el
orquestador de Pagos (unidad 7) todavía no existe y el esqueleto FastAPI no integra nada de ML 2 ni
de Voz. Sin una interfaz clara, la unidad 7 tendría que conocer SpeechBrain, umbrales y reglas del
desafío. Además, el umbral y los cortes se calibraron con el micrófono de la laptop y hay que
confirmarlos en la sala con el de la demo.

## What Changes

- Dos capabilities nuevas para H3:
  - `voice-turn-integration`: fachada de ML 2 sin HTTP y sin estado (P1) que el orquestador llama:
    del audio del comando a `context.voice` (en paralelo con `transcribe`), de la respuesta al
    desafío a `context.confirmation`, elección del modo (P5) y de la frase del desafío (el
    orquestador guarda las frases en su sesión), `context` de `say_situation` en fase COMMAND,
    fallos cerrados con 2 s de presupuesto (P2), enrolamiento web del Contrato B y privacidad.
  - `speaker-calibration`: protocolo en la sala con 4 personas y 6 intentos genuinos y 6 de
    impostor por persona (P6), métricas, evidencia mínima para mover `threshold`, el corte de
    consistencia, `minVerifySeconds` y `challengePhraseMatchMin` (P7), valores actuales si no hay
    tiempo, congelamiento en H4 con solo números agregados y plan B de la demo.
- Código en `api/`: la fachada `api/integration.py` y sus pruebas (`api/tests/integration/`),
  escritas antes del código. La calibración en la sala corre fuera del repo (`Pruebas ML2`).
- El corte de la frase tiene una sola fuente: `config.challengePhraseMatchMin` del motor (P8).

## Capabilities

### New Capabilities

- `voice-turn-integration`: interfaz de ML 2 para el orquestador del turno (verificación,
  desafío y enrolamiento web).
- `speaker-calibration`: recalibración en la sala y congelamiento de los parámetros de voz.

### Modified Capabilities

Ninguna. Las capabilities de `add-decision-engine` no cambian.

## Impact

- Pagos: la unidad 7 llama la fachada en vez de `api/speaker` y `api/voice/challenge`, guarda en su
  sesión las frases usadas, la frase pedida y `challengeAttempts`, y conecta `/api/enrollment`.
  Ratifica `kind=verify_pending` y el cuerpo `{enrolled}` de `GET /api/enrollment` (P4).
- Frontend: muestra la frase del desafío con el campo `challengePhrase` de `TurnResponse` (P3,
  cambio de Contrato B aceptado por ML 2, pendiente del OK de Pagos y Frontend).
- Voz (ML 1): agrega `CONFIRM_CHALLENGE_OVERRUN` y `CHALLENGE_FAILED`; `CHALLENGE_MIN_MATCH` queda
  solo para sus scripts (P8); coordina la batería con ruido con la recalibración en la sala.
