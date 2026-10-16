# Contratos OpenAPI y mocks

Descripción máquina-legible de los contratos HTTP del equipo (v1 más v1.1, ratificado el 16 de
octubre). La fuente de verdad sigue siendo `docs/contratos-http-v1.md` y
`docs/contratos-cambios-propuestos-v1.1.md`; si este directorio y esos documentos chocan, gana el
documento y se corrige el YAML.

| Archivo | Contrato | Mock (puerto) | Quién lo usa |
|---|---|---|---|
| `contract-a.yaml` | A: Python → Node, rutas `/v1/...` | `npm run mock:a` (4000) | Python (cliente de Node, motor, orquestador) |
| `contract-b.yaml` | B: Frontend → Python, rutas `/api/...` | `npm run mock:b` (8000) | Frontend |
| `components.yaml` | Tipos comunes (`Amount`) | — | Ambos |

Los puertos son los de CONV-5. Cada mock responde en las mismas URLs que el servicio real
(`http://localhost:4000/v1/health`, `http://localhost:8000/api/budget`), así que cuando llegue el
servicio real solo se apaga el mock.

## Uso

```bash
npm install            # una vez
npm run mock:a         # Contrato A en 127.0.0.1:4000
npm run mock:b         # Contrato B en 127.0.0.1:8000
npm run lint:openapi   # valida los dos YAML
npm run test:mocks     # levanta los mocks y verifica cada ejemplo (puertos 14000 y 18000)
```

Sin cabeceras, Prism devuelve la primera respuesta de éxito. Para pedir otra, usá `Prefer`:

```bash
# Un exceso de límite en la quote
curl -X POST localhost:4000/v1/quotes -H 'content-type: application/json' \
  -H 'Prefer: code=201, example=exceeds-remaining' \
  -d '{"grantId":"g_abc","receiver":"https://ilp.interledger-test.dev/laura","receiveAmount":{"value":"2000000","assetCode":"COP","assetScale":2}}'

# El turno de PIN del Contrato B
curl -X POST localhost:8000/api/turns -F text=1234 -H 'Prefer: code=200, example=awaiting-pin'
```

### Ejemplos disponibles

- **Contrato A:** cada error de la tabla de códigos tiene un ejemplo con el nombre del código en
  kebab-case (`limit-exceeded`, `quote-expired`, `grant-invalid`, `payment-in-progress`,
  `idempotency-key-reused`, `upstream-error`...). Los éxitos tienen `within-budget` /
  `exceeds-remaining` (quote), `completed` / `processing` / `failed` (pagos) y `active` / `pending` /
  `rejected` / `expired` (grants).
- **Contrato B, `/turns`:** un ejemplo por estado: `awaiting-command`, `awaiting-confirmation`,
  `awaiting-pin`, `awaiting-pin-retry`, `awaiting-recipient-choice`, `awaiting-authorization`,
  `payment-pending`, `completed`, `rejected`. Errores: `audio-or-text-required`, `invalid-audio`,
  `audio-too-long` (400) y `session-not-found` (404).

## Qué es propuesto y qué está ratificado

Lo ratificado el 16 de octubre lleva `x-contract-change` (A-1, A-3, B-1, B-3, B-5...). Lo que
**todavía no aprobó el equipo** lleva `x-proposed: true` y puede cambiar:

- `kind=verify_pending` en `POST /api/turns` (decisión D-1 del 16 de octubre: choque entre B-2 y B-3).
  El turno automático de `PAYMENT_PENDING` lleva `sessionId` y `kind`, sin `audio` ni `text`, y
  `AUDIO_OR_TEXT_REQUIRED` sigue valiendo para cualquier otro request vacío.
- Forma de la respuesta de `GET /api/enrollment`: `{ enrolled: boolean }` (B-5 no define el cuerpo).
- Errores `INVALID_AMOUNT` y `UPSTREAM_ERROR` en `POST /api/budget`, derivados de CONV-2 y del
  Contrato A.

`DELETE /v1/grants/{id}` (A-1) está en el contrato; si el experimento del vencimiento semanal
muestra que no hace falta, se quita en una unidad aparte.

## Límites del mock (esperaba X, pasó Y, cambio Z)

| Esperaba | Pasó | Cambio |
|---|---|---|
| Que `POST /v1/payments` sin `Idempotency-Key` devolviera `400 IDEMPOTENCY_KEY_REQUIRED` | Prism contesta los requests inválidos con el `422` del spec, o sea `IDEMPOTENCY_KEY_REUSED` | El mock solo garantiza que el request se rechaza; el código `400` se pide con `Prefer: code=400, example=idempotency-key-required`. El servicio real responde `400`. |
| `audio` como arreglo de tres archivos en `POST /api/enrollment` | Prism solo lee la última parte de un campo multipart repetido y rechaza el arreglo | `audio` se describe como un campo binario que se envía tres veces. La regla "tres muestras" (`SAMPLES_REQUIRED`) es del servicio, no del esquema. |
| Que el prefijo `/v1` o `/api` viniera de `servers.url` | Prism lo ignora y monta las rutas en la raíz | El prefijo está en cada ruta (`/v1/grants`, `/api/turns`) y `servers.url` es solo el host. |
| Que `consent: boolean` rechazara `consent=false` | Con `boolean`, Prism acepta `false` y contesta `201` | `consent` es `string` con `enum: ['true']`: cualquier otro valor se rechaza con `400 CONSENT_REQUIRED`. |
