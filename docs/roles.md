# Roles

**[PROPUESTA]** Fichas de rol acordadas en el espacio de trabajo previo (13 de octubre). Quién
ocupa cada rol está en el `README.md`.

| | Pagos (Node + Open Payments) | Frontend | Voz (ML 1) | Verificación y calidad (ML 2) |
|---|---|---|---|---|
| **Misión** | Todo lo que toca Open Payments, con los secretos dentro de Node | Una interfaz mínima que se usa hablando | Convertir lo que se dice en una intención estructurada | Que nada se pague sin las verificaciones del spec, y demostrarlo |
| **Componentes** | Microservicio Node; flujo GNAP; esqueleto FastAPI (rutas del Contrato B, estado de la conversación); cliente de Node en Python (llamadas al Contrato A, `Idempotency-Key`, reautorización ante `exceedsRemaining`/`401`/`403`, polling de pagos); `openapi.yaml` y mocks | Web app; captura de audio; TTS; teclado de PIN; redirección a la wallet y página de callback | Whisper; extracción de intención (LLM → JSON); texto → `Amount` (`TOO_MANY_DECIMALS`); agenda de contactos (SEG-4); batería de frases | SpeechBrain; enrolamiento con consentimiento (`/api/enrollment`, PRIV-2, PRIV-3); validación del PIN; motor de decisión; catálogo de pruebas de aceptación (las ejecuta Frontend) |
| **Decide** | Diseño interno de Node (`openspec/changes/add-payments-service/`) | Framework del frontend | Whisper por API o local; prompt del LLM | Umbrales del motor (similitud, "monto bajo") |
| **Depende de** | Contratos A y B | Mock del Contrato B | Esqueleto FastAPI | Esqueleto FastAPI; intención de ML 1 |
| **Suplente** | ML 2 (y Frontend para el esqueleto FastAPI) | ML 1 | Frontend | Pagos |

**Esqueleto FastAPI** (rutas del Contrato B y estado de la conversación): lo toma **Pagos**
(2026-10-13), que ya es dueño del cliente de Node en Python y de las reglas de reautorización.
Riesgo: H1 se le carga mucho; si se atrasa, **Frontend** es el apoyo (decisión del 16 de octubre).

**Independencia de las pruebas:** ML 2 escribe el motor y también sus pruebas de aceptación. Para
que no se pruebe a sí misma, las pruebas salen de los requisitos SEG/PRIV (no del código) y las

Los entregables por hito están en `docs/spec-general.md` §7.

## Responsabilidades transversales (16 de octubre)

| Tarea | Quién |
|---|---|
| Respaldo del esqueleto FastAPI si se atrasa | Frontend |
| Consolidar `AI_USAGE.md` antes de las 10:45 del sábado (cada uno llena su sección) | Voz (ML 1) |
| Ejecutar las pruebas de aceptación (las escribe ML 2 desde los requisitos) | Frontend |
