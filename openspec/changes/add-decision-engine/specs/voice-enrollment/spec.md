# Spec Delta — voice-enrollment

## Purpose

Enrolamiento de voz: crea, consulta y borra la huella del usuario a partir de 3 muestras de audio
con consentimiento explícito. Entrega a `speaker-verification` la huella que usa `verify` y alimenta
la pantalla de registro del frontend (`enrollment-ui`): la web pide el consentimiento, graba las
muestras y decide por `error.code` (CONV-2). Las rutas HTTP (`/api/enrollment`) son del esqueleto
de Pagos; ML 2 entrega las funciones que ellas invocan.

## ADDED Requirements

### Requirement: Tres muestras obligatorias

El enrolamiento SHALL requerir exactamente 3 muestras de audio; un `POST /enrollment` con otra
cantidad MUST responder `400 SAMPLES_REQUIRED` (B-5) y no crear huella. El backend MUST validar de
nuevo y no confiar en la UI.

#### Scenario: Faltan muestras

- **GIVEN** un `POST /enrollment` con 2 muestras
- **WHEN** se procesa
- **THEN** responde `400 SAMPLES_REQUIRED` y no se crea huella

#### Scenario: Tres muestras válidas

- **GIVEN** 3 muestras que pasan las validaciones de este spec
- **WHEN** se procesa el enrolamiento
- **THEN** la huella se crea y responde `201 {enrolled: true}`

### Requirement: Validación de cada muestra

Una muestra SHALL ser PCM float32 16 kHz mono (`contrato-voz` §4) con duración de 3 a 15 s, medida
después del recorte de silencios (mismo criterio que la verificación: 3 s de voz útil). Vacía,
ilegible, < 3 s o > 15 s MUST responder `400 INVALID_AUDIO` (B-3: nunca llegaría un audio de más de
30 s). El backend MUST validar duración y legibilidad, no confiar en el cliente.

#### Scenario: Muestra vacía o demasiado corta

- **GIVEN** una muestra vacía, ilegible o con menos de 3 s de voz útil tras recortar silencios
- **WHEN** se procesa el enrolamiento
- **THEN** responde `400 INVALID_AUDIO` y no se crea huella

#### Scenario: Muestra de más de 15 s

- **GIVEN** una muestra de más de 15 s
- **WHEN** se procesa el enrolamiento
- **THEN** responde `400 INVALID_AUDIO`

#### Scenario: Muestra de 4 s con 2 s de silencio

- **GIVEN** una muestra de 4 s con 2 s de silencio (2 s de voz útil tras recortar)
- **WHEN** se procesa el enrolamiento
- **THEN** la duración se mide después del recorte y responde `400 INVALID_AUDIO`

### Requirement: Consistencia entre muestras

Las 3 muestras SHALL compararse entre sí; si la similitud mínima entre pares queda bajo el corte
configurable (por defecto **0.45**, el mismo umbral de la verificación — misma persona ≥ 0.689,
otra persona 0.16–0.23, experimentos ML 2, 15 oct; recalibración en H3), MUST responder `400 INCONSISTENT_SAMPLES` (B-5) sin crear huella. Confirmado en vivo: peor par por persona 0.518,
0.686 y 0.749 — 0.45 sigue sobrando (experimentos ML 2, 17 oct, 3 personas).

#### Scenario: Muestras consistentes

- **GIVEN** 3 muestras del mismo hablante con similitud entre pares ≥ 0.689
- **WHEN** se procesa el enrolamiento
- **THEN** la huella se crea

#### Scenario: Muestras de dos personas

- **GIVEN** una muestra con similitud mínima entre pares por debajo del corte (0.45 por defecto)
- **WHEN** se procesa el enrolamiento
- **THEN** responde `400 INCONSISTENT_SAMPLES` y no queda nada registrado (la UI explica que las tres grabaciones deben ser de la misma persona)

### Requirement: Orden de los errores

Las validaciones SHALL evaluarse en orden fijo: `CONSENT_REQUIRED` → `SAMPLES_REQUIRED` →
`INVALID_AUDIO` → `INCONSISTENT_SAMPLES`; el backend SHALL responder con el primero que aplique y
MUST NOT procesar audio sin consentimiento (PRIV-2).

#### Scenario: Varios errores a la vez

- **GIVEN** un `POST /enrollment` sin consentimiento, con 2 muestras y una de ellas ilegible
- **WHEN** se procesa
- **THEN** responde `400 CONSENT_REQUIRED` (el primero del orden) y no procesa nada
- **AND** no se evalúa ninguna validación posterior hasta resolver el primero

### Requirement: Consentimiento antes de procesar

El consentimiento explícito SHALL ser obligatorio y único (opción B, 2026-10-16): el mismo
`consent=true` cubre la huella y el envío del audio de las órdenes a un proveedor externo de
transcripción. Sin `consent=true`, el backend MUST responder `400 CONSENT_REQUIRED` y MUST NOT
procesar, calcular ni almacenar nada (ni embeddings).

#### Scenario: Sin consentimiento

- **GIVEN** un `POST /enrollment` con `consent` distinto de `true`
- **WHEN** se procesa
- **THEN** responde `400 CONSENT_REQUIRED` y no se procesa ni guarda nada (PRIV-2)

#### Scenario: Con consentimiento

- **GIVEN** un `POST /enrollment` con `consent=true` y muestras válidas
- **WHEN** se procesa
- **THEN** se procesan las muestras y se crea la huella

### Requirement: El consentimiento único cubre el proveedor externo

Un enrolamiento válido SHALL registrar también el consentimiento del proveedor externo de
transcripción, que Voz consulta como `consentExterno`; los textos son de ML 2
(`verificacion-ml2/textos-enrolamiento.md`). Borrar la huella SHALL retirar ese consentimiento. El
Contrato B no cambia.

#### Scenario: Consentimiento único (huella + proveedor externo)

- **GIVEN** un enrolamiento válido con `consent=true`
- **WHEN** se procesa
- **THEN** registra también el consentimiento del proveedor externo y Voz lo consulta como `consentExterno == true`
- **AND** al borrar la huella (PRIV-3) ese consentimiento se retira y `consentExterno` vuelve a `false`

### Requirement: La huella y su ciclo de vida

La huella SHALL ser el promedio de los 3 embeddings, L2-normalizado (**[DECIDIDO 2026-10-17]**:
X-3 — promedio gana con margen +0.104 y 0 FA/0 FR a 0.45; el máximo dio 1 falso aceptado).
El re-enrolamiento SHALL ser atómico: si el nuevo
registro falla cualquier validación, se conserva la huella anterior; solo un registro válido la
reemplaza y responde `201` (B-5). El borrado va por script (PRIV-3, spec `speaker-verification`);
solo se guardan embeddings, nunca audio crudo (PRIV-1).

#### Scenario: Re-enrolamiento sobrescribe

- **GIVEN** un usuario con huella previa
- **WHEN** se procesa un nuevo enrolamiento válido
- **THEN** la huella anterior se sobrescribe y la respuesta es `201` (B-5)

#### Scenario: Re-enrolamiento fallido conserva la huella

- **GIVEN** un usuario con huella previa
- **WHEN** se procesa un nuevo enrolamiento que falla cualquier validación (consentimiento, cantidad, calidad o consistencia)
- **THEN** la huella anterior se conserva y no queda nada del intento fallido
- **AND** solo un registro válido la reemplaza

#### Scenario: Huella como promedio

- **GIVEN** 3 muestras consistentes
- **WHEN** se construye la huella
- **THEN** es el promedio de los 3 embeddings, L2-normalizado (estrategia A: genuino mín. 0.508, impostor máx. 0.405, margen +0.104, 0 FA/0 FR a 0.45; el máximo dio 1 falso aceptado — experimentos ML 2, 17 oct, 3 personas)

### Requirement: Persistencia de la huella

La huella SHALL persistir en un archivo local fuera de git (los patrones `*.npy` y `*.db` ya están
en `.gitignore`), para un solo usuario (`userId` fijo del MVP). El backend SHALL cargarla al
arrancar: un reinicio no borra el registro. Nunca se guarda audio, solo el embedding (PRIV-1).

#### Scenario: Reinicio del backend conserva la huella

- **GIVEN** un usuario enrolado
- **WHEN** el backend se reinicia
- **THEN** la huella se recarga del archivo local y `GET /enrollment` sigue respondiendo `enrolled: true`
- **AND** en el archivo solo hay embeddings, nunca audio (PRIV-1)

### Requirement: Consulta del estado y límites del componente

`GET /enrollment` SHALL responder `{enrolled}` sin ningún dato biométrico (B-5). Las rutas HTTP
(`/api/enrollment`) pertenecen al esqueleto de Pagos; ML 2 entrega las funciones que invocan. Ni
audio, ni embeddings, ni puntajes SHALL aparecer en logs ni en `error.message` (PRIV-1, PRIV-4).

#### Scenario: Consulta de estado

- **GIVEN** un usuario con o sin huella
- **WHEN** se llama `GET /api/enrollment`
- **THEN** responde `{enrolled: true | false}` y ningún dato biométrico

#### Scenario: Sin datos biométricos en los logs

- **GIVEN** cualquier llamada de enrolamiento o error
- **WHEN** se revisan los logs y `error.message`
- **THEN** no aparecen audio, embeddings ni puntajes (PRIV-4)
