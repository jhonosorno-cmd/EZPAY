# 02 — Parser de montos (amount-parsing): decisiones tras la revisión adversarial

- Fecha: 2026-10-16
- Autor del prompt: Sebasruiz00 (rol Voz, ML 1)
- Herramienta: Claude Code (Claude Sonnet 5.5)
- Contexto: respuesta a la revisión (Prompt 6) de `api/voice/amounts.py` y `api/tests/voice/test_amounts.py`.
- Spec de referencia: `openspec/changes/add-voice-understanding/specs/amount-parsing/spec.md`

Texto literal del prompt:

---

Buena revisión. Decisiones sobre tus hallazgos. Guarda este mensaje como prompt registrado (regla de
registro) antes de seguir.

## Arreglar ahora (prueba primero, cada una por separado)
**H-1 Gramática mínima de montos en palabras.** Cada componente debe ser de orden estrictamente menor
que el anterior (millones > miles > centenas > decenas > unidades). Reglas:
- Dos tokens numéricos del mismo orden seguidos → `AMBIGUOUS_AMOUNT` ("veinte veinte", "20 000",
  "1 000 000", "20.000 30.000", "diez mil mil", "veinte mil y treinta mil").
- `y` solo vale entre decena y unidad ("treinta y cinco") y antes de "medio" ("un millón y medio").
  Cualquier otro `y` → `AMBIGUOUS_AMOUNT`.
- Espacio (incluido ` `) como separador de miles → `AMBIGUOUS_AMOUNT`. No lo aceptamos.
- "mil millones" y similares: `AMBIGUOUS_AMOUNT`. Sigue válido: "mil" solo = 1000, "20 mil 500" = 20500.
- Tope: un valor mayor a 1.000.000.000 pesos → `INVALID_AMOUNT`.
**H-2 Solo dígitos ASCII.** Cualquier dígito no ASCII (٣, ２, ², ①) → `INVALID_AMOUNT`. Usa `[0-9]` y
`isascii()`; nunca `isdigit()` ni `\d`. Ninguna entrada puede lanzar excepción; toda entrada produce
un `AmountResult`.
**H-3 Topes.** Entrada de más de 200 caracteres → `INVALID_AMOUNT`. Tope de dígitos por token antes
de llamar a `int()`. Prueba con `"1"*5000 + " mil"`.
**H-5 Tabla de jerga.** Al entrar, exige enteros positivos que no sean `bool`; si no, `ValueError` con
mensaje claro (es un error de configuración, no de usuario).
**H-6 Validación de tipos.** `__post_init__` en `Amount` (value `^[0-9]+$`, sin ceros a la izquierda salvo
"0"; `asset_scale >= 0`) y en `AssetConfig` (`asset_scale >= 0`).
**Femeninos.** Acepta `doscientas…novecientas`, `veintiuna`, `una` ("doscientas mil pesos").

## Decisiones sin cambio de código
- **H-4 (`20,000` → 2000):** se mantiene el spec. No cambies nada. Anótalo en tu reporte como riesgo
  conocido: lo cubre la confirmación hablada con la cifra.
- **H-7:** queda para el paso `say`.
- **H-8:** reemplaza la prueba de "sin float" por una que recorra el módulo con `ast` y falle si
  aparece `float`, `round` o `Decimal` como nombre o llamada. Conserva la prueba de la suma.
- **H-10:** borra `"veinte"[:0]`. **H-9:** sin cambio, pero documenta en `amounts.py` que
  `to_dict()` entrega la forma del contrato (camelCase).
- Lo que el spec no pide y ya aceptas ($, COP, peso(s), de; "un millón y medio"; "20 mil 500"; tope):
  se queda. Anótalo en un comentario corto al inicio de `amounts.py`.
- Las listas que hiciste (fuera de módulo y errores en documentos ajenos) las llevo yo al equipo. No
  edites esos documentos.

## Proceso
1. Muéstrame **solo las pruebas nuevas** (una por cada H y por los femeninos, con las entradas
   hostiles de tu tabla y el resultado esperado). Espera mi "sí".
2. Luego el cambio en `amounts.py`, mostrado como diff. Espera mi "sí".
3. Corre las pruebas. Reporta cuántas pasan y re-ejecuta tus 10 entradas hostiles contra el código
   nuevo, con el resultado de cada una.
4. No hagas commit todavía. Propón primero la fila de `AI_USAGE.md` para `api/voice/amounts.py` y
   `api/tests/voice/test_amounts.py`, con la revisión humana en "Pendiente" hasta que yo la haga, y
   cita el archivo de prompt que lo originó.
5. Después de eso, propón `contact-resolution` con tu lista de casos límite. La pregunta sobre la
   medida de similitud la respondo en ese momento.


## Mensajes posteriores del mismo tema (literales, en orden)

**Aprobación del diff de `amounts.py`:**

````text
Si
````

**La misma aprobación, reenviada después de que la respuesta anterior se cortó:**

````text
Si
````

**Aprobación de las filas de `AI_USAGE.md`:**

````text
Si, acabo de revisar y si apruebo
````

**Revisión humana de `amounts.py` y `test_amounts.py`:**

````text
Si revise funciona bien
````

---

Registro: 2026-10-16 15:36 (hora de guardado) · Claude Code, Claude Sonnet 5.5 (`claude-sonnet-5-5`) · Origen: `api/voice/amounts.py` y `api/tests/voice/test_amounts.py` (H-1 a H-6, femeninos, H-8 a H-10), escritos y verificados el 2026-10-16. Aprobaciones y decisiones agregadas el 2026-10-16 19:15 (regla de registro por tema, ver `14-resumen-y-registro-por-tema.md`).
