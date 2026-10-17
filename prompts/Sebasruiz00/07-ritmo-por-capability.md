# 07 — Ritmo de trabajo por capability (tres pasos)

- Fecha del prompt: 2026-10-16
- Autor: Sebasruiz00 (rol Voz, ML 1)
- Nota: no hay archivo 06. El agente de esta sesión no recibió un mensaje que corresponda a ese número (ver informe en el chat).
- Nota: se omite del texto la última línea del mensaje recibido ("Your response above was stopped by a safety classifier…"), que parece un aviso del sistema y no texto del autor.

Texto literal del prompt:

---

Cambio de ritmo de trabajo, desde ahora y solo para las capabilities que faltan. Guarda este mensaje
como `07-ritmo-por-capability.md` (con su pie y la hora real con `date`).

## Qué sigue igual
- Termina `amount-parsing` con el ritmo anterior (ya te di el "sí" a las pruebas H-1 a H-6; sigue
  el orden que te di: pruebas → resultado en rojo → diff → mi "sí" → guardar → verificar).
- Todo lo de la política de IA: cada mensaje mío se guarda literal con su pie; cada archivo con
  ayuda de IA tiene su fila en `AI_USAGE.md` con la revisión humana en "Pendiente" hasta que yo lo lea
  y lo diga; nunca marques algo como revisado por mí.
- Sin commit, push, ramas, dependencias nuevas, ni edición de archivos fuera de tu carpeta (api/voice/,
  api/tests/voice/, prompts/Sebasruiz00/ y mi sección de AI_USAGE.md) sin mi "sí" explícito.
- Antes de cada commit: `git diff --cached`, la carpeta de prompts completa y ningún secreto.

## Ritmo nuevo: tres pasos por capability
Orden: `reply-classification` → `contact-resolution` (cuando tenga la agenda) → `intent-extraction`
(reglas primero, sin LLM) → `say`. Para cada una, rotula cada mensaje tuyo con
**"<capability> — Paso N de 3"** y haz esto:

**Paso 1 de 3 — Casos límite y pruebas.** Lee el spec en
`openspec/changes/add-voice-understanding/specs/<capability>/spec.md` (no me lo pidas pegado; léelo del
repo) y los casos de `docs/voz/frases-desarrollo.md`. Entrégame, en un solo mensaje:
(a) los casos límite que el spec no cubre, cada uno con tu recomendación y su consecuencia;
(b) el bloque de pruebas completo (una por escenario del spec, más las de los casos límite).
Espera mi respuesta. No escribas archivos.

**Paso 2 de 3 — Código y revisión.** Con mi "sí" al Paso 1, y sin preguntarme más hasta el final de
este paso:
1. Escribe las pruebas en `api/tests/voice/` y córrelas; deben fallar solo las nuevas.
2. Escribe el código mínimo en `api/voice/` hasta que pasen.
3. Haz la revisión adversarial (Prompt 6) sobre lo que escribiste: tabla escenario → prueba,
   comportamientos que el spec no pide, riesgos y 10 entradas hostiles ejecutadas con resultado esperado
   y obtenido. Si encuentras fallos graves (dinero equivocado, excepción no controlada, secreto, float),
   corrígelos y repite la revisión; los cambios menores déjalos listados.
4. Entrégame: resultado de `pytest` (cuántas pasan), diff completo de lo escrito, hallazgos de la
   revisión con su estado (corregido o pendiente), y los casos donde tuviste que decidir sin preguntarme.
Espera mi respuesta.

**Paso 3 de 3 — Cierre.** Con mi "sí" al Paso 2: propón las filas de `AI_USAGE.md` (revisión humana
"Pendiente" salvo que yo diga lo contrario), actualiza los pies de los prompts, y propón el commit
(mensaje convencional y archivos exactos). Mi "sí" a ese commit incluye la ejecución de `git add` solo de
esos archivos y de `git commit`; no hagas push.

## Reglas durante el Paso 2 (sin consultarme)
- Solo escribes en las rutas permitidas. Si necesitas algo fuera de ellas, para y pregúntame.
- Sin float, sin `round`, sin `Decimal` desde float (CONV-1). La salida de un LLM es entrada no
  confiable. Nada de audio ni transcripciones reales. Nada de secretos.
- Si el spec es ambiguo o contradice un documento, para y pregunta; no inventes comportamiento.

## Tiempo
Son las ~15:50. Dime al inicio de cada Paso 1 cuánto estimas que tardará la capability completa. El
siguiente hito es H2 a las 17:30.


## Mensajes posteriores del mismo tema (literales, en orden)

**Decisión sobre el mensaje 06 que no llegó (opción b: no existe):**

````text
B
````

---

Registro: 2026-10-16 15:59 (hora de guardado) · Claude Code, Claude Sonnet 5.5 (`claude-sonnet-5-5`) · Origen: ritmo de trabajo de las capabilities `reply-classification`, `contact-resolution`, `intent-extraction` y `say`; en este turno, las pruebas H-1 a H-6 en `api/tests/voice/test_amounts.py`. Aprobaciones y decisiones agregadas el 2026-10-16 19:15 (regla de registro por tema, ver `14-resumen-y-registro-por-tema.md`).
