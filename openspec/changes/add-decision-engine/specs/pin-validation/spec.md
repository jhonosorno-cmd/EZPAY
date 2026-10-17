# Spec Delta — pin-validation

## Purpose

Componente del PIN mínimo (D5) dentro del backend Python. Verifica el PIN, lleva los contadores de
intentos (de sesión y global) y protege el dato: el PIN nunca sale de Python, nunca pasa por el
LLM, el parser, el clasificador ni Whisper, y nunca va a logs ni a `error.message`. El motor de
decisión NO valida el PIN: recibe el resultado en `context.pin`. El PIN se **suma** a la
confirmación hablada, no la reemplaza (SEG-2).

## ADDED Requirements

### Requirement: Alta por configuración, nunca en claro

El PIN SHALL darse de alta solo por configuración: hash con sal generado con un KDF lento de la
librería estándar (`hashlib.scrypt`; alternativa `hashlib.pbkdf2_hmac`). El PIN MUST NOT existir en
claro en el código, el repo, la configuración ni los logs. MUST NOT existir un endpoint HTTP de
alta. Un script genera el hash con sal y lo imprime para copiarlo a `.env`.

#### Scenario: Alta del PIN

- **GIVEN** un PIN nuevo de 4 a 6 dígitos
- **WHEN** se corre el script de alta
- **THEN** en `.env` queda solo el hash con sal y los parámetros del KDF
- **AND** no existe ningún endpoint de alta y el PIN en claro no aparece en ningún archivo del repo

#### Scenario: Variables documentadas sin valores

- **WHEN** se revisa el repo
- **THEN** `api/.env.example` lista los nombres de las variables del PIN (hash, sal y parámetros del KDF) sin valores reales (CONV-4)

#### Scenario: Sin PIN configurado

- **GIVEN** el backend arranca sin las variables del PIN en `.env`
- **WHEN** llega un turno en `AWAITING_PIN`
- **THEN** `verify_pin` nunca devuelve `OK` (falla cerrado) y el arranque registra un aviso sin datos sensibles

### Requirement: Formato y comparación en tiempo constante

El componente SHALL aceptar PINes de 4 a 6 dígitos ASCII (0-9); un formato inválido, incluidos los
dígitos Unicode de otros alfabetos, se rechaza sin comparar.
La comparación SHALL hacerse en tiempo constante (`hmac.compare_digest` sobre los derivados) para
que el tiempo de respuesta no revele información del PIN.

#### Scenario: Formato inválido

- **GIVEN** un valor con símbolos, letras o fuera del rango de 4 a 6 dígitos
- **WHEN** se pasa a `verify_pin`
- **THEN** se rechaza con `result: "INVALID_FORMAT"`, sin invocar el KDF ni comparar hashes
- **AND** no altera los contadores de intentos **[DECIDIDO]** (2026-10-16): es entrada inválida, no intento

#### Scenario: Dígitos de otros alfabetos

- **GIVEN** un valor con dígitos Unicode no ASCII, como "٢٣٤٥" o "²³⁴⁵"
- **WHEN** se pasa a `verify_pin`
- **THEN** se rechaza con `result: "INVALID_FORMAT"` sin invocar el KDF

#### Scenario: Comparación en tiempo constante

- **GIVEN** el hash configurado y un PIN enviado
- **WHEN** el componente compara
- **THEN** usa `hmac.compare_digest` y el tiempo de respuesta no depende de cuántos dígitos coinciden

### Requirement: Contadores de intentos
El componente de PIN SHALL llevar los contadores: al tercer fallo de la sesión reporta `sessionFailures >= 3` (el motor decide `REJECT`); con 5 fallos seguidos en total marca `locked: true` hasta el script de reinicio y MUST NOT validar más intentos; un PIN correcto reinicia el contador global. En H1 el contador global vive en la memoria del proceso (limitación conocida).

#### Scenario: Reinicio del backend en H1

- **GIVEN** 3 fallos globales acumulados y el backend corriendo
- **WHEN** el backend se reinicia (por ejemplo, en un despliegue)
- **THEN** el contador global vuelve a 0 y un bloqueo activo se pierde
- **AND** en H1 el bloqueo por 5 fallos solo vale mientras el proceso vive; la persistencia queda **[DIFERIDA A H2]**

#### Scenario: Tercer fallo de la sesión

- **GIVEN** dos intentos fallidos en la sesión (`sessionFailures == 2`)
- **WHEN** la usuaria envía otro PIN incorrecto
- **THEN** el componente reporta `result: "WRONG"`, `sessionFailures: 3`, `remaining: 0`, `locked: false`
- **AND** el orquestador responde `REJECTED` y no paga (SEG-6)

#### Scenario: Sesión agotada no vuelve a validar

- **GIVEN** una sesión con `sessionFailures >= 3`
- **WHEN** llega el PIN correcto con el mismo `session_id`
- **THEN** el componente reporta `result: "WRONG"` y `remaining: 0`, sin invocar el KDF ni mover contadores (defensa en profundidad)

#### Scenario: Intentos concurrentes

- **GIVEN** varias peticiones de PIN incorrecto al mismo tiempo
- **WHEN** el componente las procesa
- **THEN** los contadores no pierden fallos: exactamente 5 fallos globales activan el bloqueo y nunca se devuelve un `OK` espurio

#### Scenario: Bloqueo global

- **GIVEN** 4 fallos consecutivos acumulados entre sesiones
- **WHEN** ocurre un quinto fallo consecutivo
- **THEN** el componente marca `locked: true`
- **AND** los intentos siguientes no se validan hasta reiniciar el bloqueo

#### Scenario: Script de reinicio

- **GIVEN** el PIN bloqueado
- **WHEN** se corre el script de reinicio
- **THEN** el bloqueo se levanta y el contador global vuelve a 0

#### Scenario: PIN correcto reinicia el contador global

- **GIVEN** 2 fallos globales acumulados
- **WHEN** la usuaria envía el PIN correcto
- **THEN** el componente reporta `result: "OK"` y el contador global vuelve a 0

### Requirement: Privacidad del PIN
El PIN MUST NOT decirse en voz alta, pasar por el LLM, el parser, la extracción de intención, el clasificador ni Whisper, ir a logs ni a `error.message`, ni salir del backend Python. En un turno de PIN, `transcript` SHALL ser `null` y el `say` MUST NOT contener ni repetir dígitos del PIN. Detalle en `design.md`.

#### Scenario: El PIN no sale de Python

- **WHEN** la usuaria envía el PIN
- **THEN** no sale ninguna llamada con el PIN fuera del backend Python (ni a Node ni a servicios externos)
- **AND** la validación la hace el componente de PIN dentro del backend

#### Scenario: El PIN no pasa por voz ni por el LLM

- **GIVEN** el turno en `AWAITING_PIN`
- **WHEN** la usuaria envía el PIN como `text`
- **THEN** el texto no pasa por `transcribe`, `extract_intent` ni `classify_reply`
- **AND** si llega `audio` en `AWAITING_PIN`, el orquestador lo descarta sin transcribirlo (`turn-orchestration`)

#### Scenario: Respuesta sin ecos del PIN

- **GIVEN** la respuesta a un turno de PIN (correcto o incorrecto)
- **WHEN** se inspecciona el `TurnResponse`
- **THEN** `transcript` es `null`
- **AND** el `say` no contiene ningún dígito del PIN ni lo repite

#### Scenario: Logs y errores sin el PIN

- **GIVEN** un turno de PIN cuando ocurre una excepción
- **WHEN** se generan la respuesta de error y sus logs
- **THEN** el PIN no aparece ni en `error.message` ni en ninguna línea de log (PRIV-4)

### Requirement: Interfaz del componente
El componente SHALL exponer `verify_pin(pin, session_id) -> PinResult` y `reset_pin_lock()`. El resultado llega al motor vía `context.pin`; el motor MUST NOT validar el PIN ni acceder al hash. Los tipos están en `design.md`.

#### Scenario: El motor solo recibe el resultado

- **GIVEN** un turno en `AWAITING_PIN`
- **WHEN** el componente verifica el PIN
- **THEN** el orquestador arma `context.pin` con el resultado y el motor decide solo con eso
- **AND** el motor no llama a `verify_pin` ni accede al hash ni a la configuración del PIN

### Requirement: Entrada del PIN hasta H3

Hasta que exista el teclado (H3), el PIN llega en el campo `text` de `POST /turns` cuando el turno
está en `AWAITING_PIN`. Un `text` de solo dígitos (4 a 6) recibido **fuera** de `AWAITING_PIN`
(incluida una sesión desconocida o perdida) MUST NOT llegar al componente de PIN ni a la extracción
de intención: el orquestador lo filtra y responde `AWAITING_COMMAND` (`turn-orchestration`,
"Dígitos fuera de `AWAITING_PIN`").

#### Scenario: PIN por campo de texto

- **GIVEN** el turno en `AWAITING_PIN` en H1 (sin teclado)
- **WHEN** la usuaria envía su PIN en el campo `text`
- **THEN** el componente de PIN lo verifica y el resultado queda en `context.pin`
- **AND** el texto no pasa por ningún componente de voz ni por el LLM

#### Scenario: Dígitos fuera de AWAITING_PIN

- **GIVEN** una sesión desconocida o un turno que no espera PIN
- **WHEN** llega `text` de 4 a 6 dígitos
- **THEN** el componente de PIN no lo recibe
- **AND** el turno responde `AWAITING_COMMAND` (decisión `REASK`)
