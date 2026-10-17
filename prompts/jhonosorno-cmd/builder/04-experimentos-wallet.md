# Builder 04 — Experimentos contra la Test Wallet

Brief enviado el 16 de octubre de 2026 por el supervisor (Claude Code, sesión "coordinator") al
builder (agente opencode "Configuración Builder Pagos EZPAY"). Aprobado por Alexander
(@jhonosorno-cmd) con "OK al plan de la unidad 4. D-12 a. Mandale el brief al builder."

---

````text
UNIDAD 4 — Experimentos contra la Test Wallet (grant semanal, rechazo, cancelación, rotación, retraso del gastado)

OBJETIVO
Responder con evidencia real cinco preguntas abiertas sobre la Test Wallet. Los experimentos preguntan cómo se comporta la WALLET, no el servicio: usan el SDK/adaptador directamente, NO levantan el servicio y NO tocan su base de datos. Entregable: scripts reproducibles + tres informes redactados que el propio script genera. Yo traigo las conclusiones al dueño; NO cambies specs, contratos ni código de src/.

PREGUNTAS
 P1 (grant puntual semanal, decisión #1 del 16 oct): ¿la wallet acepta limits.interval de una semana con UNA repetición junto con debitAmount? ¿Cómo lo devuelve en la respuesta del grant (¿eco de interval en access_token.access[].limits?)? Nota: getGrantSpentAmounts del SDK 7.4.0 devuelve solo spentDebitAmount y spentReceiveAmount (anulables); NO trae campos de período: no los busques. Hoy NO se puede observar el vencimiento real a los 7 días: concluí solo aceptación y eco.
 P2 (E3-rechazo, B-1): cuando la usuaria RECHAZA en la wallet, ¿qué NOMBRES de parámetros trae el redirect a finishUri (¿result?, ¿faltan interact_ref y hash?) y qué responde grant.continue si se llama sin interact_ref después del rechazo?
 P3 (A-1, cancelar): ¿token.revoke (manage URL) y grant.cancel (continue URI + continue token) invalidan DE VERDAD el acceso? Prueba: después de cada uno, intentar crear un pago con el access token y anotar el resultado.
 P4 (E4, rotación): ¿token.rotate funciona con un token YA VENCIDO (>10 min, expires_in observado 600 s)? ¿Qué devuelve el pago con el token vencido antes de rotar? ¿El token viejo queda inválido tras rotar?
 P5 (retraso del gastado, [VERIFICAR] de D12): tras crear un pago, ¿cuántos segundos tarda getGrantSpentAmounts (consulta DIRECTA, sin max(servidor, local)) en reflejarlo?

SEGURIDAD (duras, igual que la unidad 3)
- payments/.env existe; NO lo leas, imprimas, copies ni listes con contenido. Los scripts se ejecutan con `tsx --env-file=.env` (lo lee el proceso, no vos). Tampoco leas ni imprimas la llave privada ni su ruta.
- Nunca imprimas ni escribas en archivos, logs, mensajes o commits: access/continue tokens, nonces, interact_ref, hash, keyId, interactUrl, URLs de grants/manage/continue, llaves ni rutas de llaves. NUNCA vuelques una respuesta del SDK completa: imprimí solo campos de una lista blanca (status, códigos de error, nombres de parámetros, montos, expires_in, booleanos "existe X"). El informe .md lo ESCRIBE el script a partir de datos estructurados de esa lista blanca; vos solo lo revisás antes de commitear.
- Wallets en los informes como <remitente> y <receptor> (las dos, incluida la de Laura); ids como g_1, q_1, p_1.
- Logs de los scripts a una carpeta temporal FUERA del repo.
- Pagos reales: SOLO de 500 COP ({value:"50000", assetScale 2}); máximo 4 en toda la unidad. Si un paso falla NO reintentes pagos ni cambies claves a ciegas: reportá redactado y esperá mi instrucción.

PREPARACIÓN (rama)
Tu rama payments/backend ya está mergeada. Hacé `git fetch origin` y `git switch -c payments/experiments origin/main` (sin upstream, sin push). Verificá `npm ci`, `npm test` (69 pruebas) y `npm run typecheck` en verde antes de empezar.

SCRIPTS (payments/experiments/)
Reusá src/config.ts (carga de configuración desde el entorno), src/op/adapter.ts (SdkOpenPayments) y el SDK ya instalado; si el adaptador no expone algo, usá el cliente del SDK directamente construido con la misma configuración. NO modifiques nada de src/. Un helper común `lib.ts` con: listener en 127.0.0.1:5173 para finishUri (devuelve los parámetros en memoria; el script imprime solo sus NOMBRES), apertura de la URL en el navegador con `rundll32 url.dll,FileProtocolHandler <url>` SIN imprimirla, redacción por lista blanca y escritura del .md. Aborto limpio si el puerto 5173 está ocupado. Receptor: https://ilp.interledger-test.dev/laura. Moneda COP, escala 2. La walletAddress del remitente es la de WALLET_ADDRESS del entorno que carga config.ts (no necesitás conocerla).
 1) weekly-interval-and-token.ts (+ weekly-interval-and-token.md) — grant "A" de 5.000 COP ({value:"500000"}):
    a. Pedir el grant con actions create/read/list y limits {debitAmount, interval}. Intentar en orden hasta que uno sea aceptado: `R1/<hoy 00:00:00Z>/P1W`, `R1/<hoy 00:00:00Z>/P7D`, `R/<hoy 00:00:00Z>/P1W`. Por cada variante registrá solo: la cadena de intervalo usada (no es secreta), aceptada o rechazada, status y código de error/description saneados. P1.
    b. Aprobación del dueño (abre navegador) → continue. Registrar: si la respuesta eco-ea limits.interval y limits.debitAmount, el expires_in observado, y si existe la manage URL (solo "existe"). P1.
    c. Pago 1 de 500 COP (quote al receptor + outgoing payment). Luego P5: consultar getGrantSpentAmounts DIRECTO cada 1 s hasta que spentDebitAmount sea >= al débito del pago o 30 s; registrar la serie (segundo, valor) y cuándo apareció.
    d. P4: esperar 11 minutos (imprimir una línea de progreso por minuto, sin secretos). Intentar el Pago 2 de 500 COP con el token VENCIDO y registrar status/código. Luego token.rotate sobre ese token vencido: ¿acepta? ¿nuevo expires_in? Pago 2 con el token nuevo (500 COP). Probar si el token viejo sigue funcionando (consulta de solo lectura, p.ej. getGrantSpentAmounts con el viejo; no hagas otro pago).
    e. P3 (parte revoke): token.revoke sobre el token rotado, y luego intentar una consulta de solo lectura con él (getGrantSpentAmounts) y una cotización (SIN pagar): registrar status/códigos. Otro pago solo si no hay otra forma de saber si la revocación bloquea pagos; en ese caso es el pago 3 de 500 COP.
 2) reject-redirect.ts (+ .md) — grant "B" de 3.000 COP ({value:"300000"}), sin interval: abrir navegador; el dueño RECHAZA. Registrar los NOMBRES de los parámetros recibidos en finishUri (y el VALOR solo de un parámetro llamado result, si existe y es corto y sin caracteres de token; si no, solo "presente"). Luego llamar grant.continue SIN interact_ref y registrar status/código/description saneados. Si el dueño aprobó por error: registralo como "aprobado, experimento no concluyente" y NO repitas sin mi OK. P2.
 3) cancel-grant.ts (+ .md) — grant "C" de 4.000 COP ({value:"400000"}), sin interval: aprobación del dueño → continue → grant.cancel(continue URI + continue token) → intentar con el access token una cotización y, solo si hace falta distinguir, un pago de 500 COP. Registrar resultado. P3 (parte grant.cancel). Comparar con el resultado de revoke de weekly-interval-and-token.
Agregá a payments/package.json los scripts exp:weekly, exp:reject y exp:cancel (cada uno `tsx --env-file=.env experiments/<archivo>.ts`). Cada script con un `--dry-run` que valida imports y carga de configuración SIN red y SIN abrir el navegador.

PROTOCOLO DE EJECUCIÓN
 1. Preparación completa: pruebas y typecheck verdes, los tres scripts con --dry-run OK. NO ejecutes nada real.
 2. Mandame "LISTO PARA EJECUTAR": qué verificaste, nombres de los logs. Yo aviso al dueño y te respondo "GO". Hasta mi GO, nada contra la wallet.
 3. Con mi GO: ejecutá weekly-interval-and-token.ts. Tras su aprobación y el primer pago, mientras corre la espera de 11 minutos, ejecutá reject-redirect.ts y luego cancel-grant.ts, una tras otra, esperando que cada una termine (así no chocan en el puerto 5173). El dueño verá tres pantallas de aprobación identificables por el MONTO: 5.000 COP = APROBAR; 3.000 COP = RECHAZAR; 4.000 COP = APROBAR. Antes de abrir cada pantalla mandame un mensaje corto ("Abriendo B: 3.000 COP, el dueño debe RECHAZAR") para que yo se lo avise; no esperes mi respuesta salvo que algo falle. Esperá un máximo de 8 minutos por aprobación.
 4. Cuando los tres terminen, revisá los .md y mandá el reporte.

ARCHIVOS PERMITIDOS
payments/experiments/** (lib.ts, tres scripts, tres .md) y los tres scripts nuevos en payments/package.json. NO toques src/, test/, .env, docs/, openapi/, openspec/, api/, web/, AI_USAGE.md ni prompts/. Sin push.

CRITERIO DE TERMINADO (yo lo verifico)
- Los tres scripts y los tres .md en el repo; los .md los generó el script (datos de lista blanca), sin secretos ni URLs; wallets como <remitente>/<receptor>.
- Respuesta explícita a P1 a P5, cada una marcada EJECUTADO o NO CONCLUYENTE, con la evidencia.
- Cuántos pagos reales se hicieron (máximo 4) y cuáles.
- `npm test` y typecheck siguen en verde; `git status` limpio; commits convencionales: `feat(payments): add Test Wallet experiment scripts` y `docs(payments): record Test Wallet experiment results`.

FORMATO DEL REPORTE (por mensaje)
1) Resumen de 5 líneas máximo. 2) Commits y `git diff --stat`. 3) Una sección por pregunta P1..P5: qué se hizo, resultado real (redactado), conclusión y si es concluyente. 4) Tabla de pagos reales hechos. 5) Lo que NO pudiste comprobar y por qué (incluido el vencimiento real a 7 días). 6) Hallazgos contra los specs en formato "esperaba X, pasó Y, cambio Z". 7) Preguntas D-n (máximo 3, solo si el spec no las resuelve). Distinguí lo EJECUTADO de lo inferido.
````
