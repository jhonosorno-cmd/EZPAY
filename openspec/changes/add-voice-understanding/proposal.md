## Why

El rol Voz (ML 1) convierte lo que dice la usuaria en una intención estructurada que el motor de
decisión de ML 2 consume. Hoy ese comportamiento no está especificado: el Spec general solo lo
nombra en la ficha de rol (§7) y en SEG-3 y SEG-4, y los Contratos fijan los montos y los errores
entre servicios, pero no cómo se entiende un comando hablado. Sin un spec, tres cosas quedan al azar:

- La conversión de montos en es-CO. La función `toAmount` de `m0-ej3-toAmount.ts` lee "20.000" como
  20,00 COP, 1000 veces menos (revisión V-01).
- La forma de la intención que ML 2 recibe, y quién clasifica el "sí" que autoriza cada pago
  (revisión V-02 y V-04).
- Los límites de privacidad de la voz: audio solo en memoria, a un proveedor externo solo con consentimiento, sin grabaciones de
  prueba en el repo público (revisión V-08, V-09 y V-19).

Detalle y evidencia: la revisión del rol Voz del 13 de octubre (espacio de trabajo previo).

## What Changes

- Cinco capabilities nuevas que describen el comportamiento observable del pipeline de voz.
- Ningún requisito común cambia. Los cambios propuestos a `add-team-baseline`, al Spec general y a
  los Contratos están en la revisión (sección "Cambios propuestos a documentos del equipo") y
  necesitan el OK de los cuatro.
- Varios requisitos de este cambio **dependen de esas decisiones del equipo** y no deben archivarse
  antes:
  - D3: formato es-CO de montos y jerga (`amount-parsing`).
  - D4: esquema cerrado de la intención (`intent-extraction`).
  - D5: clasificación del "sí/no" y definición de "destinatario nuevo" (`reply-classification`,
    `contact-resolution`).
  - D6: errores de `/turns` y elección de destinatario por `text` (`speech-transcription`,
    `contact-resolution`). **Cambio de contrato.**
  - D1 y C-3: audio a un proveedor externo solo con consentimiento y respaldo local (`speech-transcription`).
- Quedan fuera: enrolamiento, verificación de hablante, validación del PIN y motor de decisión (ML 2),
  Node y Open Payments (Pagos), y la interfaz (Frontend).
- Sin código: es un cambio solo de specs.

## Capabilities

### New Capabilities

- `speech-transcription`: audio a texto en español, en memoria, con proveedor externo solo con consentimiento, con manejo de silencio
  y de entradas inválidas.
- `intent-extraction`: texto a intención con esquema cerrado, tratando la salida del LLM como no
  confiable.
- `amount-parsing`: texto hablado o escrito a `Amount` (es-CO) y formato de montos para voz y pantalla.
- `contact-resolution`: destinatario hablado a contacto de la agenda, sin adivinar.
- `reply-classification`: respuesta del usuario a `YES`, `NO` o `UNCLEAR`, de forma determinística.

### Modified Capabilities

Ninguna: `openspec/specs/` está vacío. Las modificaciones a `payment-safety`, `voice-privacy` y
`service-conventions` se proponen en la revisión (C-10) y se incorporan al archivar `add-team-baseline`.

## Impact

- ML 2: el motor de decisión consume `{action, amount, recipient, status}` y las respuestas
  `YES/NO/UNCLEAR` de este cambio.
- Pagos: el esqueleto FastAPI importa estas capacidades desde H2 y mantiene el estado de la
  conversación (intención pendiente, `options`, `quoteId`).
- Frontend: empieza a grabar solo cuando termina el TTS y devuelve la elección de destinatario como
  `text` con el `alias`.
- Contratos HTTP v1: ver D6. Hasta que el equipo decida, estos requisitos se escriben como propuesta.
