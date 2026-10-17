# Experimento C — ¿grant.cancel invalida de verdad el acceso? (P3 parte 2)

- **Fecha:** 2026-10-17T07:16:11.584Z
- **SDK:** @interledger/open-payments 7.4.0 (Node v24.20.0)
- **Remitente:** `<remitente>` · **Receptor:** `<receptor>` (mascarados por seguridad)
- Los valores se reducen a lista blanca: no hay tokens, nonces, interact_ref, hash, keyId, interactUrl ni URLs de grants/manage/continue.

## Procedimiento

1. Grant interactivo de 4.000,00 COP sin interval, aprobado por el dueño.
2. continue OK (expires_in: 600).
3. Lectura de referencia con el access token antes de cancelar: aceptada (spentDebit=no informado).

## P3 (parte 2) — resultado

- grant.cancel (DELETE sobre la continue URI con el continue token) OK.
- Lectura con el access token después de cancelar: rechazada: status 403 código 403.
- Pago con el access token después de cancelar: no se hizo: la lectura ya distinguió que el token quedó inusable.

Pagos reales en esta corrida: 0 de 500,00 COP (tope de la unidad: 5 pagos).

## Conclusión

grant.cancel revocó el acceso: la lectura con el access token quedó rechazada, igual que el efecto de token.revoke en el experimento A.
