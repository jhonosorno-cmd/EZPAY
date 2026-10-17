# Builder 08 — Grant puntual en Node (`grant.cancel` y vencimiento local)

Brief enviado el 17 de octubre de 2026 por el supervisor (Claude Code, sesión "coordinator") al
builder 1 (agente opencode "Configuración Builder Pagos EZPAY"). Aprobado por Alexander
(@jhonosorno-cmd) con "Ok al plan" tras el plan de la siguiente unidad (D-15 a).

---

````text
UNIDAD 8 — Grant puntual en Node: cancelar con grant.cancel y probar el vencimiento local (PARTE A: sin wallet real)

OBJETIVO
Aplicar la decisión del 17 oct (D-13 a, D-15 a): el grant puntual se pide con limit.interval `R1/<momento de la solicitud>/P1W` (eso ya lo hace el cliente de Python) y el servicio Node (1) lo vence solo a los 7 días y (2) lo cancela de verdad con GNAP `grant.cancel` (DELETE sobre la continue URI con el continue token), no con token.revoke. Esta parte NO llama a la wallet real. La corrida real es la PARTE B y solo la hacés cuando yo te dé el GO por escrito (ver al final).

PREPARACIÓN (rama)
git fetch origin; git switch -c payments/one-off-grant origin/main (sin upstream, sin push). Tu carpeta tiene archivos sin versionar de api/ (el venv): no los toques. Verificá npm ci, npm test y npm run typecheck en verde ANTES de tocar nada y anotá cuántas pruebas hay. Leé: payments/src/op/adapter.ts (cancelGrant, línea ~107 con un [VERIFICAR]), payments/src/ports.ts (línea ~27), payments/src/domain/service.ts (cancelGrant ~188, load() y currentPeriod), payments/src/interval.ts, payments/experiments/cancel-grant.ts y su informe cancel-grant.md, y design.md D13 en openspec/changes/add-payments-service.

REQUISITOS (primero las pruebas; que se vean fallar antes del código)
 1) El puerto OpenPayments.cancelGrant pasa a recibir { continueUri, continueToken } en vez de { manageUrl, accessToken }. El adapter llama this.c.grant.cancel({ url: continueUri, accessToken: continueToken }) (igual que en payments/experiments/cancel-grant.ts línea ~61). Quitá el comentario [VERIFICAR] del adapter.
 2) service.cancelGrant(id) usa los continueUri/continueToken ya guardados (cifrados) del grant. Comportamiento que se mantiene: 404 GRANT_NOT_FOUND si no existe; 204 idempotente si ya está EXPIRED (no llama a Open Payments dos veces); el estado local pasa a EXPIRED ANTES de llamar a la wallet (aunque el cancel falle, el grant no se usa más); si la wallet falla, 502 UPSTREAM_ERROR.
 3) Un grant que todavía no se continuó (sin access token) también se puede cancelar con grant.cancel si tiene continueUri/continueToken; si faltaran esos datos, solo se marca EXPIRED local sin llamar a la wallet. Decidí con una prueba y anotalo.
 4) Verificá en el código si continueGrant guarda un continue token nuevo cuando la wallet devuelve uno (en GNAP el continue puede rotar). Si el experimento usó el token original y funcionó, está bien; si el código descarta uno más nuevo que la wallet devuelve, guardalo y probalo. Si el puerto no expone ese dato, NO inventes: reportalo como hallazgo.
 5) Pruebas nuevas en payments/test/ (con el doble fakes.ts, sin red):
    a. DELETE /v1/grants/{id} llama grant.cancel con la continue URI y el continue token del grant (el doble los registra) y NO llama a token.revoke.
    b. Idempotencia: segundo DELETE → 204 sin segunda llamada; id desconocido → 404; falla de la wallet → 502 y el grant queda EXPIRED local.
    c. Reloj falso: un grant con interval `R1/<inicio>/P1W` está ACTIVE a los 6 días y EXPIRED a los 8; un pago al día 8 devuelve GRANT_INVALID sin llamar a Open Payments. Si ya existe una prueba equivalente (la 4b dejó una), citala en el reporte en vez de duplicar.
    d. Después de DELETE, una quote o un pago con ese grant devuelve GRANT_INVALID (no se intenta usar el token).
 6) Actualizá los comentarios y docs mínimos que mencionen token.revoke para cancelar (payments/README si lo dice). NO toques openspec/: el spec ya dice grant.cancel; si encontrás una contradicción, reportala como hallazgo.

PARTE B — CORRIDA REAL (NO la ejecutes sin mi GO)
Dejá escrito y probado contra el doble un script payments/experiments/one-off-grant-real.ts (mismo estilo que cancel-grant.ts y smoke-happy-path.ts, reutilizando lib.ts) que haga, contra la Test Wallet real y con un único pago de 500 COP (value "50000", scale 2):
 1. Crear el grant puntual con interval R1/<ahora>/P1W y limit 500 COP; imprimir la URL de interacción y esperar a que Alexander apruebe en la pantalla.
 2. Continuar, pedir quote, pagar una vez con Idempotency-Key; verificar spent == 500 COP.
 3. DELETE del grant (por el servicio, o por el adaptador si el script habla directo con la wallet) y comprobar que leer con el token da 403.
 4. Informe payments/experiments/one-off-grant-real.md SOLO con datos de lista blanca: sin tokens, sin URLs de grants ni de interacción, sin wallet ids completos; tiempos y códigos de estado sí.
No lo corras. En tu reporte decí "PARTE B lista, esperando GO". Yo la apruebo con Alexander frente a la pantalla y te mando el GO.

SEGURIDAD
- Repo público: nada de .env, tokens, llaves ni URLs de grants. No leas payments/.env. La PARTE A usa solo el doble de Open Payments.
- Revisá `git diff --cached` antes de commitear.

ARCHIVOS PERMITIDOS
payments/src/op/adapter.ts, payments/src/ports.ts, payments/src/domain/service.ts, payments/test/**, payments/experiments/one-off-grant-real.ts (nuevo; el .md solo después del GO) y payments/README si menciona la cancelación. Si necesitás tocar otro archivo de src/, pedímelo antes. NO toques api/, web/, openspec/, docs/, openapi/, prompts/, AI_USAGE.md ni los otros archivos de payments/experiments/. Sin push.

CRITERIO DE TERMINADO DE LA PARTE A (yo lo verifico)
- Las pruebas 5a a 5d existen y viste fallar 5a antes del cambio.
- npm test y typecheck en verde (el total sube respecto del que anotaste).
- git status limpio; commits convencionales (fix(payments): cancel grants with grant.cancel; test(payments): cover the one-off grant expiry and cancellation; test(payments): add the real one-off grant script).
- Reporte: 1) resumen de 5 líneas; 2) commits y git diff --stat; 3) pruebas añadidas y cuál viste fallar; 4) requisito 3 y 4: qué decidiste y por qué; 5) qué NO comprobaste; 6) hallazgos "esperaba X, pasó Y, cambio Z"; 7) preguntas D-n (máximo 3, solo si el spec no las resuelve).
````
