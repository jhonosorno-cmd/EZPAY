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

## Prompt 6 (PR de H3 y el monto 73450)

````text
haz el PR de H3.

También, volviendo al motor de decisión, Sebastian haciendo pruebas encontró que la cifra 73450 da AMBIGUOUS_AMOUNT. Esto está definido así? debería solo pasar cuando el monto incluye decimales, en este caso es un número entero. Revisa y dime
````

## Prompt 7 (ejecutar X-7)

````text
esto lo decidirá y lo arreglará Sebastian. Vamos con el X-7
````

## Prompt 8 (informe de X-7)

````text
Aquí el informe:

**# X-7 — frases del banco del desafío**

- 24 toma(s) de 2 persona(s): daniel, sebastian (72 filas: una por toma y huella).

**## Duración por frase**

| frase_id | palabras | tomas | mín s | mediana s | máx s | tomas < 2.0 s | marca |

|---|---|---|---|---|---|---|---|

| 5 | 7 | 2 | 2.74 | 2.78 | 2.82 | 0 | ok |

| 7 | 7 | 2 | 1.98 | 2.80 | 3.62 | 1 | SACAR O ALARGAR |

| 8 | 7 | 2 | 2.10 | 2.27 | 2.44 | 0 | SACAR O ALARGAR |

| 9 | 8 | 2 | 2.91 | 3.12 | 3.32 | 0 | ok |

| 14 | 8 | 2 | 2.29 | 2.45 | 2.60 | 0 | ok |

| 18 | 7 | 2 | 2.06 | 2.14 | 2.22 | 0 | SACAR O ALARGAR |

| 21 | 6 | 2 | 3.00 | 3.21 | 3.43 | 0 | ok |

| 22 | 8 | 2 | 2.69 | 2.80 | 2.92 | 0 | ok |

| 26 | 7 | 2 | 2.64 | 2.69 | 2.73 | 0 | ok |

| 27 | 6 | 2 | 2.26 | 2.57 | 2.88 | 0 | ok |

| 28 | 7 | 2 | 2.53 | 2.65 | 2.78 | 0 | ok |

| 29 | 6 | 2 | 2.99 | 3.04 | 3.08 | 0 | ok |

(una toma por hablante y frase; marca: alguna toma < 2.0 s o mínima < 2.2 s)

**## Separación por umbral**

| umbral | falso aceptado | falso rechazo | NOT_AVAILABLE | de ellos genuina | genuino mín | impostor máx | margen |

|---|---|---|---|---|---|---|---|

| 0.40 | 0 | 0 | 3 | 1 | 0.55 | 0.28 | 0.27 |

| 0.45 | 0 | 0 | 3 | 1 | 0.55 | 0.28 | 0.27 |

| 0.50 | 0 | 0 | 3 | 1 | 0.55 | 0.28 | 0.27 |

| 0.55 | 0 | 0 | 3 | 1 | 0.55 | 0.28 | 0.27 |

**## Comparación con los comandos de x2 (estrategia A, variante completo)**

- comandos: genuino mín 0.51, impostor máx 0.40, margen 0.10

- banco del desafío: margen 0.27 — el banco no separa peor.

**## phrase_score (solo con --transcribir)**

- sin phrase_score (correr de nuevo con --transcribir si 0.80 queda dudoso).

**## Recomendación**

Sacar o alargar las frases con frase_id 7, 8, 18 (tomas por debajo de 2.0 s o mínima < 2.2 s).

0.45 se mantiene (0 falsos aceptados, margen 0.27).

minVerifySeconds = 2.0 deja 1 toma(s) genuina(s) como NOT_AVAILABLE (pediría PIN en vez de desafío): alargar esas frases o revisar.

Comandos de x2: margen 0.10 (genuino mín 0.51, impostor máx 0.40); el banco separa igual o mejor.

Sin --transcribir no hay phrase_score: repetir con --transcribir si 0.80 queda dudoso.
````

## Prompt 9 (cambios al banco de frases y transcripción con Groq)

````text
aplica los cambios a las frases sugeridas, avisa a Sebastian de esto y hacemos el commit. No probemos las frases nuevamente.

Además, hay que asegurarnos  de que la parte de transcripción no se va a hacer local, Sebastián tiene esto definido, ya que el modelo local funciona muy mal en comparaación a Groq.
````

---

Registro: 2026-10-17 · transcripción literal de la sesión "Hachathon Interledger EZPAY". Las instrucciones que la IA redactó para los agentes están en `10-instrucciones-a-agentes.md` (A14, A15, B12 y B13).
