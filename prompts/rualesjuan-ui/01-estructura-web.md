# 01 — Estructura de la web app

- **Herramienta:** Claude Code (extensión de VS Code), modelo Claude Opus 5.5
- **Fecha:** 2026-10-16
- **Contexto que leyó el agente:** `AGENTS.md`, `docs/contratos-http-v1.md` (Contrato B),
  `docs/decisiones.md` y `openspec/changes/add-voice-web-client/` (proposal y specs), en el commit `59e4134`.

## Prompts (texto literal)

> estas conectado a las nevas modificaciones hechas en el repositorio, se supone que se han creado nuevas indicaciones, analiza

> clonemos esta nueva version en mi mac y como mi rol es de front end empecemos a cosntruir la idea generarl para ir haciendo pruebas y montar la estructura

> esta es una idea propuesta para la estructuracion y diseño

(Adjuntos: una imagen de referencia de una app bancaria índigo/violeta, "Lorem Bank", y un
`Fonts.txt` que indica Raleway.)

## Resultado

Esqueleto de `web/` (Vite + React + TypeScript): cliente del Contrato B, máquina de estados de la
conversación, TTS, grabación push-to-talk, teclado de PIN, recibo, `/grant-callback` y un mock del
Contrato B. Las pruebas se escribieron antes que el código, a partir de los escenarios del spec.
