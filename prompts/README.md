# Prompts

Texto **real** de los prompts enviados a herramientas de IA durante el evento, como pide la
[política de IA](https://interledger.org/es/hackathon/ai-policy/). No resúmenes.

## Convención

- Un archivo por tema: `prompts/<usuario-github>/<NN>-<tema>.md`, por ejemplo
  `prompts/<usuario>/01-parser-montos.md`.
- Texto literal del prompt. Si se pegó un spec, se deja la ruta del archivo y el commit en lugar
  de copiarlo entero.
- Claude Code: un hook `UserPromptSubmit` puede agregar cada prompt al archivo de la persona.
  Otras herramientas: exportar el historial al final de cada sesión.
- **Nunca** pegar llaves, tokens ni secretos. Si aparece uno por error, se reemplaza por
  `<redacted>` y se rota la llave.
- No se guardan transcripciones de voces reales (PRIV-1).

## Pre-evento

[`pre-evento/`](pre-evento/) tiene los prompts y plantillas usados **antes** del 16 de octubre,
declarados en `AI_USAGE.md` § Trabajo previo al evento. No son parte del registro del evento.
