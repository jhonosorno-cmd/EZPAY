# 12 — Rama H2, experimentos en vivo y código de H2

- Fecha: 2026-10-16
- Autor: Valdex328 (Daniel, rol Verificación y calidad, ML 2)
- Herramienta: Claude Code (Claude Opus 5.5 y Claude Sonnet 5.5) en Traycer, sesión de planeación y orquestación

Rama compartida `H2`, experimentos de calibración en vivo (`Pruebas ML2/experimentos_h2/`, fuera del repo), decisiones con sus resultados y código de `api/speaker/`.

Texto literal de los prompts, en orden:

---

## Prompt 1 (crear la rama H2 y mover el trabajo)

````text
antes de continuar, se sugirió que hagamos una rama que se llame "H2" en la que todos los integrantes subamos lo que hagamos de H2 para luego mergearla al main. Entonces crea la rama y mueve lo que tengo en la rama actual sobre H2
````

## Prompt 2 (plan de experimentos en vivo con las frases del enrolamiento)

````text
ahora arma el plan de los experimentos. No uses grabaciones que ya tienes, sino que me dices qué ejecutar para hacer las pruebas en vivo, grabando audio nuevo, utilizando las frases que se crearon para el enrollment. Estos scripts deben de quedar en C:\Users\danie\Desktop\Hackatons\Interledger\Pruebas ML2.

Reparte el trabajo con los agentes correspondientes
````

## Prompt 3 (decidir con los resultados de los experimentos)

````text
Ya corrí los experimentos: lee experimentos_h2/resultados/informe.md, propón las decisiones y que el Constructor actualice speaker-verification, voice-enrollment y design.md en la rama H2.
````

## Prompt 4 (cómo mejorar la coincidencia entre voces de la misma persona)

````text
antes de seguir, hay alguna forma de que podamos mejorar la coincidencia entre las voces de la misma persona?
````

## Prompt 5 (probar la mejora 6 y cobertura de los specs)

````text
probemos la 6 por ahora.

Antes de organizar el plan para realizar esta prueba, estos scripts y pruebas cubren ambas specs diseñadas para H2?
````

## Prompt 6 (experimento 6 y código de H2 con pruebas primero)

````text
Además del experimento, manda al Builder a implementar embed, verify y el enrolamiento en api/ sobre la rama H2, con una prueba por escenario de los dos specs antes del código.
````

## Prompt 7

````text
tengo que volver a correr x1?
````

## Prompt 8

````text
terminé para la persona daniel y me salió esto, es lo esperado?

 ✔ 45 fila(s) escritas en C:\Users\danie\Desktop\Hackatons\Interledger\Pruebas ML2\experimentos_h2\resultados\x6.csv

NOT_AVAILABLE en comandos: E: 0, V1: 0, V2: 0
````

## Prompt 9 (decidir el detector con dos voces)

````text
no pude hacer la prueba con Alex, así que toca decidir con lo que hay (voces de daniel y sebastian). Mira los resultados y ayúdame a decidir si es mejor dejar lo que ya estaba o cambiar el método. Lo que buscamos es poder dar más seguridad para reconocer la voz.
````

## Prompt 10 (detector actual y frase de la demo con la divisa)

````text
decidamos entonces el detector como está y actualicemos para que la frase de la demo contenga las divisas. En este caso debe quedar propuesta "pesos", pero hay que dejar la anotación que si se va a expandir para otras divisas, se debe incluir esto.

Reparte el trabajo entre los agentes y dime qué sigue para completar H2.
````

---

Registro: 2026-10-16 · transcripción literal de la sesión "Hachathon Interledger EZPAY". Las instrucciones que la IA redactó para los agentes Constructor de Specs y Builder están en `10-instrucciones-a-agentes.md`.
