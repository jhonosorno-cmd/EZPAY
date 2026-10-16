# 02 — Alinear el frontend con los mocks del Contrato B

- **Herramienta:** Claude Code (extensión de VS Code), modelo Claude Opus 5.5
- **Fecha:** 2026-10-16
- **Contexto que leyó el agente:** `openapi/contract-b.yaml`, `openapi/README.md` y
  `docs/contratos-cambios-propuestos-v1.1.md` (merge del PR #3, commit `7d7f1fe`), y
  `openspec/changes/add-voice-web-client/specs/enrollment-ui/spec.md`.

## Prompts (texto literal)

> que specs se genera correspondiente al front end

> volver a correr aplicativo

> lo que observo es que el front end tambien deberia, revisar parte de los casoss de uso que entregan as partes del back end y losmotores de transcripcion, se deben anticipar varias precauciones, y ojo con los endpoints,
> deberian existir pestañas para el registro de contactos

(Adjunto: `casos-de-uso.md`, casos de uso preliminares de ML 2.)

> revisa la rama que alexander subio, referente a los mocks correspondientes, esa es la estructura por la cua debemos guiernos, los obtetivos que se tiene, por lo que la reestructuracion del front dependen de esas bases, y ya cuando los motores y el back esten completos se integran en el front, de momento ir construyendo la simulacion de lo que se requiere segun los mocks

## Resultado

- Tipos del frontend generados desde `openapi/contract-b.yaml` (`npm run gen:api`).
- Corregido `GET /api/budget` (`limit = { debitAmount, interval }`) y el turno automático de
  `PAYMENT_PENDING` (`kind=verify_pending`).
- Registro de voz contra `/api/enrollment` (consentimiento, tres frases, revisar, repetir o usar).
- Panel de escenarios para recorrer los ejemplos del mock de Prism; mock propio alineado al contrato.
- Spec `add-voice-web-client` actualizado y validado con `openspec validate --strict`.
