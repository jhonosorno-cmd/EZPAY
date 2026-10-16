# Uso de IA

Cumple la [política de IA del hackathon](https://interledger.org/es/hackathon/ai-policy/): qué
herramientas se usaron, para qué y en qué parte del proyecto. Se llena **durante** el evento; cada
integrante completa su sección y una persona consolida antes de las 10:45 del sábado.

El texto real de los prompts está en [`prompts/`](prompts/).

## Herramientas

- Claude Code (modelo Claude Sonnet 5.5): rol Pagos. Escribe los contratos OpenAPI, las pruebas de
  los mocks y la documentación, a partir de `docs/` y `openspec/`.

## Uso por componente

| Archivo o componente | Rol | Herramienta | Para qué | Revisión humana |
|---|---|---|---|---|
| `openapi/contract-a.yaml`, `openapi/contract-b.yaml`, `openapi/components.yaml` | Pagos | Claude Code | Describir los Contratos A y B (v1 + v1.1) como OpenAPI 3.0.3, con ejemplos por escenario | Pendiente: lectura de Alexander (@jhonosorno-cmd) contra `docs/contratos-*`. Verificado con `npm run lint:openapi` (limpio) y `npm run test:mocks` (en verde) |
| `openapi/check.test.mjs` | Pagos | Claude Code | Pruebas de aceptación de los mocks escritas desde los contratos, antes del YAML | Pendiente: lectura de Alexander (@jhonosorno-cmd). Se vio fallar primero (sin specs) y luego pasar |
| `openapi/README.md`, `package.json`, `redocly.yaml`, sección "Mocks de los contratos" del `README.md` | Pagos | Claude Code | Instrucciones de uso de los mocks y configuración del lint | Pendiente: lectura de Alexander (@jhonosorno-cmd). Los comandos documentados se corrieron |

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
