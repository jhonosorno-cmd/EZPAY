## Why

El rol Voz (ML 1) convierte lo que dice la usuaria en una intención estructurada que el motor de
decisión de ML 2 consume. Este delta se ajusta para describir lo ya decidido y lo ya implementado,
sin reabrir lo ratificado por el equipo el 16 de octubre (v1.1).

- La conversión de montos en es-CO sin float (V-01) está implementada y probada
  (`api/voice/amounts.py`, `api/voice/RESULTADOS.md`).
- La forma de la intención que ML 2 recibe quedó decidida con ML 2, ML 1 y Pagos el 16 de octubre
  (`openspec/changes/add-decision-engine/design.md`, "El contexto de entrada").
- Los límites de privacidad de la voz están ratificados: audio en memoria, proveedor externo solo
  con consentimiento y sin audios en el repo (PRIV-1, PRIV-2), con el consentimiento único del
  enrolamiento (opción B, `verificacion-ml2/textos-enrolamiento.md`).

## What Changes

- Cinco capabilities nuevas que describen el comportamiento observable del pipeline de voz:
  - La extracción de intención es **solo con reglas** en el MVP (decisión de Sebastián,
    2026-10-16; `api/voice/intents.py` es sin LLM, sin red). El respaldo con LLM queda como
    requisito condicional **[PARA DECIDIR]**, no como parte del MVP.
  - Cada pipeline entrega un puntaje de confianza (`transcriptConfidence`, `intentConfidence`,
    `number | null`); en H1 ambos valen `null` y los cortes del motor están desactivados
    (decisión 3b del 16 oct, `docs/decisiones.md`; `add-decision-engine/design.md`, regla 2b).
- El turno automático de `PAYMENT_PENDING` (B-2, ratificado) se identifica por
    `kind=verify_pending` más `sessionId`, sin `audio` ni `text` (el campo sigue `x-proposed` en
    `openapi/contract-b.yaml`, ya enviado por la web): **[DECIDIDO por Voz, 2026-10-16;
    ratificación del Contrato B pendiente del equipo]**. Dueño de la propuesta: Sebastián;
    dueño del contrato: Pagos.
  - Los errores de `/turns` de B-3 y la elección por `text` con el `alias` de B-4 ya están
    ratificados: dejan de marcarse "cambio de contrato".
  - Antes del "sí" el confirm dice solo `receiveAmount` y nombre; el costo (`débito − recibido`,
    con enteros) se dice después de `COMPLETED` (B-6, ratificado).
- Los cambios a `docs/` (catálogo de `say` §7, extracción solo con reglas, frases de desarrollo
  §D) se proponen al equipo como texto actual → texto propuesto; este delta no los modifica.
- Quedan fuera: enrolamiento, verificación de hablante, validación del PIN y motor de decisión
  (ML 2), Node y Open Payments (Pagos), y la interfaz (Frontend).
- Sin código en este cambio: describe lo implementado en `api/voice/` (H1) y lo que falta para
  H2 (`transcribe`).

## Capabilities

### New Capabilities

- `speech-transcription`: audio a texto en español, en memoria, con proveedor externo solo con
  consentimiento, filtro local y previo de no-habla, puntaje de confianza y manejo de entradas
  inválidas.
- `intent-extraction`: texto a intención con esquema cerrado, solo con reglas determinísticas en
  el MVP; si el equipo activara un respaldo con LLM, su salida se trataría como no confiable
  **[PARA DECIDIR]**.
- `amount-parsing`: texto hablado o escrito a `Amount` (es-CO) y formato de montos para voz y pantalla.
- `contact-resolution`: destinatario hablado a contacto de la agenda, sin adivinar.
- `reply-classification`: respuesta del usuario a `YES`, `NO` o `UNCLEAR`, de forma determinística.

### Modified Capabilities

Ninguna: `openspec/specs/` sigue vacío.

## Impact

- ML 2: el motor consume `{action, amount, amountError, recipient, status}` (la forma `to_dict()`
  de `api/voice/intents.py`, con los nombres del `context` de `add-decision-engine/design.md`),
  las respuestas `YES/NO/UNCLEAR` de `reply-classification` y los puntajes de la regla 2b.
- Pagos: el esqueleto integra `transcribe` en H2, mapea los resultados de la validación de audio
  a los códigos B-3 (`INVALID_AUDIO`, `AUDIO_TOO_LONG`, `AUDIO_OR_TEXT_REQUIRED`) y mantiene el
  estado de la conversación (intención pendiente, `options`, `quoteId`).
- Frontend: manda la elección de destinatario como `text` con el `alias` (B-4) y un único turno de
  verificación con `kind=verify_pending` a los ~20 s de `PAYMENT_PENDING` (B-2).
- Contratos: vigente v1 + v1.1. Pendiente de ratificación del equipo que afecta a estos specs: el
  campo `kind=verify_pending` (decidido por Voz el 16 oct; propuesta: Sebastián; contrato: Pagos)
  y la lista cerrada de afirmativos (D5, `contrato-voz.md` §8).
