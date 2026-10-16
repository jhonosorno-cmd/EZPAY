# Spec Delta — enrollment-ui

## Purpose

Pantalla de registro de la voz. El enrolamiento, la huella y los umbrales son de ML 2; la web app pide
el consentimiento, graba las tres muestras y muestra el resultado. Origen: PRIV-1, PRIV-2 (Ley 1581 de
2012), Contrato B `POST /enrollment`, revisión de ML 2 (D8, C-3) y resultados X-1 a X-3.

## ADDED Requirements

### Requirement: Consentimiento antes de grabar (PRIV-2)
La web app SHALL mostrar el texto de consentimiento escrito por ML 2 (dato biométrico sensible, para qué se usa, cómo se borra y, si el equipo aprueba C-3 de ML 1, que el audio de cada comando se envía a un proveedor externo para transcribirse) y leerlo en voz alta. La casilla de aceptación MUST empezar sin marcar, y sin aceptarla la web app MUST NOT encender el micrófono ni enviar muestras.

#### Scenario: Sin aceptar
- **WHEN** la usuaria no marca la casilla de consentimiento
- **THEN** el botón para grabar las muestras está deshabilitado
- **AND** no se envía ningún `POST /api/enrollment`

### Requirement: Tres muestras con frases fijas
La web app SHALL guiar la grabación de tres muestras, mostrando y leyendo antes de cada una la frase que ML 2 defina, y enviarlas juntas en un único `POST /api/enrollment` multipart con tres campos `audio` y `consent=true`. Cada muestra SHALL durar entre 3 y 15 s; ML 2 calibró con muestras de 4,8 a 8,5 s, y los audios de menos de 3 s puntúan más bajo (X-2).

#### Scenario: Envío del registro
- **WHEN** la usuaria acepta el consentimiento y graba las tres frases
- **THEN** sale un `POST /api/enrollment` con tres campos `audio` y `consent=true`

#### Scenario: Muestra demasiado corta
- **WHEN** una muestra dura menos de 3 s
- **THEN** la web app pide repetir esa muestra antes de enviar

### Requirement: Resultado del registro
La web app SHALL decidir por `error.code` (CONV-2) y ante cualquier error permitir repetir el registro. Los códigos distintos de `CONSENT_REQUIRED` son un **cambio de contrato propuesto** (ML 2, C-3).

#### Scenario: Registro exitoso
- **WHEN** Python responde `201 { enrolled: true }`
- **THEN** la web app muestra y dice "Tu voz quedó registrada"

#### Scenario: Falta el consentimiento
- **WHEN** Python responde `400 CONSENT_REQUIRED`
- **THEN** la web app vuelve a la pantalla de consentimiento

#### Scenario: Cantidad de muestras incorrecta
- **WHEN** Python responde `400 SAMPLES_REQUIRED`
- **THEN** la web app lo registra en la consola como error de programación y repite el registro

#### Scenario: Audio inválido en el registro
- **WHEN** Python responde `400 INVALID_AUDIO`
- **THEN** la web app pide repetir las tres muestras en un lugar sin ruido

#### Scenario: Muestras de dos personas
- **WHEN** Python responde `400 INCONSISTENT_SAMPLES`
- **THEN** la web app explica que las tres grabaciones deben ser de la misma persona
- **AND** no queda nada registrado

### Requirement: Saber si hay alguien registrado
Si existe `GET /api/enrollment` (**cambio de contrato propuesto**, ML 2 C-3), la pantalla de inicio SHALL mostrar "Registrar mi voz" solo cuando `enrolled` es `false`. Sin esa ruta, la opción de registrar se muestra siempre.

#### Scenario: Usuaria ya registrada
- **WHEN** `GET /api/enrollment` responde `{ enrolled: true }`
- **THEN** la pantalla de inicio no ofrece registrar la voz
