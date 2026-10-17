# Textos del enrolamiento de voz (ML 2)

Textos definitivos de ML 2 para la pantalla de registro de voz (`web/src/enrollment/content.ts`,
`add-voice-web-client` tasks.md 1.2). Decididos el 2026-10-16.

## Decisión: un solo consentimiento (opción B)

El consentimiento del registro cubre las dos finalidades: la huella de voz y el envío del audio de
las órdenes a un servicio externo de transcripción (`speech-transcription`: «Audio a un proveedor
externo solo con consentimiento», dado en el enrolamiento). No cambia el Contrato B: el mismo
`consent=true` de `POST /api/enrollment` vale para ambas. Quien acepta y se registra queda con el
consentimiento del proveedor externo; quien no acepta no registra su voz y envía con su PIN.

Opciones descartadas: una segunda casilla con un campo nuevo en `POST /enrollment` (cambio de
contrato) y quitar el proveedor externo del MVP (decisión de Voz).

## Textos

```ts
// Texto del consentimiento y frases del enrolamiento — definitivos de ML 2 (tasks.md 1.2 de add-voice-web-client).
export const CONSENT_TITLE = "Antes de registrar tu voz"
export const CONSENT_POINTS = [
  "Tu voz es un dato biométrico sensible y está protegida por la Ley 1581 de 2012.",
  "La usamos solo para comprobar que eres tú cuando pides un envío.",
  "Para entender lo que dices, el audio de tus órdenes puede enviarse a un servicio externo que lo convierte en texto.",
  "Registrarla es opcional: si no aceptas, puedes enviar dinero con tu PIN.",
  "No guardamos tus grabaciones: solo una huella numérica de tu voz.",
  "Puedes pedir que la borremos cuando quieras.",
]
export const CONSENT_CHECK = "Acepto que EZPAY registre mi huella de voz y envíe el audio de mis órdenes a un servicio externo para estos fines."
export const PHRASES = [
  "Hola, quiero registrar mi voz para enviar dinero de forma segura.",
  "Cada semana le mando plata a mi familia desde mi celular.",
  "Confirmo que esta es mi voz y que la uso para mis pagos.",
]
```

## Criterios

| Criterio | Cómo se cumple |
|---|---|
| PRIV-2 (dato sensible, para qué se usa, cómo se borra) | Puntos 1, 2 y 6 |
| Ley 1581, art. 6: autorizar datos sensibles no es obligatorio | Punto 4, con la alternativa real: sin huella, el motor pide PIN |
| Proveedor externo solo con consentimiento | Punto 3 y la casilla |
| PRIV-1 (no se guarda audio crudo) | Punto 5 |
| Frases de 4 a 8 s (la calibración usó muestras de 4,8 a 8,5 s; bajo 3 s los puntajes bajan) | 11 a 13 palabras cotidianas cada una |
| La usuaria oye la frase y la repite (no lee bien la pantalla) | Palabras comunes, sin números, nombres propios ni trabalenguas |

No se afirma que el servicio externo no guarde el audio porque no está verificado.

## Pendiente

- Medir la duración real de las tres frases dichas por una persona mayor con el micrófono de
  solapa (H3) y recalibrar el umbral 0.45 con estas frases.
