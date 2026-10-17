# Builder 05 — Token vencido (403) y grant puntual semanal

Brief enviado el 17 de octubre de 2026 por el supervisor (Claude Code, sesión "coordinator") al
builder (agente opencode "Configuración Builder Pagos EZPAY"). Aprobado por Alexander
(@jhonosorno-cmd) con "D-13 a, D-14 a" y "OK al plan de la unidad 4b. Mandale el brief al builder."

---

````text
UNIDAD 4b — Rotar el token ante 403 (D-14 a) y probar el grant puntual semanal (D-13 a)

OBJETIVO
Cerrar dos hallazgos de los experimentos reales (payments/experiments/*.md):
 D-14 a: con el token VENCIDO la wallet responde 403 (no 401). Hoy el servicio solo rota ante 401 (service.ts, send()); ante 403 con el monto dentro del límite devuelve GRANT_INVALID sin rotar. Si el token vence antes de la rotación preventiva (<60 s), el pago de la demo falla.
 D-13 a: el grant puntual semanal se pide con limits.interval `R1/<inicio>/P1W` (la wallet lo acepta y lo devuelve) Y el servicio lo vence solo a los 7 días (ya lo hace load() con currentPeriod). Falta la prueba que lo demuestra y la documentación en los specs.

PREPARACIÓN (rama)
git fetch origin; git switch -c payments/token-expiry origin/payments/experiments (parte de la rama de los experimentos, PR #13 aún sin mergear; sin upstream, sin push). Verificá npm ci, npm test (69) y npm run typecheck en verde antes de empezar. No toques los archivos de payments/experiments/.

REQUISITOS (primero las pruebas; que se vean fallar antes del código)
 1) Ante un error `forbidden` de createOutgoingPayment, si todavía no se rotó en este envío (`rotated` false) Y el monto de la quote entra en lo que queda del grant: rotar el token UNA vez (this.token(grant, true)), guardar el token nuevo y reintentar el pago con la MISMA Idempotency-Key. No dupliques el débito (el estado de la clave pasa por RESERVED→SENT igual que hoy).
 2) Si tras rotar el 403 se repite: 401 GRANT_INVALID (como hoy). Si la rotación misma falla: lo que ya devuelve token() (401 GRANT_INVALID o 502 UPSTREAM_ERROR).
 3) Si el monto NO entra en lo que queda (comprobación con spent): 403 LIMIT_EXCEEDED sin rotar, como hoy. Orden sugerido: en `forbidden`, calcular `fits` con spent (ya existe) y rotar solo si fits y !rotated.
 4) Pruebas nuevas en payments/test/ (fakes.ts con una forma de simular "403 mientras el token no fue rotado"):
    a. 403 con token vencido y el monto cabe → rota, paga, un solo débito, el token nuevo queda guardado.
    b. 403 que se repite tras rotar → 401 GRANT_INVALID, un solo intento de rotar.
    c. 403 por tope superado → LIMIT_EXCEEDED, NO se llama a rotateToken.
    d. Repetir la petición con la misma Idempotency-Key tras (a) devuelve el mismo resultado sin cobrar de nuevo.
 5) D-13 prueba con reloj falso (el servicio ya recibe `now`): un grant con limit.interval `R1/<inicio>/P1W` está ACTIVE a los 6 días de <inicio> y EXPIRED a los 8, y un pago al día 8 devuelve GRANT_INVALID sin llamar a Open Payments. Si ya existe una prueba equivalente, citala en el reporte en vez de duplicarla.

SPECS (formato "esperaba X, pasó Y, cambio Z"; citá los informes de payments/experiments)
 - openspec/changes/add-payments-service/design.md, D13: agregar que (i) la wallet acepta R1/<inicio>/P1W y lo devuelve; (ii) el vencimiento real a 7 días no es observable; el servicio lo hace cumplir por su cuenta; (iii) token vencido → 403, no 401, y por eso se rota ante 403 cuando el monto cabe; (iv) getGrantSpentAmounts devuelve spentDebitAmount nulo antes del primer pago (se trata como 0). Marcá como resuelto el [VERIFICAR] de token.revoke vs grant.cancel (ambos dejan el token inusable).
 - openspec/changes/add-payments-service/specs/payments-service/spec.md: un escenario nuevo para "403 con token vencido y monto dentro del límite".
 - openspec/changes/add-payments-client/ (specs/turn-orchestration o proposal.md, donde dice "grant puntual"): el cliente pide el grant puntual con limit.interval `R1/<hoy 00:00:00Z>/P1W`. Solo texto, sin cambiar el contrato.
 - Corré `openspec validate add-payments-service --strict` y `openspec validate add-payments-client --strict` en verde.

SEGURIDAD
- Repo público: nada de .env, tokens, llaves ni URLs de grants. No leas payments/.env. Estas pruebas usan solo el doble de Open Payments: NO llames a la wallet real.
- Revisá `git diff --cached` antes de commitear.

ARCHIVOS PERMITIDOS
payments/src/domain/service.ts, payments/test/** y las dos carpetas de specs de openspec indicadas. Si necesitás tocar otro archivo de src/, pedímelo antes. No toques docs/, openapi/, api/, web/, prompts/, AI_USAGE.md ni payments/experiments/. Sin push.

CRITERIO DE TERMINADO (yo lo verifico)
- Las pruebas 4a a 4d y 5 existen y VISTE fallar 4a antes del cambio.
- npm test y typecheck en verde (el total sube respecto de 69); openspec validate en verde en las dos carpetas.
- git status limpio; commits convencionales (fix(payments): rotate the token once on 403 when the quote fits; test(payments): cover the weekly one-off grant expiry; docs(openspec): record Test Wallet findings).
- Reporte: 1) resumen de 5 líneas; 2) commits y git diff --stat; 3) pruebas añadidas y cuál viste fallar; 4) texto exacto de los cambios de spec; 5) qué NO comprobaste; 6) hallazgos "esperaba X, pasó Y, cambio Z"; 7) preguntas D-n (máximo 3, solo si el spec no las resuelve).
````
