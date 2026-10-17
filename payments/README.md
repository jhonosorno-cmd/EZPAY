# payments

Microservicio Node/TS que concentra todo Open Payments (Pagos). Implementa el **Contrato A v1**
(`docs/contratos-http-v1.md`) más los cambios del equipo ya incluidos en el spec
(`INVALID_AMOUNT`, `PAYMENT_IN_PROGRESS`, `IDEMPOTENCY_KEY_REUSED`, `INTERNAL_ERROR`).
Spec: `openspec/changes/add-payments-service/`.

## Correr

```bash
cd payments
npm install
cp .env.example .env      # completar WALLET_ADDRESS, KEY_ID, PRIVATE_KEY_PATH, DB_ENCRYPTION_KEY
npm start                 # escucha en 127.0.0.1:4000
npm test                  # pruebas (sin red: Open Payments simulado)
npm run typecheck
npm run reset-db          # borra la base antes de la demo
```

Requiere Node >= 24 (`node:sqlite`). Llave de cifrado: `openssl rand -base64 32`.
La llave privada de la wallet vive **fuera del repo**; solo se versiona `.env.example`.

## Estructura

| Ruta | Rol |
|---|---|
| `src/http/` | Rutas, formato de error, `requestId`, log JSON por request |
| `src/domain/service.ts` | Reglas: grants, quotes, presupuesto, idempotencia |
| `src/op/adapter.ts` | **Único** módulo que importa `@interledger/open-payments` |
| `src/store/db.ts` | **Único** módulo que toca `node:sqlite`; tokens cifrados con AES-256-GCM |
| `src/ports.ts` | Interfaz `OpenPaymentsPort` (las pruebas usan un falso) |

## Pendiente de verificar contra la Test Wallet

- `cancelGrant` hoy revoca el token vía la `manage` URL (`token.revoke`); confirmar que alcanza.
- URL de `getGrantSpentAmounts` (`<resourceServer>/outgoing-payments`); si falla se usa el gastado local.
- Cómo responde la wallet cuando el usuario rechaza (E3): hoy 401/403/400/404 en `continue` → `GRANT_REJECTED`.
- `token.rotate` y su comportamiento con un token ya vencido (E4).
- El caché de tokens no interactivos está en memoria (no en SQLite como sugiere D3).
