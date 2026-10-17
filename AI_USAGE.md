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
- Builder del rol Pagos: agente de opencode con el modelo `featherless:zai-org/GLM-5.3-Flash`. Porta
  y corrige `payments/` y escribe sus pruebas, bajo supervisión de Claude Code (Claude Sonnet 5.5),
  que lee cada diff y vuelve a correr las pruebas.

## Uso por componente

| Archivo o componente | Rol | Herramienta | Para qué | Revisión humana |
|---|---|---|---|---|
| `openapi/contract-a.yaml`, `openapi/contract-b.yaml`, `openapi/components.yaml` | Pagos | Claude Code | Describir los Contratos A y B (v1 + v1.1) como OpenAPI 3.0.3, con ejemplos por escenario | Pendiente: lectura de Alexander (@jhonosorno-cmd) contra `docs/contratos-*`. Verificado con `npm run lint:openapi` (limpio) y `npm run test:mocks` (en verde) |
| `openapi/check.test.mjs` | Pagos | Claude Code | Pruebas de aceptación de los mocks escritas desde los contratos, antes del YAML | Pendiente: lectura de Alexander (@jhonosorno-cmd). Se vio fallar primero (sin specs) y luego pasar |
| `openapi/README.md`, `package.json`, `redocly.yaml`, sección "Mocks de los contratos" del `README.md` | Pagos | Claude Code | Instrucciones de uso de los mocks y configuración del lint | Pendiente: lectura de Alexander (@jhonosorno-cmd). Los comandos documentados se corrieron |
| `docs/flujos/flujo-actual.md` | Pagos | Claude Code (Claude Sonnet 5.5) y subagente general-purpose | Diagramas Mermaid del flujo actual (`main`) a partir de specs, contratos y mocks. Los 7 bloques se renderizaron con mermaid-cli | Pendiente: lectura de Alexander (@jhonosorno-cmd) |
| `docs/flujos/flujo-con-prs.md` | Pagos | Claude Code (Claude Sonnet 5.5) y subagente general-purpose | Diagramas Mermaid del flujo con los PRs #2, #4 y #5 mergeados, a partir de specs y de los PRs. Los 7 bloques se renderizaron con mermaid-cli | Pendiente: lectura de Alexander (@jhonosorno-cmd) |
| `payments/src/config.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): lectura y validación de variables de entorno | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/src/crypto.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): cifrado AES-256-GCM de tokens y verificación del hash de interacción | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/src/domain/service.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): reglas de grants, quotes, pagos e idempotencia. Cambio de la unidad 2: campos faltantes de `POST /v1/grants` y `interval` no soportado se mapean a códigos del Contrato A (D-10 a) | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/src/errors.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): errores tipados del servicio | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/src/http/app.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): rutas `/v1`, formato de error y log por request. Cambio de la unidad 2: ruta desconocida y JSON malformado responden `500 INTERNAL_ERROR` (D-10 a) | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/src/interval.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): lectura de `interval` ISO 8601 repetitivo | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/src/main.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): arranque del servicio en 127.0.0.1 | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/src/money.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): montos con `BigInt`, sin floats (CONV-1) | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/src/op/adapter.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): único módulo que usa el SDK de Open Payments. Cambios de la unidad 2: acciones `create`, `read`, `list` (A-3) y URL de `getGrantSpentAmounts` con la raíz del resource server | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/src/ports.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): puertos del dominio | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/src/store/db.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): persistencia SQLite con tokens cifrados | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/scripts/reset-db.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): script que borra la base de datos para preparar la demo | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/test/fakes.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): doble de Open Payments para las pruebas | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/test/grants.test.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): pruebas de grants | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/test/payments.test.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): pruebas de quotes, pagos e idempotencia. Cambio de la unidad 2: rutas temporales con `os.tmpdir()` | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/test/http.test.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): pruebas HTTP del flujo completo | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/test/op-adapter.test.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Escrito por el builder antes de la corrección: prueba la URL de `getGrantSpentAmounts` y las acciones del grant (se vieron fallar primero) | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/test/contract-errors.test.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Escrito por el builder antes de la corrección: mapeo de D-10 a y enum de códigos del Contrato A (se vieron fallar primero) | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/test/contract.test.ts` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Escrito por el builder: valida las respuestas del servicio contra `openapi/contract-a.yaml` con `ajv`, con doble de Open Payments y sin red | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/package.json`, `payments/package-lock.json`, `payments/tsconfig.json` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander). Cambios de la unidad 2: `engines` Node >=24 y dependencias de desarrollo `yaml`, `ajv` y `ajv-formats` | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `payments/.env.example`, `payments/.gitignore`, `payments/README.md` | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Importado del PR #1 (cerrado, rama `claude/nifty-dijkstra-gl0od2`; herramienta del PR por confirmar con Alexander): plantilla de variables (según el builder, sin valores), ignorados de git y notas del servicio | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff; `npm test` (66/66) y `npm run typecheck` re-ejecutados desde cero en una carpeta aparte |
| `openspec/changes/add-payments-service/specs/payments-service/spec.md` (una frase) | Pagos | Builder (opencode, `featherless:zai-org/GLM-5.3-Flash`) y Claude Code (supervisor) | Acciones del grant `create`, `read` y `list` (A-3), con la nota "esperaba create/read/list, pasó create/read, cambio: spec actualizado". Validado con `openspec validate add-payments-service --strict` | Pendiente: lectura de Alexander (@jhonosorno-cmd). Supervisor: leí el diff y corrí `openspec validate add-payments-service --strict` (válido) |

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
