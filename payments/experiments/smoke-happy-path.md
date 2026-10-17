# Smoke test — camino feliz contra la Test Wallet real

- **Fecha:** 2026-10-17 (corrida única, sin reintentos).
- **Servicio:** `payments/` de la rama `payments/backend` (incluye los fixes de la unidad 2: URL de
  `getGrantSpentAmounts` y acciones A-3; y el aviso `spent_fallback` de esta unidad).
- **SDK:** `@interledger/open-payments` 7.4.0 (Node 24, `tsx`).
- **Script:** `experiments/smoke-happy-path.ts` (`npm run smoke -- --wallet <remitente>`).
- **Parámetros:** tope del grant 5.000,00 COP (`value "500000"`), pago 1.000,00 COP
  (`value "100000"`), exceso 5.000,00 COP; receptor: `https://ilp.interledger-test.dev/laura`;
  remitente: `<remitente>`.
- **Seguridad:** el script no lee `.env`; el log del servicio y el del script quedaron en una
  carpeta temporal fuera del repo. En este informe las wallets son `<remitente>` y
  `https://ilp.interledger-test.dev/laura` (pública), los ids se anonimizan (`g_1`, `q_1`, `p_1`)
  y no hay tokens, nonces, `interact_ref`, `hash`, `keyId` ni `interactUrl`.

## Resultado: 12/12 pasos OK en la primera corrida

| Paso | Llamada | Status / código | Monto | Duración | OK |
|---|---|---|---|---|---|
| a | `GET /v1/health` | 200 `{ok:true}` | — | 55 ms | OK |
| b | listener del callback en `127.0.0.1:5173` | — | — | 28 ms | OK |
| c | `POST /v1/grants` (tope total 5.000,00) | 201 `PENDING` | límite 5.000,00 COP | 1.842 ms | OK |
| d | aprobación del dueño en la wallet (redirect a `finishUri`) | callback con `hash` + `interact_ref` | — | 6.646 ms (espera) | OK |
| e | `POST /v1/grants/{grantId}/continue` | 200 `ACTIVE` | remaining 5.000,00 COP | 1.034 ms | OK |
| f | `GET /v1/grants/{grantId}` | 200 | spent 0,00 / remaining 5.000,00 | 307 ms | OK |
| g | `POST /v1/quotes` (1.000,00 al receptor) | 201 | debit 1.000,00 / receive 1.000,00 | 3.005 ms | OK |
| h | `POST /v1/payments` + polling | 201 → `COMPLETED` | debit 1.000,00 | 1.069 ms llamada + 2,8 s de polling | OK |
| i | `GET /v1/grants/{grantId}` | 200 | spent 1.000,00 / remaining 4.000,00 | 325 ms | OK |
| j | reintento: misma clave → misma respuesta; clave nueva → 404 | 201 idéntico / 404 `QUOTE_NOT_FOUND` | spent sin cambios | 367 ms | OK |
| k | exceso: quote 5.000,00 → `exceedsRemaining: true` → pago | 201 quote / 403 `LIMIT_EXCEEDED` | — | 2.117 ms | OK |
| l | cierre del listener y resumen | — | — | 2 ms | OK |

## Datos clave

- **Costo observado:** 0,00 COP — la quote de la Test Wallet devolvió `debitAmount` igual a
  `receiveAmount` (método `ilp`), es decir, sin comisión para este par de wallets.
- **Fuente del gastado:** el servidor respondió siempre (cero líneas `spent_fallback` en el log del
  servicio): la URL corregida en la unidad 2 funciona contra la Test Wallet real. No se puede
  distinguir con estos datos si el servidor ya reflejaba el pago de inmediato o si el valor final
  lo fijó la suma local (`max(servidor, local)` da el mismo resultado).
- **Tiempo hasta `COMPLETED`:** ~2,8 s de polling (la primera consulta, 1 s después de crear el
  pago, aún devolvió `PROCESSING`; la segunda, `COMPLETED`). Consistente con la nota de evidencia
  de E2 (el pago se completa entre la primera y la segunda consulta).
- **Idempotencia:** el reintento con la misma clave devolvió la respuesta original en 2 ms con
  **0 llamadas** a Open Payments (sirvió la respuesta guardada); la clave nueva sobre la misma
  quote devolvió 404 `QUOTE_NOT_FOUND`. Un solo débito confirmado por el gastado.
- **Exceso de límite:** la quote de 5.000,00 volvió `exceedsRemaining: true` y el pago se rechazó
  con 403 `LIMIT_EXCEEDED` sin crear ningún outgoing payment.

## Observaciones (detalles de la corrida, sin secretos)

- En el paso k, el request del 403 registra **1 llamada** a Open Payments en su línea de log: es
  la consulta del gastado (`getGrantSpentAmounts`) que el chequeo de presupuesto necesita antes de
  rechazar; **no** hay llamada de creación de pago. El brief esperaba 0 llamadas: ver
  "Hallazgos" abajo.
- En el log por request, la ruta se registra como `/payments` cuando la respuesta sale del router
  y como `/v1/payments` cuando el error sale por `next(err)` hacia el handler de errores (pasos j
  y k). Inconsistencia cosmética de observabilidad; no afecta el contrato.
- El callback de la wallet trajo los parámetros `hash` e `interact_ref` (nombres registrados; los
  valores nunca se imprimieron).

## Hallazgos ("esperaba X, pasó Y, cambio Z")

1. **Llamadas de Open Payments en el rechazo por tope.** Esperaba 0 llamadas en el 403 del paso k
   (asumido del brief); pasó 1: el servicio consulta el gastado para decidir `LIMIT_EXCEEDED`
   localmente antes de rechazar, y no crea el pago. El requisito del spec ("Presupuesto
   insuficiente… sin crear el pago") se cumple tal como está. Cambio propuesto: ninguno; solo
   corregir la expectativa del equipo (el chequeo consume una lectura del gastado).
2. **Ruta inconsistente en el log por request.** Esperaba una ruta uniforme; pasó `/payments` en
   respuestas exitosas y `/v1/payments` en errores que salen por `next(err)` (Express 5 restaura
   la URL al propagar el error). Cambio propuesto: registrar `req.originalUrl` en el log
   (observabilidad menor, fuera de esta unidad).
3. **Sin comisión en la quote de la Test Wallet.** Esperaba (por los ejemplos del contrato) un
   `debitAmount` mayor que `receiveAmount`; pasó igualdad (costo 0,00). El contrato no exige
   comisión, así que no hay cambio; solo sirve para la demo: el costo hablado puede ser 0.
