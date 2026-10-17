# 07 — Flujos del equipo y conflictos con otros roles

- Fecha: 2026-10-16
- Autor: Valdex328 (Daniel, rol Verificación y calidad, ML 2)
- Herramienta: Claude Code (Claude Opus 5.5 y Claude Sonnet 5.5) en Traycer, sesión de planeación y orquestación

Prioridades a partir de `docs/flujos/` y decisiones sobre los conflictos con los PRs de Frontend (#2), Voz (#4) y el spec de Pagos.

Texto literal de los prompts, en orden:

---

## Prompt 1 (priorizar actividades según los flujos)

````text
en el repo, revisa la carpeta docs\flujos y ambos archivos que están ahí. Según los flujos, organiza mis siguientes actividades por prioridad. Prioriza resolver los conflictos con otras specs u otros compañeros.
````

## Prompt 2 (decisiones sobre los conflictos 1 a 4 y reparto del trabajo)

````text
- Para el conflicto 1 de PAYMENT_PENDING, vamos con la opción de Juan. La idea es esperar la respuesta de la wallet para ver si se hace o se rechaza el envío. Después de la respuesta de la wallet se cambia el estado.

- Para el conflicto 2, proponemos un solo catálogo con mis textos agregados, es decir, la solución propuesta en la tabla.

- Para el conflicto 3, enviar a Alexander la lista de ajustes.

- Para el conflicto 4, corrige el proposal y sube los archivos faltantes.

- Reparte el trabajo entre los agentes
````

---

Registro: 2026-10-16 · transcripción literal de la sesión "Hachathon Interledger EZPAY". Las instrucciones que la IA redactó para los agentes Constructor de Specs y Builder están en `10-instrucciones-a-agentes.md`.
