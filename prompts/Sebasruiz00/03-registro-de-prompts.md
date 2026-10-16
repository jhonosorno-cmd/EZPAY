# 03 — Regla adicional de registro de prompts

- Fecha del prompt: 2026-10-16
- Autor: Sebasruiz00 (rol Voz, ML 1)
- Nota: el prompt pedía guardarlo como 01-registro-de-prompts.md; se guarda como 03 por la numeración cronológica (ver 04).

Texto literal del prompt:

---

Regla adicional de registro de prompts (política de IA del hackathon,
https://interledger.org/es/hackathon/ai-policy/: "el texto real de los prompts enviados a la IA,
no solo un resumen").

1. Cada mensaje mío que te dé una tarea (incluido el primero de contexto y este) es un prompt que
   debe quedar guardado **tal cual lo escribí**, sin resumir ni corregir. Hazlo en
   `prompts/Sebasruiz00/NN-tema.md`, con NN consecutivo (00, 01, 02...). Usa 00-contexto-agente.md
   para el primero. Si un archivo ya existe, no lo sobrescribas: agrega el siguiente número.
2. Antes de guardar, muéstrame el archivo que vas a crear y espera mi "sí", como con cualquier otro.
3. Si pego un spec o un archivo largo dentro del prompt, deja la ruta y el commit en vez de copiarlo.
4. Nunca guardes llaves, tokens, `.env` ni transcripciones de voces reales. Si aparece uno, reemplázalo
   por `<redacted>` y avísame.
5. Guarda también, al final de cada archivo, una línea con: fecha y hora, herramienta y modelo, y a
   qué archivos del repo dio origen ese prompt.
6. Propón instalar un hook `UserPromptSubmit` de Claude Code que añada mis prompts automáticamente a
   un archivo de registro, y dime qué cambia en mi configuración antes de tocarla. Si no lo apruebo,
   seguimos a mano.
7. Cuando una fila de `AI_USAGE.md` dependa de un prompt, cita su archivo, por ejemplo
   `prompts/Sebasruiz00/01-parser-montos.md`.
8. Antes de cada commit, revisa que `prompts/Sebasruiz00/` tenga todos los prompts enviados hasta ese
   momento. Si falta alguno, avísame y no hagas el commit.

Confírmame con una línea que entendiste, y guarda este mensaje como `00-contexto-agente.md`
(el de contexto inicial) y este como `01-registro-de-prompts.md`, mostrándome primero el contenido.

---

Registro: 2026-10-16 15:36 (hora de guardado) · Claude Code, Claude Sonnet 5.5 (`claude-sonnet-5-5`) · Origen: este registro (`prompts/Sebasruiz00/`) y las reglas 5, 7 y 8 para `AI_USAGE.md` y los commits.
