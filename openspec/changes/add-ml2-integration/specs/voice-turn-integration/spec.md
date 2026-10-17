# Spec Delta — voice-turn-integration

## Purpose

Fachada de ML 2 para el orquestador de Pagos (unidad 7, aún inexistente; el esqueleto de la unidad
5 NO integra `api/decision`, `api/pin`, `api/speaker` ni `api/voice`): el orquestador solo llama
funciones de ML 2 y **no conoce SpeechBrain, umbrales, recortes ni las reglas del desafío**. La
fachada convierte el audio del comando en `context.voice`, la respuesta al desafío en
`context.confirmation`, conecta el enrolamiento web del Contrato B con `api/speaker/` y falla
cerrado: sin modelo, sin huella, timeout o excepción ⇒ `NOT_AVAILABLE`, nunca `VERIFIED`.


## ADDED Requirements

### Requirement: Fachada de ML 2 para el orquestador

ML 2 SHALL exponer en `api/` una fachada **sin estado** (sin HTTP y sin sesión) que encapsule toda
la verificación y el enrolamiento: el orquestador MUST NOT importar SpeechBrain ni leer umbrales,
recortes ni reglas del desafío. La fachada SHALL ofrecer: voz del comando, `confirmation` del
desafío, elección del modo, frase siguiente del desafío, estado y borrado del enrolamiento. Todo lo
que dependa del turno le llega como datos; lo que produce lo devuelve como valores.

#### Scenario: El orquestador no importa el modelo

- **GIVEN** el orquestador de la unidad 7
- **WHEN** usa la fachada de ML 2 en un turno de comando
- **THEN** no importa `speechbrain` ni `speaker.verification`, ni conoce `umbral`, `trim_silence` ni el banco de frases
- **AND** recibe el `context.voice` y la `confirmation` listos para el `context`
- **AND** la fachada no guarda nada entre turnos: todo vive en la sesión del orquestador

### Requirement: Del audio del comando a context.voice

La fachada SHALL convertir el audio del comando en `context.voice` con el decoder de Voz
(`AvDecoder`, ya existe) y `SpeakerVerifier.verify`: la verificación corre en paralelo con
`transcribe` (el orquestador lanza ambas y espera las dos). El resultado MUST ser exactamente
`{"status", "score"}`. Con `enrolled == false` la fachada devuelve `NOT_AVAILABLE` sin llamar al
modelo. El audio ya llega validado por B-3 (≤ 30 s), que se comprueba antes de decodificar.

#### Scenario: Comando por voz

- **GIVEN** un comando con `audio` de un usuario enrolado
- **WHEN** el orquestador pide el `context.voice` a la fachada y `transcribe` en paralelo
- **THEN** recibe `{"status", "score"}` de `SpeakerVerifier.verify` sin conocer el modelo ni el umbral
- **AND** la verificación y la transcripción corren en paralelo (latencia ≈ la más lenta de las dos)

### Requirement: De la respuesta al desafío a context.confirmation

Para la respuesta al desafío, la fachada SHALL armar la `confirmation` completa que espera el
motor: `mode`, `phraseScore` con `phrase_match` de Voz (`null` si no hubo respuesta por voz),
`voice` con `verify` sobre el audio de la respuesta (en paralelo con `transcribe`) y
`challengeAttempts` de la sesión. El corte lo aplica el motor; la fachada solo mide. Con modo
`REPLY` la fachada SHALL armar `confirmation` con `mode: "REPLY"` (o omitirla) y no verifica nada.

#### Scenario: Respuesta al desafío

- **GIVEN** una respuesta por voz a la frase pedida, con la frase guardada en la sesión
- **WHEN** el orquestador pide la `confirmation` a la fachada
- **THEN** recibe `{mode, phraseScore, voice, challengeAttempts}` con las claves camelCase del issue #12, listo para el `context`
- **AND** `phraseScore` es el número de `phrase_match` (no el booleano) y `voice` es `verify` del audio de la respuesta

### Requirement: Elección del modo y frase del desafío

La fachada SHALL elegir `CHALLENGE` solo si `config.confirmationChallenge` está activa, la decisión
`ASK_CONFIRM` viene directo de la fase `COMMAND` (no de la fase PIN) y
`context.voice.status == "VERIFIED"`; en cualquier otro caso, `REPLY` **[DECIDIDO 2026-10-17,**
**Daniel]**. Sin estado, la fachada SHALL recibir las frases ya usadas y devolver la nueva
(`pick_phrase`: al azar, nunca el LLM, sin repetir) más la lista de usadas actualizada; el
orquestador lo guarda en su sesión.

#### Scenario: Pago que pasó por PIN

- **GIVEN** `config.confirmationChallenge == true` y un pago que pasó por PIN (texto, voz no verificada, destinatario nuevo o monto alto)
- **WHEN** la fachada elige el modo de la confirmación
- **THEN** el modo es `REPLY`: el PIN ya es el segundo factor y no hay ciclos de PIN
- **AND** también es `REPLY` si la confirmación viene de la fase PIN (un pago que ya pasó por PIN se confirma con "sí")

#### Scenario: Frases sin repetir, sin estado

- **GIVEN** una confirmación que repite el desafío (`challengeAttempts == 1`) y las frases ya usadas, guardadas en la sesión del orquestador
- **WHEN** la fachada recibe esas frases y pide la siguiente con `pick_phrase`
- **THEN** devuelve otra frase del banco, distinta de la usada, más la lista de usadas actualizada
- **AND** el orquestador guarda ambas en su sesión (la fachada no conserva nada entre turnos)

### Requirement: say_situation en fase COMMAND con modo CHALLENGE

Para que el `say` de la confirmación pida la frase (`CONFIRM_CHALLENGE` /
`CONFIRM_CHALLENGE_OVERRUN`), la fachada SHALL armar para fase `COMMAND` el mismo `context` con
`confirmation = {mode: "CHALLENGE", phraseScore: null, voice: null, challengeAttempts: 0}` cuando el
modo elegido sea `CHALLENGE`: `say_situation` elige la situación del
desafío; sin `confirmation` sale `CONFIRM`/`AUTH_OVERRUN` ("sí" como hoy). La frase queda
en la sesión del orquestador, no en la fachada.

#### Scenario: Pregunta de confirmación con frase

- **GIVEN** una decisión `ASK_CONFIRM` en fase `COMMAND` con modo `CHALLENGE` elegido
- **WHEN** el orquestador llama `say_situation(decision, context_con_confirmation)`
- **THEN** la situación es `CONFIRM_CHALLENGE` (o `CONFIRM_CHALLENGE_OVERRUN` con exceso) y el `say` lleva la frase elegida como `{frase}`
- **AND** sin `confirmation` la situación es `CONFIRM`/`AUTH_OVERRUN` (modo `REPLY`, "sí" como hoy)

### Requirement: Fallos cerrados y presupuesto de tiempo

Toda falla de la fachada SHALL ser fail-closed: excepción, timeout, modelo sin cargar, huella
ausente o audio ilegible ⇒ `NOT_AVAILABLE` (y `phraseScore` `null` sin transcripción),
nunca `VERIFIED`; el motor cae al PIN (SEG-6). El paralelo `transcribe + verify` SHALL caber en
2 s; vencidos, la fachada devuelve `NOT_AVAILABLE` **[DECIDIDO 2026-10-17, Daniel]**.

#### Scenario: Modelo caído a mitad del turno

- **GIVEN** el modelo ECAPA falló durante la verificación de la respuesta al desafío
- **WHEN** el orquestador pide la `confirmation`
- **THEN** `confirmation.voice` es `{"status": "NOT_AVAILABLE", "score": null}` (sin excepción) y `phraseScore` sale de la transcripción si existe
- **AND** el motor pide PIN (`CHALLENGE_VOICE_NOT_VERIFIED`); nunca se paga sin checks

#### Scenario: Verificación que se pasa del tiempo

- **GIVEN** una verificación en curso que tarda más de 2 s (CPU cargada) y llega otro turno que pide verificar
- **WHEN** vencen los 2 s del primero y el segundo pide su turno
- **THEN** la fachada devuelve `NOT_AVAILABLE` para el primero sin cancelarlo (el modelo sigue ocupado)
- **AND** no lanza la segunda mientras la primera corra: la segunda también responde `NOT_AVAILABLE` (el motor cae al PIN las dos veces)

Notas:

- En Python la verificación vencida NO se cancela: el modelo sigue ocupado y, por el candado (una
verificación a la vez), la siguiente espera. La fachada SHALL NOT lanzar otra verificación mientras
la anterior siga corriendo, y esa nueva también devuelve `NOT_AVAILABLE`.
- Latencias medidas en H2 (x0_entorno): embed + coseno 0,16–0,47 s con 3–10 s de audio; con Groq la
transcripción tarda ~1 s, así que el paralelo cabe en los 2 s con margen (y en `TURN_BUDGET_S = 8`).

### Requirement: Enrolamiento web (Contrato B)

La fachada SHALL conectar `POST /api/enrollment` (B-5) con `SpeakerEnrollment.enroll`: decodifica
las 3 partes `audio` con el decoder de Voz y llama `enroll(muestras, consent)`;
`EnrollmentError` SHALL mapearse 1 a 1 a los 400 del contrato con los códigos de B-5 en orden
(mensaje = código, B-5/B-7). `GET /api/enrollment` SHALL responder `status()` (`{"enrolled": bool}`, cuerpo hoy `x-proposed`). El
borrado sigue siendo `scripts/delete_voiceprint.py` (PRIV-3) y retira `consentExterno`.

#### Scenario: Enrolamiento aceptado y rechazado

- **GIVEN** tres muestras válidas con `consent=true` (o una muestra corta, para el rechazo)
- **WHEN** la ruta llama la fachada
- **THEN** `201 {"enrolled": true}` guarda solo la huella promedio (o `400` con el código del error, en el orden B-5, sin datos biométricos)
- **AND** `GET /api/enrollment` responde `{"enrolled": bool}` y `consent_external()` alimenta la consulta de Voz

### Requirement: Reparto con Pagos

ML 2 SHALL entregar la fachada y sus pruebas; el orquestador (unidad 7) mantiene TODO el estado de
sesión (frases usadas, frase pedida, `challengeAttempts`), las llamadas a Node, el mapeo de
`Decision` a `TurnState` y los logs sin cuerpos del request. La frase del desafío para mostrarla en
la web necesita un campo nuevo
en `TurnResponse` (`challengePhrase`): propuesta aceptada por ML 2 **[DECIDIDO 2026-10-17,**
**Daniel]**, pendiente del OK de Pagos y Frontend (dueños del contrato).

#### Scenario: Reparto en un turno de comando

- **GIVEN** un turno de comando por voz
- **WHEN** la unidad 7 lo procesa
- **THEN** ML 2 entrega `context.voice` y la situación del `say`; la unidad 7 arma el `context`, decide, mapea el estado y habla con Node
- **AND** ningún archivo de ML 2 abre HTTP ni guarda estado de sesión de la web

### Requirement: Privacidad en la integración

La fachada y sus pruebas MUST NOT escribir audio, embeddings, transcripciones ni puntajes en logs,
`error.message` ni disco: en disco solo la huella (`huella.npy`) y `consent.json` bajo
`EZPAY_SPEAKER_DATA_DIR` (fuera de git, PRIV-1). Los mensajes de log SHALL ser fijos y sin datos
del request (PRIV-4). Las pruebas usan audio sintético o falso: nunca voces reales en el repo
público (AGENTS.md).

#### Scenario: Logs de la fachada

- **GIVEN** un turno de comando y uno de desafío, con éxito o con error
- **WHEN** se revisan los logs y `error.message` de la fachada
- **THEN** no aparecen audio, embeddings, transcripciones ni puntajes; solo eventos fijos con `requestId`
- **AND** el disco solo acumula `huella.npy` y `consent.json` (PRIV-1)
