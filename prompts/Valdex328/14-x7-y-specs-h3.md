# 14 — X-7 y specs de H3: integración y recalibración

- Fecha: 2026-10-17
- Autor: Valdex328 (Daniel, rol Verificación y calidad, ML 2)
- Herramienta: Claude Code (Claude Opus 5.5) en Traycer, sesión de planeación y orquestación

Experimento X-7 con las frases del banco del desafío (`Pruebas ML2/experimentos_h2/`, fuera del repo) y decisiones sobre las specs de H3 (`openspec/changes/add-ml2-integration/`).

Texto literal de los prompts, en orden:

---

## Prompt 1 (experimento X-7)

````text
Arma el experimento x7_desafio en Pruebas ML2 (fuera del repo): leer frases del banco, medir voz útil contra minVerifySeconds y puntajes genuino/impostor, sin guardar audio; mándalo al Builder
````

## Prompt 2 (decisiones P1 a P8, rama H3 e implementación)

````text
acepta todas las recomendaciones de H3, P6 con 4 personas porque desde ya, vamos mal de tiempo, y la corrección al estado de sesión. Que el constructor lo aplique, arregla el README.

Como esto es H3, la idea sería crear una rama que se llame H3 y subir los archivos.

Posterior a esto, inicia con la implementación con el builder.

La prueba X-7 la correré después.
````

---

Registro: 2026-10-17 · transcripción literal de la sesión "Hachathon Interledger EZPAY". Las instrucciones que la IA redactó para los agentes están en `10-instrucciones-a-agentes.md` (A14, A15 y B12).
