# Experimento A — intervalo semanal, retraso del gastado, rotación y revocación

- **Fecha:** 2026-10-17T07:23:41.637Z
- **SDK:** @interledger/open-payments 7.4.0 (Node v24.20.0)
- **Remitente:** `<remitente>` · **Receptor:** `<receptor>` (mascarados por seguridad)
- Los valores se reducen a lista blanca: no hay tokens, nonces, interact_ref, hash, keyId, interactUrl ni URLs de grants/manage/continue.

## P1 — ¿la wallet acepta un interval semanal con una repetición junto a debitAmount?

Intentos (en orden); la cadena de intervalo es pública:

| interval | aceptado | status / código |
|---|---|---|
| `R1/2026-10-17T00:00:00Z/P1W` | sí | — |

Intervalo aceptado: `R1/2026-10-17T00:00:00Z/P1W`.

Respuesta del continue: eco de limits.interval: `R1/2026-10-17T00:00:00Z/P1W`; eco de limits.debitAmount: presente; expires_in del token: 600; manage URL existe: true.

## P5 — retraso del gastado tras un pago (consulta directa, sin servicio)

Gastado antes del pago: no informado. Serie tras crear el pago (segundo, spentDebitAmount):

| segundo | spentDebitAmount |
|---|---|
| 0 | 50000 |

El pago se reflejó en 0 s.

## P4 — rotación de un token vencido (>10 min)

- Intento de pago con el token vencido: pago con token vencido rechazado: status 403 código 403
- token.rotate sobre token VENCIDO aceptado; expires_in nuevo=600; manage URL cambió: true
- consulta con el token VIEJO tras rotar: RECHAZADA (status 403 código 403)

## P3 (parte 1) — ¿token.revoke invalida de verdad el acceso?

- token.revoke OK; consulta de lectura con el token revocado RECHAZADA (status 403 código 403)
- no se hizo: la lectura ya demostró que el token revocado queda inusable

¿Bloquea el acceso?: sí (la lectura quedó inusable).

## Pagos reales de esta corrida (tope de la unidad: 5 pagos de 500,00 COP)

| pago | realizado | detalle |
|---|---|---|
| Pago 1 (grant A, token original) | sí | debit=500.00 |
| Intento de pago con el token VENCIDO | no | status 403 código 403 |
| Pago 2 con token rotado | sí | debit=500.00 |

Pagos reales hechos aquí: 2 (Pago 1 (grant A, token original); Pago 2 con token rotado).
