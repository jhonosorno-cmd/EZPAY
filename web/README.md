# web

Web app (Frontend). Spec: `openspec/changes/add-voice-web-client/`. Contrato: B (solo habla con `/api`).

Vite + React + TypeScript. Pruebas con Vitest.

## Cómo correrlo

```bash
cd web
npm install
cp .env.example .env      # moneda y presupuesto de la demo
npm run mock              # terminal 1: mock del Contrato B en :8000 (mientras no esté Python)
npm run dev               # terminal 2: http://localhost:5173
npm test                  # pruebas
npm run typecheck
```

Cuando el backend Python esté en `:8000`, se apaga el mock y no cambia nada más: Vite redirige `/api`
al mismo puerto (`VITE_API_TARGET`).

## Guion del mock

| Qué hacer | Qué pasa |
|---|---|
| Escribir "envíale 20 mil a laura hija" sin presupuesto | Pide ir a la billetera (wallet falsa con Aprobar / Rechazar) |
| Comando escrito | Siempre pide PIN (`1234`); tres errores → `REJECTED` |
| Comando por voz | Cualquier audio se toma como "envíale veinte mil a laura hija"; en confirmación, como "sí" |
| "laura" sin "hija" / "vecina" | Elección de destinatario |
| Monto mayor a lo que queda ("300 mil") | Confirmación de exceso → billetera → recibo |
| "lento" en el comando | `PAYMENT_PENDING` y verificación automática a los 20 s |
| "error audio" / "error raro" | `400 INVALID_AUDIO` / código desconocido |

Reiniciar el mock: `curl localhost:8000/mock/reset`.

## Estructura

| Ruta | Qué hay |
|---|---|
| `src/api/` | Tipos y cliente del Contrato B (`X-Request-Id`, errores por `code`, catálogo en español) |
| `src/useConversation.ts` | Máquina de estados de la pantalla según `TurnResponse.state` |
| `src/screens/` | Conversación y `/grant-callback` |
| `src/components/` | Micrófono push-to-talk, teclado de PIN, recibo, comando por texto |
| `src/voice/` | TTS (`speechSynthesis`) y grabación (`MediaRecorder`, tope de 15 s, nada se guarda) |
| `src/lib/` | Montos sin `number` (CONV-1), sesión en `sessionStorage`, lectura del callback |
| `mock/` | Mock del Contrato B (no es el backend real) |

Se implementa contra lo propuesto en v1.1 que el spec adopta (`PAYMENT_PENDING`, `result` en el
callback, errores de `/turns`, elección como `alias`). Si el equipo rechaza alguno, se quita.

Pendiente: registro de voz con consentimiento (`enrollment-ui`, H3).
