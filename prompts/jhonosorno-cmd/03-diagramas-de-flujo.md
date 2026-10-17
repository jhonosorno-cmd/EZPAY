# 03 — Diagramas de flujo de EZPAY: estado actual y estado con los PRs abiertos

Prompts enviados el 16 de octubre de 2026 al agente del rol Pagos (Claude Code), en orden.

> **Nota:** el agente `gentle-orchestrator`, que el Prompt 1 pedía usar para la ejecución, no existía
> en el entorno. Por decisión D-3 de Alexander, la ejecución se delegó a `general-purpose`.

---

## Prompt 1 (pedido original)

````text
# Diagramas de flujo de EZPAY: estado actual y estado con los PRs abiertos

Quiero entender cómo se comportan los servicios de EZPAY entre sí según los specs, y cómo cambia
ese comportamiento si se mergean los PRs abiertos. **No lo ejecutes vos: delegá la ejecución al
agente `gentle-orchestrator`** con todo el contexto de este mensaje. Si ese agente no existe en tu
entorno, avisame antes de seguir. Vos supervisás su trabajo y me traés el resultado.

## Qué quiero

**Entregable A — Flujo actual (`main`).** Cómo interactúan Frontend → backend Python (esqueleto
FastAPI, voz, motor, verificación de hablante, PIN) → Node → Test Wallet, **según los specs y los
contratos de `main`**:
- `docs/contratos-http-v1.md` + `docs/contratos-cambios-propuestos-v1.1.md` (v1.1 gana si chocan)
- `openapi/contract-a.yaml` y `openapi/contract-b.yaml`
- `openspec/changes/*`
- `docs/decisiones.md`

Importante: en `main` todavía no hay código de backend. El diagrama muestra el comportamiento
diseñado, y marca con un estilo visual aparte (por ejemplo, borde punteado) los componentes que
solo existen como spec o como mock.

**Entregable B — Flujo con los PRs abiertos mergeados.** El mismo flujo, suponiendo que se mergean
los PRs abiertos al momento de ejecutar (hoy son el #2 web y el #4 voz; confirmalo con
`gh pr list`). **Todo lo que cambia respecto de A va en un color distinto**, con una leyenda.
Distinguí dos tipos de cambio con dos estilos:
1. **Comportamiento distinto**, por ejemplo:
   - la intención se extrae solo con reglas, sin LLM;
   - si falta el monto o el destinatario, `status: "UNCLEAR"`;
   - las frases de `say` salen del catálogo de `api/voice/phrases.py`;
   - el turno automático lleva `kind=verify_pending`.
2. **Pasa de spec o mock a código real**, por ejemplo la web real o las funciones de `api/voice/`.

La rama `ml2/verificacion-calidad` no tiene PR: no la incluyas, salvo que tenga un PR abierto
cuando ejecutes.

## Qué diagramas

Proponeme la lista antes de escribirlos. Como punto de partida:
1. Vista general de componentes y contratos (flowchart).
2. Pago normal dentro del presupuesto, por voz (secuencia).
3. Exceso de límite con el grant puntual de vencimiento semanal (secuencia).
4. Comando por texto o usuario no enrolado → PIN, con intentos y `REJECTED` (secuencia).
5. `PAYMENT_PENDING` y el turno de verificación (secuencia).
6. Enrolamiento de voz con consentimiento (secuencia).

## Formato

- **Mermaid dentro de Markdown**, para que se vea en GitHub: `docs/flujos/flujo-actual.md` y
  `docs/flujos/flujo-con-prs.md`, con un diagrama por sección y un índice arriba.
- Para resaltar cambios: en flowcharts, `classDef` y `class`; en secuencias, `rect rgb(...)`. Cada
  archivo lleva una leyenda de colores y estilos.
- Debajo de cada diagrama, de 2 a 4 líneas con lo que muestra. **Cada paso cita su fuente**
  (archivo y sección, o PR y archivo). Si algo no está definido en ningún spec, marcalo
  **[SIN SPEC]**; no lo inventes.
- Comprobá que cada bloque Mermaid renderiza, por ejemplo con
  `npx -y @mermaid-js/mermaid-cli -i <archivo> -o <salida>` usando una carpeta temporal fuera del
  repo, y mostrame el resultado real.

## Reglas

- **Solo lectura sobre los PRs:** leelos con `gh pr diff <n>` o `git show origin/<rama>:<ruta>`.
  No los mergees, no los cambies y no hagas checkout en el árbol de trabajo.
- Rama `docs/flujos`, conventional commits, PR a `main`. **El merge me lo pedís.**
- Antes de escribir, mostrame la lista de diagramas y el criterio de colores, y esperá mi OK.
  Para las decisiones usá el formato habitual: D-n, por qué importa, opciones con su costo y una
  recomendación; hasta 3 decisiones por mensaje.

## Registro de IA

- Agregá a `AI_USAGE.md` una fila por cada archivo de `docs/flujos/`: rol Pagos, herramientas
  (vos y `gentle-orchestrator`), para qué, y "Revisión humana: pendiente de lectura de Alexander".
- Guardá este prompt literal en `prompts/jhonosorno-cmd/` con el número que siga.
````

## Prompt 2 (respuesta a D-3)

````text
D-3: elijo a. Delegá a `general-purpose` y mostrame primero la lista de diagramas y el criterio de colores.
````

## Prompt 3 (aprobación de los 7 diagramas, la paleta y D-4, D-5, D-6)

````text
OK a los 7 diagramas y a la paleta. D-4 a, D-5 a, D-6 a: delegá la escritura a `general-purpose`, con renders y supervisión tuya.
````
