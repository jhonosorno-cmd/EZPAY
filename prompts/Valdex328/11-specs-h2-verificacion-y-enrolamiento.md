# 11 — Specs de H2: verificación de hablante y enrolamiento

- Fecha: 2026-10-16
- Autor: Valdex328 (Daniel, rol Verificación y calidad, ML 2)
- Herramienta: Claude Code (Claude Opus 5.5 y Claude Sonnet 5.5) en Traycer, sesión de planeación y orquestación

Decisiones sobre `voice-enrollment` y `speaker-verification` (carpeta `openspec/changes/add-decision-engine/`), y el retraso al empezar a grabar en la web.

Texto literal de los prompts, en orden:

---

## Prompt 1 (propuestas y decisiones de voice-enrollment)

````text
que propuestas y decisiones hay para el vioce-enrollment spec?
````

## Prompt 2 (aceptar los 7 huecos; la huella espera X-3; retraso al grabar)

````text
- para la propuesta sobre la huella, después de que hagamos el experimento tomamos la decisión
- Acepta todas tus propuestas para los huecos.
- Además, encontramos con unas pruebas que hizo Juan, que puede haber un pequeño delay entre cuando se da al botón de iniciar grabación y el momento en que empieza a grabar, qué soluciones hay para esto y quien las debería hacer según su rol?
````

## Prompt 3 (mensaje para el agente de Juan y explicación de H2 para el equipo)

````text
dame el mensaje con la explicación de lo que debe hacer Juan, algo que pueda pasar a su propio agente de IA y que lo haga.

También, dime en qué consiste H2 para todo el equipo para leerselas en voz alta ahora mismo.
````

## Prompt 4 (propuestas y decisiones de speaker-verification)

````text
que decisiones y propuestas hay en la spec de speaker-verification?
````

## Prompt 5 (aceptar los 6 huecos y subir los specs de H2)

````text
Acepta las 6 propuestas de los huecos: que el Constructor actualice speaker-verification y luego sube los dos specs de H2 a una rama ml2/h2-verificacion desde main, validados con --strict.
````

---

Registro: 2026-10-16 · transcripción literal de la sesión "Hachathon Interledger EZPAY". Las instrucciones que la IA redactó para los agentes Constructor de Specs y Builder están en `10-instrucciones-a-agentes.md`.
