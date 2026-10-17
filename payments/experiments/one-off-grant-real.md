# Experimento D — grant puntual semanal: pago único y cancelación con grant.cancel

- **Fecha:** 2026-10-17T12:24:03.271Z
- **SDK:** @interledger/open-payments 7.4.0 (Node v24.20.0)
- **Remitente:** `<remitente>` · **Receptor:** `<receptor>` (mascarados por seguridad)
- Los valores se reducen a lista blanca: no hay tokens, nonces, interact_ref, hash, keyId, interactUrl ni URLs de grants/manage/continue.

## Grant puntual con interval semanal

Interval pedido y aceptado: `R1/2026-10-17T12:23:46.008Z/P1W`. expires_in del token: 600.

## Pago único

- Quote: debit=500.00 receive=500.00.
- Pago: debit=500.00 sent=0.00.
- Gastado verificado: 500.00 en 1 s.

## Cancelación y lectura posterior

- grant.cancel OK.
- Lectura con el access token después del DELETE: rechazada: status 403 código 403.

## Pagos reales de esta corrida

- Un único pago de 500,00 COP: realizado.
