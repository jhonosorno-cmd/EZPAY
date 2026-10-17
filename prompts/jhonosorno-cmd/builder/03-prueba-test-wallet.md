# Builder 03 — Prueba real de `payments/` contra la Test Wallet (camino feliz)

Brief enviado el 16 de octubre de 2026 por el supervisor (Claude Code, sesión "coordinator") al
builder (agente opencode "Configuración Builder Pagos EZPAY"). Aprobado por Alexander
(@jhonosorno-cmd) con "El `.env` está listo. D-11 a. Mandale el brief de la unidad 3 al builder y
avisame cuando tenga que aprobar el grant."

---

````text
UNIDAD 3 — Prueba real de payments/ contra la Test Wallet (camino feliz)

OBJETIVO
Comprobar contra la Test Wallet REAL el ciclo grant → continue → gastado → quote → pago → idempotencia → límite, con el servicio de tu rama payments/backend (ahora con main fusionado). Dejar un script reproducible y un informe redactado. El dueño (Alexander) aprueba el grant en su navegador; el resto es tuyo.

REGLAS DE SEGURIDAD (duras)
- El archivo payments/.env YA EXISTE (lo preparó el dueño). NO lo leas, NO lo imprimas, NO lo copies, NO lo listes con su contenido, NO lo abras con ninguna herramienta. Solo el servicio lo lee, vía `npm start` (que ya usa `--env-file=.env`). Tampoco leas ni imprimas la llave privada ni su ruta.
- Nunca imprimas ni guardes en archivos, logs, mensajes o commits: access tokens, continue tokens, nonces, interact_ref, hash, keyId, la URL de aprobación del grant (interactUrl), llaves ni rutas de llaves. Si alguna salida los contiene, pegá la salida con esos valores reemplazados por <redacted> y avisame.
- Los logs del servicio y del script van a una carpeta temporal FUERA del repo, nunca dentro.
- Si algo falla, NO reintentes pagos a ciegas ni cambies la Idempotency-Key para "probar otra vez": reportá el error redactado y esperá mi instrucción. Un pago real se crea UNA vez.

DECISIONES YA TOMADAS
- D-11 a: el script abre la URL de aprobación en el navegador predeterminado SIN imprimirla (en Windows, `rundll32 url.dll,FileProtocolHandler <url>` con child_process.spawn, que evita problemas de escape). Opción `--print-url` que la imprime solo si el usuario la pide explícitamente; por defecto desactivada.
- Receptor: https://ilp.interledger-test.dev/laura (no es secreto).
- Moneda: ASSET_CODE=COP, ASSET_SCALE=2 como parámetros del script (no del servicio). Si la wallet emisora no está en COP/2, el servicio responderá 400 INVALID_RECEIVER: no lo "arregles", reportalo.
- Presupuesto de la prueba: tope total de 5.000 COP, sin interval → debitAmount {value:"500000"}. Pago: receiveAmount 1.000 COP {value:"100000"}. Prueba de exceso: receiveAmount 5.000 COP {value:"500000"}.
- DELETE, rechazo en la wallet, rotación de token (esperar >10 min), vencimiento semanal: NO en esta unidad (unidad 4).

PASO 0 — Observabilidad del respaldo (código + prueba, antes de la prueba real)
Hoy `spent()` en payments/src/domain/service.ts traga cualquier error de getGrantSpent con `catch { return local }`: eso ocultó el bug de la URL en las pruebas. Agregá una prueba que falle primero: cuando getGrantSpent lanza, el servicio emite UNA línea de log JSON {"level":"warn","event":"spent_fallback"} (sin valores, sin tokens, sin URLs) y el resultado sigue siendo el gastado local. Luego la implementación mínima (inyectá un logger/callback opcional en el servicio; no cambies el contrato HTTP ni los códigos). Mostrame la salida roja y la verde. Todo `npm test` y `npm run typecheck` en verde. Commit: `fix(payments): log a warning when the spent fallback is used`.

PASO 1 — Script de humo
Creá payments/experiments/smoke-happy-path.ts (se ejecuta con tsx, agregá el script `smoke` a payments/package.json). Lee la URL del servicio y los parámetros de línea de comandos o variables NO secretas (SERVICE_URL por defecto http://127.0.0.1:4000; RECEIVER; ASSET_CODE; ASSET_SCALE); nunca lee payments/.env. Hace, en este orden, midiendo la duración de cada llamada:
 a) GET /v1/health → 200.
 b) Levanta un listener temporal en 127.0.0.1:5173 que recibe GET /grant-callback (el finishUri http://localhost:5173/grant-callback), guarda los valores de los parámetros en memoria SIN imprimirlos (sí podés registrar los NOMBRES de los parámetros recibidos) y responde una página HTML mínima en español ("Listo, ya podés volver a la terminal"). Si el puerto 5173 está ocupado, abortá con un mensaje claro antes de crear el grant.
 c) POST /v1/grants {userId:"demo-user", walletAddress:<la de la usuaria>, limit:{debitAmount:{value:"500000",assetCode,assetScale}}, finishUri:"http://localhost:5173/grant-callback"}. PROBLEMA: el script no sabe la walletAddress sin leer .env. Resolvelo así: el script acepta --wallet o la variable SMOKE_WALLET que te paso YO por mensaje justo antes de ejecutar (no la inventes ni la busques).
 d) Abre la interactUrl con el método de D-11 a y espera el redirect (hasta 8 minutos; el grant pendiente vence a los 10).
 e) POST /v1/grants/{id}/continue con interactRef y hash recibidos, reenviados tal cual. Espera 200 ACTIVE y remaining = 5.000.
 f) GET /v1/grants/{id} → spent 0, remaining 5.000.
 g) POST /v1/quotes {grantId, receiver, receiveAmount:{100000}} → 201, receiveAmount 1.000, debitAmount ≥ receiveAmount, exceedsRemaining false. Anotá el costo (debit − receive).
 h) POST /v1/payments con Idempotency-Key UUID nuevo y ese quoteId → 201. Luego GET /v1/payments/{id} cada 1 s hasta COMPLETED o 30 s; anotá cuánto tardó.
 i) GET /v1/grants/{id} → spent = debitAmount del pago, remaining = 5.000 − debit. Anotá si el servidor ya lo reflejaba de inmediato (con el log spent_fallback del paso 0 sabrás si el gastado vino del servidor o del respaldo local).
 j) Reintento idempotente: POST /v1/payments con la MISMA clave y MISMO quoteId → misma respuesta (status y cuerpo). Otro POST con una clave NUEVA y el mismo quoteId → 404 QUOTE_NOT_FOUND. Ninguno de los dos crea otro pago: confirmá con el gastado (sigue siendo un solo débito).
 k) Exceso: POST /v1/quotes con receiveAmount 500000 → 201 con exceedsRemaining true; POST /v1/payments con ese quote y una clave nueva → 403 LIMIT_EXCEEDED, y el log del request del servicio muestra 0 llamadas a Open Payments para ese pago.
 l) Cierra el listener. Termina con un resumen en consola SIN secretos.
Cada paso afirma el resultado esperado y marca OK/FALLÓ con el motivo. Si un paso falla, el script se detiene (no sigue pagando).

PASO 2 — Protocolo de ejecución (importante)
 1. Dejá todo listo: pruebas en verde, servicio arrancado con `npm start` (en segundo plano, con su log en una carpeta temporal fuera del repo) y GET /v1/health OK. No ejecutes el script todavía.
 2. Mandame un mensaje que empiece con "LISTO PARA EJECUTAR" y diga: qué verificaste, cómo se llama el log, y que necesitás el valor de SMOKE_WALLET. Yo aviso al dueño y te contesto con "GO" y la wallet. NO ejecutes nada antes de mi GO.
 3. Con mi GO: ejecutá el script. El navegador se abrirá y el dueño aprueba el grant. Esperá el resultado.
 4. Al terminar, detené el servicio.

PASO 3 — Informe y archivos
Escribí payments/experiments/smoke-happy-path.md (junto al script) con: fecha, versión del SDK, tabla de pasos (paso | llamada | status/código | monto | duración | OK/FALLÓ), costo observado, si el gastado vino del servidor o del respaldo, tiempo hasta COMPLETED, y observaciones. REDACTADO: sin tokens, sin keyId, sin interactUrl, sin URLs de grants, sin nonces, sin interact_ref ni hash, las wallets como <remitente> y <receptor>, los ids como g_1, q_1, p_1. Podés registrar los NOMBRES de los parámetros del redirect (por ejemplo interact_ref, hash).
Commits convencionales separados (`test:`/`fix:` del paso 0; `feat(payments): add Test Wallet smoke script`; `docs(payments): record smoke test results` solo si la prueba corrió). Sin push.

ARCHIVOS PERMITIDOS
payments/src/ (solo el cambio del paso 0), payments/test/ (la prueba del paso 0), payments/experiments/ (script y .md), payments/package.json (script `smoke`). NO toques payments/.env, docs/, openapi/, openspec/, api/, web/, AI_USAGE.md ni prompts/.

CRITERIO DE TERMINADO (yo lo verifico)
- Paso 0: salida roja y verde; todo `npm test` y typecheck en verde.
- Script en el repo, sin secretos; informe redactado con la tabla completa.
- Cada paso c–l con resultado real (OK o FALLÓ con motivo redactado).
- Cero secretos en el diff, en el .md y en lo que pegues en mensajes.
- `git status` limpio; sin push.

FORMATO DEL REPORTE (por mensaje)
1) Resumen de 5 líneas máximo. 2) Commits y `git diff --stat`. 3) Paso 0: rojo y verde literales. 4) Tabla de pasos con resultados reales (redactada). 5) Lo que NO pudiste comprobar y por qué. 6) Hallazgos nuevos contra los specs, en formato "esperaba X, pasó Y, cambio Z". 7) Preguntas en formato D-n (máximo 3, solo si el spec no las resuelve). Distinguí lo EJECUTADO de lo inferido.
````
