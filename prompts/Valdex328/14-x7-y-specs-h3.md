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

## Prompt 3 (estado de H3 y prioridades)

````text
que no he revisado hasta donde vamos de H3? qué debo priorizar?
````

## Prompt 4 (ejecutar las pruebas de la fachada)

````text
empecemos con las pruebas. Cuales son los archivos que tengo que ejecutar.
````

## Prompt 5 (resultado de las pruebas de la fachada)

````text
**...........Facade failed to decode enrollment audio**

**...Speaker enrollment failed (RuntimeError)**

**Speaker enrollment status failed**

**.Facade not loaded**

**........Speaker verification failed**

**Facade failed to decode audio**

**.Facade not loaded**

**Facade not loaded**

**...Speaker verification timed out**

**Speaker verification busy; returning NOT_AVAILABLE**

**.**

Ran 28 tests in 1.442s

OK

....................................................................................................................................................... [ 15%]

.................................................................................................................ss.................................... [ 30%]

....................................................................................................................................................... [ 45%]

....................................................................................................................................................... [ 61%]

....................................................................................................................................................... [ 76%]

....................................................................................................................................................... [ 91%]

................................................................................                                                                        [100%]

984 passed, 2 skipped in 29.65s

Esto me dio la ejecución de las pruebas. Hubo fallos en el primero
````

---

Registro: 2026-10-17 · transcripción literal de la sesión "Hachathon Interledger EZPAY". Las instrucciones que la IA redactó para los agentes están en `10-instrucciones-a-agentes.md` (A14, A15, B12 y B13).
