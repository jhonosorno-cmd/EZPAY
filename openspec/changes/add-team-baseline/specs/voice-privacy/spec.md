# Spec Delta — voice-privacy

## Purpose

Tratamiento de la biometría de voz, que es un dato sensible según la Ley 1581 de 2012. Origen:
Spec general §5 (PRIV-1 a PRIV-4) y PLAN §5.3.

## ADDED Requirements

### Requirement: Nunca se guarda audio crudo (PRIV-1)
El audio SHALL procesarse en memoria y descartarse. Solo se guardan embeddings de voz.

#### Scenario: Comando de voz procesado
- **WHEN** se procesa un comando de voz y luego se revisan la base de datos, los archivos temporales y los logs
- **THEN** no existe ese audio en ninguno de ellos

### Requirement: Consentimiento explícito antes del registro de voz (PRIV-2)
El registro de voz SHALL exigir un consentimiento explícito, informando que la biometría es un dato sensible y para qué se usa.

#### Scenario: Registro sin consentimiento
- **WHEN** se envían las muestras de voz sin consentimiento
- **THEN** el registro se rechaza con `400 CONSENT_REQUIRED`
- **AND** no se guarda nada

### Requirement: Borrado de la huella de voz (PRIV-3)
El usuario SHALL poder borrar su huella de voz (derecho de supresión). En el MVP alcanza un script; no hace falta una pantalla.

#### Scenario: Borrado solicitado
- **WHEN** se ejecuta el borrado de la huella de un usuario
- **THEN** sus embeddings dejan de existir
- **AND** la verificación de hablante trata al usuario como no registrado

### Requirement: Logs sin datos personales sensibles (PRIV-4)
Los logs MUST NOT contener audio, embeddings ni transcripciones completas. Mostrar la transcripción en pantalla sí está permitido.

#### Scenario: Revisión de logs después de un pago por voz
- **WHEN** se completa un pago por voz y se revisan los logs de los tres servicios
- **THEN** no aparecen audio, embeddings ni la transcripción completa
