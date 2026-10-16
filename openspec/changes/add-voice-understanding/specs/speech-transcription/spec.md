# Spec Delta — speech-transcription

## Purpose

Convertir el audio de un comando en texto en español, sin guardarlo, enviándolo a un proveedor externo solo
con consentimiento y sin que el silencio o el ruido se confundan con una respuesta. Origen: Spec general §5
(PRIV-1, PRIV-4), §4 (SEG-2), la revisión del rol Voz del 13 de octubre (espacio de trabajo previo) (V-08, V-09, V-12, V-19) y
`voz-ml1/experimentos/x1-whisper-comparacion.md`. Los requisitos que dependen de decisiones del equipo (D1, D6)
están marcados.

## ADDED Requirements

### Requirement: El audio se decodifica y se procesa solo en memoria
El sistema SHALL decodificar el audio recibido a PCM en memoria, una sola vez por turno, y entregar el mismo buffer a la transcripción y a la verificación de hablante. El audio MUST NOT escribirse en disco, ni siquiera como archivo temporal.

#### Scenario: Comando de voz procesado
- **WHEN** se procesa un comando de voz y luego se revisan los archivos temporales y la base de datos
- **THEN** no existe ningún archivo de audio

#### Scenario: Un solo decodificado por turno
- **WHEN** un turno con audio pasa por transcripción y por verificación de hablante
- **THEN** el audio se decodifica una sola vez
- **AND** ambos consumidores reciben el mismo buffer

### Requirement: Audio a un proveedor externo solo con consentimiento
El sistema SHALL enviar el audio a un proveedor de transcripción externo únicamente si el usuario dio consentimiento explícito para ello en el enrolamiento (PRIV-2). Sin ese consentimiento, o si el proveedor no responde en su plazo, MUST transcribir localmente. El proveedor MUST NOT recibir embeddings de voz. Depende de la decisión D1 (actualizada) y del cambio C-3 propuestos al equipo.

#### Scenario: Usuario con consentimiento
- **WHEN** el usuario dio consentimiento y se procesa un comando de voz
- **THEN** el audio se envía al proveedor configurado
- **AND** la transcripción vuelve en el plazo del turno

#### Scenario: Usuario sin consentimiento
- **WHEN** el usuario no dio consentimiento para el proveedor externo y se procesa un comando de voz
- **THEN** el audio se transcribe localmente
- **AND** no se hace ninguna conexión saliente con el audio

#### Scenario: El proveedor falla
- **WHEN** el proveedor externo supera su plazo o devuelve un error
- **THEN** el sistema transcribe el mismo audio localmente
- **AND** el turno no falla por eso

### Requirement: La llave del proveedor no se versiona ni se registra
La llave de acceso al proveedor externo SHALL leerse solo de una variable de entorno o de `.env` (CONV-4). MUST NOT aparecer en el repositorio, en los logs ni en los prompts.

#### Scenario: Revisión de logs y repositorio
- **WHEN** se revisan los archivos versionados y los logs después de transcribir con el proveedor
- **THEN** no aparece la llave

### Requirement: Transcripción en español
El sistema SHALL transcribir el audio indicando el idioma español, sin detección automática de idioma.

#### Scenario: Comando en español colombiano
- **WHEN** se transcribe el audio "envíale veinte mil a mi hija"
- **THEN** el resultado es el texto de la frase en español

### Requirement: El silencio y el ruido no son una respuesta
El sistema SHALL decidir si el audio contiene habla antes de transcribirlo, con un filtro propio que no dependa del motor. Si no hay habla (silencio, ruido de sala o duración menor a la mínima), la transcripción MUST ser vacía y la respuesta MUST tratarse como `UNCLEAR`.

#### Scenario: Audio en silencio
- **WHEN** llega el audio de 4 segundos sin voz
- **THEN** no se envía al motor de transcripción
- **AND** la transcripción es vacía y el turno se trata como `UNCLEAR`

#### Scenario: Ruido de sala
- **WHEN** llega un audio con ruido de sala y sin voz
- **THEN** la transcripción es vacía
- **AND** no se ejecuta ningún pago

#### Scenario: El motor inventa texto
- **WHEN** el filtro detecta que no hay habla pero el motor, de usarse, devolvería "Gracias." o "¡Suscríbete!" (texto que motores locales y de API inventaron sobre silencio el 2026-10-15)
- **THEN** el resultado sigue siendo una transcripción vacía

### Requirement: El filtro de no-habla es local y previo
El filtro de no-habla SHALL ejecutarse en la máquina del backend antes de enviar el audio a cualquier motor, y MUST NOT depender de las métricas de confianza del proveedor. Un audio sin habla MUST NOT enviarse al proveedor externo.

#### Scenario: Silencio con proveedor externo
- **WHEN** llega un audio sin habla y el proveedor externo está activo
- **THEN** no se hace ninguna llamada al proveedor
- **AND** el turno se trata como `UNCLEAR`

#### Scenario: Respuesta corta de una sílaba
- **WHEN** llega el audio de un "no" de poco más de un segundo
- **THEN** el filtro lo deja pasar a la transcripción

### Requirement: El vocabulario guía no se usa sin filtro previo
Si se usa un texto guía con los nombres de la agenda (parámetro `prompt` o `initial_prompt`), MUST aplicarse solo a audios que ya pasaron el filtro de no-habla, y la transcripción MUST validarse igual contra la agenda.

#### Scenario: Silencio con vocabulario guía
- **WHEN** un audio sin habla llegara al motor junto con un texto guía que contiene "Laura"
- **THEN** el filtro previo ya lo descartó
- **AND** la respuesta nunca contiene un nombre de la agenda por efecto del texto guía

### Requirement: El límite de uso del proveedor no tumba el turno
Si el proveedor responde con límite de uso excedido (HTTP 429), el sistema SHALL respetar `retry-after` solo si cabe en el plazo del turno; en caso contrario MUST transcribir localmente el mismo audio. El plazo del turno lo fija el equipo.

#### Scenario: Límite excedido
- **WHEN** el proveedor responde 429 con un `retry-after` mayor al plazo restante del turno
- **THEN** el sistema transcribe localmente el mismo audio
- **AND** el usuario no ve ningún error

### Requirement: Entradas de audio inválidas
Un `POST /turns` con audio vacío, ilegible o en formato no soportado SHALL responder `400 INVALID_AUDIO`; con un audio más largo que 30 s, `400 AUDIO_TOO_LONG`; la duración se lee de la cabecera **antes** de decodificar. El tope sale de la medición de ML 2 (la memoria crece ~10 MB por segundo de audio) y el navegador corta antes, a los 15 s. **Cambio de contrato** (D6): no está en el Contrato B de hoy.

#### Scenario: Audio ilegible
- **WHEN** llega un `POST /turns` con bytes que no son audio
- **THEN** responde `400 INVALID_AUDIO` con el cuerpo `{ error: { code, message } }`

#### Scenario: Audio demasiado largo
- **WHEN** llega un audio de 60 s
- **THEN** responde `400 AUDIO_TOO_LONG` leyendo solo la cabecera
- **AND** no se decodifica ni se transcribe

### Requirement: Entrada de texto o de audio, no ambas ni ninguna
Un `POST /turns` SHALL traer exactamente uno de `audio` o `text`. Si trae los dos o ninguno, MUST responder `400 AUDIO_OR_TEXT_REQUIRED`, con una sola excepción: si la sesión está en `PAYMENT_PENDING`, un `POST /turns` con `sessionId` y sin `audio` ni `text` es el turno de verificación del pago pendiente y MUST aceptarse (propuesta de Pagos D-2; el Frontend lo pidió como F-1). **Cambio de contrato** (D6).

#### Scenario: Ambos campos
- **WHEN** llega un `POST /turns` con `audio` y `text`
- **THEN** responde `400 AUDIO_OR_TEXT_REQUIRED`

#### Scenario: Ninguno
- **WHEN** llega un `POST /turns` sin `audio` ni `text` y la sesión no está en `PAYMENT_PENDING`
- **THEN** responde `400 AUDIO_OR_TEXT_REQUIRED`

#### Scenario: Verificación de un pago pendiente
- **WHEN** llega un `POST /turns` con `sessionId` de una sesión en `PAYMENT_PENDING` y sin `audio` ni `text`
- **THEN** se acepta como turno de verificación
- **AND** no responde `AUDIO_OR_TEXT_REQUIRED`

### Requirement: La transcripción no se guarda en logs
Los logs MUST NOT contener la transcripción completa ni el audio. La transcripción SHALL viajar solo en la respuesta (`transcript`) para mostrarse en pantalla. Cada línea de log MUST llevar el `X-Request-Id`.

#### Scenario: Revisión de logs después de un comando
- **WHEN** se procesa un comando de voz y se revisan los logs del backend
- **THEN** no aparece la transcripción completa
- **AND** cada línea tiene el `X-Request-Id` de la acción
