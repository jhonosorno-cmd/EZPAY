# Uso de IA

Cumple la [política de IA del hackathon](https://interledger.org/es/hackathon/ai-policy/): qué
herramientas se usaron, para qué y en qué parte del proyecto. Se llena **durante** el evento; cada
integrante completa su sección y una persona consolida antes de las 10:45 del sábado.

El texto real de los prompts está en [`prompts/`](prompts/).

## Herramientas

- Claude Code (modelo Claude Sonnet 5.5): rol Pagos. Escribe los contratos OpenAPI, las pruebas de
  los mocks y la documentación, a partir de `docs/` y `openspec/`.
- Claude Code (Claude Sonnet 5.5 y Claude Opus 5.5): módulo de voz `api/voice/`, sus pruebas y el registro de prompts (rol Voz)
- Subagente `general-purpose` de Claude Code: rol Pagos. Escribe los diagramas de flujo de
  `docs/flujos/` a partir de los specs, los contratos y los PRs abiertos, bajo supervisión de
  Claude Code.
- Claude Code (Claude Opus 5.5 y Claude Sonnet 5.5) y OpenCode (modelo `zai-org/GLM-5.3-Flash`, agentes Constructor de Specs y Builder): rol Verificación y calidad (ML 2). Los prompts están en `prompts/Valdex328/`.

## Uso por componente

| Archivo o componente | Rol | Herramienta | Para qué | Revisión humana |
|---|---|---|---|---|
| `openapi/contract-a.yaml`, `openapi/contract-b.yaml`, `openapi/components.yaml` | Pagos | Claude Code | Describir los Contratos A y B (v1 + v1.1) como OpenAPI 3.0.3, con ejemplos por escenario | Pendiente: lectura de Alexander (@jhonosorno-cmd) contra `docs/contratos-*`. Verificado con `npm run lint:openapi` (limpio) y `npm run test:mocks` (en verde) |
| `openapi/check.test.mjs` | Pagos | Claude Code | Pruebas de aceptación de los mocks escritas desde los contratos, antes del YAML | Pendiente: lectura de Alexander (@jhonosorno-cmd). Se vio fallar primero (sin specs) y luego pasar |
| `openapi/README.md`, `package.json`, `redocly.yaml`, sección "Mocks de los contratos" del `README.md` | Pagos | Claude Code | Instrucciones de uso de los mocks y configuración del lint | Pendiente: lectura de Alexander (@jhonosorno-cmd). Los comandos documentados se corrieron |
| `api/voice/amounts.py` | Voz (ML 1) | Claude Code (Claude Sonnet 5.5) | Parser es-CO texto → `Amount` y formato (`amount-parsing`). Borrador en una sesión previa (`prompts/Sebasruiz00/00a-origen-amounts-sesion-previa.md`); revisión adversarial y correcciones H-1 a H-6 (`prompts/Sebasruiz00/01-revision-amounts.md`, `prompts/Sebasruiz00/02-parser-montos.md`) | Sebastián: lo revisó y confirmó que funciona bien (2026-10-16). Evidencia automática: 191 pruebas pasan; revisión adversarial (Prompt 6) hecha por la IA |
| `api/tests/voice/test_amounts.py` | Voz (ML 1) | Claude Code (Claude Sonnet 5.5) | Pruebas de `amount-parsing`: escenarios del spec, frases de `docs/voz/frases-desarrollo.md` §A y entradas hostiles H-1 a H-8 (mismos prompts que la fila anterior) | Sebastián: lo revisó y confirmó que funciona bien (2026-10-16) |
| `prompts/Sebasruiz00/` | Voz (ML 1) | Claude Code (Claude Sonnet 5.5 y Claude Opus 5.5) | Transcripción literal de los prompts de Sebastián, con pie de registro (`prompts/Sebasruiz00/03-registro-de-prompts.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/voice/text.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Normalización de texto compartida (sin tildes ni mayúsculas) (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee). Evidencia automática: 494 pruebas pasan |
| `api/voice/config.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Moneda del MVP, palabra "pesos" y ruta de la agenda (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/voice/replies.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | `classify_reply` (`reply-classification`), lista cerrada sin LLM (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee). Revisión adversarial (Prompt 6) hecha por la IA |
| `api/voice/phrases.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5; Claude Sonnet 5.5 en los cambios del 16 oct) | `say`: catálogo de `docs/voz/contrato-voz.md` §7 (`prompts/Sebasruiz00/08-todas-las-etapas.md`) y, tras fusionar `main`, las 13 situaciones del catálogo único de ML 2, `PIN_KEYBOARD` nuevo y el costo como débito − recibido (`prompts/Sebasruiz00/15-adoptar-catalogo-unico.md`) | Pendiente (Sebastián aún no lo lee). Revisión adversarial hecha por la IA sobre el catálogo original; corrigió una confirmación sin destinatario. Los cambios del 16 oct no tuvieron revisión adversarial aparte. Evidencia automática: 89 pruebas de `say` y 717 en `api/` |
| `api/voice/agenda_provisional.json` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Agenda ficticia y provisional; se reemplaza por la de Pagos (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/voice/contacts.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | `resolve_recipient` y `resolve_choice` (`contact-resolution`) (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee). Revisión adversarial hecha por la IA |
| `api/voice/intents.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | `extract_intent` solo con reglas, sin LLM (`intent-extraction`) (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee). Revisión adversarial hecha por la IA; corrigió "-20 mil" y "…, cancela" |
| `api/voice/RESULTADOS.md` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Resumen de pruebas, cobertura y entradas hostiles (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/tests/voice/test_replies.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Pruebas de `reply-classification` desde el spec y `frases-desarrollo.md` §C (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/tests/voice/test_phrases.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5; Claude Sonnet 5.5 en los cambios del 16 oct) | Pruebas del catálogo de `say` (`prompts/Sebasruiz00/08-todas-las-etapas.md`) y las de las 13 situaciones nuevas, `PIN_KEYBOARD` y el costo (`prompts/Sebasruiz00/15-adoptar-catalogo-unico.md`); se escribieron antes del código y se vieron fallar | Pendiente (Sebastián aún no lo lee) |
| `api/tests/voice/test_contacts.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Pruebas de `contact-resolution` desde el spec y `frases-desarrollo.md` §B (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/tests/voice/test_intents.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Pruebas de `intent-extraction` desde el spec y las 30 frases de `frases-desarrollo.md` §D (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/tests/voice/test_package.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Pruebas del paquete: sin LLM, sin red, sin disco, sin float (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/tests/voice/test_context_shapes.py`; `to_dict()` en `api/voice/intents.py` y `api/voice/contacts.py`; `PAYMENT_PENDING` en `api/voice/phrases.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Forma de `intent` y `resolution` con los nombres del `context` del motor de ML 2, "o" entre montos o destinatarios, y texto de `PAYMENT_PENDING` (v1.1) (`prompts/Sebasruiz00/11-integracion-contexto.md`) | Pendiente (Sebastián aún no lo lee). Evidencia automática: 521 pruebas pasan |
| `docs/flujos/flujo-actual.md` | Pagos | Claude Code (Claude Sonnet 5.5) y subagente general-purpose | Diagramas Mermaid del flujo actual (`main`) a partir de specs, contratos y mocks. Los 7 bloques se renderizaron con mermaid-cli | Pendiente: lectura de Alexander (@jhonosorno-cmd) |
| `docs/flujos/flujo-con-prs.md` | Pagos | Claude Code (Claude Sonnet 5.5) y subagente general-purpose | Diagramas Mermaid del flujo con los PRs #2, #4 y #5 mergeados, a partir de specs y de los PRs. Los 7 bloques se renderizaron con mermaid-cli | Pendiente: lectura de Alexander (@jhonosorno-cmd) |
| `openspec/changes/add-decision-engine/` (`proposal.md`, `design.md`, `tasks.md`, `specs/decision-engine/spec.md`, `specs/pin-validation/spec.md`) | ML 2 | Claude Code y OpenCode (Constructor de Specs) | Specs del motor de decisión y del PIN (H1) y de la verificación de hablante y el enrolamiento (H2). Prompts: `prompts/Valdex328/03-specs-h1-motor-y-pin.md`, `prompts/Valdex328/07-flujos-y-conflictos.md`, `prompts/Valdex328/11-specs-h2-verificacion-y-enrolamiento.md` y `prompts/Valdex328/10-instrucciones-a-agentes.md` (A1 a A12) | `openspec validate add-decision-engine --strict` en verde |
| `api/decision/` | ML 2 | Claude Code y OpenCode (Builder) | Motor de decisión `decide(context)`, `parse_context`, `decide_dict` y traducción de `reason` al catálogo de `say`. Prompts: `prompts/Valdex328/04-mocks-openspec-y-siguiente-paso.md`, `prompts/Valdex328/05-integracion-y-pr.md`, `prompts/Valdex328/07-flujos-y-conflictos.md` y `prompts/Valdex328/10-instrucciones-a-agentes.md` (B1 a B5) | Pruebas de `api/tests/decision/`: `PYTHONPATH=. python -m unittest discover -s tests/decision` (desde `api/`) |
| `api/pin/pin.py`, `api/scripts/make_pin_hash.py`, `api/scripts/reset_pin_lock.py`, `api/.env.example` | ML 2 | Claude Code y OpenCode (Builder) | PIN mínimo: hash con sal, contadores, bloqueo, alta y reinicio. Prompts: `prompts/Valdex328/03-specs-h1-motor-y-pin.md` y `prompts/Valdex328/10-instrucciones-a-agentes.md` (B1 y B2) | 35 pruebas pasan: `PYTHONPATH=. python -m unittest discover -s tests/pin` (desde `api/`) |
| `api/tests/decision/`, `api/tests/pin/` | ML 2 | Claude Code y OpenCode (Builder) | Pruebas de los escenarios de los specs. Prompts: `prompts/Valdex328/10-instrucciones-a-agentes.md` (B1 a B5) | Se corren con los comandos de las dos filas anteriores |
| `api/README-ml2.md` | ML 2 | OpenCode (Builder) | Cómo correr las pruebas y cómo usa el orquestador el motor y el PIN. Prompts: `prompts/Valdex328/10-instrucciones-a-agentes.md` (B4 y B5) | Los comandos documentados se corrieron |
| `verificacion-ml2/textos-enrolamiento.md` | ML 2 | Claude Code | Textos del consentimiento y frases del enrolamiento para la web. Prompts: `prompts/Valdex328/08-textos-enrolamiento.md` | Criterios de PRIV-1, PRIV-2, Ley 1581 y duración de las frases, en el mismo archivo |
| `prompts/Valdex328/`, `prompts/pre-evento/Valdex328/` | ML 2 | Claude Code | Registro de los prompts. Prompts: `prompts/Valdex328/06-prompts-y-ai-usage.md` y `prompts/Valdex328/09-pr-5-y-merge.md` | Texto literal de las transcripciones |

## Archivos con mínima o ninguna IA

- `verificacion-ml2/casos-de-uso.md`: casos de uso preliminares, escritos a mano.

## Trabajo previo al evento

Antes del 16 de octubre no se escribió código del proyecto. La organización confirmó el 16 de
octubre que se permiten los specs escritos antes del evento. Sí se escribieron, con ayuda de IA
(Claude Code), especificaciones y diseños, que se trajeron a este repo el 16 de octubre:

| Archivo o carpeta | Qué es |
|---|---|
| `docs/spec-general.md`, `docs/roles.md` | Spec del equipo: problema, demo, seguridad, privacidad, convenciones, roles |
| `docs/contratos-http-v1.md`, `docs/contratos-cambios-propuestos-v1.1.md` | Contratos HTTP entre frontend, Python y Node |
| `docs/voz/contrato-voz.md` | Interfaz interna del módulo de voz (diseño) |
| `docs/voz/frases-desarrollo.md` | Frases de prueba (texto) |
| `docs/voz/prompt-llm-intencion.md` | Prompt de sistema del LLM de intención, con resultados de prueba |
| `openspec/` | Specs en formato OpenSpec: `add-team-baseline`, `add-payments-service`, `add-payments-client`, `add-voice-understanding`, `add-voice-web-client` |
| `prompts/pre-evento/` | Prompts y plantillas usados antes del evento |
| `prompts/pre-evento/Valdex328/` | Prompts de ML 2 de la revisión del repo de pruebas (decisiones D1 a D9) y de los experimentos de SpeechBrain |

Los experimentos descartables (scripts contra la Test Wallet, mediciones de Whisper y SpeechBrain)
se hicieron fuera de este repo y no se trajeron. Los de SpeechBrain (ML 2) tampoco: audio y embeddings de voces reales no van al repo público. Sus prompts están en `prompts/pre-evento/Valdex328/02-speechbrain.md`.
