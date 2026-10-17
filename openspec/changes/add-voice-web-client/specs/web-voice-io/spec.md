# Spec Delta — web-voice-io

## Purpose

Entrada y salida de voz en el navegador. El navegador graba y reproduce; no transcribe, no verifica la
voz y no detecta silencio: eso lo hace Python (ML 1, `speech-transcription`; ML 2, verificación).
Origen: Contratos HTTP v1 (TTS del navegador, `[DECIDIDO]`), PRIV-1, SEG-2, y los pedidos de ML 1
(V-08, V-13, X-4) y ML 2 (X-1, X-2).

## ADDED Requirements

### Requirement: Grabación con botón (push-to-talk)
La web app SHALL grabar solo mientras la usuaria mantiene presionado el botón de hablar (o la barra espaciadora), con `MediaRecorder` y el formato por defecto del navegador. Al soltar, envía el audio en el campo `audio` de `POST /api/turns` como archivo con una extensión que coincida con su tipo (por ejemplo, `comando.webm` para `audio/webm`).

#### Scenario: Comando grabado
- **WHEN** la usuaria mantiene presionado el botón, dice "envíale veinte mil a mi hija" y suelta
- **THEN** sale un `POST /api/turns` multipart con un único campo `audio`
- **AND** el nombre del archivo tiene la extensión del tipo grabado

#### Scenario: Toque accidental
- **WHEN** la usuaria suelta el botón antes de 0,5 s
- **THEN** no se envía nada y la pantalla pide mantenerlo presionado

### Requirement: Tope de duración
La web app SHALL cortar la grabación a los 15 s y enviar lo grabado hasta ese momento. El servidor tiene su propio tope (ML 2 propone 30 s y ML 1 el error `AUDIO_TOO_LONG`); el del navegador evita llegar a él.

#### Scenario: Comando demasiado largo
- **WHEN** la usuaria sigue hablando con el botón presionado durante 20 s
- **THEN** la grabación se corta a los 15 s y se envía

### Requirement: El audio no se guarda en el navegador (PRIV-1)
El audio grabado SHALL existir solo en memoria hasta que se envía. MUST NOT guardarse en `localStorage`, `sessionStorage`, IndexedDB, caché ni descargas, ni escribirse en la consola. En el push-to-talk de la conversación, entre grabaciones la web app SHALL mantener el micrófono abierto con las pistas desactivadas (no capta audio) y SHALL detener todas las pistas al salir de la pantalla o cuando la pestaña se oculta. En el enrolamiento (tocar para empezar y parar) SHALL detener todas las pistas al terminar cada grabación.

> Esperaba que abrir el micrófono en cada pulsación no costara nada; pasó que `getUserMedia` tardaba lo suficiente para perder la primera palabra ("envíale" llegaba a Groq como "20 mil pesos a Laura" y no se entendía). Cambio: en la conversación el micrófono queda abierto y silenciado entre grabaciones; el indicador del navegador permanece encendido mientras la pantalla está visible. Prueba en la sala del 17 de octubre.

#### Scenario: Después de enviar
- **WHEN** se envía un comando grabado y se revisa el almacenamiento del navegador
- **THEN** no hay audio guardado
- **AND** las pistas del micrófono están desactivadas y no captan audio

#### Scenario: Al salir de la pantalla o al ocultar la pestaña
- **GIVEN** el micrófono quedó abierto entre grabaciones
- **WHEN** la usuaria sale de la pantalla o la pestaña se oculta
- **THEN** se detienen todas las pistas y el indicador de micrófono del navegador se apaga
- **AND** la siguiente grabación vuelve a pedir el micrófono

#### Scenario: Segunda grabación sin perder el principio
- **GIVEN** la usuaria ya grabó un comando en esta pantalla
- **WHEN** presiona de nuevo el botón de hablar
- **THEN** la web app reutiliza el micrófono abierto y no llama otra vez a `getUserMedia`

#### Scenario: Enrolamiento
- **WHEN** termina la grabación de una muestra de enrolamiento
- **THEN** se detienen todas las pistas y el indicador de micrófono del navegador está apagado

### Requirement: Nunca grabar mientras habla el TTS
La web app MUST NOT grabar mientras el TTS está hablando, para que el micrófono no capte la pregunta del sistema (ML 1 V-13: el eco "¿Le envío 20.000 a Laura?" se clasificaría como respuesta). Si la usuaria presiona el botón de hablar mientras el TTS habla, la web app SHALL cancelar el TTS y empezar a grabar después.

#### Scenario: Botón durante el TTS
- **WHEN** el TTS está leyendo el `say` y la usuaria presiona el botón de hablar
- **THEN** el TTS se calla antes de que empiece la grabación

### Requirement: Lectura del say con el TTS del navegador
La web app SHALL leer cada `say` con `speechSynthesis`, con una voz en español elegida en este orden: `es-CO`, `es-419`, `es-MX`, `es-US`, cualquier `es-*`. Las voces cargan de forma asíncrona, así que la elección se hace después del evento `voiceschanged`. Si no hay ninguna voz en español, el `say` se muestra solo como texto.

#### Scenario: Elección de voz
- **WHEN** el navegador ofrece `es-ES` y `es-MX`
- **THEN** el `say` se lee con la voz `es-MX`

#### Scenario: Monto hablado
- **WHEN** el TTS lee "¿Le envío 20.000 pesos a Laura?"
- **THEN** se oye "veinte mil" (se verifica en la laptop de la demo, ML 1 F-4)

### Requirement: Desbloqueo del audio por un gesto
Los navegadores bloquean `speechSynthesis` hasta que hay un gesto de la usuaria. Cuando la página carga (también al volver de la wallet), la web app SHALL mostrar un botón grande "Continuar" y leer el `say` pendiente al tocarlo.

#### Scenario: Vuelta de la wallet
- **WHEN** la página se recarga en `/grant-callback` con un `TurnResponse` listo
- **THEN** se muestra el botón "Continuar"
- **AND** el `say` se lee después de tocarlo

### Requirement: Permiso del micrófono
Si el navegador niega el micrófono, la web app SHALL decirlo en pantalla y dejar el campo de texto como camino alterno (con PIN, capability `web-conversation`). La web app SHALL correr en un contexto seguro: `localhost` en la laptop de la demo.

#### Scenario: Micrófono denegado
- **WHEN** la usuaria rechaza el permiso del micrófono
- **THEN** la pantalla explica cómo activarlo y ofrece escribir el comando

### Requirement: La grabación empieza cuando el navegador lo confirma
La web app SHALL mostrar "Habla ahora" solo después del evento `onstart` del `MediaRecorder` y SHALL medir la duración de la grabación (`durationMs`) desde `onstart` hasta `onstop`. Mientras se abre el micrófono SHALL mostrar "Preparando el micrófono…" con el botón deshabilitado. Al llegar `onstart` SHALL emitir una señal corta (vibración si existe; si no, un tono de Web Audio de 60 ms o menos y de volumen bajo). En modo desarrollo SHALL registrar en consola los milisegundos entre el toque y `onstart`, sin ningún dato de audio.

#### Scenario: Micrófono abriéndose
- **GIVEN** la usuaria tocó "Iniciar grabación"
- **WHEN** el navegador todavía no emitió `onstart`
- **THEN** se muestra "Preparando el micrófono…" con el botón deshabilitado
- **AND** no se muestra "Habla ahora"

#### Scenario: El navegador confirma
- **GIVEN** el micrófono se está abriendo
- **WHEN** el `MediaRecorder` emite `onstart`
- **THEN** se muestra "Habla ahora" y suena (o vibra) una señal corta

#### Scenario: La duración no incluye el retraso
- **GIVEN** el micrófono tardó 400 ms en abrir
- **WHEN** la usuaria habla 3 s y detiene la grabación
- **THEN** `durationMs` es de unos 3 000 ms, no de 3 400 ms

#### Scenario: Soltar antes de que empiece
- **GIVEN** la usuaria mantiene presionado el botón de hablar y el micrófono se está abriendo
- **WHEN** suelta antes de `onstart`
- **THEN** no se envía audio
- **AND** las pistas quedan desactivadas (se detienen si el micrófono no se mantiene abierto)

#### Scenario: Medición en desarrollo
- **GIVEN** la web app corre en modo desarrollo
- **WHEN** llega `onstart`
- **THEN** la consola muestra el retraso en ms y ningún dato de audio
