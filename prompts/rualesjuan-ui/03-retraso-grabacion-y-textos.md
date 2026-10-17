# 03 — Retraso al grabar, textos de enrolamiento y PIN del mock

- **Herramienta:** opencode (agente Builder), modelo `zai-org/GLM-5.3-Flash`
- **Fecha:** 2026-10-16
- **Contexto que leyó el agente:** el plan de planeación hecho con Opus
  (artefacto `plan-retraso-grabacion-y-textos` en Traycer, sobre `origin/main` tras el merge
  de PR #2), `web/src/voice/useRecorder.ts`, `web/src/enrollment/`,
  `openspec/changes/add-voice-web-client/`, `verificacion-ml2/textos-enrolamiento.md` y
  `api/voice/phrases.py`.

## Prompts (texto literal)

> debes implementar el plan que el padre realizo con opus

## Resultado

- `web/src/voice/useRecorder.ts`: estado `preparing`, `startedAt` y "recording" solo en
  `onstart`, cancelación al soltar antes de que empiece, log DEV de la latencia sin datos de audio.
- Nuevo `web/src/voice/cue.ts`: señal corta de "Habla ahora" (vibración o tono de 60 ms).
- `MicButton.tsx` con `aria-disabled` (no `disabled`) y `setPointerCapture`; `Enrollment.tsx`
  con "Preparando el micrófono…" deshabilitado, "Habla ahora" al confirmar y `MIC_DENIED`.
- Pruebas nuevas: `useRecorder.test.tsx` (10 escenarios), `MicButton.test.tsx`,
  `Enrollment.test.tsx`, `MIC_DENIED` en `enrollmentFlow.test.ts`.
- `content.ts` con los textos definitivos de ML 2 y `content.test.ts`.
- `web/mock/phrases.ts` y `server.ts` alineados con el catálogo de `api/voice/phrases.py`.
- Spec `web-voice-io` ("La grabación empieza cuando el navegador lo confirma"),
  `enrollment-ui` (consentimiento único) y `tasks.md` 1.2.
- Revisión humana pendiente: medición real del retraso del micrófono en la laptop de la demo
  (`[ezpay] mic-start-latency` en consola) y lectura de los textos por Voz y ML 2.