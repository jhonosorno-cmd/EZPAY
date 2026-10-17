# 03 — Specs de H1: motor de decisión y PIN

- Fecha: 2026-10-16
- Autor: Valdex328 (Daniel, rol Verificación y calidad, ML 2)
- Herramienta: Claude Code (Claude Opus 5.5 y Claude Sonnet 5.5) en Traycer, sesión de planeación y orquestación

Decisiones de Daniel sobre las specs `decision-engine` y `pin-validation` (carpeta `openspec/changes/add-decision-engine/`). Cada prompt responde a una propuesta o pregunta de la sesión.

Texto literal de los prompts, en orden:

---

## Prompt 1 (pedir las specs de H1 al Constructor de Specs)

````text
Estas decisiones las tomamos luego, por ahora hay que sacar el hito H1 que depende de mi.

envía la instruccipn al Constructor de specs para cree las specs para realizar H1 según mi rol.
````

## Prompt 2 (forma del context y de resolution)

````text
dame un ejemplo de los puntos abiertos de la spec del decision engine sobre la propuesta de la forma exacta del context y de resolution para socializarlo con Pagos y definir
````

## Prompt 3 (aceptar propuestas 1 a 7; el motor devuelve decision y reason; regla 6)

````text
acepta todas las propuestas de las preguntas de la tabla, menos la 8. En este caso, el motor debe devolver decision y reason para mostrar al usuario. Dile al constructor de specs que actualice mientras tanto la spec.

Ahora pasemos a la regla 6 de REJECT o REASK.  Dame ejemplos de casos de uso en los que aplique esta regla para socializar y decidir con ML1.
````

## Prompt 4 (decisiones con ML 1 sobre la regla 6 y PAYMENT_PENDING)

````text
Con ML1 se decidió lo siguiente:

Situaciones 1, 2, 3. No deben ocurrir. La plataforma debe mostrar una pantalla de carga mientras se procesa el pago, no deja interactuar hasta que el pago se complete o se rechace por completo.

El resto de situaciones están bien.

Para el reject o reask por ambiguedad, vamos con reask.

Payment_pending mostraría envío en camino, pero por lo que te dije de las situaciones 1, 2 y 3, no debería mostrarse nunca.
````

## Prompt 5 (ventana de 120 s, umbral de monto alto y casos de confianza e intent.status)

````text
pendingWindowSeconds queda de 120s

highAmountThreshold esperamos a los experimentos.

para las decisiones de cortes de confianza y su uso y de la semantica de intent.status, dame ejemplos de casos de uso para tomar las decisiones
````

## Prompt 6 (opción A para las dos decisiones; marcar lo hablado como decidido)

````text
para ambas toma la opcion A. Ya fue hablado con ML1.

Las propuestas que dicen en el spec que falta confirmar o cerrar con pagos, ya están habladas con ellos. Marcalas como decidido.

Que el constructor actualice el spec.

Mientras tanto analicemos las decisiones que faltan, con ejemplos de casos de uso.
````

## Prompt 7 (PAYMENT_PENDING con opción A y plantillas del say)

````text
PAYMENY_PENDING vamos con la opción A.

confirma las plantillas del say y añadelas a la Spec.

que el constructor de specs la actualice. En cuanto esté lista, confirma que no hay decisiones pendientes y súbela al repositorio
````

## Prompt 8 (ejemplo de historia de usuario para B-7)

````text
para la decisión pendiente B-7, dame un ejemplo de un user story para visualizar la situación y decidir.

El resto de propuestas apruebalas, la limitación déjala para H2. Que el constructor actualice la spec de pin-validation mientras tanto.
````

## Prompt 9 (mantener B-7 y marcar las propuestas como decididas en pin-validation)

````text
que el constructor actualice las specs, deja B-7 como está y las propuestas como Decididas en pin-validation.

En la spec del decision-engine, qué hay que definir en la regla 6?
````

## Prompt 10 (regla 6b: aviso por pago no confirmado)

````text
Toma la opción A: que el Constructor agregue al spec decision-engine la regla 6b, el reason PENDING_PAYMENT_UNCONFIRMED con su plantilla, y que un pago sin paymentId cuente como PROCESSING desde el primer intento.
````

---

Registro: 2026-10-16 · transcripción literal de la sesión "Hachathon Interledger EZPAY". Las instrucciones que la IA redactó para los agentes Constructor de Specs y Builder están en `10-instrucciones-a-agentes.md`.
