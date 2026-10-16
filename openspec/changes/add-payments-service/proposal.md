# Proposal — Microservicio de pagos (Node/TS)

## Why

Todo lo que toca Open Payments (GNAP, firmas HTTP, grants, quotes y pagos) tiene que vivir en un
solo servicio Node/TS, porque el SDK oficial de Python todavía no está terminado (ver PLAN.md §5).
Sin este servicio no hay demo: el hackathon exige mostrar solicitud, autorización, ejecución y
pago completado.

## What Changes

- Nuevo microservicio Node/TS que implementa el lado servidor del **Contrato A**
  (`docs/contratos-http-v1.md`): grants interactivos con límites, quotes,
  pagos idempotentes y consulta de estado.
- Persistencia local en SQLite con los tokens cifrados, para que un reinicio no obligue a volver
  a autorizar en plena demo.
- Cálculo local del presupuesto (`spent` / `remaining`), con tope total o por período.
- Traducción de los errores de Open Payments a los códigos tipados del contrato.
- **Cambio de contrato** (decisión del equipo; afecta a Python): se agregan
  `400 INVALID_AMOUNT`, `409 PAYMENT_IN_PROGRESS`, `422 IDEMPOTENCY_KEY_REUSED` y
  `500 INTERNAL_ERROR`. El cuarto valor del hash pasa a llamarse `grantEndpointUri`.

## Capabilities

### New Capabilities

- `payments-service`: comportamiento observable del microservicio de pagos frente a su único
  cliente (el backend Python), incluyendo sus requisitos de seguridad, resiliencia y
  observabilidad.

### Modified Capabilities

Ninguna (no hay specs previos en `openspec/specs/`).

## Impact

- **API:** Contrato A v1 con cuatro códigos de error nuevos (no son cambios que rompan nada:
  son respuestas adicionales).
- **Dependencias:** `@interledger/open-payments` (SDK oficial) y Express (base preferida:
  `interledger/hackathon-backend-example`; plan B: Express desde cero). Node 24 con
  `node:sqlite` incluido.
- **Sistemas:** Test Wallet de Interledger (`wallet.interledger-test.dev`).
- **Equipo:** el backend Python consume este servicio; el frontend nunca lo ve.
