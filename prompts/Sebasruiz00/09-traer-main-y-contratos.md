# 09 — Pausa: traer main y alinear el módulo con mocks y contratos

- Fecha del prompt: 2026-10-16
- Autor: Sebasruiz00 (rol Voz, ML 1)
- Nota: antes de este mensaje llegó un reenvío idéntico de `08-todas-las-etapas.md`; no se registró aparte.

Texto literal del prompt:

---

Pausa en las capabilities. Antes de continuar quiero traer lo que hay en `main` y alinear mi módulo con los
mocks y los contratos que subió el equipo. Guarda este mensaje como prompt registrado (siguiente número
libre, hora real con `date`).

## Paso A — Solo lectura (no cambies nada todavía)
1. Ejecuta `git fetch origin` (no `pull`, no `merge`, no `rebase`). Muéstrame:
   - `git log --oneline main..origin/main` y `git diff --stat main origin/main`;
   - los PR abiertos y recién fusionados, si `gh pr list --state all` está disponible;
   - mi estado local: `git status -s` y en qué rama estoy.
2. Lee **lo nuevo** en `origin/main` (sin traerlo todavía, con `git show origin/main:<ruta>`), y entre
   todo eso presta atención a:
   - `openapi.yaml` y cualquier mock (Prism u otro), con cómo se levantan y en qué puerto;
   - el esqueleto FastAPI en `api/` (rutas del Contrato B, estado de la conversación) y cómo importa o
     importará `api/voice/`: qué funciones llama, con qué firma y qué espera de vuelta;
   - el cliente de Node en Python, el motor de decisión de ML 2 y el contexto que recibe (`decide(context)`);
   - cambios en `docs/` (decisiones, contratos v1/v1.1, spec general) y en `openspec/` que afecten a Voz;
   - `AI_USAGE.md` y `prompts/` de los demás: el formato que usan, para que el mío sea coherente;
   - el `.gitignore` y la estructura de carpetas.
3. Entrégame un resumen corto con:
   (a) con quién me integro y por dónde entra mi código (rutas de importación, funciones, firmas);
   (b) qué esperan de Voz que yo todavía no tenga o que contradiga lo que ya hice (nombres de campos,
       forma de `Amount`, `Intent`, `say`, estados, códigos de error);
   (c) qué mocks existen y contra qué contrato (A o B), y cómo se corren;
   (d) conflictos previsibles con mi trabajo local: sobre todo `AI_USAGE.md` (lo tengo modificado) y
       `api/`.

## Paso B — Propuesta, sin ejecutar
Después de mostrarme eso, propón (no ejecutes) cómo traer `main` a mi rama `voz/h1-parser` con el menor
riesgo, y espera mi "sí": por ejemplo, primero commitear o guardar mis cambios locales, luego `merge` o
`rebase`, y cómo resolver `AI_USAGE.md` sin perder ninguna fila de nadie. Indica qué se podría perder o
romper y cómo lo revertiríamos.

## Paso C — Verificar mi módulo contra el contrato
Con los mocks y los esquemas del contrato, propón un plan de **pruebas de contrato** para lo que entrego:
- `Amount` con `value` solo de dígitos y los nombres exactos del contrato (`assetCode`, `assetScale`);
- `options` solo con `alias` y `name`, nunca la wallet;
- los textos de `say` dentro del estado (`TurnState`) que corresponde;
- errores de monto que no son errores HTTP;
- cualquier campo que el esqueleto o el motor esperen de `Intent`/`Reply`/`Resolution`.
Dime qué se puede comprobar con un mock, qué solo con el esqueleto real y qué dependería de dependencias
nuevas (por ejemplo Node/Prism). No instales nada ni levantes servidores sin mi "sí". Cualquier prueba
que propongas vive en `api/tests/voice/` y no toca archivos de otros roles.

## Reglas
- Nada de escribir, commit, push, merge, rebase, stash ni instalar sin mi "sí" explícito.
- No toques `docs/`, `openspec/config.yaml`, `payments/`, `web/` ni el resto de `api/`.
- Nunca leas ni muestres `.env`, llaves ni tokens. Si algo de `main` incluye uno, avísame sin copiarlo.
- Si encuentras que el contrato o el esqueleto contradicen mi spec, no lo arregles: dímelo y proponme
  qué cambiar y a quién avisar.
- No imprimas listas largas de entradas hostiles en el chat; resúmelas.

Cuando termines el Paso A, para y espera mi respuesta. Retomamos las capabilities después del Paso C.

---

Registro: 2026-10-16 17:22 (hora de guardado) · Claude Code, Claude Opus 5.5 (`claude-opus-5-5`) · Origen: Paso A (lectura de `origin/main`, sin cambios en el repo).
