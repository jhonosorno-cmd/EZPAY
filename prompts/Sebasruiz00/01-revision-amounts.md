# 01 — Revisión adversarial de amounts.py

- Fecha del prompt: 2026-10-16
- Autor: Sebasruiz00 (rol Voz, ML 1)

Texto literal del prompt:

---

Tienes mi OK. Resumen aprobado. Respondo a tus puntos y te doy el alcance de este turno.

## Respuestas a tus puntos
1. **Nombres de la intención:** usa `{action, amount, recipient, status}` (contrato-voz.md §3). Si el
   equipo adopta otros, será un renombrado. No esperes.
2. **Puntaje de confianza (3b):** no lo hagas en H1. Lo tratamos después de las 4 capabilities, con
   los valores de corte que yo decida. No lo agregues a ningún spec todavía.
3. **30 s:** ya está. No falta nada.
4. **Cifra de la confirmación:** por defecto es solo el `receiveAmount` y el nombre
   (contrato-voz.md §6, V-16). No esperes el cierre del equipo.
5. **"pesos" fijo en `say`:** el MVP es COP. Usa la palabra "pesos" como constante de configuración
   junto a `AssetConfig`, no escrita dentro de la plantilla.
6. **Frase 15 ("10.505"):** tu lectura es correcta: con la regla es-CO son 10.505 pesos
   (`1050500`), no `TOO_MANY_DECIMALS`. En las pruebas usa esa expectativa y anota la etiqueta
   engañosa en tu reporte. No edites `docs/voz/frases-desarrollo.md`; yo lo corrijo después.
7. **Frases 22, 24 y 25:** las pruebas deben aceptar `UNKNOWN` y `UNCLEAR`; ambos significan no pagar.
8. **Fuera de mi módulo:** "sí tardío", `AWAITING_PIN`, errores HTTP de `/turns`, `previouslyPaid`.
   No los pruebes en `api/voice/`. Déjalos en una lista "fuera de módulo" para pasarla a Pagos.
9. **v1.1 (PAYMENT_PENDING, `text` = `alias`):** usa v1. Que `resolve_choice` acepte `alias` es
   compatible con ambas.
10. **Errores de documentos ajenos** (roles.md, prompt-llm-intencion.md): no los toques. Haz una
    lista para que yo la lleve al equipo.
11. **`__pycache__`:** el `.gitignore` ya tiene `__pycache__/`. Confírmalo con `git status` y `git check-ignore`.
12. **Validación:** usa el comando de npx que te di.

## Alcance de este turno: solo revisión, no cambies nada
Lee `api/voice/amounts.py` y `api/tests/voice/test_amounts.py` y haz el Prompt 6 (revisor adversarial):
1. Tabla escenario del spec `amount-parsing` → prueba que lo cubre. Marca los que no tienen prueba.
2. Puntos donde el código hace algo que el spec no pide, o no hace lo que pide.
3. Riesgos: `float`, redondeos, `int()` sobre texto sin normalizar, entradas enormes, caracteres
   Unicode raros (dígitos árabes o de ancho completo, espacios invisibles, `٣`), `slang` mal usado.
4. **10 entradas hostiles** que no estén en las pruebas, cada una con el resultado que esperas y el que
   obtienes al ejecutarla. Corre el parser con ellas (puedes ejecutar `python`/`pytest` para leer
   resultados, pero no guardes archivos).
5. Cada hallazgo con archivo y línea, y tu propuesta de arreglo.

No escribas ni cambies ningún archivo. Muéstrame los hallazgos ordenados por gravedad y espera mi
decisión sobre cuáles arreglar. Después de eso, propón el siguiente paso (`contact-resolution`).

---

Registro: 2026-10-16 15:36 (hora de guardado) · Claude Code, Claude Sonnet 5.5 (`claude-sonnet-5-5`) · Origen: revisión de `api/voice/amounts.py` y `api/tests/voice/test_amounts.py`; no creó ni cambió archivos (informe en el chat).
