# Diseño — add-ml2-integration

Material de referencia de `voice-turn-integration`, `speaker-calibration`: trazabilidad y puntos abiertos. Los requisitos y escenarios normativos están en `specs/`.

## Trazabilidad

### voice-turn-integration

| Requisito | Origen |
| --- | --- |
| Fachada sin HTTP; el orquestador no conoce el modelo ni los umbrales | `docs/spec-general.md` §7 (H3); brief 06-esqueleto-api-fastapi (unidad 5 no integra; unidad 7 falta); issue #12 |
| Del audio del comando a `context.voice` | `speaker-verification` (H2); `docs/voz/contrato-voz.md` §4 (Voz decodifica); README-ml2 "Cómo lo usa el orquestador" |
| De la respuesta al desafío a `context.confirmation` | `decision-engine` (H1, desafío 2026-10-17); propuesta "Confirmación con desafío de voz"; issue #12 (forma exacta del campo) |
| Elección del modo (`CHALLENGE` solo con bandera activa y comando verificado sin PIN) | `decision-engine` notas del desafío; issue #12 ("El MODO lo decide el orquestador") |
| Frase pedida y frases usadas guardadas en la sesión | `voice/challenge.py` (`pick_phrase`, sin repetir); issue #12 (la frase se guarda en la sesión) |
| `say_situation` en fase COMMAND con modo CHALLENGE | `say_map.py` (`ALL_CHECKS_PASSED`); issue #12 (nota del `say`) |
| Fallos cerrados y presupuesto de tiempo | `speaker-verification` (NOT_AVAILABLE, latencias x0_entorno); SEG-6 |
| Enrolamiento web (Contrato B) | B-5 ratificado (`POST /api/enrollment`); `GET /api/enrollment` cuerpo `x-proposed`; B-7/B-8; `voice-enrollment` (H2) |
| Reparto con Pagos y campo nuevo del contrato | Issue #12; propuesta "Confirmación con desafío de voz" (Impacto por documento) |
| Privacidad: nada biométrico en logs ni disco | PRIV-1, PRIV-4; AGENTS.md (repo público); `voice-privacy` |

### speaker-calibration

| Requisito | Origen |
| --- | --- |
| Umbral 0.45 y recorte `trim_silence` calibrados el 15 oct; recalibración pendiente con el micrófono de la sala | `speaker-verification` (H2, puntos abiertos); experimentos ML 2, 15–17 oct (margen +0.104, muestra de 3 personas) |
| Corte de consistencia 0.45 | `voice-enrollment` (H2); peor par del 17 oct: alex 0.518 |
| `minVerifySeconds` = 2,0 s | Experimentos ML 2, 17 oct; frase de la demo con divisa (mín. 2,28 s) |
| `challengePhraseMatchMin` = 0.80 | Decisión del desafío (2026-10-17); `CHALLENGE_MIN_MATCH` de Voz se confirma "con un experimento" (`voice/config.py`) |
| Batería con ruido de la sala | Coordinación con Voz (Sebastián); X-6 midió solo con micrófono del PC |
| Repo público: nada de audio ni embeddings | AGENTS.md; PRIV-1/PRIV-4; `voice-privacy` |
| Congelamiento del código | `docs/spec-general.md` §7 (sábado 10:45) |

## Puntos abiertos

### voice-turn-integration

| Punto | Dueño / estado |
| --- | --- |
| **P1** Nombre y forma de la fachada: `api/integration.py` con funciones sueltas (`voice_of_command`, `build_confirmation`, `choose_confirmation_mode`, `next_challenge_phrase`) sobre `SpeakerVerifier`/`SpeakerEnrollment`/`voice.challenge` | **[DECIDIDO 2026-10-17, Daniel]** |
| **P2** Presupuesto de tiempo: paralelo `transcribe + verify` < 2 s en confirmación; timeout de la fachada 2 s ⇒ `NOT_AVAILABLE`, sin cancelar la verificación vencida ni lanzar otra mientras corra | **[DECIDIDO 2026-10-17, Daniel]** |
| **P3** Campo `challengePhrase` (string) en `TurnResponse` cuando `AWAITING_CONFIRMATION` en modo CHALLENGE: aceptado por ML 2, falta el OK de los dueños del contrato | **[DECIDIDO 2026-10-17, Daniel]** — pendiente OK de Pagos/Frontend |
| **P4** Ratificar el cuerpo `{enrolled}` de `GET /api/enrollment` (hoy `x-proposed`): aceptado por ML 2 tal cual | **[DECIDIDO 2026-10-17, Daniel]** — pendiente OK de Pagos |
| **P5** Helper puro `choose_confirmation_mode` en la fachada que la unidad 7 llama; la decisión final es del orquestador | **[DECIDIDO 2026-10-17, Daniel]** |
| **P8** Corte de frase unificado: la fachada usa solo `config.challengePhraseMatchMin` del motor; `CHALLENGE_MIN_MATCH` de Voz queda solo para sus scripts | **[DECIDIDO 2026-10-17, Daniel]** |
| Ratificar el campo `kind=verify_pending` de `TurnRequest` (el estado `PAYMENT_PENDING` está ratificado; el campo que activa la verificación silenciosa sigue `x-proposed` en `contract-b.yaml`) | **Dueño: Pagos** |

### speaker-calibration

| Punto | Dueño / estado |
| --- | --- |
| **P6** Protocolo en la sala: 4 personas del equipo enroladas, 6 genuinos + 6 impostor por persona, 10 frases del banco y comandos de la demo, micrófono de la sala | **[DECIDIDO 2026-10-17, Daniel]** (con cambio: 6+6, no 10+10, por tiempo) |
| **P7** Evidencia mínima para mover cada parámetro (inversión del margen, FR de enrolamiento, > 10 % de `NOT_AVAILABLE`, > 10 % de errores de frase); sin evidencia no se mueve nada y se anota en `docs/decisiones.md` | **[DECIDIDO 2026-10-17, Daniel]** |
| Coordinación con la batería con ruido de Sebastián (Voz) para compartir grabaciones de la sala | ML 2 + Voz |
| Resultado de la recalibración (qué parámetros se mueven, con sus números) | Se decide en la sala el sábado; si no hay tiempo, quedan los valores actuales |
