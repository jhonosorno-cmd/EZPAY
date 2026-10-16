# Uso de IA

Cumple la [política de IA del hackathon](https://interledger.org/es/hackathon/ai-policy/): qué
herramientas se usaron, para qué y en qué parte del proyecto. Se llena **durante** el evento; cada
integrante completa su sección y una persona consolida antes de las 10:45 del sábado.

El texto real de los prompts está en [`prompts/`](prompts/).

## Herramientas

- Claude Code (modelo Claude Sonnet 5.5): rol Pagos. Escribe los contratos OpenAPI, las pruebas de
  los mocks y la documentación, a partir de `docs/` y `openspec/`.
- Claude Code (Claude Sonnet 5.5 y Claude Opus 5.5): módulo de voz `api/voice/`, sus pruebas y el registro de prompts (rol Voz)

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
| `api/voice/phrases.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | `say`: catálogo de `docs/voz/contrato-voz.md` §7 (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee). Revisión adversarial hecha por la IA; corrigió una confirmación sin destinatario |
| `api/voice/agenda_provisional.json` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Agenda ficticia y provisional; se reemplaza por la de Pagos (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/voice/contacts.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | `resolve_recipient` y `resolve_choice` (`contact-resolution`) (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee). Revisión adversarial hecha por la IA |
| `api/voice/intents.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | `extract_intent` solo con reglas, sin LLM (`intent-extraction`) (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee). Revisión adversarial hecha por la IA; corrigió "-20 mil" y "…, cancela" |
| `api/voice/RESULTADOS.md` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Resumen de pruebas, cobertura y entradas hostiles (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/tests/voice/test_replies.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Pruebas de `reply-classification` desde el spec y `frases-desarrollo.md` §C (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/tests/voice/test_phrases.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Pruebas del catálogo de `say` (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/tests/voice/test_contacts.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Pruebas de `contact-resolution` desde el spec y `frases-desarrollo.md` §B (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/tests/voice/test_intents.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Pruebas de `intent-extraction` desde el spec y las 30 frases de `frases-desarrollo.md` §D (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |
| `api/tests/voice/test_package.py` | Voz (ML 1) | Claude Code (Claude Opus 5.5) | Pruebas del paquete: sin LLM, sin red, sin disco, sin float (`prompts/Sebasruiz00/08-todas-las-etapas.md`) | Pendiente (Sebastián aún no lo lee) |

## Archivos con mínima o ninguna IA

- <ruta>: <motivo>

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

Los experimentos descartables (scripts contra la Test Wallet, mediciones de Whisper y SpeechBrain)
se hicieron fuera de este repo y no se trajeron.
