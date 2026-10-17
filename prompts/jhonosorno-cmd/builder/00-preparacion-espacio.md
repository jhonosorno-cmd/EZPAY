# Builder 00 — Preparación del espacio de trabajo

Mensaje enviado el 16 de octubre de 2026 por el supervisor (Claude Code, sesión "coordinator") al
builder (agente opencode "Configuración Builder Pagos EZPAY"), por el canal entre agentes de
Traycer. Lo aprobó Alexander (@jhonosorno-cmd) al aprobar la lista de unidades.

---

````text
Soy el supervisor del backend de Pagos de EZPAY (sesión "coordinator"). Tu interlocutor soy yo; no le escribas al dueño (Alexander): si necesitás una decisión, mandámela a mí con opciones y yo la elevo.

Preparé tu espacio de trabajo:
- Directorio: C:\Users\Admin\ezpay-backend (git worktree del repo EZPAY)
- Rama: payments/backend, creada desde origin/main (commit e282151). Sin upstream a propósito.
- Todavía NO hay trabajo asignado. La primera unidad (revisar el código del PR #1 contra los specs) te llega en un brief aparte cuando el dueño la apruebe.

Reglas desde ya:
1. Trabajá SOLO en C:\Users\Admin\ezpay-backend, rama payments/backend. Dejá de usar el worktree viejo (payments/openapi-mocks): esa rama ya está mergeada.
2. No hagas push, no abras PRs ni mergees: el push te lo pido yo cuando toque. Commits convencionales, sin atribución a IA.
3. Repo público: nunca leas ni escribas .env, *.key, *.pem, tokens ni keyId en archivos, logs, commits o chat.
4. Los contratos y docs/ no se tocan sin aprobación del dueño. Si un spec resulta incorrecto, reportalo como "esperaba X, pasó Y, cambio Z" y proponé el ajuste; no lo cambies.
5. Spec primero: pruebas desde los escenarios, después el código. Mostrame siempre la salida real de las pruebas, incluidas las que fallan. No reportes "listo" sin evidencia; yo voy a releer tu diff y a correr las pruebas por mi cuenta.

Pedido ahora (solo verificación, sin cambios): confirmame en 3 líneas que (a) podés leer y escribir en C:\Users\Admin\ezpay-backend, (b) `git status` y `git branch --show-current` ahí te dan payments/backend y árbol limpio, (c) tenés Node >= 24 (`node -v`) y qué herramientas de Python hay (`python --version`). Si no podés acceder al directorio, decime exactamente el error; no lo rodees con otro directorio.
````
