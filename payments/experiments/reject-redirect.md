# Experimento B — rechazo en la wallet y continue sin interact_ref

- **Fecha:** 2026-10-17T07:13:51.482Z
- **SDK:** @interledger/open-payments 7.4.0 (Node v24.20.0)
- **Remitente:** `<remitente>` · **Receptor:** `<receptor>` (mascarados por seguridad)
- Los valores se reducen a lista blanca: no hay tokens, nonces, interact_ref, hash, keyId, interactUrl ni URLs de grants/manage/continue.

## P2 — ¿qué nombres de parámetros trae el redirect a finishUri cuando el usuario rechaza?

Parámetros recibidos: `result`.

- interact_ref: ausente
- hash: ausente
- result: grant_rejected

## P2 — ¿qué responde grant.continue después del rechazo?

continue sin interact_ref respondió: status 401 código request_denied.
