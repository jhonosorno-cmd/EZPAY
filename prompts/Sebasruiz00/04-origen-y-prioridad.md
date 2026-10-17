# 04 — Numeración cronológica, origen de amounts.py, hook y prioridad

- Fecha del prompt: 2026-10-16
- Autor: Sebasruiz00 (rol Voz, ML 1)

Texto literal del prompt:

---

Sí a tus pendientes, con estas decisiones. Guarda este mensaje también como prompt registrado.

## 1. Numeración cronológica
Renombra (aún no hay commit) según el orden en que te los envié:
- `00-contexto-agente.md` (contexto inicial)
- `01-revision-amounts.md` (mi "Tienes mi OK… Alcance de este turno")
- `02-parser-montos.md` (mis decisiones tras tu revisión: lo que hoy se llama `01-parser-montos.md`)
- `03-registro-de-prompts.md` (la regla de registro de prompts)
Primero dime si ese orden coincide con lo que ves en esta conversación; si no, usa el tuyo. Cada
archivo conserva el texto literal del mensaje. Muéstrame los cuatro contenidos antes de guardar.
Sí, agrega a cada uno la línea final de registro (regla 5). Tienes mi "sí" para editar el que ya existe.

## 2. Origen de amounts.py y test_amounts.py
Los escribió Claude Code (Claude Sonnet 5.5) en una sesión anterior mía, hoy 16 oct ~13:20, en la rama
`voz/h1-parser`, a partir de `amount-parsing/spec.md` y `docs/voz/frases-desarrollo.md` (sección A).
Prompt que lo originó, literal, de esa sesión (mensajes míos, en orden):
1. "Puedes clonar el repo nuevo, en el que vamos a trabajar, y entenderlo todo"
2. "Necesito que revices y entiendas como va funcionar la dinamica de prompts y space"
3. "Crees que debamos crear nuevamente los specs y los prompts?, para lograr entregar nuestr parte?"
4. "Hoy es viernes"
El mensaje 4 es el que desencadenó la escritura. Esa sesión no usó la plantilla del Prompt 1 de
`prompts/pre-evento/voz-plantillas-del-evento.md`; el agente de esa sesión escribió primero las
pruebas y luego el código en un solo paso, sin mi aprobación individual por archivo. Declara eso
con esas palabras. Guarda esto como `prompts/Sebasruiz00/00a-origen-amounts-sesion-previa.md` con
los cuatro mensajes literales y la nota anterior, y úsalo como cita en las filas de AI_USAGE.md de
esos dos archivos. La revisión humana de ambos es "Pendiente" hasta que yo los lea.

## 3. Hook UserPromptSubmit
Todavía no lo instales. Primero termina los puntos 1 y 2 y avanza con el código (H-1 a H-6). Cuando
llegue el momento, muéstrame el script completo y la entrada exacta de `settings.local.json`, y
qué hace con un prompt que contenga algo que parezca una llave. No lo instales sin mi "sí".

## 4. Prioridad
Son las ~15:30 y el plazo de H1 ya pasó. Después de guardar los prompts, vuelve a las correcciones
H-1 a H-6 de amounts.py y no te detengas en más registro de lo necesario. Antes de cada commit
revisa la carpeta de prompts, como dijiste.

---

Registro: 2026-10-16 15:36 (hora de guardado) · Claude Code, Claude Sonnet 5.5 (`claude-sonnet-5-5`) · Origen: renumeración de `prompts/Sebasruiz00/`, `00a-origen-amounts-sesion-previa.md` y la cita para las filas de `AI_USAGE.md`; pausa del hook; prioridad de H-1 a H-6.
