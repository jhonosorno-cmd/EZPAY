# 06 — Desafío de voz en la confirmación (B11)

- **Herramienta:** Claude Code (Claude Opus 5.5), dentro de Traycer
- **Fecha:** 2026-10-17
- **Contexto que leyó el agente:** `openspec/changes/add-ml2-integration/specs/voice-turn-integration/spec.md`,
  `api/README-ml2.md` § Confirmación con desafío de voz, `api/decision/{engine,say_map}.py`,
  `api/voice/{challenge,phrases}.py` y `api/voice/challenge_phrases.json`.

## Prompts (texto literal)

> lo hablamos entre todos y necesitamos que implementes para probar el desafio de probar la voz, lo necesitamos urgente

## Resultado

- Orquestador: modo CHALLENGE con `EZPAY_CONFIRMATION_CHALLENGE=1` (P5: solo con `ASK_CONFIRM` desde
  COMMAND y voz VERIFIED); frase al azar del banco sin repetir; `phraseScore` con `phrase_match` y
  verificación de la voz de la respuesta; reintento con otra frase; PIN tras frase correcta con voz
  no verificada (`CONFIRMED_WITH_PIN`).
- Contrato B: `challengePhrase` en `TurnResponse` (`x-proposed`, P3). Web: tarjeta con la frase y
  "No, cancelar".
- Probado con Groq y ECAPA reales y voces sintéticas de macOS (sin voces reales): pago con la
  frase correcta, PIN con otra voz, rechazo tras dos frases equivocadas.
- Revisión humana pendiente: calibración en la sala de `challengePhraseMatchMin` (0.80) con el
  micrófono de la demo (ML 2).
