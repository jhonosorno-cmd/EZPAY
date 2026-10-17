# Builder 10 — `INVALID_REQUEST` en el servicio de Node (contrato v1.2, AB-1)

Brief del 17 de octubre de 2026 del supervisor (Claude Code, sesión "coordinator") al builder 1
(agente opencode "Configuración Builder Pagos EZPAY"). Unidad pedida por Alexander
(@jhonosorno-cmd): "contrato v1.2 — INVALID_REQUEST (ratificado por el equipo el 17 oct)". Se envía
cuando el builder 1 cierra la parte A de la unidad 8 (ambas tocan `payments/src/domain/service.ts`).

---

````text
UNIDAD 10 — INVALID_REQUEST en Node (contrato v1.2, AB-1)

OBJETIVO
El equipo ratificó el 17 oct el cambio AB-1: nuevo código `INVALID_REQUEST` (HTTP 400) en el ErrorCode de los Contratos A y B, para peticiones mal formadas (JSON inválido, campos obligatorios faltantes o inválidos, ruta desconocida). Reemplaza el mapeo provisorio a `500 INTERNAL_ERROR` de D-10 a. Ya están hechos por el supervisor los contratos (openapi/), docs/contratos-cambios-v1.2.md y los specs: leé el requisito "Petición mal formada" en openspec/changes/add-payments-service/specs/payments-service/spec.md (PR de contratos v1.2). Tu parte es el código de Node.

PREPARACIÓN (rama)
Cuando cerremos la unidad 8: git fetch origin; git switch -c payments/invalid-request origin/main (sin upstream, sin push; el PR de contratos v1.2 y tu unidad 8 deberían estar ya en main; si no, avisame). npm ci, npm test y npm run typecheck en verde ANTES de empezar; anotá cuántas pruebas hay.

REQUISITOS (primero las pruebas; que se vean fallar antes del código)
 1) payments/test/contract-errors.test.ts hoy afirma D-10a ('unknown route', 'malformed JSON' y 'missing userId, walletAddress, finishUri, limit or limit.debitAmount' → 500 INTERNAL_ERROR). Actualizá ESAS pruebas para que esperen 400 INVALID_REQUEST (esperaba 500, pasó 400, cambio D-10a) y renombrá el describe; verlas fallar primero.
 2) payments/src/http/app.ts: ruta desconocida y `entity.parse.failed` (JSON inválido) → 400 INVALID_REQUEST. Un error inesperado real sigue siendo 500 INTERNAL_ERROR.
 3) payments/src/domain/service.ts (createGrant, líneas ~130-134): userId, walletAddress, finishUri y limit.debitAmount faltantes o de tipo inválido → 400 INVALID_REQUEST. Un `interval` no soportado sigue siendo 400 INVALID_AMOUNT (hay una prueba; que siga igual).
 4) Revisá los demás cuerpos que reciben datos del cliente (continue: interactRef/hash; quotes: grantId/receiver/receiveAmount; payments: quoteId y el header Idempotency-Key). Donde falte un campo obligatorio o venga de tipo inválido y hoy responda 500 o un código que miente (p. ej. 404 por no ser string), usá INVALID_REQUEST SOLO si el spec y el contrato no definen otro código para ese caso; el header Idempotency-Key ausente sigue siendo 400 IDEMPOTENCY_KEY_REQUIRED y un grantId desconocido sigue siendo GRANT_NOT_FOUND. Si dudás, no cambies: listalo como hallazgo.
 5) La batería de payments/test/contract-errors.test.ts "every emitted error code is in the Contract A enum" debe leer el enum actualizado de openapi/contract-a.yaml (con INVALID_REQUEST); que pase.
 6) Mensajes de error: ninguno con datos del request (ni valores de campos).

SEGURIDAD
Repo público: sin .env, tokens ni URLs de grants. Pruebas solo con el doble de Open Payments. `git diff --cached` antes de commitear. Ningún proceso en primer plano.

ARCHIVOS PERMITIDOS
payments/src/http/app.ts, payments/src/domain/service.ts, payments/src/errors.ts si hiciera falta, payments/test/**. NO toques openapi/, openspec/, docs/, api/, web/, prompts/, AI_USAGE.md ni payments/experiments/. Sin push.

CRITERIO DE TERMINADO (yo lo verifico)
- Las pruebas del punto 1 vistas fallar y luego en verde; npm test y typecheck en verde (el total no baja del que anotaste).
- git status limpio; commits convencionales (test(payments): expect INVALID_REQUEST for malformed requests; fix(payments): answer 400 INVALID_REQUEST for malformed requests).
- Reporte: 1) resumen de 5 líneas; 2) commits y git diff --stat; 3) pruebas cambiadas/añadidas y cuáles viste fallar; 4) punto 4: qué cambiaste y qué dejaste como hallazgo; 5) qué NO comprobaste; 6) hallazgos "esperaba X, pasó Y, cambio Z"; 7) preguntas D-n (máximo 3, solo si el spec no las resuelve).
````
