# Builder 01 — Revisión del código del PR #1 contra los specs

Brief enviado el 16 de octubre de 2026 por el supervisor (Claude Code, sesión "coordinator") al
builder (agente opencode "Configuración Builder Pagos EZPAY"). Plan aprobado por Alexander
(@jhonosorno-cmd) con "OK al plan de la unidad 1. Mandale el brief al builder."

---

````text
UNIDAD 1 — Revisar el código del PR #1 contra los specs (SOLO LECTURA)

OBJETIVO
Decidir con evidencia qué del código del PR #1 (servicio Node/TS de pagos, cerrado sin mergear, 22 archivos en payments/, +5987 líneas, dice tener 56 pruebas) se conserva para payments/ en tu rama. El PR nunca se probó contra la Test Wallet. No construyas nada todavía.

QUÉ LEER (en este orden)
1. AGENTS.md y docs/decisiones.md (decisiones del equipo; la del grant puntual semanal está PENDIENTE de un experimento: marcala "pendiente del experimento", no la resuelvas).
2. openspec/changes/add-payments-service/specs/payments-service/spec.md (cada "Requirement" y sus escenarios) y openspec/changes/add-payments-service/design.md (D1 a D13).
3. docs/contratos-http-v1.md y docs/contratos-cambios-propuestos-v1.1.md (v1.1 gana si chocan). De v1.1 te importan A-1 (DELETE /v1/grants/{id}), A-2 (varios grants ACTIVE por usuario) y A-3 (acciones create, read, list).
4. openapi/contract-a.yaml (cómo lo mockean los demás roles).
5. El código del PR #1: `git fetch origin pull/1/head:pr1` en C:\Users\Admin\ezpay-backend (solo crea la referencia local `pr1`; NO hagas checkout ni merge). Leelo con `git show pr1:<ruta>`.

QUÉ HACER
A. Para CADA requisito del spec de payments-service (hay unos 35), y para D1..D13 del design, determiná: ¿lo implementa el PR #1? Citá archivo:línea (de `pr1`). ¿Qué prueba del PR lo cubre (archivo y nombre del test)? Veredicto: CONSERVAR / AJUSTAR (qué cambiar) / FALTA.
B. Lista aparte de lo que el PR hace y NINGÚN spec pide (candidato a quitar), y de desvíos del diseño (por ejemplo cómo guarda la idempotencia, cómo rota el token, cómo calcula el gastado).
C. Brechas contra v1.1: A-1, A-2, A-3. Y todo lo que el PR escribió contra "v1 anterior" (por ejemplo, un grant único por usuario).
D. Prueba real y reproducible FUERA de los repos: extraé el PR a una carpeta temporal (por ejemplo %TEMP%\pr1-review): `git archive pr1 payments | tar -x -C <carpeta>`; entrá a <carpeta>\payments, corré `npm ci` y `npm test` con Node 24. Pegá la salida real: cuántas pruebas pasan, cuántas fallan, advertencias. Si algo no corre, decí exactamente por qué. NO copies nada a C:\Users\Admin\ezpay-backend en esta unidad.
E. Señalá riesgos que veas para correr contra la Test Wallet real (SDK de @interledger/open-payments: versión, API que usa el adaptador, timeouts, manejo de errores) sin ejecutar nada contra la wallet.

ARCHIVOS PERMITIDOS
Ninguno del repo. Solo la carpeta temporal del punto D y la referencia local `pr1`. Sin commits, sin push. Al terminar, `git status` en C:\Users\Admin\ezpay-backend tiene que estar limpio.

NO HAGAS
No leas ni imprimas .env, llaves, tokens ni keyId. No cambies specs ni contratos: si un spec contradice a otro o a v1.1, listalo como "esperaba X, pasó Y, cambio Z" y proponé el ajuste. No resuelvas por tu cuenta lo que dependa de una decisión del dueño: pasámelo con opciones.

CRITERIO DE TERMINADO (yo lo verifico)
- Todos los requisitos del spec y D1..D13 están en la tabla, cada uno con fuente (archivo:línea) y veredicto.
- Conteo real de pruebas con la salida pegada.
- Listas B, C y E presentes.
- `git status` limpio y sin commits nuevos en payments/backend.

FORMATO DEL REPORTE (respondeme por mensaje; no escribas archivos)
1) Resumen de 5 líneas máximo. 2) Tabla: requisito | ¿en el PR? (archivo:línea) | prueba | veredicto. 3) Listas B, C, E. 4) Resultado literal de `npm test`. 5) Propuesta de qué se conserva y en qué orden se ajusta para la unidad 2. 6) Preguntas/decisiones en formato D-n (por qué importa; opciones con costo; recomendación), máximo 3. Distinguí lo que COMPROBASTE ejecutando de lo que inferís leyendo.
````
