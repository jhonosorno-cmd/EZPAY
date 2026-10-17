# web

Web app (Frontend). Spec: `openspec/changes/add-voice-web-client/`. Contrato: B (solo habla con `/api`).

Vite + React + TypeScript. Pruebas con Vitest.

## Cómo correrlo

```bash
npm install                 # en la raíz: Prism (mock oficial del Contrato B)
cd web && npm install && cp .env.example .env
npm test                    # pruebas
npm run typecheck
```

Hay dos mocks del Contrato B, los dos en `:8000` (CONV-5). Se usa uno a la vez:

| Mock | Comando | Para qué |
|---|---|---|
| **Prism** (oficial, `openapi/contract-b.yaml`) | `npm run mock:prism` + `npm run dev:prism` | Ver cada estado y error **tal como lo define el contrato**. Sin estado: el panel 🧪 elige qué ejemplo devuelve la próxima petición (`Prefer`) |
| **Propio** (`mock/server.ts`) | `npm run mock` + `npm run dev` | Recorrer el flujo completo con estado: presupuesto, PIN, wallet falsa, exceso, pago pendiente, registro de voz |

Solo Prism valida contra el contrato: rechaza cualquier request que no cumpla el YAML. El mock propio
imita las respuestas del contrato, pero no valida. Antes de dar algo por hecho, se prueba también
contra Prism. Cuando el backend Python esté en `:8000`, se apaga el mock y no cambia nada más.

Los tipos de `src/api/` salen del contrato: si cambia `openapi/contract-b.yaml`, correr
`npm run gen:api` y `npm run typecheck`. TypeScript avisa dónde hay que ajustar el frontend.

## Guion del mock propio

| Qué hacer | Qué pasa |
|---|---|
| Escribir "envíale 20 mil a laura hija" sin presupuesto | Pide ir a la billetera (wallet falsa con Aprobar / Rechazar) |
| Comando escrito | Siempre pide PIN (`1234`); tres errores → `REJECTED` |
| Comando por voz | Cualquier audio se toma como "envíale veinte mil a laura hija"; en confirmación, como "sí" |
| "laura" sin "hija" / "vecina" | Elección de destinatario |
| Monto mayor a lo que queda ("300 mil") | Confirmación de exceso → billetera → recibo |
| "lento" en el comando | `PAYMENT_PENDING` y verificación automática (`kind=verify_pending`) a los 20 s |
| "error audio" / "error raro" | `400 INVALID_AUDIO` / código desconocido |
| "Registrar mi voz" | Consentimiento, tres frases (mínimo 3 s), revisar, repetir o usar, y `POST /api/enrollment` |

Reiniciar el mock: `curl 127.0.0.1:8000/mock/reset`.

**Pregunta abierta a Pagos:** el contrato no define qué devuelve `GET /api/budget` sin presupuesto.
El mock propio responde `404`; el frontend trata cualquier error o estado distinto de `ACTIVE` como
"sin presupuesto".

## Estructura

| Ruta | Qué hay |
|---|---|
| `src/api/` | Tipos generados desde `openapi/contract-b.yaml` y cliente (`X-Request-Id`, errores por `code`, catálogo en español) |
| `src/useConversation.ts` | Máquina de estados de la pantalla según `TurnResponse.state` |
| `src/screens/` | Conversación y `/grant-callback` |
| `src/enrollment/` | Registro de voz: flujo (reducer probado), pantalla y textos provisionales de ML 2 |
| `src/components/` | Micrófono push-to-talk, teclado de PIN, recibo, comando por texto |
| `src/voice/` | TTS (`speechSynthesis`) y grabación (`MediaRecorder`, tope de 15 s, nada se guarda) |
| `src/lib/` | Montos sin `number` (CONV-1), sesión en `sessionStorage`, lectura del callback |
| `mock/` | Mock del Contrato B (no es el backend real) |

Contrato vigente: v1 más v1.1 (ratificado el 16 de octubre). Lo marcado `x-proposed` en el YAML
(`kind=verify_pending`, forma de `GET /api/enrollment`) puede cambiar.

Pendiente: textos definitivos del consentimiento y de las frases (ML 2, `src/enrollment/content.ts`).
