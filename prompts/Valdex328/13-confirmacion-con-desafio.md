# 13 — Confirmación con desafío de voz

- Fecha: 2026-10-17
- Autor: Valdex328 (Daniel, rol Verificación y calidad, ML 2)
- Herramienta: Claude Code (Claude Opus 5.5) en Traycer, sesión de planeación y orquestación

Tarea de seguridad compartida con Voz: confirmar el pago repitiendo una frase al azar de un banco (coincidencia de la frase + verificación de la voz). Propuesta en `verificacion-ml2/confirmacion-con-desafio.md`, decisión en `docs/decisiones.md` (17 oct) y requisitos en `openspec/changes/add-decision-engine/`.

Texto literal de los prompts, en orden:

---

## Prompt 1 (tareas de Sebastián y de ML 2; tarea de seguridad; ¿se puede empezar H3?)

````text
para Sebastian y para mi había quedado una tarea sobre la identificación por voz para dar más seguridad, que consiste en asignar scores a el nivel de coincidencia de la transcripción de Sebastian con la frase modelo (la que debe leer el usuario) y los scores de mi identificación de voces. Según lo que hay en H2 y lo que se hizo en H1 anteriormente (en las diferentes ramas y en el main), qué debe hacer Sebastian para completar su parte de H2, qué debe hacer Sebastian para esta tarea de seguridad y qué debo hacer yo?

Es posible y viable ya comenzar con H3 de mi rol?
````

## Prompt 2 (transcripción y verificación en paralelo; cambios de Sebastián)

````text
para la decodificación del audio, no podríamos simplemente, cuando se grabe un audio, llamar al servicio de transcripción y al de reconocimiento del hablante al mismo tiempo?

Revisa los cambios de Sebastian para H2?, qué puede hacer solo y para qué actividades necesita al orquestador de Alexander?
````

## Prompt 3 (la decodificación ya existe en los cambios de Voz)

````text
pero si ya en los cambios de Sebastian está la decodificación, por qué me dices que necesito esta función y que está faltando?
````

## Prompt 4 (dónde va la spec de la función de seguridad)

````text
Listo. Ahora, para la spec de la función de seguridad, según la estructura del repo, deberíamos añadir esta función en la spec general? o donde quedaría? a podríamos generar entre Sebastian y yo sin involucrar al resto?
````

## Prompt 5 (desafío en todas las confirmaciones)

````text
Prefiero la opción B (desafío en todas las confirmaciones); redacta la propuesta al equipo con su impacto.
````

## Prompt 6 (alternativa: banco de frases aleatorias)

````text
otra propuesta es tener un banco de frases aleatorias que se pidan para confirmar los movimientos. Cual es mejor y más fácil de implementar?
````

## Prompt 7 (actualizar la propuesta y primer banco de 30 frases)

````text
Toma el banco de frases: actualiza la propuesta (frases al azar con el pago dicho antes, reglas del banco y coincidencia del 80 %) y arma un primer banco de 30 frases para revisarlo.
````

## Prompt 8 (aprobación presencial, push y aviso en GitHub (issue #12))

````text
de manera presencial se dijo que sí a la propuesta. Pusheamos al repo para que los roles impactados puedan ver qué deben hacer nuevo y generamos un mensaje que les avise que tienen que revisar, mencionandolos en Github.
````

## Prompt 9 (el desafío en decision-engine y speaker-verification)

````text
Que el Constructor agregue el desafío a decision-engine y speaker-verification (entradas nuevas de la confirmación, reglas con los dos puntajes, reasons nuevos) y luego súbelo a H2.
````

## Prompt 10 (comentario en el issue #12 e implementación del desafío en el motor)

````text
redacta un comentario y publicalo mencionando a todos sobre las specs actualizadas, ya que vi que se tocaron las de H1.

Después de esto, que el builder empiece a implementar el desafío. Toma casos suponiendo resultados de la parte de Sebastian, quien debe hacer sus propias pruebas.

Cuando esté hecho, me dices, ejecuto, leemos los resultados y lo implementamos todo.
````

---

Registro: 2026-10-17 · transcripción literal de la sesión "Hachathon Interledger EZPAY". La instrucción que la IA redactó para el Constructor de Specs está en `10-instrucciones-a-agentes.md` (A13) y para el Builder en el mismo archivo (B11).
