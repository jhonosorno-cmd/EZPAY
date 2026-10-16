# Spec Delta — wallet-handoff

## Purpose

Ida a la Test Wallet para autorizar un presupuesto o un exceso, y vuelta por `finishUri`
(`http://localhost:5173/grant-callback`). La autorización ocurre en la wallet, nunca en la web app
(SEG-1; nota de Pagos sobre SEG-1, en el espacio de trabajo previo). La web app solo explica el
paso, lleva a la usuaria y reenvía lo que la wallet devuelve.

## ADDED Requirements

### Requirement: Explicar el paso antes de redirigir
En `AWAITING_AUTHORIZATION`, la web app SHALL leer el `say`, mostrar un botón grande "Ir a mi billetera" y redirigir a `interactUrl` solo cuando la usuaria lo toca. MUST NOT redirigir automáticamente.

#### Scenario: Exceso de presupuesto
- **WHEN** llega `AWAITING_AUTHORIZATION` con `interactUrl` y el `say` "Supera tu presupuesto, ¿lo autorizas en tu billetera?"
- **THEN** la web app lee el `say` y muestra "Ir a mi billetera"
- **AND** el navegador va a `interactUrl` solo después del toque

### Requirement: Autorizar el presupuesto
La pantalla de inicio SHALL ofrecer "Autorizar presupuesto", que envía `POST /api/budget` con un monto predefinido, sin que la usuaria escriba cifras, y lleva a `interactUrl`. El monto y si lleva `interval` dependen de la decisión D-4 del equipo.

#### Scenario: Presupuesto de la demo
- **WHEN** la usuaria toca "Autorizar presupuesto" con el monto de la demo de 200.000 COP
- **THEN** se envía `POST /api/budget` con `debitAmount: { value: "20000000", assetCode: "COP", assetScale: 2 }`
- **AND** con la `interactUrl` de la respuesta se muestra el botón "Ir a mi billetera"

### Requirement: Moneda del presupuesto por configuración
El `assetCode` y el `assetScale` del presupuesto SHALL salir de la configuración de la web app y coincidir con `ASSET_CODE` y `ASSET_SCALE` del backend Python (demo: COP y 2), porque el Contrato B no los expone.

#### Scenario: Configuración de la demo
- **WHEN** la web app arranca con la moneda COP y escala 2
- **THEN** todo `Amount` que construye lleva `assetCode: "COP"` y `assetScale: 2`

### Requirement: Comando sin presupuesto
Si un comando de voz llega sin presupuesto activo, Python responde `AWAITING_AUTHORIZATION` con la `interactUrl` del presupuesto (Pagos, "Sin grant de presupuesto activo"). La web app SHALL tratarlo igual que cualquier otra ida a la wallet.

#### Scenario: Primer comando sin presupuesto
- **WHEN** la usuaria da un comando de pago sin haber autorizado un presupuesto
- **THEN** la web app muestra el botón "Ir a mi billetera" con la `interactUrl` recibida

### Requirement: La sesión sobrevive a la wallet
Antes de redirigir, la web app SHALL guardar en `sessionStorage` el `sessionId` y el motivo de la ida (presupuesto o exceso), porque la página se recarga completa al volver.

#### Scenario: Vuelta con la sesión
- **WHEN** la usuaria vuelve de la wallet a `/grant-callback`
- **THEN** la web app recupera el `sessionId` guardado y lo usa en el siguiente turno

### Requirement: Reenvío completo del callback
La página `/grant-callback` SHALL leer de la URL `interact_ref`, `hash` y `result` (los que vengan) y enviarlos a `POST /api/grant-callback` como `{ interactRef?, hash?, result? }`, sin validarlos ni descartar ninguno. **Cambio de contrato propuesto** (Pagos D-1): el Contrato B hoy solo define `{ interactRef, hash }`. Si faltan `interactRef` o `hash`, igual se envía la petición: Python responde `REJECTED` y descarta el pago pendiente.

#### Scenario: Aprobación
- **WHEN** la wallet redirige a `/grant-callback?interact_ref=abc&hash=xyz`
- **THEN** se envía `POST /api/grant-callback` con `{ interactRef: "abc", hash: "xyz" }`

#### Scenario: Rechazo
- **WHEN** la wallet redirige a `/grant-callback?result=grant_rejected`
- **THEN** se envía `POST /api/grant-callback` con `{ result: "grant_rejected" }`
- **AND** la web app muestra y lee el `say` del `TurnResponse` en `REJECTED`

### Requirement: El callback se usa una sola vez
Después de enviar el callback, la web app SHALL limpiar la URL (`history.replaceState`) para que recargar la página no lo reenvíe. Los valores de `interact_ref` y `hash` MUST NOT escribirse en la consola ni guardarse (PRIV-4).

#### Scenario: Recarga después del callback
- **WHEN** la usuaria recarga la página después de que se envió el callback
- **THEN** no sale un segundo `POST /api/grant-callback`
