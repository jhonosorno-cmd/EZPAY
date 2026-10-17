# Spec Delta — speaker-verification

## Purpose

Verificación de hablante con SpeechBrain para el pago por voz: dadas la voz del comando y la huella
del usuario, decide si el hablante es el usuario y produce el `context.voice` que consume el motor
(`decision-engine`). La voz es una verificación adicional, no la barrera principal: si una
grabación del usuario pasa como `VERIFIED`, con destinatario conocido y dentro del presupuesto el
motor NO pide PIN — contra una grabación protegen el tope del grant de presupuesto (SEG-1/SEG-5),
el "sí" hablado (SEG-2) y `highAmountThreshold` (SEG-6, 100.000 COP decididos en X-4,
2026-10-17). El PIN protege
cuando la voz no se verifica (D3). Todo corre en Python dentro del backend, no en un servicio
aparte.

## ADDED Requirements

### Requirement: Verificación como funciones del backend

El rol SHALL exponer la verificación como funciones Python dentro del backend (sin servicio
aparte): `embed(pcm) -> embedding` y `verify(pcm, user) -> {status: "VERIFIED" | "BELOW_THRESHOLD" | "NOT_AVAILABLE", score: number | null}`, con el modelo
`speechbrain/spkrec-ecapa-voxceleb` (ECAPA, ~85 MB) en CPU (SpeechBrain 1.1.2). `verify` SHALL
producir exactamente el `context.voice` que espera el motor: con `VERIFIED`/`BELOW_THRESHOLD` el
`score` es el coseno y con `NOT_AVAILABLE` es `null`.

#### Scenario: La salida es el context.voice del motor

- **GIVEN** un comando de voz y una huella enrolada
- **WHEN** se llama `verify(pcm, user)`
- **THEN** devuelve `{status, score}` con los valores exactos que el motor espera en `context.voice` (`decision-engine`)

#### Scenario: Presupuesto de latencia

- **GIVEN** el backend con el modelo ECAPA cargado en CPU
- **WHEN** se verifica la voz de un comando de hasta 10 s
- **THEN** responde en menos de 1 s (**[DECIDIDO 2026-10-17]**, x0_entorno: mediana 0,16 s con 3 s de audio, 0,28 s con 5 s y 0,47 s con 10 s)
- **AND** un comando de 30 s tarda ~1,5 s: dato documentado, no requisito

### Requirement: Carga del modelo al arrancar

El modelo ECAPA SHALL cargarse una sola vez al iniciar el backend, no en la primera petición. Si
la carga falla, toda verificación SHALL devolver `status: "NOT_AVAILABLE"` con `score: null` y el
arranque SHALL dejar un aviso en el log sin datos biométricos (PRIV-4). Cargó sin red en 0,3 s
con 383 MB de RAM (x0_entorno, 16 oct; **[DECIDIDO 2026-10-17]**).

#### Scenario: Primer comando sin espera de carga

- **GIVEN** el backend ya arrancado con el modelo en memoria
- **WHEN** llega el primer comando de voz
- **THEN** la verificación responde de inmediato: no hay carga perezosa ni espera en la primera petición

#### Scenario: Modelo que no carga ⇒ NOT_AVAILABLE

- **GIVEN** un arranque en el que la carga del modelo falló
- **WHEN** se llama `verify` con cualquier comando
- **THEN** devuelve `NOT_AVAILABLE` con `score: null` (nunca `VERIFIED`)
- **AND** el arranque dejó un aviso en el log sin datos biométricos (PRIV-4)

### Requirement: Entrada de audio normalizada

`verify` y `embed` SHALL recibir PCM float32 16 kHz mono ya decodificado (lo decodifica Voz,
`contrato-voz` §4) y pasarlo por el mismo recorte de silencios que el enrolamiento: el umbral se
midió con audio recortado (experimentos ML 2, 15 oct). `verify` y `embed` MUST NOT procesar más de
30 s de audio: si reciben más (B-3 ya lo rechaza antes, `AUDIO_TOO_LONG`), MUST devolver
`NOT_AVAILABLE` sin cargar el audio en el modelo (defensa en profundidad), no recortarlo.

#### Scenario: Audio de más de 30 s

- **GIVEN** un `verify`/`embed` que recibe más de 30 s de audio (no debería pasar: B-3 ya rechaza esos comandos con `AUDIO_TOO_LONG` leyendo la duración de la cabecera, antes de decodificar)
- **WHEN** se procesa
- **THEN** devuelve `NOT_AVAILABLE` sin cargar el audio en el modelo (defensa en profundidad, SEG-6); no se recorta
- **AND** el motor pide PIN

### Requirement: Recorte de silencios fijado

Enrolamiento y verificación SHALL usar exactamente la función `trim_silence` del script de
calibración de ML 2 con que se calibró el umbral 0.45: ventanas de 320 muestras (20 ms a 16 kHz) y
0,25 s de margen a cada lado (experimentos ML 2, 15 oct). Cambiar la función o sus parámetros MUST
ir acompañado de una recalibración del umbral de verificación y del corte de consistencia.

#### Scenario: Mismo recorte en enrolamiento y verificación

- **GIVEN** un audio con silencios al inicio y al final
- **WHEN** se procesa en enrolamiento y en verificación
- **THEN** ambos caminos usan exactamente `trim_silence` con ventanas de 320 muestras (20 ms a 16 kHz) y 0,25 s de margen (el umbral vale para audio recortado así)

#### Scenario: Cambiar el recorte exige recalibrar

- **GIVEN** un cambio de `trim_silence` (ventanas o margen)
- **WHEN** se procesa audio
- **THEN** no es válido sin recalibrar el umbral de verificación y el corte de consistencia (H3)

### Requirement: Decisión por umbral configurable

La similitud SHALL medirse como coseno entre el embedding del comando y la huella del usuario, y
compararse contra un umbral configurable. El valor provisional MUST ser 0.45, sesgado contra
falsos aceptados (D6): con 0.45 hubo 0 % de aceptación ajena; el 0.25 por defecto aceptó a otra
persona en 28,9 % de clips cortos (experimentos ML 2, 15 oct). Recalibración en H3. La comparación
SHALL ser en el borde: `score >= umbral` ⇒ `VERIFIED` y `score < umbral` ⇒ `BELOW_THRESHOLD`.

#### Scenario: Misma persona pasa el umbral

- **GIVEN** la voz del usuario enrolado (genuino mínimo 0.508 con la huella promedio — experimentos ML 2, 17 oct, 3 personas; rangos 0.57–0.73 del 15 oct)
- **WHEN** se verifica con umbral 0.45
- **THEN** `status` es `VERIFIED` con su `score`

#### Scenario: En el borde (score == 0.45)

- **GIVEN** un comando con similitud coseno exactamente 0.45 (igual al umbral)
- **WHEN** se verifica
- **THEN** `status` es `VERIFIED`: `score >= umbral` incluye el borde

#### Scenario: Otra persona no pasa el umbral

- **GIVEN** la voz de otra persona (impostor máximo 0.405 con la huella promedio — experimentos ML 2, 17 oct, 3 personas)
- **WHEN** se verifica con umbral 0.45
- **THEN** `status` es `BELOW_THRESHOLD` con su `score`
- **AND** el motor pide PIN (regla 7, SEG-6/D3)

#### Scenario: Clip demasiado corto

- **GIVEN** un comando cuya voz útil (tras recortar silencios) dura menos de `minVerifySeconds` (configurable; **2,0 s** **[DECIDIDO 2026-10-17]**: 1,0 s ⇒ 11 falsos rechazados, 1,5 s ⇒ 4, 2,0/2,5/3,0 s ⇒ 0 falsos aceptados y 0 falsos rechazados — experimentos ML 2, 17 oct, 3 personas)
- **WHEN** se verifica
- **THEN** `verify` devuelve `NOT_AVAILABLE`: no hay audio suficiente para decidir (NO `BELOW_THRESHOLD`, que significaría "otra persona")
- **AND** el motor pide PIN
- **AND** D4: la verificación corre solo sobre el comando, nunca sobre el "sí"

Nota (experimentos ML 2, 17 oct, 3 personas; **[DECIDIDO 2026-10-17]**): el umbral se mantiene en
**0.45** — queda entre el impostor máximo 0.405 y el genuino mínimo 0.508 (con la huella promedio,
estrategia A); a 0.55 hubo 3 falsos rechazados. Sigue configurable y se recalibra en H3 con el
micrófono de solapa. Riesgo: el margen (+0.104) es pequeño y la muestra es de 3 personas — repetir
el experimento con más personas queda en los puntos abiertos del story.

### Requirement: Una verificación a la vez

El acceso al modelo SHALL serializarse con un candado: una verificación a la vez; las peticiones
en paralelo SHALL esperar su turno y responder. El candado evita multiplicar la RAM (medido: 4
peticiones de 30 s en paralelo usaron 1,85 GB — experimentos ML 2, 15 oct).

#### Scenario: Dos peticiones simultáneas

- **GIVEN** dos verificaciones que llegan a la vez
- **WHEN** se procesan
- **THEN** ambas responden, una tras otra (una a la vez), y la RAM no crece como con cuatro en paralelo

### Requirement: Fallo cerrado

`verify` SHALL devolver `status: "NOT_AVAILABLE"` con `score: null` cuando no hay voz que comparar:
usuario sin huella, audio corto (`minVerifySeconds`), más de 30 s, error interno o modelo sin
cargar; nunca `VERIFIED` en esos casos (falla cerrada, SEG-6). El motor pide PIN cuando la voz no
se verifica (D3).

#### Scenario: Usuario no enrolado

- **GIVEN** un usuario sin huella
- **WHEN** se llama `verify`
- **THEN** `status` es `NOT_AVAILABLE` con `score: null` y el motor pide PIN (`turn-orchestration` "Usuario no enrolado")

#### Scenario: Error interno del modelo

- **GIVEN** un fallo interno del modelo o del proceso
- **WHEN** se llama `verify`
- **THEN** `status` es `NOT_AVAILABLE` con `score: null` (nunca `VERIFIED`) y el motor pide PIN

### Requirement: Privacidad del dato biométrico

El componente MUST NOT guardar audio crudo: solo embeddings (PRIV-1). Ni audio, ni embeddings, ni
puntajes SHALL aparecer en logs ni en `error.message` (PRIV-4). La huella SHALL poder borrarse por
script (PRIV-3): tras borrar, `verify` trata al usuario como no enrolado. El modelo MUST cargar sin
internet (pesos en caché local) **[DECIDIDO 2026-10-17]** (x0_entorno, 16 oct).

#### Scenario: Solo se guardan embeddings

- **GIVEN** una verificación o un enrolamiento
- **WHEN** se revisan la base de datos, los archivos temporales y los logs
- **THEN** no queda audio crudo en ninguno (PRIV-1)

#### Scenario: Nada biométrico en los logs

- **GIVEN** cualquier verificación, enrolamiento o error
- **WHEN** se revisan los logs y `error.message`
- **THEN** no aparecen audio, embeddings ni puntajes (PRIV-4)

#### Scenario: Borrado de la huella

- **GIVEN** una huella enrolada
- **WHEN** se corre el script de borrado (PRIV-3)
- **THEN** la huella deja de existir y `verify` devuelve `NOT_AVAILABLE` (usuario tratado como no enrolado)
- **AND** se retira también el consentimiento del proveedor externo (consentimiento único, opción B): Voz consulta `consentExterno == false`

#### Scenario: Carga sin internet

- **GIVEN** una máquina sin acceso a internet
- **WHEN** el backend arranca
- **THEN** el modelo carga desde la caché local de pesos (x0_entorno, 16 oct: sin red en 0,3 s, 383 MB de RAM)

### Requirement: Fuera de alcance: anti-spoofing

H2 MUST NOT incluir anti-spoofing (X-4): una grabación del usuario podría pasar la verificación.
Es un riesgo conocido y documentado: contra una grabación protegen el tope del grant de
presupuesto (SEG-1/SEG-5), el "sí" hablado (SEG-2) y `highAmountThreshold` (SEG-6, valor de X-4);
el motor NO pide PIN si pasa con destinatario conocido y dentro del presupuesto (evidencia:
experimentos ML 2, 17 oct — 1 de 3 reproducciones desde el celular pasó como `VERIFIED` con la
huella promedio).

#### Scenario: Riesgo documentado

- **GIVEN** un atacante con una grabación del usuario, destinatario conocido y presupuesto suficiente
- **WHEN** se verifica y la grabación pasa como `VERIFIED`
- **THEN** el motor NO pide PIN: la decisión sale de las reglas restantes
- **AND** contra la grabación protegen el tope del grant de presupuesto (SEG-1/SEG-5), el "sí" hablado (SEG-2) y `highAmountThreshold` (SEG-6, 100.000 COP — X-4, 2026-10-17)
- **AND** evidencia: de 3 reproducciones desde el celular, 1 pasó (coseno 0.506; los otros 0.338 y 0.417) — experimentos ML 2, 17 oct, 3 personas
- **AND** es un riesgo conocido y documentado (X-4, fuera de alcance en H2)
