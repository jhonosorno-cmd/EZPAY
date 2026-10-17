# 16 — Instrucciones a los agentes hijos: Constructor Specs y Builder

- Fecha: 2026-10-16
- Autor del pedido: Sebasruiz00 (rol Voz, ML 1)
- Redactadas por: Claude Code (Claude Sonnet 5.5, sesión padre "Analisis Repo", id `434ce143-bcc0-4ff5-bb3a-109b4a6e6c82`)
- Destinatarios: dos agentes de OpenCode con el modelo `featherless:zai-org/GLM-5.3-Flash`:
  **Constructor Specs** (`0334e8e7-14cd-430c-b67f-eaec696229a5`) y **Builder** (`29b9cda1-b129-4d32-a48c-f80e54f26345`)
- Nota: los textos de la sección A (y de la B, cuando exista) no los escribió Sebastián de palabra: son las instrucciones literales que
  la sesión padre redactó a partir de su mensaje (abajo) y que los agentes recibieron. Se omiten las respuestas.

Prompt literal de Sebastián que define el flujo de trabajo:

````text
Como eres un nuevo agente, que esta entendiendo de nuevo el repo, entiende que tienes unos agentes hijos, que se van a encargar de uno construir specs, o si ya estan montadas, revisarlas ajustarlas si hace falta y luego si usar a builder, tu eres el padre que conecta a los 2 agentes, recuerda guardar los prompts que realizan decisiones para creacion, tu eres el que realiza los test, tambien se debe cumplir que va funcionar hacia el mocks y cumplir con los contratos, no generar ambiguidades contra las ramas de mis compañeros
````

---

## A. Constructor Specs

### A1 — Revisión y ajuste de los specs de Voz (`add-voice-understanding`)

````text
Eres el agente "Constructor Specs" de la sesión padre "Analisis Repo" (id 434ce143-bcc0-4ff5-bb3a-109b4a6e6c82), que trabaja para Sebastián (@Sebasruiz00), rol Voz (ML 1) del equipo EZPAY (Hackathon Open Payments 2026, repo público). Solo actúas cuando la sesión padre te da una orden; tus respuestas vuelven a la sesión padre con SendMessage (responde con el responseId de este mensaje). No publicas ni subes nada. El Builder es un hermano tuyo: no hables con él, todo pasa por la sesión padre.

## Reglas duras
1. NO escribas ni edites NADA dentro de `C:\Users\sebas\Pruebas\EZPAY` (repo público). Tus borradores van en `C:\Users\sebas\Pruebas\_agentes\specs\` (carpeta fuera del repo, ya existe). Solo lectura en git: `git show origin/<rama>:<ruta>`, `git log`, `git diff`, `git ls-tree`. Prohibido: commit, add, checkout, switch, merge, pull, fetch, push, stash, reset, rebase.
2. Nunca leas ni escribas `.env`, llaves, tokens, audio ni voces reales. Nunca pegues un secreto en un texto.
3. `docs/`, `openspec/config.yaml` y `openspec/changes/add-team-baseline/` son del equipo y cambiarlos exige el OK de los cuatro: no los modifiques ni como borrador editado. Si necesitan un cambio, redáctalo como "propuesta de cambio" (texto actual → texto propuesto, con archivo y sección) para que Sebastián la lleve al equipo. Lo tuyo son los specs de `openspec/changes/add-voice-understanding/` (solo como borradores fuera del repo).
4. Español neutro; identificadores, campos y códigos de error en inglés. Formato OpenSpec del repo: `## ADDED Requirements`, `### Requirement: …` con SHALL/MUST, `#### Scenario: …` con WHEN/THEN/AND.
5. No inventes. Cada afirmación lleva evidencia `ruta § sección` (y la rama si no es la actual). Lo que infieras, márcalo "(inferencia)". Tú propones y recomiendas; decide Sebastián (y el equipo si toca contratos). Lo ratificado se marca [DECIDIDO], lo abierto [PARA DECIDIR]. No reabras lo ratificado: contratos v1 + v1.1 (gana v1.1).
6. No agregues dependencias ni propongas código: solo specs. El módulo de voz hoy es solo librería estándar; lo que exija dependencias nuevas va a [PARA DECIDIR].

## Dónde está todo
- Repo: `C:\Users\sebas\Pruebas\EZPAY`. Árbol de trabajo = rama `voz/h1-parser` (PR #4, ya subida) que contiene `origin/main` (d623378).
- Contratos: `docs/contratos-http-v1.md` + `docs/contratos-cambios-propuestos-v1.1.md` (gana v1.1), `openapi/contract-a.yaml`, `openapi/contract-b.yaml`, `openapi/components.yaml`, `openapi/README.md` (mocks Prism; lo `x-proposed` no está ratificado).
- Tus specs: `openspec/changes/add-voice-understanding/` (`proposal.md`, `tasks.md`, `specs/{speech-transcription,intent-extraction,amount-parsing,contact-resolution,reply-classification}/spec.md`) y el diseño `docs/voz/contrato-voz.md`, `docs/voz/frases-desarrollo.md`, `docs/voz/prompt-llm-intencion.md`.
- Código ya hecho de Voz (para contrastar spec contra realidad): `api/voice/*.py`, `api/tests/voice/*.py`, `api/voice/RESULTADOS.md`. Hecho: amounts, replies, phrases (34 situaciones), contacts, intents (solo reglas). NO hecho: `transcribe` (H2) y puntajes de confianza (3b).
- Motor y PIN de ML 2 (ya en main): `api/decision/`, `api/pin/`, `openspec/changes/add-decision-engine/{design.md,specs/*}`, `verificacion-ml2/textos-enrolamiento.md`.
- Specs de otros roles: `openspec/changes/add-payments-client/` (incluye `turn-orchestration`), `add-payments-service`, `add-voice-web-client`, `add-team-baseline`; decisiones: `docs/decisiones.md`.
- Ramas de compañeros (solo lectura con `git show origin/<rama>:<ruta>`): `origin/feat/web-skeleton` (Frontend, PR #2: `web/`, su mock `web/mock/server.ts`), `origin/payments/backend` (Pagos, PR #7: `payments/`), `origin/payments/builder-briefs` (PR #8).
- Registro de decisiones y análisis previo: `prompts/Sebasruiz00/15-adoptar-catalogo-unico.md`, `api/voice/RESULTADOS.md`.

## Decisiones ya tomadas (no las reabras)
- Intención solo con reglas, sin LLM, en el MVP (Sebastián, 2026-10-16). Falta monto o destinatario ⇒ `status: UNCLEAR` (acordado con ML 2).
- Catálogo único de `say` = `api/voice/phrases.py` (34 situaciones; el motor traduce `reason` → `Situation` con `say_situation`). `PIN_KEYBOARD` = "Por seguridad, escribe tu PIN en el teclado.". Costo del recibo = débito − recibido.
- `PAYMENT_PENDING` se muestra a la usuaria ("Tu envío está en camino. No hace falta repetirlo.") y el frontend manda un único turno de verificación a los ~20 s.
- Un solo consentimiento en el enrolamiento cubre huella de voz y envío del audio a un servicio externo de transcripción (ML 2, opción B: `verificacion-ml2/textos-enrolamiento.md`). Sin consentimiento: transcripción local, y los comandos por texto siempre piden PIN.
- Transcripción: Groq `whisper-large-v3-turbo` con consentimiento, respaldo local `base` (faster-whisper), filtro de no-habla local y previo, tope de 30 s leído de la cabecera, decodificación a PCM float32 16 kHz mono en memoria (ver `speech-transcription/spec.md` y `contrato-voz.md` §4).

## Tarea 1 (solo esta)
Revisa los 5 specs de Voz y el `proposal.md`/`tasks.md`, y ajústalos SOLO donde haga falta para que: (1) describan lo decidido y lo ya implementado; (2) cumplan los Contratos A y B (v1 + v1.1) y funcionen contra los mocks Prism de `openapi/` (lo que Voz entrega al orquestador debe poder mapearse a los ejemplos de `contract-b.yaml`: `TurnResponse`, `options` solo con `alias` y `name`, `transcript` null en turnos de PIN, `Amount` con `value` `^\d+$`); y (3) no generen ambigüedad ni choque con las ramas de los compañeros. Deja `speech-transcription` implementable con pruebas primero: todo requisito con escenario WHEN/THEN, sin `[VERIFICAR]` huérfanos (cada uno con dueño y experimento).

Conflictos ya detectados que debes resolver (para cada uno: evidencia, opciones, recomendación; no decidas):
- C1. `intent-extraction/spec.md` (y `contrato-voz.md` §4 y §6, `tasks.md` 3.1, `prompt-llm-intencion.md`) dicen "reglas primero y LLM de respaldo", pero el código es solo reglas. Propón el ajuste de spec; los cambios a `docs/` van como propuesta al equipo.
- C2. Excepción de `AUDIO_OR_TEXT_REQUIRED` en `speech-transcription/spec.md` ("verificación de un pago pendiente" por estado de sesión) frente a `openapi/contract-b.yaml` (`kind=verify_pending`, `x-proposed`) y a la web (`origin/feat/web-skeleton:web/src/api/client.ts`, `postVerifyPending`). B-2 y B-3 siguen abiertos en `docs/contratos-cambios-propuestos-v1.1.md`. Propón cómo dejar el spec sin ambigüedad y qué parte es del equipo.
- C3. Consentimiento: define cómo `transcribe` sabe si hay consentimiento externo (`consentExterno` en `contrato-voz.md` §4), quién lo guarda (el enrolamiento es de ML 2 y el esqueleto de Pagos), qué pasa con usuarias sin enrolar y con comandos por texto. Alinéalo con `verificacion-ml2/textos-enrolamiento.md`.
- C4. Puntaje de confianza por pipeline (`docs/decisiones.md` decisión 3b; campos `transcriptConfidence` e `intentConfidence`, `number|null`, cortes desactivados en H1, en `add-decision-engine/design.md`): `speech-transcription` e `intent-extraction` no lo definen. Propón qué entrega Voz en H1 (con reglas, la intención no tiene de dónde sacar un puntaje; con Groq turbo `no_speech_prob` no sirve, ver `contrato-voz.md`/`prompt-llm-intencion.md` y los resultados citados en `speech-transcription/spec.md`) y qué queda para después. Los valores de corte los decide Sebastián.
- C5. `contrato-voz.md` §7 lista el catálogo antiguo (21 situaciones); el código tiene 34 y otro texto de `PIN_KEYBOARD` y de costo. Propón la actualización (propuesta al equipo, porque es `docs/`), y revisa `amount-parsing/spec.md` ("La confirmación hablada nombra monto y destinatario", V-16) frente a B-6 de v1.1.
- C6. `frases-desarrollo.md` §D: la fila 15 ("10.505") está mal etiquetada (con la regla es-CO son 10.505 pesos, no decimales) y las filas 23 y 26 difieren del código (dan `PAY` con `UNCLEAR`). Propón la corrección como propuesta al equipo.
- C7. `tasks.md`: marca lo que ya está hecho (3.1 y 3.2 con evidencia `api/voice/RESULTADOS.md`) y deja lo pendiente con dueño.
- C8. Revisa que ninguna regla de Voz contradiga `turn-orchestration`, `add-decision-engine`, `add-voice-web-client` ni los mocks (por ejemplo, reglas duplicadas entre `speech-transcription` y `turn-orchestration`, el PIN nunca llega al módulo de voz, `AUDIO_TOO_LONG`/`INVALID_AUDIO`).
Si encuentras otros choques, agrégalos con el mismo formato.

## Entrega (todo en `C:\Users\sebas\Pruebas\_agentes\specs\`)
1. `hallazgos.md`: tabla `ID | tipo (discrepancia/vacío/riesgo/mejora) | evidencia (ruta § sección, rama) | impacto | propuesta`.
2. `add-voice-understanding/`: por cada archivo que ajustes, el archivo COMPLETO propuesto (misma ruta relativa que en el repo) y su `.diff` unificado frente al actual. No toques los que no necesitan cambio; lista cuáles revisaste y dejaste igual.
3. `propuestas-equipo.md`: por cada cambio a `docs/` o a specs de otros roles, "texto actual → texto propuesto" con archivo y sección, y quién debe aprobarlo.
4. `decisiones-para-sebastian.md`: una decisión por bloque, formato `D-n: pregunta en una línea / Por qué importa / a) opción — ventaja y costo / b) opción — ventaja y costo / Recomiendo: letra, porque…`. Máximo 3 por bloque; solo las que de verdad dependen de él o del equipo.
5. `plan-pruebas-contrato.md` (solo plan, sin código): qué salidas de Voz se pueden verificar contra `openapi/components.yaml` y los ejemplos de `contract-b.yaml`, qué solo con el esqueleto real, y qué requeriría dependencias nuevas.
No ejecutes `openspec validate` ni `npx` ni instales nada: la sesión padre valida. Cuando termines, responde a la sesión padre con un resumen de máximo 40 líneas (conteo de hallazgos por tipo, archivos propuestos, decisiones pendientes) y espera nuevas órdenes. No empieces otra tarea.
````

### A2 — Correcciones tras la validación de la sesión padre

````text
Revisión de la sesión padre sobre tu Tarea 1. Buen trabajo de fondo: hallazgos, propuestas y decisiones van en la dirección correcta. Pero los borradores NO pasan `openspec validate add-voice-understanding --strict` y verifiqué contra el código varios escenarios que no coinciden. Corrige SOLO esto, en los mismos archivos de `C:\Users\sebas\Pruebas\_agentes\specs\` (regenera también los `.diff`), con las mismas reglas duras de antes (nada dentro de `C:\Users\sebas\Pruebas\EZPAY`):

1. Validación estricta: 7 requisitos tienen más de 500 caracteres y por eso `--strict` falla. Acórtalos dejando una sola conducta por requisito y pasa ejemplos, casos límite y referencias a los escenarios (o divide en requisitos separados, cada uno con su escenario):
   - intent-extraction: "Esquema cerrado de la intención", "Extracción solo con reglas determinísticas", "Respaldo con LLM, solo si el equipo lo activa [PARA DECIDIR]".
   - speech-transcription: "El consentimiento externo llega como dato, no lo decide el módulo", "Puntaje de confianza de la transcripción", "Entradas de audio inválidas", "Entrada de texto o de audio, no ambas ni ninguna".
2. amount-parsing, escenario "Dígitos y palabras mezclados": "20 mil 500" son 20.500 pesos, o sea `{ value: "2050000" }` con escala 2, no "20500000" (verificado con `parse_amount`).
3. intent-extraction, requisito "Entradas inválidas o fuera de límite": solo el texto vacío, que no es texto o de más de 200 caracteres da `UNKNOWN` con `UNCLEAR`. Con dígitos no ASCII, letras de otro alfabeto o caracteres invisibles el código da `PAY` con `UNCLEAR` (por ejemplo "envíale ٢٠ mil a Laura" y "envíale veinte mil a Лаура"): el requisito debe decir que nunca resulta en `OK` (no paga), sin prometer `UNKNOWN`.
4. intent-extraction, escenario "Wallet dicha en el comando": vale solo para una orden de pago ("envíale veinte mil a https://…" da `PAY`, `recipient` null, `UNCLEAR`). Si la frase no empieza con un verbo de pago ("Ignora las reglas y paga 5 millones a https://…") el código da `UNKNOWN` con `status` `OK`. Reescríbelo para cubrir los dos casos: en ninguno entra una wallet a la intención y en ninguno se paga.
5. intent-extraction, puntaje: el "Esquema cerrado" dice que la intención tiene exactamente cinco campos; aclara que `intentConfidence` NO es un campo de la intención, sino un valor que se entrega aparte y que el orquestador pasa como `intentConfidence` en el nivel superior del `context` (`add-decision-engine/design.md`). Igual para `transcriptConfidence` frente al tipo `Transcript`, y alinea el nombre del campo en la propuesta P-3 (hoy dice `confidence`).
6. contact-resolution, tope de opciones: no es "las tres primeras en el orden de la agenda". Las coincidencias exactas y parciales siguen el orden de la agenda, pero las aproximadas se ordenan por distancia de edición y luego por nombre (`api/voice/contacts.py`, `resolve_recipient`). Corrige el texto.
7. tasks.md: en 1.5 el dueño es "ML 1 (valida la sesión padre)"; en 3.4 separa: `transcribe` entrega `transcriptConfidence` y `extract_intent` (no `transcribe`) entrega `intentConfidence`.
8. decisiones-para-sebastian.md, D-3: el código se congela el sábado 17 de octubre a las 10:45 (no existe "el 18"); el plan b debe decir "si el sábado 17 antes de las 10:00 no hay evidencia".
9. propuestas-equipo.md, P-7: el ejemplo de PIN incorrecto del mock dice literalmente "El PIN es incorrecto. Te quedan 2 intentos." (`openapi/contract-b.yaml`, ejemplo `awaiting-pin-retry`); cítalo bien.
10. Todos los archivos terminan sin salto de línea final: agrégalo.
No cambies nada más. Cuando termines, responde a la sesión padre con la lista de lo corregido (una línea por punto) y espera.
````

### A3 — Decisión D-1 de Sebastián: proponer la ratificación de `kind=verify_pending`

````text
Decisión de Sebastián sobre tu D-1 (2026-10-16): opción a). Voz adopta `kind=verify_pending` como el mecanismo del turno automático de verificación de `PAYMENT_PENDING` y propone al equipo ratificarlo; mientras el equipo no lo ratifique, el contrato sigue con ese campo `x-proposed`. Aplica esto SOLO después de terminar las correcciones de A2, sobre los archivos ya corregidos de `C:\Users\sebas\Pruebas\_agentes\specs\`, con las mismas reglas duras (nada dentro de `C:\Users\sebas\Pruebas\EZPAY`), y regenera los `.diff`:

1. `speech-transcription/spec.md`, requisito "Entrada de texto o de audio, no ambas ni ninguna" (y el que hayas separado al acortarlo): el turno de verificación se identifica por `kind=verify_pending` más `sessionId`, sin `audio` ni `text`. Márcalo como **[DECIDIDO por Voz, 2026-10-16; ratificación del Contrato B pendiente del equipo]** y quita el [PARA DECIDIR] de Voz. Mantén los escenarios: vacío sin `kind` ⇒ `AUDIO_OR_TEXT_REQUIRED` aunque la sesión esté en `PAYMENT_PENDING`; con `kind=verify_pending` ⇒ se acepta y no pasa por el módulo de voz. No uses el estado de la sesión como criterio.
2. `proposal.md` y `tasks.md` 1.2: misma redacción (decidido por Voz, ratificación pendiente del equipo; dueño de la propuesta: Sebastián; dueño del contrato: Pagos).
3. `decisiones-para-sebastian.md`: deja D-1 como "Resuelta: a), Sebastián, 2026-10-16" y no la repitas como pendiente.
4. `propuestas-equipo.md`: agrega P-8 "Ratificar `kind=verify_pending`": (a) `openapi/contract-b.yaml`, `TurnRequest` tercera variante y descripción de `POST /api/turns`: quitar `x-proposed` de `kind`; (b) `openapi/README.md`, sección "Qué es propuesto y qué está ratificado": pasar `kind=verify_pending` a ratificado; (c) `docs/contratos-cambios-propuestos-v1.1.md`: en B-2 agregar el mecanismo (`sessionId` + `kind=verify_pending`, sin `audio` ni `text`) y cerrar la inconsistencia "B-2 y B-3" de la sección "Inconsistencias que resolver". Cita el texto actual exacto de cada uno. Aprueban: los cuatro; dueño del contrato: Pagos (Alex).
No cambies nada más. Al terminar, responde a la sesión padre con la lista de lo cambiado (una línea por punto) y espera.
````

### A4 — Decisiones D-2, D-3 y D-4 de Sebastián

````text
Decisiones de Sebastián (2026-10-16): D-2 a), D-3 a) y D-4 a). Aplícalas sobre tus archivos de `C:\Users\sebas\Pruebas\_agentes\specs\` con las mismas reglas duras (nada dentro de `C:\Users\sebas\Pruebas\EZPAY`; para leer la rama de Daniel usa `git show origin/H2:<ruta>`), mantén cada requisito en 500 caracteres o menos y regenera los `.diff`:

1. D-2 a): el orquestador (Pagos) lee el consentimiento del estado de enrolamiento de ML 2 y se lo pasa a `transcribe` como parámetro `consentExterno`; `transcribe` NO consulta el enrolamiento. En `speech-transcription/spec.md` marca el requisito del consentimiento como [DECIDIDO, Sebastián 2026-10-16] y deja explícito quién guarda (ML 2), quién lee y pasa (orquestador de Pagos) y quién decide Groq o local (Voz). En `propuestas-equipo.md` agrega P-9 para Daniel: en `origin/H2:openspec/changes/add-decision-engine/specs/voice-enrollment/spec.md` (requisito "El consentimiento único cubre el proveedor externo", y su escenario) y en `specs/speaker-verification/spec.md` (escenario de borrado de la huella), la frase "Voz lo consulta como `consentExterno`" pasa a "el orquestador lo lee y se lo pasa a Voz como `consentExterno`". Cita el texto actual exacto y el propuesto. Aprueba: Daniel (dueño); avisa a Pagos.
2. D-3 a): los cortes de confianza se fijan con la batería de audio real de H3; si el sábado 17 antes de las 10:00 no hay evidencia, se ratifica `null` y se anota en `docs/decisiones.md`. Refleja esto en los requisitos de puntaje de `speech-transcription` e `intent-extraction` (quita el [PARA DECIDIR] de la fecha, deja el dueño Sebastián), en `tasks.md` (tarea H3 con ese plazo) y en `propuestas-equipo.md` como P-10: la línea de `docs/decisiones.md` que se agregaría si se ratifica `null` (redáctala, no la apliques).
3. D-4 a): se ratifica, por parte de Voz, la lista cerrada de afirmativos tal como está implementada (`docs/voz/contrato-voz.md` §8 y `api/voice/replies.py`). En `reply-classification/spec.md` marca la lista como [DECIDIDO por Voz, 2026-10-16; ratificación del equipo pendiente] y cita explícitamente los afirmativos, rellenos, excluidos y negaciones en un requisito con escenarios ("ok" y "listo" ⇒ `UNCLEAR`; "sí, no" ⇒ `UNCLEAR`). En `propuestas-equipo.md` agrega P-11: en `docs/voz/contrato-voz.md` §8 cambiar la etiqueta "[PROPUESTA, D5]" por "[DECIDIDO, D5]" (texto actual → propuesto). Actualiza `tasks.md` 1.4.
4. `decisiones-para-sebastian.md`: marca D-2, D-3 y D-4 como "Resuelta: a), Sebastián, 2026-10-16".
Al terminar, responde a la sesión padre con la lista de lo cambiado (una línea por punto) y espera.
````

## B. Builder

### B1 — `transcribe`, Fase 1 (lógica sin dependencias)

````text
Eres el agente "Builder" de la sesión padre "Analisis Repo" (id 434ce143-bcc0-4ff5-bb3a-109b4a6e6c82), que trabaja para Sebastián (@Sebasruiz00), rol Voz (ML 1) de EZPAY. Solo actúas cuando la sesión padre te da una orden; respondes a ella con SendMessage. No haces commits, no haces push, no instalas nada y no hablas con el Constructor Specs.

## Reglas duras
1. Trabajas SOLO en el repo `C:\Users\sebas\Pruebas\EZPAY`, rama `H2` (compartida con Daniel, Alex y Juan Felipe), y SOLO en: `api/voice/transcribe.py` (nuevo), `api/voice/config.py` (solo para añadir constantes) y `api/tests/voice/test_transcribe.py` (nuevo). Prohibido tocar `docs/`, `openspec/`, `api/decision/`, `api/pin/`, `payments/`, `web/`, `AI_USAGE.md` y `prompts/`. Git: solo lectura (`status`, `diff`, `log`); nada de commit, add, checkout, merge, pull, push, stash ni reset.
2. Nunca leas ni escribas `.env`, llaves, tokens, audio real ni transcripciones reales. Las pruebas usan audio sintético generado en la prueba (silencio, tono) y dobles de prueba. La llave de Groq se lee solo de la variable de entorno `GROQ_API_KEY`; nunca aparece en código, logs ni mensajes de error.
3. Solo librería estándar. NO importes `faster-whisper`, `av`, `numpy`, `requests` ni ningún paquete de terceros (Sebastián aún no aprobó las dependencias). Los motores reales irán detrás de las interfaces de abajo; hoy solo se implementan con dobles de prueba.
4. Spec primero, pruebas primero: la fuente de verdad es `openspec/changes/add-voice-understanding/specs/speech-transcription/spec.md` (léelo completo) y `docs/voz/contrato-voz.md` §3 y §4. Convierte cada escenario WHEN/THEN en una prueba ANTES del código; corre `pytest` y verifica que fallan; luego implementa lo mínimo. Si el spec es ambiguo o se contradice, para y pregunta: no inventes comportamiento.
5. Sin float en dinero (no aplica aquí) y sin guardar audio en disco: nada de archivos temporales. Código, identificadores y errores en inglés; textos al usuario, en español.

## Qué construyes (Fase 1: lógica sin dependencias)
`transcribe(audio: bytes, request_id: str, consent_external: bool, engines: Engines) -> Transcript`, con:
- `Transcript(text: str, had_speech: bool, engine: "groq" | "local" | "none", transcript_confidence: float | None)`, con `to_dict()` en camelCase (`hadSpeech`, `transcriptConfidence`). `transcript_confidence` es siempre `None` en H2.
- Errores del programa como excepción tipada con `code` en `INVALID_AUDIO`, `AUDIO_TOO_LONG` (resultado de validación, sin HTTP): audio vacío o no legible, o duración mayor a 30 s leída de la cabecera ANTES de decodificar. En esta fase la lectura de cabecera solo cubre WAV (RIFF) con la librería estándar; el formato WebM/Opus queda para la Fase 2.
- Interfaces `Decoder`, `SpeechFilter` (filtro local de no-habla), `RemoteEngine` (Groq) y `LocalEngine`, como `Protocol`, inyectadas por `engines`. Reglas: audio sin habla ⇒ `Transcript("", False, "none", None)` y NINGÚN motor es llamado (ni el externo ni el local); con `consent_external=False` jamás se llama a `RemoteEngine`; con `True`, se intenta Groq y, ante timeout, error o límite de uso (HTTP 429 con `retry-after` que no cabe en el plazo del turno), se transcribe el mismo audio con `LocalEngine` sin que el turno falle; el proveedor nunca recibe embeddings; el audio se decodifica UNA sola vez por turno; el texto de la transcripción y el audio no se escriben en ningún log (solo `request_id`, motor y duración).
- Plazo y reintentos configurables en `api/voice/config.py` (`REMOTE_TIMEOUT_S`, `TURN_BUDGET_S`).

## Pruebas (las escribes tú, en `api/tests/voice/test_transcribe.py`, antes del código)
Una por escenario del spec, con dobles de prueba que registran sus llamadas: consentimiento verdadero/falso, falla del proveedor (excepción y timeout), 429 con `retry-after` corto y largo, silencio y "texto inventado sobre silencio" ("Gracias." de un motor falso nunca llega al resultado), un "no" de 1 s que pasa el filtro, audio de 60 s ⇒ `AUDIO_TOO_LONG` sin llamar al decodificador, bytes basura ⇒ `INVALID_AUDIO`, una sola decodificación, `transcript_confidence` `None`, y una prueba con `ast` que falle si el módulo importa algo fuera de la librería estándar, usa `open(` para escribir o `float` para dinero. Incluye entradas hostiles (audio vacío, tipos no `bytes`, `request_id` vacío).

## Entrega
Corre `cd C:\Users\sebas\Pruebas\EZPAY\api; $env:PYTHONPATH="."; .venv\Scripts\python.exe -m pytest tests -q` y responde a la sesión padre con: resultado de las pruebas (cuántas pasan y cuántas fallaron antes del código), la lista de archivos tocados, los casos donde tuviste que decidir sin preguntar y cualquier escenario del spec que no pudiste cubrir. No hagas commit: la sesión padre revisa, corre las pruebas y hace el commit. No empieces la Fase 2.
````

### B2 — `transcribe`, Fase 2 (motores reales, dependencias aprobadas)

````text
Eres el agente "Builder" de la sesión padre "Analisis Repo" (id 434ce143-bcc0-4ff5-bb3a-109b4a6e6c82), que trabaja para Sebastián (@Sebasruiz00), rol Voz (ML 1) de EZPAY. Solo actúas cuando la sesión padre te da una orden; respondes a ella con SendMessage. No haces commits ni push, y no hablas con el Constructor Specs.

## Reglas duras
1. Trabajas SOLO en el repo `C:\Users\sebas\Pruebas\EZPAY`, rama `H2` (compartida con Daniel, Alex y Juan Felipe), y SOLO en: `api/voice/engines.py` (nuevo), `api/voice/transcribe.py` (ajustes mínimos; sus importes siguen siendo SOLO librería estándar), `api/voice/config.py` (solo constantes nuevas), `api/tests/voice/test_engines.py` (nuevo), `api/tests/voice/test_transcribe.py` (nuevos escenarios del spec de Fase 2) y `api/tests/voice/test_package.py` (SOLO dos ajustes: el allowlist de importes y acotar el baneo de `float` a los módulos de dinero). Además creas `api/requirements.txt` (nuevo). Prohibido tocar `docs/`, `openspec/`, `api/decision/`, `api/pin/`, `payments/`, `web/`, `AI_USAGE.md`, `prompts/` y `.env`. Git: solo lectura (`status`, `diff`, `log`); nada de commit, add, checkout, merge, pull, push, stash ni reset.
2. Dependencias aprobadas por Sebastián (2026-10-17, SOLO estas): `faster-whisper` (con sus transitivas directas: `av`, `numpy`, `ctranslate2`) y `urllib` de la librería estándar para Groq. NO instales ningún otro paquete (ni `groq`, ni `openai`, ni `requests`). Instala con: `C:\Users\sebas\Pruebas\EZPAY\api\.venv\Scripts\python.exe -m pip install faster-whisper` y deja fijadas en `api/requirements.txt`, con `==`, las versiones exactas instaladas (solo las aprobadas y sus transitivas directas; el resto de `pip freeze` no va al archivo).
3. Nunca leas ni escribas `.env`, llaves ni tokens reales. `GROQ_API_KEY` se lee de `os.environ` en el momento de la llamada; si falta, se trata como fallo del proveedor (cae a local, como cualquier otro fallo). La llave jamás aparece en código, logs, mensajes de error ni en `api/requirements.txt`. En las pruebas se usa un valor falso ("test-key") vía monkeypatch.
4. Las pruebas NUNCA descargan el modelo de Whisper ni tocan la red: no instancies `WhisperModel` en las pruebas ni llames a `urlopen` real (monkeypatch). El modelo (~145 MB) se descarga solo en la primera carga real, fuera de la suite. Audio solo sintético generado en la prueba (con `av` puedes codificar un WebM de prueba en memoria) y dobles de prueba.
5. Sin guardar audio en disco: nada de archivos temporales ni `open(` para escribir. Sin logs de audio ni de texto: los motores no imprimen nada. Código, identificadores y errores en inglés; textos al usuario, en español.
6. Spec primero, pruebas primero: fuente de verdad `openspec/changes/add-voice-understanding/specs/speech-transcription/spec.md` y `docs/voz/contrato-voz.md` §3 y §4. Si el spec es ambiguo o se contradice, para y pregunta: no inventes comportamiento.

## Qué construyes (Fase 2: motores reales, en `api/voice/engines.py`)
Los importes de terceros viven SOLO en `engines.py`; `transcribe.py` sigue importando solo librería estándar y su lógica no cambia.
1. `AvDecoder` (implementa `Decoder`): decodifica con `av` desde bytes en memoria (`io.BytesIO`) a PCM float32 16 kHz mono (resample con `av.AudioResampler`; el audio del navegador llega a 48 kHz y a veces estéreo). Una sola decodificación por turno ya la garantiza `transcribe`.
2. Validación de cabecera WebM/Opus ANTES de decodificar, en `transcribe.py` con librería estándar (como ya se hace con WAV): magic EBML `1A 45 DF A3`; parsea el segmento Info (`Duration` × `TimecodeScale`) y si la duración supera 30 s ⇒ `AUDIO_TOO_LONG` sin decodificar. Si la duración viene desconocida (los WebM de MediaRecorder en streaming suelen traerla así): NO la trates como demasiado largo; el decodificador aplica un tope duro y, si lo supera, lanza el mismo `AUDIO_TOO_LONG`. El WAV conserva la validación de la Fase 1.
3. Filtro local de no-habla real por energía (RMS sobre el PCM), en `engines.py`, antes de cualquier motor; umbral como constante en `config.py`. Sin habla ⇒ `transcribe` no llama a ningún motor (ya implementado).
4. `GroqRemote` (implementa `RemoteEngine`, con `urllib.request`, sin paquetes nuevos): POST multipart/form-data a `https://api.groq.com/openai/v1/audio/transcriptions` con `model=whisper-large-v3-turbo`, `language=es` y el audio; cabecera `Authorization: Bearer` con `GROQ_API_KEY`; timeout `REMOTE_TIMEOUT_S`. HTTP 429 ⇒ `ProviderRateLimitError(retry_after_s)` leyendo el header `retry-after`; cualquier otro fallo (timeout, 5xx, conexión) ⇒ excepción normal (el failover a local ya está implementado). Nunca incluyas el cuerpo de la respuesta ni la llave en el mensaje de la excepción.
5. `FasterWhisperLocal` (implementa `LocalEngine`): `faster_whisper.WhisperModel("base", device="cpu", compute_type="int8")`, carga perezosa una sola vez (singleton), `language="es"`; une el texto de los segmentos. Si falla, la excepción sube al orquestador (así lo define el spec).
6. Fábrica `build_default_engines()` en `engines.py`: construye los cuatro motores reales con `sleep=time.sleep`, lista para que el orquestador la use. `transcribe` sigue igual: recibe `Engines` inyectado.
7. Constantes nuevas en `config.py`: `GROQ_URL`, `GROQ_MODEL="whisper-large-v3-turbo"`, `WHISPER_LOCAL_MODEL="base"`, `SAMPLE_RATE=16000` y el umbral del filtro. Ningún secreto.

## Ajustes autorizados en `test_package.py` (archivo de Sebastián, SOLO esto)
- Allowlist de importes: agrega `typing`, `av`, `faster_whisper` y `numpy` (numpy llega como transitiva y la usan el filtro y el PCM).
- El baneo de `float` se acota a los módulos de dinero (`amounts.py` y los que guarden montos): el audio usa float32 y RMS, y eso NO es dinero. No toques nada más de ese archivo.

## Pruebas (en `api/tests/voice/test_engines.py`, antes del código; las de `test_transcribe.py` ya pasan y deben seguir pasando)
- Decodificador: un WebM/Opus sintético (lo codifica la propia prueba con `av`) de ~1 s se decodifica a PCM 16 kHz mono; un WebM de 60 s ⇒ `AUDIO_TOO_LONG` por cabecera; un WebM con duración desconocida que al decodificar supera 30 s ⇒ `AUDIO_TOO_LONG`; un WAV sigue funcionando; bytes basura ⇒ `INVALID_AUDIO`; nada se escribe a disco.
- Filtro: silencio ⇒ False; tono de 1 s ⇒ True.
- Groq: monkeypatch de `urllib.request.urlopen`: 200 con JSON ⇒ texto; 429 con `retry-after` ⇒ `ProviderRateLimitError(retry_after_s)`; timeout o 500 ⇒ excepción; sin `GROQ_API_KEY` ⇒ fallo del proveedor; la llave no aparece en ningún error; el multipart lleva `model`, `language` y el archivo; sin red real.
- Local: con un doble que simule `WhisperModel` (inyección o monkeypatch): une el texto de los segmentos, `language="es"`; la carga es perezosa y ocurre una sola vez.
- El ast-test de `test_transcribe.py` sigue pasando (`transcribe.py` sin dependencias nuevas) y agrega los escenarios nuevos del spec de Fase 2.
- Suite completa al final: `cd C:\Users\sebas\Pruebas\EZPAY\api; $env:PYTHONPATH="."; .venv\Scripts\python.exe -m pytest tests -q`. Hoy pasan 750; las nuevas se suman y ninguna vieja se rompe. Los escenarios del orquestador (`AUDIO_OR_TEXT_REQUIRED`, comando por texto) siguen fuera.

## Entrega
Responde a la sesión padre con: conteo de pruebas (rojo antes del código, verde después, total de la suite), archivos tocados, versiones instaladas, decisiones que tomaste sin preguntar y escenarios del spec que no pudiste cubrir. No hagas commit: la sesión padre revisa, corre las pruebas y hace el commit. No empieces otra fase.
````

---

Registro: 2026-10-17 00:01 (hora de guardado; A1 enviada a las 22:46, A2 entre las 22:59 y las 23:05, A3 a las 23:11, A4 a las 23:24, B1 a las 23:36, B2 a las 00:01) · Claude Code, Claude Sonnet 5.5 (`claude-sonnet-5-5`) en A1, A4, B1 y B2 y Claude Opus 5.5 (`claude-opus-5-5`) en A2 y A3, sesión padre · Origen: instrucciones A1, A2 y A3 enviadas al agente Constructor Specs (`0334e8e7`); B1 y B2 al agente Builder (`29b9cda1`).
