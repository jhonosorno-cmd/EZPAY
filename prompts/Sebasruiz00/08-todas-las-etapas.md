# 08 — Paso 1 de las capabilities restantes (sin LLM en la intención)

- Fecha del prompt: 2026-10-16
- Autor: Sebasruiz00 (rol Voz, ML 1)

Texto literal del prompt:

---

Quiero avanzar en todas las etapas que faltan. Guarda este mensaje como prompt registrado (siguiente
número libre, hora real con `date`).

## Qué hacer
Entrega, **en un solo mensaje**, el **Paso 1 de 3** de estas cuatro capabilities, en este orden de
construcción:
1. `reply-classification` (`classify_reply`) y `say` (catálogo de textos de `docs/voz/contrato-voz.md` §7).
2. `contact-resolution` (`resolve_recipient`, `resolve_choice`).
3. `intent-extraction` (`extract_intent`), **solo reglas, sin LLM** (decisión mía: el MVP no usa LLM
   para la intención; whisper/`transcribe` no cambia).

Para cada una, lee su spec en `openspec/changes/add-voice-understanding/specs/<capability>/spec.md` y los
casos de `docs/voz/frases-desarrollo.md`, y entrégame: (a) casos límite que el spec no cubre, cada uno con
tu recomendación y su consecuencia; (b) el bloque de pruebas completo; (c) para `intent-extraction`, la
gramática (verbos, preposiciones, sinónimos de destinatario) y una medición de cobertura de las 30 frases
de la sección D; (d) los cambios exactos que habría que hacer a `intent-extraction/spec.md`,
`contrato-voz.md`, `tasks.md` y la plantilla del Prompt 3 por la decisión de no usar LLM (propuestos,
no aplicados).

## Agenda provisional
Pagos aún no me entrega la agenda. Para `contact-resolution` propón una agenda **ficticia y provisional**
en un archivo de configuración dentro de `api/voice/` (alias, nombre, `previouslyPaid`, y una wallet
address de ejemplo con el dominio de la Test Wallet, sin datos reales), con: un contacto único, dos
contactos parecidos entre sí (para el caso ambiguo) y una coincidencia aproximada única. Márcala
claramente como reemplazable por la de Pagos. No inventes wallets reales.

## Reglas de este tramo
- Espera mi respuesta única a los cuatro Pasos 1. No escribas archivos hasta entonces.
- Con mi "sí", haz el Paso 2 de cada capability **seguida de la siguiente, sin consultarme entre ellas**,
  en el orden anterior: pruebas en rojo → código mínimo → revisión adversarial → corrección de fallos
  graves. Al terminar las cuatro, entrégame un solo informe: pytest por capability, diff por archivo,
  hallazgos y decisiones que tomaste sin preguntarme.
- Para el informe y para `RESULTADOS.md`, **resume las entradas hostiles con conteos y categorías**; no
  copies listas largas de entradas hostiles al chat, déjalas en el archivo de pruebas.
- Antes de cada commit: `git diff --cached`, `prompts/` completo y ningún secreto. Un PR por capability
  (o por pareja `classify_reply` + `say`). Dos commits (pruebas, luego código) cuando se pueda.
- `AI_USAGE.md` actualizado con una fila por archivo; revisión humana "Pendiente" salvo que yo diga otra cosa.
- Si algo te bloquea o el spec contradice un documento, para y pregúntame.

---

Registro: 2026-10-16 16:59 (hora de guardado) · Claude Code, Claude Opus 5.5 (`claude-opus-5-5`) · Origen: Paso 1 y Paso 2 de `reply-classification` + `say`, `contact-resolution` e `intent-extraction`: `api/voice/{text,config,replies,phrases,contacts,intents}.py`, `api/voice/agenda_provisional.json`, `api/voice/RESULTADOS.md` y `api/tests/voice/test_{replies,phrases,contacts,intents,package}.py`.
