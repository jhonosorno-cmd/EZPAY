# Builder 02 — Portar `payments/` desde el PR #1 y corregirlo (sin Test Wallet)

Brief enviado el 16 de octubre de 2026 por el supervisor (Claude Code, sesión "coordinator") al
builder (agente opencode "Configuración Builder Pagos EZPAY"). Plan aprobado por Alexander
(@jhonosorno-cmd) con "OK al plan de la unidad 2. D-10 a. Mandale el brief al builder."

---

````text
UNIDAD 2 — Portar payments/ desde el PR #1 y corregirlo (SIN Test Wallet)

OBJETIVO
Dejar en tu rama payments/backend el servicio Node/TS del PR #1 con los defectos de tu revisión corregidos, probado y validado contra openapi/contract-a.yaml. Nada contra la wallet real en esta unidad (eso es la unidad 3).

DECISIONES YA TOMADAS (no las reabras)
- D-10 a: los casos que el Contrato A no cubre se mapean a códigos EXISTENTES, sin tocar el contrato: ruta desconocida, JSON malformado y campos obligatorios faltantes o inválidos de POST /grants (userId, walletAddress, finishUri, forma de limit) → 500 INTERNAL_ERROR con un message descriptivo y sin datos del request ni internos; interval no soportado → 400 INVALID_AMOUNT. NO agregues INVALID_REQUEST ni NOT_FOUND al enum. En el reporte anotá "propuesta para v1.2: INVALID_REQUEST" (no la escribas en ningún doc).
- DELETE /v1/grants/{id} se mantiene como en el PR (A-1 ratificado), marcado [VERIFICAR]; no lo cambies hasta el experimento.
- El vencimiento semanal del grant puntual sigue pendiente del experimento: no lo implementes.

PASOS (en este orden)
1. Importar: traé payments/ desde la referencia local `pr1` a C:\Users\Admin\ezpay-backend (por ejemplo `git restore --source=pr1 --worktree --staged -- payments`, o `git checkout pr1 -- payments`). Sin traer historial ni otros directorios. Subí `engines` de payments/package.json a Node >=24. Reemplazá el uso de la ruta fija /tmp en las pruebas por os.tmpdir() (test/payments.test.ts; usá la ruta temporal con nombres únicos). `npm ci` y `npm test` tienen que dar 56/56 y `npm run typecheck` limpio ANTES de seguir. Commit 1: `chore(payments): import service from PR #1`.
2. Pruebas primero, y mostrame que FALLAN antes de corregir (pegá la salida roja real):
   a) una prueba que capture la URL con que el adaptador llama a getGrantSpentAmounts y afirme que es la raíz del resource server (sin el sufijo /outgoing-payments), de modo que el SDK 7.4.0 arme <raiz>/outgoing-payment-grant (fuente: node_modules/@interledger/open-payments/dist/client/outgoing-payment.js:102-104). Que la prueba no dependa del fallback local, que hoy lo oculta;
   b) una prueba que afirme que requestGrant pide para outgoing-payment las acciones exactamente ["create","read","list"] (A-3);
   c) pruebas del mapeo de D-10 (ruta desconocida, JSON malformado, userId/finishUri faltantes → 500 INTERNAL_ERROR; interval no soportado → 400 INVALID_AMOUNT), y una que verifique que NINGÚN code emitido por el servicio queda fuera del enum del Contrato A (leé el enum de openapi/contract-a.yaml, components.schemas.ErrorCode).
3. Correcciones mínimas para ponerlas en verde: la URL de getGrantSpentAmounts (op/adapter.ts ~línea 176), las acciones (~línea 75), el mapeo de códigos (src/http/app.ts y src/domain/service.ts). Nada más. No refactorices, no "mejores" lo que no esté en este brief. Commits convencionales separados por tema (`fix(payments): ...`, `test(payments): ...`).
4. Spec: en openspec/changes/add-payments-service/specs/payments-service/spec.md, requisito "Creación de grant interactivo con límite", cambiá "acciones `create` y `read`" por "acciones `create`, `read` y `list`" (A-3). Es la ÚNICA edición permitida en openspec/. Agregá en el reporte la nota "esperaba create/read/list, pasó create/read, cambio: spec actualizado". Corré `openspec validate add-payments-service --strict` y pegá el resultado real.
5. Contrato: agregá una validación de las respuestas del servicio contra openapi/contract-a.yaml, con el doble de Open Payments (FakeOp), SIN red. Dos caminos válidos; elegí uno y justificalo en una línea: (i) levantar la app en un puerto local con FakeOp y ponerle `prism proxy` (el Prism ya está en el package.json de la raíz del repo; usá `--errors`) delante, o (ii) un validador de respuestas OpenAPI dentro de una prueba. Cubrí al menos: POST /v1/grants, POST /v1/grants/{id}/continue, GET /v1/grants/{id}, DELETE /v1/grants/{id}, POST /v1/quotes, POST /v1/payments (201 y un error por código del contrato que el servicio emita), GET /v1/payments/{id}, GET /v1/health. Cualquier diferencia entre el servicio y el contrato la reportás: NO cambies openapi/ ni docs/.
6. Cierre: `npm test` (todo, incluidas las pruebas nuevas) y `npm run typecheck` en verde; `git status` limpio; nada de .env, llaves ni tokens en ningún archivo ni log.

ARCHIVOS PERMITIDOS
payments/** ; la única línea indicada de openspec/changes/add-payments-service/specs/payments-service/spec.md. NO toques docs/, openapi/, AI_USAGE.md, README.md de la raíz, prompts/ ni código de otros roles (web/, api/). Si necesitás una dependencia nueva, ponela en payments/package.json y justificala. Sin push (te lo pido yo).

CRITERIO DE TERMINADO (yo lo verifico: leo tu diff, corro todo por mi cuenta, busco secretos)
- 56 pruebas originales + las nuevas, todas en verde; salida pegada. Salida ROJA previa de las pruebas nuevas, pegada.
- La URL de getGrantSpentAmounts correcta, probada.
- Acciones ["create","read","list"], probadas.
- Ningún error code fuera del enum del Contrato A, probado.
- Validación contra contract-a.yaml corrida; lista de diferencias (si hay).
- `openspec validate add-payments-service --strict` válido.
- Commits convencionales, sin atribución a IA.

FORMATO DEL REPORTE (por mensaje, no escribas archivos de reporte)
1) Resumen de 5 líneas máximo. 2) Commits (hash y asunto) y `git diff --stat origin/main`. 3) Salida roja y verde literales. 4) Resultado de la validación contra el contrato y diferencias. 5) Resultado de openspec validate. 6) Lo que NO pudiste comprobar y por qué. 7) Preguntas en formato D-n (por qué importa; opciones con costo; recomendación), máximo 3, solo si el spec no las resuelve. Distinguí lo EJECUTADO de lo inferido.
````
