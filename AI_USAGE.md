# Uso de IA

Cumple la [política de IA del hackathon](https://interledger.org/es/hackathon/ai-policy/): qué
herramientas se usaron, para qué y en qué parte del proyecto. Se llena **durante** el evento; cada
integrante completa su sección y una persona consolida antes de las 10:45 del sábado.

El texto real de los prompts está en [`prompts/`](prompts/).

## Herramientas

- Claude Code (modelo Claude Sonnet 5.5): rol Pagos. Escribe los contratos OpenAPI, las pruebas de
  los mocks y la documentación, a partir de `docs/` y `openspec/`.
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
| `docs/flujos/flujo-actual.md` | Pagos | Claude Code (Claude Sonnet 5.5) y subagente general-purpose | Diagramas Mermaid del flujo actual (`main`) a partir de specs, contratos y mocks. Los 7 bloques se renderizaron con mermaid-cli | Pendiente: lectura de Alexander (@jhonosorno-cmd) |
| `docs/flujos/flujo-con-prs.md` | Pagos | Claude Code (Claude Sonnet 5.5) y subagente general-purpose | Diagramas Mermaid del flujo con los PRs #2, #4 y #5 mergeados, a partir de specs y de los PRs. Los 7 bloques se renderizaron con mermaid-cli | Pendiente: lectura de Alexander (@jhonosorno-cmd) |
| `openspec/changes/add-decision-engine/` (`proposal.md`, `design.md`, `tasks.md`, `specs/decision-engine/spec.md`, `specs/pin-validation/spec.md`) | ML 2 | Claude Code y OpenCode (Constructor de Specs) | Specs del motor de decisión y del PIN de H1. Prompts: `prompts/Valdex328/03-specs-h1-motor-y-pin.md`, `prompts/Valdex328/07-flujos-y-conflictos.md` y `prompts/Valdex328/10-instrucciones-a-agentes.md` (A1 a A9) | `openspec validate add-decision-engine --strict` en verde |
| `api/decision/` | ML 2 | Claude Code y OpenCode (Builder) | Motor de decisión `decide(context)`, `parse_context`, `decide_dict` y traducción de `reason` al catálogo de `say`. Prompts: `prompts/Valdex328/04-mocks-openspec-y-siguiente-paso.md`, `prompts/Valdex328/05-integracion-y-pr.md`, `prompts/Valdex328/07-flujos-y-conflictos.md` y `prompts/Valdex328/10-instrucciones-a-agentes.md` (B1 a B5) | Pruebas de `api/tests/decision/`: `PYTHONPATH=. python -m unittest discover -s tests/decision` (desde `api/`) |
| `api/pin/pin.py`, `api/scripts/make_pin_hash.py`, `api/scripts/reset_pin_lock.py`, `api/.env.example` | ML 2 | Claude Code y OpenCode (Builder) | PIN mínimo: hash con sal, contadores, bloqueo, alta y reinicio. Prompts: `prompts/Valdex328/03-specs-h1-motor-y-pin.md` y `prompts/Valdex328/10-instrucciones-a-agentes.md` (B1 y B2) | 35 pruebas pasan: `PYTHONPATH=. python -m unittest discover -s tests/pin` (desde `api/`) |
| `api/tests/decision/`, `api/tests/pin/` | ML 2 | Claude Code y OpenCode (Builder) | Pruebas de los escenarios de los specs. Prompts: `prompts/Valdex328/10-instrucciones-a-agentes.md` (B1 a B5) | Se corren con los comandos de las dos filas anteriores |
| `api/README-ml2.md` | ML 2 | OpenCode (Builder) | Cómo correr las pruebas y cómo usa el orquestador el motor y el PIN. Prompts: `prompts/Valdex328/10-instrucciones-a-agentes.md` (B4 y B5) | Los comandos documentados se corrieron |
| `prompts/Valdex328/`, `prompts/pre-evento/Valdex328/` | ML 2 | Claude Code | Registro de los prompts. Prompts: `prompts/Valdex328/06-prompts-y-ai-usage.md` | Texto literal de las transcripciones |

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
